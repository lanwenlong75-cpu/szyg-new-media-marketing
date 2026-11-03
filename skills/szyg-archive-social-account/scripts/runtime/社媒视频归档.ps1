[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [ValidateSet("douyin", "shipinhao", "xiaohongshu", "bilibili", "other")]
    [string]$Platform,

    [Parameter(Mandatory = $true)]
    [string]$SourceUrl,

    [string]$VideoId,

    [Parameter(Mandatory = $true)]
    [string]$Title,

    [string]$Author = "待补",
    [datetime]$PublishedAt = (Get-Date),

    [Parameter(Mandatory = $true)]
    [string]$VideoPath,

    [string]$AudioPath,
    [string]$CoverPath,
    [string]$CommentsPath,
    [switch]$CollectComments,
    [ValidateSet("high-value", "uncertain", "transcript-only")]
    [string]$Retention = "high-value",
    [string]$PythonPath,
    [switch]$ForceTranscription,
    [switch]$RequireGpu,
    [ValidateSet("fast", "accurate")]
    [string]$TranscriptionMode = "fast"
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$SecureRoot = Join-Path $PSScriptRoot "secure"
$StateRoot = Join-Path $PSScriptRoot "state"
$VenvRoot = Join-Path $SecureRoot "视频转写环境"
$ModelRoot = Join-Path $SecureRoot "视频转写模型"
$TempRoot = Join-Path $SecureRoot "视频转写临时文件"
$IndexPath = Join-Path $StateRoot "social-video-index.csv"

$PlatformNames = @{
    douyin = "抖音"
    shipinhao = "视频号"
    xiaohongshu = "小红书"
    bilibili = "哔哩哔哩"
    other = "其他"
}

function Get-PlatformId {
    param([string]$ExplicitId, [string]$Url)
    if ($ExplicitId) { return $ExplicitId.Trim() }
    $patterns = @(
        '/video/(\d+)',
        'modal_id=(\d+)',
        '/note/([A-Za-z0-9]+)',
        '/video/([A-Za-z0-9]+)'
    )
    foreach ($pattern in $patterns) {
        if ($Url -match $pattern) { return $Matches[1] }
    }
    throw "无法从链接识别平台 ID，请传入 -VideoId。"
}

function Get-SafeName {
    param([string]$Value)
    $name = ($Value -replace '\s*#.*$', '').Trim()
    foreach ($char in [IO.Path]::GetInvalidFileNameChars()) {
        $name = $name.Replace([string]$char, "")
    }
    $name = ($name -replace '\s+', ' ').Trim().TrimEnd('.')
    if ($name.Length -gt 60) { $name = $name.Substring(0, 60).Trim() }
    if (-not $name) { return "无标题" }
    return $name
}

function Get-DefaultPython {
    $existingVenv = Join-Path $VenvRoot "Scripts\python.exe"
    if (Test-Path -LiteralPath $existingVenv) { return $existingVenv }
    $command = Get-Command python.exe -ErrorAction SilentlyContinue
    if ($command) { return $command.Source }
    $launcher = Get-Command py.exe -ErrorAction SilentlyContinue
    if ($launcher) {
        $resolved = @(& $launcher.Source -3 -c "import sys; print(sys.executable)") |
            Select-Object -Last 1
        if ($LASTEXITCODE -eq 0 -and (Test-Path -LiteralPath $resolved)) {
            return $resolved
        }
    }
    throw "未找到 Python。请通过 -PythonPath 指定 Python 3.10 或更高版本。"
}

function Ensure-TranscriptionEnvironment {
    param([string]$BootstrapPython)
    $venvPython = Join-Path $VenvRoot "Scripts\python.exe"
    if (-not (Test-Path -LiteralPath $venvPython)) {
        New-Item -ItemType Directory -Force -Path $SecureRoot | Out-Null
        & $BootstrapPython -m venv $VenvRoot
        if ($LASTEXITCODE -ne 0) { throw "创建视频转写环境失败。" }
    }
    $marker = Join-Path $VenvRoot ".requirements-social-video"
    $requirements = Join-Path $PSScriptRoot "requirements-social-video.txt"
    $requiredHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $requirements).Hash
    $installedHash = if (Test-Path -LiteralPath $marker) {
        (Get-Content -Raw -LiteralPath $marker).Trim()
    } else { "" }
    if ($requiredHash -ne $installedHash) {
        & $venvPython -m pip install --disable-pip-version-check -r $requirements | Out-Host
        if ($LASTEXITCODE -ne 0) { throw "安装视频转写依赖失败。" }
        Set-Content -Encoding utf8 -LiteralPath $marker -Value $requiredHash
    }
    return $venvPython
}

