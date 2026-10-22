[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$ProjectRoot,

    [Parameter(Mandatory = $true)]
    [string]$PythonPath
)

$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = New-Object Text.UTF8Encoding($false)
$OutputEncoding = [Console]::OutputEncoding
$resolvedProject = (Resolve-Path -LiteralPath $ProjectRoot).Path
$resolvedPython = (Resolve-Path -LiteralPath $PythonPath).Path
$automationRoot = Join-Path $resolvedProject '自动化'
$requirements = Join-Path $automationRoot 'requirements-social-video.txt'
$diagnostic = Join-Path $automationRoot 'check-social-video-runtime.py'

foreach ($required in @($requirements, $diagnostic)) {
    if (-not (Test-Path -LiteralPath $required)) {
        throw "缺少运行时文件，请先运行 install_runtime.ps1：$required"
    }
}

$secureRoot = Join-Path $automationRoot 'secure'
$venvRoot = Join-Path $secureRoot '视频转写环境'
$venvPython = Join-Path $venvRoot 'Scripts\python.exe'
$modelRoot = Join-Path $secureRoot '视频转写模型'
New-Item -ItemType Directory -Force -Path $secureRoot, $modelRoot | Out-Null

if (-not (Test-Path -LiteralPath $venvPython)) {
    & $resolvedPython -m venv $venvRoot
    if ($LASTEXITCODE -ne 0) {
        throw '创建视频转写虚拟环境失败。'
    }
}

& $venvPython -m pip install --disable-pip-version-check -r $requirements
if ($LASTEXITCODE -ne 0) {
    throw '安装视频转写依赖失败。'
}

& $venvPython $diagnostic --model-cache $modelRoot --model 'large-v3-turbo'
if ($LASTEXITCODE -ne 0) {
    throw 'GPU运行环境验证失败。请检查NVIDIA驱动和CUDA依赖。'
}

[pscustomobject]@{
    Python = $venvPython
    ModelRoot = $modelRoot
    Device = 'cuda'
    ComputeType = 'int8_float16'
} | ConvertTo-Json -Compress
