[CmdletBinding()]
param(
    [switch]$Repair
)

$ErrorActionPreference = "Stop"
$SecureRoot = Join-Path $PSScriptRoot "secure"
$VenvPython = Get-ChildItem -LiteralPath $SecureRoot -Recurse -Filter "python.exe" |
    Where-Object { $_.FullName -like "*\Scripts\python.exe" } |
    Select-Object -First 1 -ExpandProperty FullName
$Requirements = Join-Path $PSScriptRoot "requirements-social-video.txt"
$ModelRoot = Get-ChildItem -LiteralPath $SecureRoot -Directory |
    Where-Object {
        @(Get-ChildItem -LiteralPath $_.FullName -Directory -Filter "*faster-whisper-large-v3-turbo").Count -gt 0
    } |
    Select-Object -First 1 -ExpandProperty FullName
$Diagnostic = Join-Path $PSScriptRoot "check-social-video-runtime.py"

if (-not $VenvPython) {
    throw "The social-video Python environment is missing. Run the archive entry point first."
}
if (-not $ModelRoot) {
    throw "The cached Whisper model directory is missing."
}

if ($Repair) {
    & $VenvPython -m pip install --disable-pip-version-check -r $Requirements
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to repair transcription dependencies."
    }
}

& $VenvPython $Diagnostic --model-cache $ModelRoot --model "large-v3-turbo"
if ($LASTEXITCODE -ne 0) {
    throw "GPU runtime check failed. Re-run with -Repair to restore project dependencies."
}

Write-Host "SOCIAL_VIDEO_GPU_READY"
