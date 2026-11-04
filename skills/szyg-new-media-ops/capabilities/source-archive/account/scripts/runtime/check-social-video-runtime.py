#!/usr/bin/env python3
"""Check the local social-video transcription runtime and print JSON diagnostics."""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Any


_DLL_HANDLES: list[Any] = []


def configure_cuda_dlls() -> list[str]:
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


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model-cache", required=True, type=Path)
    parser.add_argument("--model", default="large-v3-turbo")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    dll_dirs = configure_cuda_dlls()
    result: dict[str, Any] = {
        "ok": False,
        "python": sys.version.split()[0],
        "python_executable": sys.executable,
        "cuda_dll_dirs": dll_dirs,
        "model": args.model,
        "model_cached": args.model_cache.is_dir()
        and any(args.model_cache.iterdir()),
    }
    try:
        import ctranslate2
        import faster_whisper
        from faster_whisper import WhisperModel

        result["ctranslate2"] = ctranslate2.__version__
        result["faster_whisper"] = faster_whisper.__version__
        result["cuda_device_count"] = ctranslate2.get_cuda_device_count()
        started = time.perf_counter()
        WhisperModel(
            args.model,
            device="cuda",
            compute_type="int8_float16",
            download_root=str(args.model_cache),
        )
        result["gpu_model_load_seconds"] = round(time.perf_counter() - started, 3)
        result["device"] = "cuda"
        result["compute_type"] = "int8_float16"
        result["ok"] = True
    except Exception as exc:
        result["error"] = f"{type(exc).__name__}: {exc}"

    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
