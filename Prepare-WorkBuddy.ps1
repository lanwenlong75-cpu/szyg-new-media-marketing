param([string]$OutputRoot,[string]$RuntimeCacheRoot,[switch]$ForcePortablePython)
$ErrorActionPreference='Stop'
[Console]::OutputEncoding=New-Object Text.UTF8Encoding($false)
$env:PYTHONIOENCODING='utf-8'
$env:PYTHONUTF8='1'
. (Join-Path $PSScriptRoot 'installer-runtime.ps1')
if(-not $OutputRoot){$OutputRoot=Join-Path $env:LOCALAPPDATA ('SzygNewMedia/WorkBuddy/'+[Guid]::NewGuid().ToString('N').Substring(0,8))}
$python=Get-SzygPython -CacheRoot $RuntimeCacheRoot -ForcePortable:$ForcePortablePython
& $python '-X' 'utf8' '-B' (Join-Path $PSScriptRoot 'distribution/prepare_workbuddy.py') '--package-root' $PSScriptRoot '--output' $OutputRoot
if($LASTEXITCODE -ne 0){throw 'Preparation stopped; existing files are preserved.'}
