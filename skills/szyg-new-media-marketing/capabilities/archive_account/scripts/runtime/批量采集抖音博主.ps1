[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$InventoryPath,

    [Parameter(Mandatory = $true)]
    [string]$OutputRoot,

    [int]$MaxItems = 0
)

$ErrorActionPreference = 'Stop'
$acquisitionScript = Join-Path $PSScriptRoot 'TikHub社媒视频采集.ps1'
if (-not (Test-Path -LiteralPath $acquisitionScript)) {
    throw "缺少采集脚本：$acquisitionScript"
}

$inventory = Get-Content -LiteralPath $InventoryPath -Raw -Encoding UTF8 | ConvertFrom-Json
New-Item -ItemType Directory -Force -Path $OutputRoot | Out-Null
$resolvedOutputRoot = (Resolve-Path -LiteralPath $OutputRoot).Path
$statePath = Join-Path $resolvedOutputRoot 'batch-state.json'

function Write-BatchState {
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
$indexPath = Join-Path $PSScriptRoot 'state\social-video-index.csv'
if (Test-Path -LiteralPath $indexPath) {
    foreach ($row in (Import-Csv -LiteralPath $indexPath)) {
        if ($row.VideoId) {
            $existingIds[[string]$row.VideoId] = $true
        }
    }
}

$items = @($inventory.videos | Where-Object {
    $_.status -eq '待采集' -and -not $existingIds.ContainsKey([string]$_.video_id)
})
if ($MaxItems -gt 0) {
    $items = @($items | Select-Object -First $MaxItems)
}

$state = [ordered]@{
    profile_name = $inventory.profile_name
    started_at = (Get-Date).ToString('o')
    requested_items = $items.Count
    api_cost_per_attempt_usd = 0.001
    attempts = 0
    completed = 0
    failed = 0
    results = @()
}

foreach ($item in $items) {
    $videoId = [string]$item.video_id
    $itemOutput = Join-Path $resolvedOutputRoot $videoId
    $existingResult = Join-Path $itemOutput 'acquisition-result.json'

    if (Test-Path -LiteralPath $existingResult) {
        $saved = Get-Content -LiteralPath $existingResult -Raw -Encoding UTF8 | ConvertFrom-Json
        $state.completed++
        $state.results += [ordered]@{
            video_id = $videoId
            status = '已存在'
            output_directory = $itemOutput
            video_path = $saved.VideoPath
        }
        continue
    }

    $state.attempts++
    try {
        $output = & $acquisitionScript `
            -SourceUrl ([string]$item.url) `
            -OutputDirectory $itemOutput
        $result = $output | Select-Object -Last 1 | ConvertFrom-Json
        $state.completed++
        $state.results += [ordered]@{
            video_id = $videoId
            status = '采集成功'
            output_directory = $itemOutput
            video_path = $result.VideoPath
            video_bytes = $result.VideoBytes
            duration_ms = $result.DurationMs
            title = $result.Title
            author = $result.Author
            published_at = $result.PublishedAt
        }
    }
    catch {
        $state.failed++
        $state.results += [ordered]@{
            video_id = $videoId
            status = '采集失败'
            output_directory = $itemOutput
            error = $_.Exception.Message
        }
    }

    $state.updated_at = (Get-Date).ToString('o')
    $state.estimated_api_cost_usd = [math]::Round($state.attempts * 0.001, 3)
    Write-BatchState -Value $state -Path $statePath
}

$state.finished_at = (Get-Date).ToString('o')
$state.estimated_api_cost_usd = [math]::Round($state.attempts * 0.001, 3)
Write-BatchState -Value $state -Path $statePath

[pscustomobject]@{
    Profile = $state.profile_name
    Requested = $state.requested_items
    Attempts = $state.attempts
    Completed = $state.completed
    Failed = $state.failed
    EstimatedApiCostUsd = $state.estimated_api_cost_usd
    StatePath = $statePath
} | ConvertTo-Json -Compress
