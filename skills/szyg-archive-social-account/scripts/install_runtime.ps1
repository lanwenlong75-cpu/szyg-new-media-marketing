[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$ProjectRoot,

    [switch]$Force
)

$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = New-Object Text.UTF8Encoding($false)
$OutputEncoding = [Console]::OutputEncoding
$resolvedProject = (Resolve-Path -LiteralPath $ProjectRoot).Path
$agentsPath = Join-Path $resolvedProject 'AGENTS.md'
if (-not (Test-Path -LiteralPath $agentsPath)) {
    throw "项目根目录缺少 AGENTS.md：$resolvedProject"
}

$sourceRoot = Join-Path $PSScriptRoot 'runtime'
$targetRoot = Join-Path $resolvedProject '自动化'
New-Item -ItemType Directory -Force -Path $targetRoot | Out-Null

$files = @(
    'TikHub社媒视频采集.ps1',
    '批量采集抖音博主.ps1',
    '续传TikHub视频.ps1',
    '社媒视频归档.ps1',
    '批量归档抖音视频.ps1',
    '转写社媒视频.py',
    'check-social-video-runtime.ps1',
    'check-social-video-runtime.py',
    'requirements-social-video.txt'
)

$installed = 0
$preserved = 0
foreach ($name in $files) {
    $source = Join-Path $sourceRoot $name
    $target = Join-Path $targetRoot $name
    if (-not (Test-Path -LiteralPath $source)) {
        throw "Skill 运行时缺少文件：$source"
    }
    if ((Test-Path -LiteralPath $target) -and -not $Force) {
        $preserved++
        continue
    }
    Copy-Item -LiteralPath $source -Destination $target -Force
    $installed++
}

[pscustomobject]@{
    ProjectRoot = $resolvedProject
    Installed = $installed
    Preserved = $preserved
    AutomationRoot = $targetRoot
} | ConvertTo-Json -Compress
