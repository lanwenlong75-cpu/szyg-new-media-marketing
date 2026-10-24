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
