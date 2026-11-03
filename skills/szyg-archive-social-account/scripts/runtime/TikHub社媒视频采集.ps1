[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$SourceUrl,

    [Parameter(Mandatory = $true)]
    [string]$OutputDirectory,

    [string]$CredentialPath,

    [ValidateSet('douyin')]
    [string]$Platform = 'douyin'
)

$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'

if ([string]::IsNullOrWhiteSpace($CredentialPath)) {
    $CredentialPath = Join-Path $PSScriptRoot 'secure\tikhub-credential.xml'
}

function Get-PlainTextFromSecureString {
    param([Parameter(Mandatory = $true)][Security.SecureString]$SecureValue)

    $pointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($SecureValue)
    try {
        return [Runtime.InteropServices.Marshal]::PtrToStringBSTR($pointer)
    }
    finally {
        [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($pointer)
    }
}

function Get-FirstPropertyValue {
    param(
        [Parameter(Mandatory = $true)]$Object,
        [Parameter(Mandatory = $true)][string[]]$Names
    )

    foreach ($name in $Names) {
        $property = $Object.PSObject.Properties[$name]
        if ($null -ne $property -and $null -ne $property.Value) {
            return $property.Value
        }
    }
    return $null
}

function Get-FirstUrl {
    param([Parameter(Mandatory = $true)]$Video)

    $addressNames = @(
        'play_addr',
        'play_addr_h264',
        'download_addr',
        'play_addr_265',
        'play_addr_bytevc1'
    )

    foreach ($addressName in $addressNames) {
        $address = Get-FirstPropertyValue -Object $Video -Names @($addressName)
        if ($null -eq $address) {
            continue
        }

        $urlList = Get-FirstPropertyValue -Object $address -Names @('url_list', 'urlList')
        if ($null -ne $urlList) {
            foreach ($candidate in @($urlList)) {
                if ($candidate -is [string] -and $candidate -match '^https?://') {
                    return $candidate
                }
            }
        }

        $directUrl = Get-FirstPropertyValue -Object $address -Names @('url', 'uri')
        if ($directUrl -is [string] -and $directUrl -match '^https?://') {
            return $directUrl
        }
    }

    throw 'TikHub 响应中没有找到可下载的视频地址。'
}

if (-not (Test-Path -LiteralPath $CredentialPath)) {
    throw "未找到 TikHub 加密凭据：$CredentialPath"
}

$credential = Import-Clixml -LiteralPath $CredentialPath
if ($credential -isnot [Security.SecureString]) {
    throw 'TikHub 凭据文件格式无效。'
}

New-Item -ItemType Directory -Force -Path $OutputDirectory | Out-Null
$resolvedOutputDirectory = (Resolve-Path -LiteralPath $OutputDirectory).Path
$responsePath = Join-Path $resolvedOutputDirectory 'tikhub-response.json'
$resultPath = Join-Path $resolvedOutputDirectory 'acquisition-result.json'
$videoPath = Join-Path $resolvedOutputDirectory 'source.mp4'

$apiKey = Get-PlainTextFromSecureString -SecureValue $credential
try {
    $encodedUrl = [Uri]::EscapeDataString($SourceUrl)
    $endpoint = "https://api.tikhub.io/api/v1/douyin/web/fetch_one_video_by_share_url?share_url=$encodedUrl"
    $headers = @{
        Authorization = "Bearer $apiKey"
        Accept = 'application/json'
    }

    $webResponse = Invoke-WebRequest -Method Get -Uri $endpoint -Headers $headers -TimeoutSec 90 -UseBasicParsing
    $webResponse.RawContentStream.Position = 0
    $reader = New-Object IO.StreamReader(
        $webResponse.RawContentStream,
        (New-Object Text.UTF8Encoding($false)),
        $true
    )
    try {
        $responseText = $reader.ReadToEnd()
    }
    finally {
        $reader.Dispose()
    }
    $response = $responseText | ConvertFrom-Json
}
finally {
    $apiKey = $null
    $headers = $null
}

$response | ConvertTo-Json -Depth 100 | Set-Content -LiteralPath $responsePath -Encoding UTF8

$statusCode = Get-FirstPropertyValue -Object $response -Names @('code', 'status_code', 'statusCode')
if ($null -ne $statusCode -and [int]$statusCode -notin @(0, 200)) {
    $message = Get-FirstPropertyValue -Object $response -Names @('message', 'msg', 'detail')
    throw "TikHub 请求失败，状态码 $statusCode：$message"
}

$data = Get-FirstPropertyValue -Object $response -Names @('data')
if ($null -eq $data) {
    throw 'TikHub 响应缺少 data。'
}

$item = Get-FirstPropertyValue -Object $data -Names @('aweme_detail', 'awemeDetail', 'item')
if ($null -eq $item) {
    $item = $data
}

$video = Get-FirstPropertyValue -Object $item -Names @('video')
if ($null -eq $video) {
    throw 'TikHub 响应缺少 video 元数据。'
}

$downloadUrl = Get-FirstUrl -Video $video
$curl = Get-Command curl.exe -ErrorAction SilentlyContinue
if ($curl) {
    & $curl.Source `
        --fail `
        --location `
        --silent `
        --show-error `
        --http1.1 `
        --ssl-no-revoke `
        --connect-timeout 30 `
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
        throw "视频下载失败，curl 退出码：$LASTEXITCODE"
    }
}
else {
    $downloadHeaders = @{
        'User-Agent' = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/138 Safari/537.36'
        Referer = 'https://www.douyin.com/'
    }
    Invoke-WebRequest -Uri $downloadUrl -Headers $downloadHeaders -OutFile $videoPath -TimeoutSec 900
}

$videoItem = Get-Item -LiteralPath $videoPath
if ($videoItem.Length -lt 102400) {
    throw "下载的视频文件异常小：$($videoItem.Length) bytes"
}

$authorObject = Get-FirstPropertyValue -Object $item -Names @('author')
$author = if ($null -ne $authorObject) {
    Get-FirstPropertyValue -Object $authorObject -Names @('nickname', 'name', 'unique_id')
}
else {
    $null
}

$createTime = Get-FirstPropertyValue -Object $item -Names @('create_time', 'createTime')
$publishedAt = $null
if ($null -ne $createTime) {
    $publishedAt = [DateTimeOffset]::FromUnixTimeSeconds([long]$createTime).ToLocalTime().ToString('yyyy-MM-dd HH:mm:ss zzz')
}

$result = [ordered]@{
    Platform = $Platform
    SourceUrl = $SourceUrl
    VideoId = [string](Get-FirstPropertyValue -Object $item -Names @('aweme_id', 'awemeId', 'item_id', 'id'))
    Title = [string](Get-FirstPropertyValue -Object $item -Names @('desc', 'title'))
    Author = [string]$author
    PublishedAt = $publishedAt
    DurationMs = Get-FirstPropertyValue -Object $video -Names @('duration')
    VideoPath = $videoItem.FullName
    VideoBytes = $videoItem.Length
    ApiResponsePath = $responsePath
    ApiEndpoint = '/api/v1/douyin/web/fetch_one_video_by_share_url'
    ApiCostUsd = 0.001
}

$result | ConvertTo-Json -Depth 10 | Set-Content -LiteralPath $resultPath -Encoding UTF8
$result | ConvertTo-Json -Compress
