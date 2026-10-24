param([switch]$LibraryOnly, [switch]$NoOpenFolder, [string]$RecipientHome, [string]$RuntimeCacheRoot, [string]$SkillsRoot, [string]$WorkspaceRoot)
$ErrorActionPreference = 'Stop'
if (-not (Get-Command Assert-SzygHash -ErrorAction SilentlyContinue)) {
    . (Join-Path $PSScriptRoot 'installer-runtime.ps1')
}

function Get-SzygReleaseBundle {
    param([string]$CacheRoot)
    $tag = 'v0.2.7-public.2026.10.24.2'
    $name = 'szyg-new-media-marketing-codex-2026.10.24.2.zip'
    [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
    $release = Invoke-RestMethod -Uri ('https://api.github.com/repos/lanwenlong75-cpu/szyg-new-media-marketing/releases/tags/' + $tag) -Headers @{'User-Agent'='Szyg-New-Media-Installer'}
    if ($release.tag_name -ne $tag -or $release.draft -or $release.prerelease) { throw 'The fixed public release is unavailable.' }
    $assets = @($release.assets | Where-Object { $_.name -eq $name -and $_.state -eq 'uploaded' })
    if ($assets.Count -ne 1) { throw 'The release must contain exactly one complete installation ZIP.' }
    $asset = $assets[0]
    $expectedUrl = 'https://github.com/lanwenlong75-cpu/szyg-new-media-marketing/releases/download/' + $tag + '/' + $name
    if ($asset.browser_download_url -ne $expectedUrl -or $asset.digest -notmatch '^sha256:([a-fA-F0-9]{64})$') { throw 'The release asset URL or GitHub SHA-256 is invalid.' }
    $expected = $asset.digest.Substring(7)
    if (-not $CacheRoot) { $CacheRoot = Join-Path ([IO.Path]::GetTempPath()) ('sznm-' + [Guid]::NewGuid().ToString('N').Substring(0, 8)) }
    Assert-SzygPlainPath $CacheRoot
    if (Test-Path -LiteralPath $CacheRoot) { throw 'A new download directory is required.' }
    New-Item -ItemType Directory -Path $CacheRoot | Out-Null
    $archive = Join-Path $CacheRoot $name
    Write-Host 'Downloading the fixed new-media team release from GitHub...'
    Receive-SzygFile $expectedUrl $archive
    if ((Get-Item -LiteralPath $archive).Length -ne $asset.size) { throw 'The download is incomplete.' }
    Assert-SzygHash $archive $expected
    $bundle = Join-Path $CacheRoot 'bundle'
    Expand-SzygZip $archive $bundle
    if (-not (Test-Path -LiteralPath (Join-Path $bundle 'install.ps1'))) { throw 'The verified archive does not contain its installer.' }
    return $bundle
}

if (-not $LibraryOnly) {
    try {
        $bundle = Get-SzygReleaseBundle
        $arguments = @('-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', (Join-Path $bundle 'install.ps1'))
        if ($NoOpenFolder) { $arguments += '-NoOpenFolder' }
        if ($RecipientHome) { $arguments += @('-RecipientHome', $RecipientHome) }
        if ($RuntimeCacheRoot) { $arguments += @('-RuntimeCacheRoot', $RuntimeCacheRoot) }
        if ($SkillsRoot) { $arguments += @('-SkillsRoot', $SkillsRoot) }
        if ($WorkspaceRoot) { $arguments += @('-WorkspaceRoot', $WorkspaceRoot) }
        & powershell.exe @arguments
        if ($LASTEXITCODE -ne 0) { throw 'Installation stopped. Read the message above; existing projects are preserved.' }
        exit 0
    } catch {
        Write-Host ('Installation needs attention: ' + $_.Exception.Message) -ForegroundColor Red
        exit 1
    }
}
