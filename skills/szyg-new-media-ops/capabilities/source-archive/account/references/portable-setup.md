# 采集运行时准备

安装完整的新媒体运营岗位包后，本目录已经随包提供；不用另装“归档Skill”。按任务把所需运行时接入当前项目，凭据和业务资料留在项目中。

## Install the project runtime

Run from PowerShell:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File `
  "<运营Skill>/capabilities/source-archive/account\scripts\install_runtime.ps1" `
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
  "<运营Skill>/capabilities/source-archive/account\scripts\initialize_tikhub_credential.ps1" `
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
  "<运营Skill>/capabilities/source-archive/account\scripts\setup_runtime.ps1" `
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
└── 03-任务与交付\来源归档\
```

The installer creates the automation folders. New projects archive under 03-任务与交付/来源归档 by default; existing configured source archives stay in place. Knowledge-base compilation and Wiki checks apply only when the selected project has that structure. Pass -ArchiveRoot for another source folder inside this project.
