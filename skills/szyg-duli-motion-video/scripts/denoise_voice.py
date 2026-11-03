"""DeepFilterNet CLI + FFmpeg voice repair. Standard library; audio-only output."""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import re
import shutil
import subprocess
import wave


def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def executable(value):
    found = shutil.which(value)
    p = Path(found or value).expanduser().resolve()
    if not p.is_file():
        raise ValueError(f'Executable not found: {value}')
    return p


def run(args, log):
    r = subprocess.run([str(a) for a in args], capture_output=True, encoding='utf-8',
                       errors='replace', creationflags=0x08000000 if os.name == 'nt' else 0)
    log.write_text(r.stdout + '\n' + r.stderr, encoding='utf-8')
    if r.returncode:
        raise RuntimeError(f'Command failed ({r.returncode}); see {log}')
    return r


def measure(ff, source, log, target):
    r = run([ff, '-v', 'info', '-i', source, '-af', target + ':print_format=json',
             '-f', 'null', '-'], log)
    blocks = re.findall(r'\{[^{}]*"input_i"[^{}]*\}', r.stderr)
    if not blocks:
        raise ValueError(f'Loudness measurement missing: {log}')
    data = json.loads(blocks[-1])
    for field in ('input_i', 'input_tp', 'input_lra', 'input_thresh', 'target_offset'):
        if not math.isfinite(float(data[field])):
            raise ValueError(f'Non-finite {field}; check silent/invalid input: {log}')
    return data


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--input', type=Path, required=True)
    ap.add_argument('--output-dir', type=Path, required=True)
    ap.add_argument('--deep-filter', required=True)
    ap.add_argument('--ffmpeg', default='ffmpeg')
    ap.add_argument('--ffprobe', default='ffprobe')
    ap.add_argument('--channels', type=int, choices=(1, 2), default=2)
    ap.add_argument('--beta', type=float, default=0.06)
    ap.add_argument('--atten-lim-db', type=float, default=100)
    ap.add_argument('--loudness', type=float, default=-16)
    ap.add_argument('--true-peak', type=float, default=-1.5)
    ap.add_argument('--duration-seconds', type=float)
    ap.add_argument('--preview-seconds', type=float)
    args = ap.parse_args()
    source = args.input.expanduser().resolve()
    out = args.output_dir.expanduser().resolve()
    if not source.is_file() or out.exists():
        ap.error('Input must exist; output directory must be new.')
    if not (0 <= args.beta <= 1 and 0 <= args.atten_lim_db <= 100):
        ap.error('beta must be 0..1 and atten-lim-db 0..100.')
    if not (-70 <= args.loudness <= -5 and -9 <= args.true_peak <= -0.5):
        ap.error('Loudness/true peak outside supported loudnorm range.')
    for duration in (args.duration_seconds, args.preview_seconds):
        if duration is not None and (not math.isfinite(duration) or duration <= 0):
            ap.error('Duration must be finite and positive.')
    if args.preview_seconds is not None and args.duration_seconds is not None:
        ap.error('Choose preview-seconds or duration-seconds, not both.')
    ff, probe, df = map(executable, (args.ffmpeg, args.ffprobe, args.deep_filter))
    out.mkdir(parents=True)
    help_text = run([df, '--help'], out/'deep-filter-help.log').stdout
    if '--pf-beta' not in help_text or '--compensate-delay' not in help_text:
        raise ValueError('CLI differs from tested v0.5.6; review options before adapting.')
    raw = out/'input_pcm.wav'
    extraction = [ff, '-n', '-v', 'warning', '-i', source, '-map', '0:a:0', '-vn']
    if args.preview_seconds is not None:
        extraction += ['-t', args.preview_seconds]
    run(extraction + ['-ar', '48000', '-ac', args.channels, '-c:a', 'pcm_s16le', raw], out/'extract.log')
    with wave.open(str(raw), 'rb') as f:
        raw_seconds = f.getnframes()/f.getframerate()
    target_seconds = args.duration_seconds or raw_seconds
    if raw_seconds <= 0 or abs(target_seconds - raw_seconds) > 0.1:
        raise ValueError('Target differs from extracted audio by >0.1s; align source first.')
    # Feed a little extra silence so native delay compensation does not discard speech at EOF.
    model_input = out/'model_input.wav'
    run([ff, '-n', '-v', 'warning', '-i', raw, '-af', 'apad=pad_dur=0.1',
         '-c:a', 'pcm_s16le', model_input], out/'pad-input.log')
    model_dir = out/'model'
    df_args = ['-D', '--pf', '--pf-beta', args.beta, '--atten-lim-db', args.atten_lim_db,
               '--reduce-mask', '2', '-v', '-o', model_dir, model_input]
    result = run([df] + df_args, out/'deep-filter.log')
    model_output = model_dir/model_input.name
    if not model_output.is_file():
        raise ValueError('Expected model output missing; see deep-filter.log')
    native = json.loads(run([probe, '-v', 'error', '-show_entries', 'format=duration',
                             '-of', 'json', model_output], out/'model-duration.log').stdout)
    model_seconds = float(native['format']['duration'])
    if abs(model_seconds - target_seconds) > 0.1:
        raise ValueError('Model audio duration differs by >0.1s; inspect before padding.')
    target = f'loudnorm=I={args.loudness}:TP={args.true_peak}:LRA=9'
    m = measure(ff, model_output, out/'model-loudness.log', target)
    af = (target + f":measured_I={m['input_i']}:measured_TP={m['input_tp']}"
          f":measured_LRA={m['input_lra']}:measured_thresh={m['input_thresh']}"
          f":offset={m['target_offset']}:linear=true,aresample=48000,apad,atrim=end_sample={round(target_seconds*48000)}")
    pcm = out/'denoised_pcm.wav'
    run([ff, '-n', '-v', 'warning', '-i', model_output, '-af', af, '-ar', '48000',
         '-ac', args.channels, '-c:a', 'pcm_s16le', pcm], out/'normalize.log')
    with wave.open(str(pcm), 'rb') as f:
        if f.getnframes() != round(target_seconds*48000):
            raise ValueError('PCM length mismatch.')
    track = out/'denoised_audio.m4a'
    run([ff, '-n', '-v', 'warning', '-i', pcm, '-c:a', 'aac', '-b:a', '192k',
         '-ar', '48000', '-movflags', '+faststart', track], out/'encode.log')
    final = measure(ff, track, out/'encoded-loudness.log', target)
    if abs(float(final['input_i']) - args.loudness) > 1 or float(final['input_tp']) > -0.5:
        raise ValueError('Encoded loudness/true peak check failed; inspect before delivery.')
    log_text = result.stdout + result.stderr
    model_match = re.search(r'model type\s+([^\s,]+)', log_text, re.I)
    report = dict(project='https://github.com/Rikorose/DeepFilterNet', source=str(source),
                  source_sha256=digest(source), deep_filter=str(df), executable_sha256=digest(df),
                  model_from_log=model_match.group(1) if model_match else 'unconfirmed',
                  command=[str(x) for x in [df]+df_args], sample_rate=48000, channels=args.channels,
                  source_seconds=raw_seconds, model_seconds=model_seconds, target_seconds=target_seconds,
                  preview_seconds=args.preview_seconds, normalization=af, encoded_loudness=final,
                  native_delay_compensation=True, model_input_tail_padding_seconds=0.1,
                  additional_waveform_alignment_checked=False,
                  subjective_listening_checked=False, video_mux_checked=False,
                  scope='Audio processing and encoded loudness only; perform waveform, content, A/B and final-video checks separately.',
                  outputs=[dict(file=f.name,sha256=digest(f)) for f in (pcm,track)])
    (out/'denoise_report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(dict(output_dir=str(out),model=report['model_from_log'],seconds=target_seconds,
                          encoded_i=final['input_i'],encoded_tp=final['input_tp']),ensure_ascii=False))


if __name__ == '__main__':
    main()
