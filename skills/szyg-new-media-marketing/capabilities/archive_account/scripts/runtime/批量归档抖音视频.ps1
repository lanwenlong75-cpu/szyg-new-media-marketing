[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$AcquisitionRoot,

    [Parameter(Mandatory = $true)]
    [string]$StatePath
)

$ErrorActionPreference = 'Stop'
$archiveScript = Join-Path $PSScriptRoot '社媒视频归档.ps1'
$indexPath = Join-Path $PSScriptRoot 'state\social-video-index.csv'

function Write-ArchiveState {
    param(
        [Parameter(Mandatory = $true)]$Value,
        [Parameter(Mandatory = $true)][string]$Path
    )

    $json = $Value | ConvertTo-Json -Depth 10
    for ($attempt = 1; $attempt -le 10; $attempt++) {
        try {
            [IO.File]::WriteAllText($Path, $json, (New-Object Text.UTF8Encoding($true)))
            return
        }
        catch [IO.IOException] {
            if ($attempt -eq 10) {
                throw
            }
            Start-Sleep -Milliseconds 200
        }
    }
}

$existingIds = @{}
if (Test-Path -LiteralPath $indexPath) {
    foreach ($row in (Import-Csv -LiteralPath $indexPath)) {
        if ($row.VideoId) {
            $existingIds[[string]$row.VideoId] = $true
        }
    }
}

$resultFiles = @(Get-ChildItem -LiteralPath $AcquisitionRoot -Directory |
    ForEach-Object {
        $path = Join-Path $_.FullName 'acquisition-result.json'
        if (Test-Path -LiteralPath $path) {
            Get-Item -LiteralPath $path
        }
    } |
    Sort-Object FullName)

$pending = @($resultFiles | Where-Object {
    $result = Get-Content -LiteralPath $_.FullName -Raw -Encoding UTF8 | ConvertFrom-Json
    -not $existingIds.ContainsKey([string]$result.VideoId)
})

$state = [ordered]@{
    started_at = (Get-Date).ToString('o')
    requested = $pending.Count
    completed = 0
    failed = 0
    results = @()
}
Write-ArchiveState -Value $state -Path $StatePath

foreach ($resultFile in $pending) {
    $result = Get-Content -LiteralPath $resultFile.FullName -Raw -Encoding UTF8 | ConvertFrom-Json
    $videoId = [string]$result.VideoId
    $itemDirectory = Split-Path -Parent $resultFile.FullName
    $responsePath = Join-Path $itemDirectory 'tikhub-response.json'
    $coverPath = Join-Path $itemDirectory 'cover.jpg'

    try {
        if (-not (Test-Path -LiteralPath $coverPath) -and (Test-Path -LiteralPath $responsePath)) {
            $response = Get-Content -LiteralPath $responsePath -Raw -Encoding UTF8 | ConvertFrom-Json
            $coverUrl = @($response.data.aweme_detail.video.cover.url_list | Where-Object { $_ -match '^https?://' })[0]
            if ($coverUrl) {
                & curl.exe `
                    --fail `
                    --location `
                    --silent `
                    --show-error `
                    --retry 3 `
                    --retry-delay 1 `
                    --output $coverPath `
                    $coverUrl
                if ($LASTEXITCODE -ne 0) {
                    Remove-Item -LiteralPath $coverPath -Force -ErrorAction SilentlyContinue
                }
            }
        }

        $archiveArguments = @{
            Platform = 'douyin'
            SourceUrl = [string]$result.SourceUrl
            VideoId = $videoId
            Title = [string]$result.Title
            Author = [string]$result.Author
            PublishedAt = [datetime]$result.PublishedAt
            VideoPath = [string]$result.VideoPath
            Retention = 'high-value'
            RequireGpu = $true
            TranscriptionMode = 'fast'
        }
        if (Test-Path -LiteralPath $coverPath) {
            $archiveArguments.CoverPath = $coverPath
        }

        & $archiveScript @archiveArguments | Out-Null
        $indexRow = Import-Csv -LiteralPath $indexPath | Where-Object VideoId -eq $videoId | Select-Object -Last 1
        $state.completed++
        $state.results += [ordered]@{
            video_id = $videoId
            status = '归档成功'
            title = [string]$result.Title
            duration_ms = $result.DurationMs
            archive_path = $indexRow.LocalPath
            runtime_device = $indexRow.RuntimeDevice
            transcription_speed_x = $indexRow.TranscriptionSpeedX
        }
    }
    catch {
        $state.failed++
        $state.results += [ordered]@{
            video_id = $videoId
            status = '归档失败'
            title = [string]$result.Title
            error = $_.Exception.Message
        }
    }

    $state.updated_at = (Get-Date).ToString('o')
    Write-ArchiveState -Value $state -Path $StatePath
}

$state.finished_at = (Get-Date).ToString('o')
Write-ArchiveState -Value $state -Path $StatePath

[pscustomobject]@{
    Requested = $state.requested
    Completed = $state.completed
    Failed = $state.failed
    StatePath = $StatePath
} | ConvertTo-Json -Compress
