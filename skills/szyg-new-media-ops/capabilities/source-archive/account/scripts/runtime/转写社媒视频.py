#!/usr/bin/env python3
"""使用 faster-whisper 生成可追溯的社媒视频逐字稿。"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


_DLL_HANDLES: list[Any] = []


def configure_cuda_dlls() -> list[str]:
    """让项目虚拟环境内的 CUDA DLL 对当前进程可见。"""
    candidates = [
        Path(sys.prefix) / "Lib" / "site-packages" / "nvidia" / "cublas" / "bin",
        Path(sys.prefix) / "Library" / "bin",
    ]
    loaded: list[str] = []
    for candidate in candidates:
        if not candidate.is_dir():
            continue
        candidate_text = str(candidate)
        os.environ["PATH"] = candidate_text + os.pathsep + os.environ.get("PATH", "")
        if os.name == "nt" and hasattr(os, "add_dll_directory"):
            _DLL_HANDLES.append(os.add_dll_directory(candidate_text))
        loaded.append(candidate_text)
    return loaded


CUDA_DLL_DIRS = configure_cuda_dlls()

from faster_whisper import WhisperModel  # noqa: E402


@dataclass
class Runtime:
    device: str
    compute_type: str
    fallback_reason: str | None = None
    cuda_dll_dirs: list[str] | None = None


def stamp(seconds: float) -> str:
    milliseconds = max(0, round(seconds * 1000))
    hours, remainder = divmod(milliseconds, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    secs, millis = divmod(remainder, 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}.{millis:03d}"


def create_model(
    model_name: str, cache_dir: Path, require_gpu: bool
) -> tuple[WhisperModel, Runtime]:
    try:
        model = WhisperModel(
            model_name,
            device="cuda",
            compute_type="int8_float16",
            download_root=str(cache_dir),
        )
        runtime = Runtime(
            "cuda", "int8_float16", cuda_dll_dirs=CUDA_DLL_DIRS or None
        )
        print("转写设备：NVIDIA GPU（CUDA / int8_float16）", file=sys.stderr)
        return model, runtime
    except Exception as exc:
        reason = f"{type(exc).__name__}: {exc}"
        if require_gpu:
            raise RuntimeError(f"GPU 初始化失败：{reason}") from exc
        print(f"GPU 初始化失败，自动回退 CPU：{reason}", file=sys.stderr)
        model = WhisperModel(
            model_name,
            device="cpu",
            compute_type="int8",
            download_root=str(cache_dir),
        )
        return model, Runtime("cpu", "int8", reason, CUDA_DLL_DIRS or None)


def transcribe(
    model: WhisperModel, media: Path, beam_size: int
) -> tuple[list[Any], Any]:
    segments, info = model.transcribe(
        str(media),
        language="zh",
        beam_size=beam_size,
        vad_filter=True,
        word_timestamps=True,
        condition_on_previous_text=True,
    )
    return list(segments), info


def normalize_text(text: str) -> str:
    text = re.sub(r"\s+", "", text.strip())
    return re.sub(r"([。！？，])\1+", r"\1", text)


def write_outputs(
    output_dir: Path,
    source_id: str,
    model_name: str,
    runtime: Runtime,
    segments: list[Any],
    info: Any,
    elapsed_seconds: float,
    beam_size: int,
) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    generated = datetime.now().astimezone().isoformat(timespec="seconds")
    language_probability = getattr(info, "language_probability", None)
    duration = float(getattr(info, "duration", 0.0) or 0.0)
    speed_x = duration / elapsed_seconds if elapsed_seconds > 0 else 0.0

    rows: list[dict[str, Any]] = []
    for segment in segments:
        words = []
        for word in segment.words or []:
            words.append(
                {
                    "start": word.start,
                    "end": word.end,
                    "word": word.word,
                    "probability": getattr(word, "probability", None),
                }
            )
        rows.append(
            {
                "id": segment.id,
                "start": segment.start,
                "end": segment.end,
                "text": segment.text.strip(),
                "avg_logprob": segment.avg_logprob,
                "no_speech_prob": segment.no_speech_prob,
                "compression_ratio": segment.compression_ratio,
                "words": words,
            }
        )

    raw_lines = [
        "---",
        f"source_id: {source_id}",
        "status: 原始识别",
        f"generated: {generated}",
        f"model: {model_name}",
        f"device: {runtime.device}",
        f"compute_type: {runtime.compute_type}",
        f"beam_size: {beam_size}",
        f"language: {getattr(info, 'language', 'zh')}",
        f"language_probability: {language_probability}",
        f"duration_seconds: {duration:.3f}",
        f"transcription_seconds: {elapsed_seconds:.3f}",
        f"transcription_speed_x: {speed_x:.2f}",
        "---",
        "",
        "# 逐字稿（原始识别）",
        "",
        "> 机器识别原样永久保留。置信信息见每段尾注，词级时间戳见同名 JSON。",
        "",
    ]
    for row in rows:
        raw_lines.extend(
            [
                f"## [{stamp(row['start'])} → {stamp(row['end'])}]",
                "",
                row["text"],
                "",
                f"<!-- avg_logprob={row['avg_logprob']:.4f}; no_speech_prob={row['no_speech_prob']:.4f}; compression_ratio={row['compression_ratio']:.4f} -->",
                "",
            ]
        )
    if rows and duration - float(rows[-1]["end"]) > 1.0:
        raw_lines.extend(
            [
                f"## [{stamp(rows[-1]['end'])} → {stamp(duration)}]",
                "",
                "[无可识别语音 / 画面收尾]",
                "",
            ]
        )
    (output_dir / "01-逐字稿-原始.md").write_text(
        "\n".join(raw_lines), encoding="utf-8"
    )

    json_payload = {
        "source_id": source_id,
        "generated": generated,
        "model": model_name,
        "runtime": asdict(runtime),
        "beam_size": beam_size,
        "language": getattr(info, "language", "zh"),
        "language_probability": language_probability,
        "duration_seconds": duration,
        "transcription_seconds": elapsed_seconds,
        "transcription_speed_x": speed_x,
        "segments": rows,
    }
    (output_dir / "01-逐字稿-原始.json").write_text(
        json.dumps(json_payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    cleaned_lines = [
        "---",
        f"source_id: {source_id}",
        "status: 待语义核验",
        f"updated: {generated[:10]}",
        "speaker_status: 待确认",
        "---",
        "",
        "# 逐字稿（整理稿）",
        "",
        "> 当前为机器初排版。需对照章节、画面字幕和上下文完成语义核验；存疑处使用 `[听不清]` 或 `[说话人待确认]`。",
        "",
    ]
    for row in rows:
        cleaned_lines.extend(
            [
                f"### {stamp(row['start'])}",
                "",
                f"[说话人待确认] {normalize_text(row['text'])}",
                "",
            ]
        )
    if rows and duration - float(rows[-1]["end"]) > 1.0:
        cleaned_lines.extend(
            [
                f"### {stamp(rows[-1]['end'])} → {stamp(duration)}",
                "",
                "[无可识别语音 / 画面收尾]",
                "",
            ]
        )
    (output_dir / "02-逐字稿-整理.md").write_text(
        "\n".join(cleaned_lines), encoding="utf-8"
    )

    return {
        "source_id": source_id,
        "device": runtime.device,
        "compute_type": runtime.compute_type,
        "duration_seconds": duration,
        "transcription_seconds": round(elapsed_seconds, 3),
        "transcription_speed_x": round(speed_x, 2),
        "segment_count": len(rows),
        "output_dir": str(output_dir),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--source-id", required=True)
    parser.add_argument("--model", default="large-v3-turbo")
    parser.add_argument("--beam-size", default=1, type=int)
    parser.add_argument("--model-cache", required=True, type=Path)
    parser.add_argument(
        "--require-gpu",
        action="store_true",
        help="GPU 不可用时直接失败；用于环境体检和性能验收。",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    args.model_cache.mkdir(parents=True, exist_ok=True)
    model, runtime = create_model(args.model, args.model_cache, args.require_gpu)
    started = time.perf_counter()
    try:
        segments, info = transcribe(model, args.input, args.beam_size)
    except Exception as exc:
        if runtime.device != "cuda" or args.require_gpu:
            raise
        reason = f"{type(exc).__name__}: {exc}"
        print(f"GPU 转写失败，自动回退 CPU：{reason}", file=sys.stderr)
        model = WhisperModel(
            args.model,
            device="cpu",
            compute_type="int8",
            download_root=str(args.model_cache),
        )
        runtime = Runtime("cpu", "int8", reason, CUDA_DLL_DIRS or None)
        started = time.perf_counter()
        segments, info = transcribe(model, args.input, args.beam_size)
    elapsed_seconds = time.perf_counter() - started
    result = write_outputs(
        args.output_dir,
        args.source_id,
        args.model,
        runtime,
        segments,
        info,
        elapsed_seconds,
        args.beam_size,
    )
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
