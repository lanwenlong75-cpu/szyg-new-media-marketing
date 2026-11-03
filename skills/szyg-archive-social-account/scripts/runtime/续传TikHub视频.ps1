[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$OutputDirectory,

    [Parameter(Mandatory = $true)]
    [string]$SourceUrl
)

$ErrorActionPreference = 'Stop'
$resolvedDirectory = (Resolve-Path -LiteralPath $OutputDirectory).Path
$responsePath = Join-Path $resolvedDirectory 'tikhub-response.json'
$videoPath = Join-Path $resolvedDirectory 'source.mp4'
$resultPath = Join-Path $resolvedDirectory 'acquisition-result.json'

if (-not (Test-Path -LiteralPath $responsePath)) {
    throw "缺少已计费请求响应：$responsePath"
}

$response = Get-Content -LiteralPath $responsePath -Raw -Encoding UTF8 | ConvertFrom-Json
$item = $response.data.aweme_detail
if ($null -eq $item) {
    throw 'TikHub 响应缺少 aweme_detail。'
}

$downloadUrl = @($item.video.play_addr.url_list | Where-Object { $_ -match '^https?://' })[0]
if (-not $downloadUrl) {
    throw 'TikHub 响应中没有可续传的视频地址。'
}

$curl = (Get-Command curl.exe -ErrorAction Stop).Source
& $curl `
    --fail `
    --location `
    --silent `
    --show-error `
    --http1.1 `
    --ssl-no-revoke `
    --max-time 1800 `
    --retry 5 `
    --retry-delay 2 `
    --retry-all-errors `
    --continue-at - `
    --user-agent 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/138 Safari/537.36' `
    --referer 'https://www.douyin.com/' `
    --output $videoPath `
    $downloadUrl

if ($LASTEXITCODE -ne 0) {
    throw "视频续传失败，curl 退出码：$LASTEXITCODE"
}

$video = Get-Item -LiteralPath $videoPath
if ($video.Length -lt 102400) {
    throw "续传后的视频文件异常小：$($video.Length) bytes"
}

$result = [ordered]@{
    Platform = 'douyin'
    SourceUrl = $SourceUrl
    VideoId = [string]$item.aweme_id
    Title = [string]$item.desc
    Author = [string]$item.author.nickname
    PublishedAt = [DateTimeOffset]::FromUnixTimeSeconds([long]$item.create_time).ToLocalTime().ToString('yyyy-MM-dd HH:mm:ss zzz')
    DurationMs = $item.video.duration
    VideoPath = $video.FullName
    VideoBytes = $video.Length
    ApiResponsePath = $responsePath
    ApiEndpoint = '/api/v1/douyin/web/fetch_one_video_by_share_url'
    ApiCostUsd = 0.001
    DownloadResumedFromSavedResponse = $true
}

$result | ConvertTo-Json -Depth 10 | Set-Content -LiteralPath $resultPath -Encoding UTF8
$result | ConvertTo-Json -Compress