function Upsert-Index {
    param([pscustomobject]$Row)
    New-Item -ItemType Directory -Force -Path $StateRoot | Out-Null
    $rows = @()
    if (Test-Path -LiteralPath $IndexPath) {
        $rows = @(Import-Csv -LiteralPath $IndexPath)
    }
    $rows = @($rows | Where-Object { $_.SourceId -ne $Row.SourceId })
    $rows += $Row
    $rows | Sort-Object SourceId | Export-Csv -NoTypeInformation -Encoding utf8 -LiteralPath $IndexPath
}

$ResolvedId = Get-PlatformId -ExplicitId $VideoId -Url $SourceUrl
$SourceId = "${Platform}:$ResolvedId"
$PlatformLabel = $PlatformNames[$Platform]
$SafeTitle = Get-SafeName $Title
$DatePath = $PublishedAt.ToString("yyyy\\MM\\dd")
$ArchiveRoot = Join-Path $ProjectRoot "知识库\第六层-输入\社媒视频原始同步"
$ExistingRow = $null
if (Test-Path -LiteralPath $IndexPath) {
    $ExistingRow = Import-Csv -LiteralPath $IndexPath |
        Where-Object { $_.SourceId -eq $SourceId } |
        Select-Object -First 1
}
$DefaultArchiveDir = Join-Path $ArchiveRoot (
    Join-Path $PlatformLabel (Join-Path $DatePath "$ResolvedId-$SafeTitle")
)
$ArchiveDir = $DefaultArchiveDir
if ($ExistingRow -and $ExistingRow.LocalPath) {
    $IndexedPath = [IO.Path]::GetFullPath($ExistingRow.LocalPath)
    $AllowedRoot = [IO.Path]::GetFullPath($ArchiveRoot).TrimEnd('\') + '\'
    if ($IndexedPath.StartsWith($AllowedRoot, [StringComparison]::OrdinalIgnoreCase)) {
        $ArchiveDir = $IndexedPath
    } else {
        throw "索引中的归档目录越出社媒视频原始同步范围：$IndexedPath"
    }
}

New-Item -ItemType Directory -Force -Path $ArchiveDir, $TempRoot, $ModelRoot | Out-Null

$ResolvedVideo = (Resolve-Path -LiteralPath $VideoPath).Path
$VideoHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $ResolvedVideo).Hash
$TranscriptJson = Join-Path $ArchiveDir "01-逐字稿-原始.json"
$ShouldTranscribe = $ForceTranscription -or
    -not $ExistingRow -or
    $ExistingRow.MediaSha256 -ne $VideoHash -or
    -not (Test-Path -LiteralPath $TranscriptJson)
$VideoExtension = [IO.Path]::GetExtension($ResolvedVideo).ToLowerInvariant()
$ArchivedVideo = Join-Path $ArchiveDir "source$VideoExtension"
if ($Retention -ne "transcript-only") {
    $ResolvedArchiveVideo = [IO.Path]::GetFullPath($ArchivedVideo)
    if (-not $ResolvedVideo.Equals($ResolvedArchiveVideo, [StringComparison]::OrdinalIgnoreCase)) {
        Copy-Item -Force -LiteralPath $ResolvedVideo -Destination $ArchivedVideo
    }
}

$TranscriptionInput = $ResolvedVideo
$TempAudio = $null
if ($ShouldTranscribe -and $AudioPath) {
    $ResolvedAudio = (Resolve-Path -LiteralPath $AudioPath).Path
    $AudioExtension = [IO.Path]::GetExtension($ResolvedAudio).ToLowerInvariant()
    $TempAudio = Join-Path $TempRoot "$Platform-$ResolvedId$AudioExtension"
    Copy-Item -Force -LiteralPath $ResolvedAudio -Destination $TempAudio
    $TranscriptionInput = $TempAudio
}

$ArchivedCover = ""
if ($CoverPath) {
    $ResolvedCover = (Resolve-Path -LiteralPath $CoverPath).Path
    $CoverExtension = [IO.Path]::GetExtension($ResolvedCover).ToLowerInvariant()
    $ArchivedCover = Join-Path $ArchiveDir "cover$CoverExtension"
    Copy-Item -Force -LiteralPath $ResolvedCover -Destination $ArchivedCover
}

$ArchivedComments = ""
if ($CommentsPath) {
    $ResolvedComments = (Resolve-Path -LiteralPath $CommentsPath).Path
    $ArchivedComments = Join-Path $ArchiveDir "03-评论语料.md"
    Copy-Item -Force -LiteralPath $ResolvedComments -Destination $ArchivedComments
}

$DownloadedAt = (Get-Date).ToString("yyyy-MM-dd HH:mm:ss zzz")
$SourceInfo = @"
---
source_id: $SourceId
platform: $PlatformLabel
platform_id: $ResolvedId
author: $Author
published_at: $($PublishedAt.ToString("yyyy-MM-dd HH:mm:ss"))
source_url: $SourceUrl
downloaded_at: $DownloadedAt
retention: $Retention
verification_status: 待全文核验
---

# $Title

## 来源

