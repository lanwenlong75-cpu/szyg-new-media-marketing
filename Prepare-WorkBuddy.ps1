param([string[]]$Skill, [string]$OutputRoot, [string]$RuntimeCacheRoot)
$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = New-Object Text.UTF8Encoding($false)
. (Join-Path $PSScriptRoot 'installer-runtime.ps1')
$runtime = Get-SzygPython -CacheRoot $RuntimeCacheRoot
if (-not $OutputRoot) { $OutputRoot = Join-Path (Split-Path $PSScriptRoot -Parent) ('WorkBuddy-skills-' + [Guid]::NewGuid().ToString('N').Substring(0,8)) }
$arguments = @('-X','utf8','-B',(Join-Path $PSScriptRoot 'distribution/prepare_workbuddy.py'),'--output',$OutputRoot)
foreach ($name in $Skill) { $arguments += @('--skill',$name) }
& $runtime @arguments
if ($LASTEXITCODE -ne 0) { throw 'Preparation stopped; read the error.' }
