"""Analyze waveform/VAD and propose quiet-center cuts. Does not edit media or judge fillers."""
import argparse
from array import array
from fractions import Fraction
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import sys
import wave


def executable(value):
    path = Path(shutil.which(value) or value).expanduser().resolve()
    if not path.is_file():
        raise ValueError(f'Executable not found: {value}')
    return path


def run(args, log):
    result = subprocess.run([str(x) for x in args], capture_output=True, encoding='utf-8',
                            errors='replace', creationflags=0x08000000 if os.name == 'nt' else 0)
    log.write_text(result.stdout + '\n' + result.stderr, encoding='utf-8')
    if result.returncode:
        raise RuntimeError(f'Command failed ({result.returncode}); see {log}')
    return result


def digest(file):
    h = hashlib.sha256()
    with file.open('rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def db(value):
    return round(20 * math.log10(value), 3) if value > 0 else None


def ranges(values, threshold, duration):
    found = []
    start = None
    for i, value in enumerate(values + [float('inf')]):
        if value < threshold and start is None:
            start = i * .01
        elif value >= threshold and start is not None:
            found.append((start, min(i * .01, duration)))
            start = None
    return found


def max_channel_rms(samples, channels):
    frames = len(samples) // channels
    if not frames:
        return 0
    return max(math.sqrt(sum(x * x for x in samples[c::channels]) / frames) / 32768
               for c in range(channels))


def vad_ranges(raw_bytes, channels):
    import numpy as np
    from faster_whisper.vad import get_speech_timestamps, VadOptions
    audio = np.frombuffer(raw_bytes, dtype='<i2').reshape(-1, channels).astype(np.float32) / 32768
    found = []
    options = VadOptions(threshold=.45, min_silence_duration_ms=100,
                         speech_pad_ms=20, min_speech_duration_ms=80)
    # Union independent channels; averaging can cancel anti-phase speech.
    for c in range(channels):
        found.extend((x['start'] / 16000, x['end'] / 16000)
                     for x in get_speech_timestamps(audio[:, c].copy(), options))
    merged = []
    for a, b in sorted(found):
        if merged and a <= merged[-1][1]:
            merged[-1][1] = max(b, merged[-1][1])
        else:
            merged.append([a, b])
    return merged


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--input', type=Path, required=True)
    p.add_argument('--output-dir', type=Path, required=True)
    p.add_argument('--ffmpeg', default='ffmpeg')
    p.add_argument('--ffprobe', default='ffprobe')
    p.add_argument('--auto-editor')
    p.add_argument('--vad', action='store_true', help='Requires local numpy + faster-whisper Silero assets.')
    p.add_argument('--fps', help='Target CFR, e.g. 30 or 30000/1001; required for audio-only inputs.')
    p.add_argument('--quiet-db', type=float, default=-32)
    p.add_argument('--core-db', type=float, default=-40)
    p.add_argument('--min-quiet', type=float, default=.33)
    p.add_argument('--min-core', type=float, default=.13)
    p.add_argument('--keep-pause', type=float, default=.22)
    p.add_argument('--left-guard', type=float, default=.085)
    p.add_argument('--right-guard', type=float, default=.105)
    p.add_argument('--core-guard', type=float, default=.025)
    p.add_argument('--min-cut-frames', type=int, default=4)
    args = p.parse_args()
    source = args.input.expanduser().resolve()
    out = args.output_dir.expanduser().resolve()
    if not source.is_file() or out.exists():
        p.error('Input must exist; output directory must be new.')
    durations = [args.min_quiet, args.min_core, args.keep_pause, args.left_guard,
                 args.right_guard, args.core_guard]
    if any(not math.isfinite(x) or x <= 0 for x in durations) or args.min_cut_frames < 1:
        p.error('Time guards must be finite and positive; min-cut-frames must be >= 1.')
    if not (math.isfinite(args.core_db) and math.isfinite(args.quiet_db)
            and -100 <= args.core_db < args.quiet_db < 0):
        p.error('Expected -100 <= core-db < quiet-db < 0.')
    ff, probe = executable(args.ffmpeg), executable(args.ffprobe)
    ae = executable(args.auto_editor) if args.auto_editor else None
    out.mkdir(parents=True)
    info = json.loads(run([probe, '-v', 'error', '-show_streams', '-show_format',
                           '-of', 'json', source], out/'probe.log').stdout)
    audio = next((s for s in info['streams'] if s['codec_type'] == 'audio'), None)
    video = next((s for s in info['streams'] if s['codec_type'] == 'video'), None)
    if audio is None:
        raise ValueError('No audio stream.')
    if video:
        average, nominal = video.get('avg_frame_rate', '0/1'), video.get('r_frame_rate', '0/1')
        if average == '0/0' or Fraction(average) <= 0:
            raise ValueError('Unknown video clock; establish CFR first.')
        if nominal != '0/0' and Fraction(nominal) > 0 and Fraction(average) != Fraction(nominal):
            raise ValueError('Average and nominal frame rates differ; establish/verify CFR first.')
        if args.fps and Fraction(args.fps) != Fraction(average):
            raise ValueError('Requested FPS differs from input video; align target CFR before analysis.')
        fps = Fraction(average)
        offset = float(audio.get('start_time', 0)) - float(video.get('start_time', 0))
        if abs(offset) > .02:
            raise ValueError('Audio/video origins differ by >20ms; align before applying cut times.')
    else:
        if not args.fps:
            raise ValueError('Audio-only input requires --fps for the target frame clock.')
        fps, offset = Fraction(args.fps), 0
    if not 1 <= fps <= 240:
        raise ValueError('FPS must be between 1 and 240.')
    pcm = out/'analysis_pcm.wav'
    run([ff, '-n', '-v', 'warning', '-i', source, '-map', '0:a:0', '-vn',
         '-ar', '16000', '-c:a', 'pcm_s16le', pcm], out/'extract.log')
    with wave.open(str(pcm), 'rb') as f:
        channels, rate, frames = f.getnchannels(), f.getframerate(), f.getnframes()
        raw_bytes = f.readframes(frames)
    samples = array('h', raw_bytes)
    if sys.byteorder != 'little':
        samples.byteswap()
    duration = frames / rate
    if duration <= 0:
        raise ValueError('Empty PCM.')
    step = 160 * channels
    rms, peaks = [], []
    for i in range(0, len(samples), step):
        block = samples[i:i+step]
        rms.append(max_channel_rms(block, channels))
        peaks.append(max(abs(x) for x in block) / 32768)
    native = None
    if ae:
        version = run([ae, '--version'], out/'auto-editor-version.log').stdout.strip()
        result = run([ae, 'levels', pcm, '--timebase', '100', '--no-cache'], out/'auto-editor-levels.log')
        values = [float(line) for line in result.stdout.splitlines()
                  if line.strip() and not line.strip().startswith('@')]
        if any(not math.isfinite(x) or x < 0 for x in values) or abs(len(values)/100-duration) > .03:
            raise ValueError('Auto-Editor levels do not match decoded PCM clock; inspect log.')
        native = {'version': version, 'timebase': 100, 'peakLevels': values}
    speech = vad_ranges(raw_bytes, channels) if args.vad else None
    quiet = ranges(rms, 10 ** (args.quiet_db/20), duration)
    cores = ranges(rms, 10 ** (args.core_db/20), duration)
    candidates = []
    for a, b in quiet:
        if b-a < args.min_quiet or a < .15 or b > duration-.15:
            continue
        inside = [(max(a, c), min(b, d)) for c, d in cores
                  if min(b, d)-max(a, c) >= args.min_core]
        if not inside:
            continue
        c, d = max(inside, key=lambda x:x[1]-x[0])
        removed = b-a-args.keep_pause
        left = max((a+b-removed)/2, a+args.left_guard, c+args.core_guard)
        right = min((a+b+removed)/2, b-args.right_guard, d-args.core_guard)
        first, last = math.ceil(left*fps), math.floor(right*fps)
        if last-first < args.min_cut_frames:
            continue
        start, end = float(first/fps), float(last/fps)
        x, y = math.ceil(start*rate)*channels, math.floor(end*rate)*channels
        block = samples[x:y]
        cut_rms = max_channel_rms(block, channels)
        cut_peak = max((abs(x) for x in block), default=0) / 32768
        if cut_rms > 10 ** (-36/20) or cut_peak > 10 ** (-22/20):
            continue
        overlap = None if speech is None else sum(max(0, min(end, v)-max(start, u)) for u, v in speech)
        candidates.append({'kind': 'pause_candidate', 'start': start, 'end': end,
                           'startFrame': first, 'endFrame': last, 'removedFrames': last-first,
                           'removedSeconds': float((last-first)/fps), 'quietSpan': [a, b],
                           'deepQuietCore': [c, d], 'removedRmsDbfs': db(cut_rms),
                           'removedSamplePeakDbfs': db(cut_peak), 'vadSpeechOverlapSeconds': overlap,
                           'semanticStatus': 'not_evaluated', 'boundaryStatus': 'needs_review',
                           'renderReady': False})
    waveform = {'source': str(source), 'duration': duration, 'bucketSeconds': .01,
                'channels': channels, 'method': 'maximum channel RMS; maximum absolute sample peak',
                'rms': [round(x, 7) for x in rms], 'peak': [round(x, 7) for x in peaks],
                'sileroSpeech': speech, 'nativeAutoEditor': native}
    (out/'waveform.json').write_text(json.dumps(waveform, ensure_ascii=False), encoding='utf-8')
    report = {'source': str(source), 'sourceSha256': digest(source), 'duration': duration,
              'fps': f'{fps.numerator}/{fps.denominator}', 'audioVideoOriginOffsetSeconds': offset,
              'parameters': {k:v for k,v in vars(args).items() if k not in ['input','output_dir']},
              'candidates': candidates, 'candidateCount': len(candidates),
              'semanticReview': 'not_performed', 'boundaryReview': 'pending', 'renderReady': False,
              'humanListeningChecked': False,
              'unresolvedItems': ['Candidates require original-speech and boundary review; waveform does not classify redundant content.']}
    (out/'breath_candidates.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({'output': str(out), 'seconds': duration, 'candidates': len(candidates),
                      'autoEditor': native['version'] if native else None, 'sileroUsed': speech is not None,
                      'renderReady': False}, ensure_ascii=False))


if __name__ == '__main__':
    main()
