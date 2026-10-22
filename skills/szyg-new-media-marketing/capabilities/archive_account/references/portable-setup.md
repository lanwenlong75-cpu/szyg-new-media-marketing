# Portable setup

## Install the Skill

Extract the package, then run:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File `
  ".\szyg-archive-social-account\scripts\install_skill.ps1"
```

Alternatively, copy the complete `szyg-archive-social-account` folder to:

```text
%USERPROFILE%\.codex\skills\szyg-archive-social-account
```

Restart Codex after copying.

## Install the project runtime

Run from PowerShell:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File `
  "<skill>\scripts\install_runtime.ps1" `
  -ProjectRoot "<project-root>"
```

The installer copies only automation source files. It does not copy API keys,
model weights, videos, transcripts, or knowledge-base content. Existing runtime
files are preserved unless `-Force` is supplied.

## Configure TikHub on each computer

DPAPI credentials are bound to the Windows user and computer. Create a new
encrypted credential on the destination computer:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File `
  "<skill>\scripts\initialize_tikhub_credential.ps1" `
  -ProjectRoot "<project-root>"
```

The script reads the key as a secure string and exports it directly to the
project's `自动化\secure` directory. Do not copy the encrypted XML from another
computer.

Use a restricted key that only permits the required read-only media endpoints.

## Prepare GPU transcription

Install a current NVIDIA driver and Python 3.10 or newer, then run:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File `
  "<skill>\scripts\setup_runtime.ps1" `
  -ProjectRoot "<project-root>" `
  -PythonPath "<python.exe>"
```

This creates a project-local virtual environment, installs pinned transcription
dependencies, downloads `large-v3-turbo`, and verifies CUDA with
`int8_float16`.

Model files and the Python environment stay under `自动化\secure`; they are not
part of the portable Skill package.

## Required project layout

The selected project must contain:

```text
<project-root>\
├── AGENTS.md
├── 自动化\
└── 知识库\
```

If a different knowledge-base layout is used, adjust the archive and Wiki paths
before running a production batch.