- 作者：$Author
- 平台：$PlatformLabel
- 原链接：[$SourceUrl]($SourceUrl)
- 发布时间：$($PublishedAt.ToString("yyyy-MM-dd HH:mm:ss"))
- 下载时间：$DownloadedAt
- 视频 SHA256：$VideoHash
- 评论采集：$(if ($CollectComments) { "需要，当前文件：$(if ($ArchivedComments) { '已归档' } else { '待采集' })" } else { "本次不需要" })

## 留存

- 原视频：$(if ($Retention -ne "transcript-only") { "保留" } else { "核验后清理" })
- 封面：$(if ($ArchivedCover) { "已保留" } else { "待补" })
- 音频：仅作为转写中间文件，转写结束后清理
"@
    $SourceInfoPath = Join-Path $ArchiveDir "00-来源信息.md"
if (-not (Test-Path -LiteralPath $SourceInfoPath)) {
    Set-Content -Encoding utf8 -LiteralPath $SourceInfoPath -Value $SourceInfo
}

$TranscriptStatus = if ($ExistingRow -and $ExistingRow.TranscriptStatus) {
    $ExistingRow.TranscriptStatus
} else {
    "待语义核验"
}
$RuntimeDevice = if ($ExistingRow -and $ExistingRow.RuntimeDevice) {
    $ExistingRow.RuntimeDevice
} else {
    ""
}
$TranscriptionSpeedX = if ($ExistingRow -and $ExistingRow.TranscriptionSpeedX) {
    $ExistingRow.TranscriptionSpeedX
} else {
    ""
}
if ((-not $RuntimeDevice) -and (Test-Path -LiteralPath $TranscriptJson)) {
    $ExistingTranscript = Get-Content -Raw -Encoding UTF8 -LiteralPath $TranscriptJson |
        ConvertFrom-Json
    if ($ExistingTranscript.runtime.device) {
        $RuntimeDevice = $ExistingTranscript.runtime.device
    }
    if ($ExistingTranscript.transcription_speed_x) {
        $TranscriptionSpeedX = $ExistingTranscript.transcription_speed_x
    }
}
if ($ShouldTranscribe) {
    $BootstrapPython = if ($PythonPath) { (Resolve-Path -LiteralPath $PythonPath).Path } else { Get-DefaultPython }
    $VenvPython = Ensure-TranscriptionEnvironment -BootstrapPython $BootstrapPython
    $Transcriber = Join-Path $PSScriptRoot "转写社媒视频.py"
    $BeamSize = if ($TranscriptionMode -eq "accurate") { 5 } else { 1 }
    $TranscriptStatus = "转写失败"
    try {
        $TranscriberArgs = @(
            $Transcriber,
            "--input", $TranscriptionInput,
            "--output-dir", $ArchiveDir,
            "--source-id", $SourceId,
            "--model", "large-v3-turbo",
            "--beam-size", $BeamSize,
            "--model-cache", $ModelRoot
        )
        if ($RequireGpu) {
            $TranscriberArgs += "--require-gpu"
        }
        $TranscriptionOutput = @(& $VenvPython @TranscriberArgs)
        if ($LASTEXITCODE -ne 0) { throw "转写脚本返回错误码 $LASTEXITCODE。" }
        $ResultLine = $TranscriptionOutput | Select-Object -Last 1
        $TranscriptionResult = $ResultLine | ConvertFrom-Json
        $RuntimeDevice = $TranscriptionResult.device
        $TranscriptionSpeedX = $TranscriptionResult.transcription_speed_x
        Write-Host $ResultLine
        Write-Host "转写完成：设备 $RuntimeDevice，速度 ${TranscriptionSpeedX}x"
        $TranscriptStatus = "待语义核验"
    }
    finally {
        if ($TempAudio -and (Test-Path -LiteralPath $TempAudio)) {
            Remove-Item -Force -LiteralPath $TempAudio
        }
    }
}

$Row = [pscustomobject]@{
    SourceId = $SourceId
    Platform = $PlatformLabel
    VideoId = $ResolvedId
    SourceUrl = $SourceUrl
    Title = $Title
    Author = $Author
    PublishedAt = $PublishedAt.ToString("yyyy-MM-dd HH:mm:ss")
    LocalPath = $ArchiveDir
    MediaSha256 = $VideoHash
    DownloadStatus = "已下载"
    TranscriptStatus = $TranscriptStatus
    RuntimeDevice = $RuntimeDevice
    TranscriptionSpeedX = $TranscriptionSpeedX
    CompileStatus = if ($ExistingRow -and $ExistingRow.CompileStatus) { $ExistingRow.CompileStatus } else { "待编译" }
    UpdatedAt = (Get-Date).ToString("yyyy-MM-dd HH:mm:ss zzz")
}
Upsert-Index -Row $Row

[pscustomobject]@{
    SourceId = $SourceId
    ArchiveDir = $ArchiveDir
    TranscriptStatus = $TranscriptStatus
    IndexPath = $IndexPath
}





