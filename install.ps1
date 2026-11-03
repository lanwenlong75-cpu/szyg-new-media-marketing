param([string[]]$Skill, [string]$SkillsRoot, [string]$WorkspaceRoot, [string]$RecipientHome, [string]$RuntimeCacheRoot, [switch]$NoOpenFolder)
$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = New-Object Text.UTF8Encoding($false)
. (Join-Path $PSScriptRoot 'installer-runtime.ps1')
$runtime = Get-SzygPython -CacheRoot $RuntimeCacheRoot
$arguments = @('-X','utf8','-B',(Join-Path $PSScriptRoot 'install.py'))
foreach ($name in $Skill) { $arguments += @('--skill',$name) }
if ($SkillsRoot) { $arguments += @('--skills-root',$SkillsRoot) }
if ($WorkspaceRoot) { $arguments += @('--workspace-root',$WorkspaceRoot) }
if ($RecipientHome) { $arguments += @('--home',$RecipientHome) }
& $runtime @arguments
if ($LASTEXITCODE -ne 0) { throw 'Installation stopped. Existing data is preserved; read the error.' }
