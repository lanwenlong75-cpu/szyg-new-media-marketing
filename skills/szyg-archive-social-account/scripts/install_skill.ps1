[CmdletBinding()]
param(
    [switch]$Force
)

$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = New-Object Text.UTF8Encoding($false)
$OutputEncoding = [Console]::OutputEncoding

$skillSource = Split-Path -Parent $PSScriptRoot
$skillName = Split-Path -Leaf $skillSource
$codexSkills = Join-Path $env:USERPROFILE '.codex\skills'
$destination = Join-Path $codexSkills $skillName

if ([IO.Path]::GetFullPath($skillSource).Equals(
    [IO.Path]::GetFullPath($destination),
    [StringComparison]::OrdinalIgnoreCase
)) {
    [pscustomobject]@{
        Installed = $true
        Destination = $destination
        Action = 'already-installed'
    } | ConvertTo-Json -Compress
    exit 0
}

if ((Test-Path -LiteralPath $destination) -and -not $Force) {
    throw "目标 Skill 已存在：$destination。确认替换时使用 -Force。"
}

New-Item -ItemType Directory -Force -Path $codexSkills | Out-Null
if (Test-Path -LiteralPath $destination) {
    $resolvedSkills = [IO.Path]::GetFullPath($codexSkills).TrimEnd('\') + '\'
    $resolvedDestination = [IO.Path]::GetFullPath($destination)
    if (-not $resolvedDestination.StartsWith(
        $resolvedSkills,
        [StringComparison]::OrdinalIgnoreCase
    )) {
        throw "拒绝清理 Skill 根目录之外的路径：$resolvedDestination"
    }
    [IO.Directory]::Delete($resolvedDestination, $true)
}

Copy-Item -LiteralPath $skillSource -Destination $destination -Recurse -Force

[pscustomobject]@{
    Installed = $true
    Destination = $destination
    Action = 'copied'
} | ConvertTo-Json -Compress
