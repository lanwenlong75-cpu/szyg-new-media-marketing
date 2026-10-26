param([Parameter(Mandatory=$true)][string]$SkillRoot,[string]$WorkspaceRoot,[string]$RuntimeRoot,[switch]$NoOpenFolder)
$ErrorActionPreference='Stop'
[Console]::OutputEncoding=New-Object Text.UTF8Encoding($false)
$env:PYTHONIOENCODING='utf-8'
$env:PYTHONUTF8='1'
. (Join-Path $PSScriptRoot 'offline-helpers.ps1')
function Receive-SzygFile {throw 'Offline setup never downloads files.'}
$metadata=[IO.File]::ReadAllText((Join-Path $PSScriptRoot 'offline-files.json')) | ConvertFrom-Json
foreach($row in $metadata.files){
 if([IO.Path]::IsPathRooted($row.path) -or $row.path.Contains(':') -or ($row.path -split '[\\/]') -contains '..'){throw 'Invalid offline manifest path'}
 $target=Join-Path $PSScriptRoot $row.path
 Assert-SzygPlainPath $target
 Assert-SzygHash $target $row.sha256
}
$arch=$env:PROCESSOR_ARCHITEW6432
if(-not $arch){$arch=$env:PROCESSOR_ARCHITECTURE}
$architectures=@{'AMD64'='amd64';'ARM64'='arm64'}
if(-not $architectures.ContainsKey($arch)){throw 'This offline runtime supports Windows x64 and ARM64.'}
$suffix=$architectures[$arch]
$name='python-3.13.17-embed-'+$suffix
$archive=Join-Path $PSScriptRoot ('runtime/'+$name+'.zip')
if(-not $RuntimeRoot){$RuntimeRoot=Join-Path $env:LOCALAPPDATA 'SzygNewMedia/offline'}
Assert-SzygPlainPath $RuntimeRoot
if(-not(Test-Path -LiteralPath $RuntimeRoot)){[IO.Directory]::CreateDirectory($RuntimeRoot) | Out-Null}
# A fresh directory ensures that prior local runtime files cannot be mixed in.
$destination=Join-Path $RuntimeRoot ($name+'-'+[Guid]::NewGuid().ToString('N').Substring(0,8))
Expand-SzygZip $archive $destination
$python=Join-Path $destination 'python.exe'
if(-not $WorkspaceRoot){$WorkspaceRoot=Join-Path $env:USERPROFILE ([string]$metadata.default_workspace)}
$arguments=@('-X','utf8','-B',(Join-Path $PSScriptRoot 'workbuddy_init.py'),'--skill-root',$SkillRoot,'--workspace-root',$WorkspaceRoot)
& $python @arguments
if($LASTEXITCODE -ne 0){throw 'Initialization stopped. Read the reason above; existing business folders are preserved.'}
if(-not $NoOpenFolder){Start-Process -FilePath 'explorer.exe' -ArgumentList @('"'+$WorkspaceRoot+'"')}
