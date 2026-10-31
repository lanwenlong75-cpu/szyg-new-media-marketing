@echo off
setlocal
set "SZYG_BOOTSTRAP_FILE=%~f0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "$content=[IO.File]::ReadAllText($env:SZYG_BOOTSTRAP_FILE); & ([scriptblock]::Create(($content -split ':SZYG_POWERSHELL\r?\n',2)[1]))"
set "SZYG_RESULT=%ERRORLEVEL%"
if not "%SZYG_RESULT%"=="0" echo Installation needs attention. Read the message above.
pause
exit /b %SZYG_RESULT%
:SZYG_POWERSHELL
$LibraryOnly=$false; $NoOpenFolder=$false; $RecipientHome=$null; $RuntimeCacheRoot=$null; $SkillsRoot=$null; $WorkspaceRoot=$null
# Shared Windows bootstrap helpers. No administrator rights or PATH changes.
Set-StrictMode -Version 2.0

function Receive-SzygFile {
    param([string]$Uri, [string]$Destination)
    if (-not $Uri.StartsWith('https://')) { throw 'An HTTPS download URL is required.' }
    [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
    $priorProgress = $ProgressPreference
    try {
        $ProgressPreference = 'SilentlyContinue'
        Invoke-WebRequest -UseBasicParsing -Uri $Uri -OutFile $Destination -Headers @{'User-Agent'='Szyg-New-Media-Installer'}
    } finally { $ProgressPreference = $priorProgress }
}

function Assert-SzygHash {
    param([string]$Path, [string]$Expected)
    if ($Expected -notmatch '^[a-fA-F0-9]{64}$') { throw 'The expected SHA-256 is missing or invalid.' }
    $stream = [IO.File]::OpenRead($Path)
    $algorithm = [Security.Cryptography.SHA256]::Create()
    try {
        $actual = [BitConverter]::ToString($algorithm.ComputeHash($stream)).Replace('-', '').ToLowerInvariant()
        if ($actual -ne $Expected.ToLowerInvariant()) { throw ('SHA-256 verification failed: ' + $Path) }
    } finally { $algorithm.Dispose(); $stream.Dispose() }
}

function Assert-SzygPlainPath {
    param([string]$Path)
    $cursor = [IO.Path]::GetFullPath($Path)
    while ($cursor) {
        if (Test-Path -LiteralPath $cursor) {
            $item = Get-Item -LiteralPath $cursor -Force
            if ($item.Attributes -band [IO.FileAttributes]::ReparsePoint) { throw 'A destination path contains a link. Existing files are preserved.' }
        }
        $parent = [IO.Directory]::GetParent($cursor)
        if (-not $parent) { break }
        $cursor = $parent.FullName
    }
}

function Expand-SzygZip {
    param([string]$Archive, [string]$Destination)
    Add-Type -AssemblyName System.IO.Compression
    Add-Type -AssemblyName System.IO.Compression.FileSystem
    Assert-SzygPlainPath $Destination
    $root = [IO.Path]::GetFullPath($Destination).TrimEnd([IO.Path]::DirectorySeparatorChar) + [IO.Path]::DirectorySeparatorChar
    if (Test-Path -LiteralPath $Destination) { throw 'Extraction requires a new directory.' }
    $zip = [IO.Compression.ZipFile]::OpenRead($Archive)
    try {
        foreach ($entry in $zip.Entries) {
            $relative = $entry.FullName.Replace('/', [IO.Path]::DirectorySeparatorChar)
            if ([IO.Path]::IsPathRooted($relative) -or $relative.Contains(':') -or ($relative -split '[\\/]') -contains '..') { throw 'Unsafe archive member path.' }
            $target = [IO.Path]::GetFullPath((Join-Path $Destination $relative))
            if (-not $target.StartsWith($root, [StringComparison]::OrdinalIgnoreCase)) { throw 'Archive member escapes its destination.' }
            $unixType = ($entry.ExternalAttributes -shr 16) -band 61440
            if ($unixType -eq 40960) { throw 'Archive links are not supported.' }
        }
    } finally { $zip.Dispose() }
    [IO.Compression.ZipFile]::ExtractToDirectory($Archive, $Destination)
}

function Test-SzygPython {
    param([string]$Executable, [string[]]$PrefixArgs = @())
    if (-not (Test-Path -LiteralPath $Executable -PathType Leaf)) { return $null }
    try {
        $probe = & $Executable @PrefixArgs '-c' 'import sys,json; print(json.dumps(sys.executable, ensure_ascii=True)) if sys.version_info >= (3,10) else sys.exit(2)' 2>$null
        if ($LASTEXITCODE -eq 0 -and $probe) {
            $resolved = ([string]($probe | Select-Object -Last 1)) | ConvertFrom-Json
            if (Test-Path -LiteralPath $resolved) { return [string]$resolved }
        }
    } catch { return $null }
    return $null
}

function Get-SzygPython {
    param([string]$CacheRoot, [switch]$ForcePortable)
    if (-not $ForcePortable) {
        $bundled = Join-Path $env:USERPROFILE '.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
        $found = Test-SzygPython $bundled
        if ($found) { return $found }
        $launcher = Get-Command py.exe -ErrorAction SilentlyContinue
        if ($launcher) {
            $found = Test-SzygPython $launcher.Source @('-3')
            if ($found) { return $found }
        }
        foreach ($name in @('python.exe', 'python3.exe')) {
            $command = Get-Command $name -ErrorAction SilentlyContinue
            if ($command -and $command.Source -notlike '*WindowsApps*') {
                $found = Test-SzygPython $command.Source
                if ($found) { return $found }
            }
        }
    }
    if (-not $CacheRoot) { $CacheRoot = Join-Path $env:LOCALAPPDATA 'SzygNewMedia\runtime' }
    Assert-SzygPlainPath $CacheRoot
    $architecture = $env:PROCESSOR_ARCHITEW6432
    if (-not $architecture) { $architecture = $env:PROCESSOR_ARCHITECTURE }
    $hashes = @{
        'AMD64' = @('amd64', '9e35319bffedab8b36ad44d8f377cb4f1733bcec257a0b6d04d94f01486ddb38')
        'ARM64' = @('arm64', '7b58787a047b400edbfcb539aa3cdb4e2ed77bf0f22cae42b7c01cedd7dd6614')
    }
    if (-not $hashes.ContainsKey($architecture)) { throw 'The automatic runtime supports Windows x64 and ARM64. Provide Python 3.10+ on this computer.' }
    $suffix, $expected = $hashes[$architecture]
    $name = 'python-3.13.17-embed-' + $suffix
    $destination = Join-Path $CacheRoot $name
    $python = Join-Path $destination 'python.exe'
    $found = Test-SzygPython $python
    if ($found) { return $found }
    if (Test-Path -LiteralPath $destination) { throw ('A runtime directory is incomplete. Preserve and inspect it before retrying: ' + $destination) }
    New-Item -ItemType Directory -Path $CacheRoot -Force | Out-Null
    $archive = Join-Path $CacheRoot ($name + '.zip')
    if (-not (Test-Path -LiteralPath $archive)) {
        Write-Host 'Preparing a private Python runtime from python.org (no system installation)...'
        Receive-SzygFile ('https://www.python.org/ftp/python/3.13.17/' + $name + '.zip') $archive
    }
    Assert-SzygHash $archive $expected
    Expand-SzygZip $archive $destination
    $found = Test-SzygPython $python
    if (-not $found) { throw 'The downloaded Python runtime could not start.' }
    return $found
}

$ErrorActionPreference = 'Stop'
if (-not (Get-Command Assert-SzygHash -ErrorAction SilentlyContinue)) {
    . (Join-Path $PSScriptRoot 'installer-runtime.ps1')
}

function Get-SzygReleaseBundle {
    param([string]$CacheRoot)
    $tag = 'v0.2.7-public.2026.10.31.1'
    $name = 'szyg-new-media-marketing-codex-2026.10.31.1.zip'
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
