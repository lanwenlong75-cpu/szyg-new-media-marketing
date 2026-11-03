param([string]$Skill, [string]$SkillRoot, [string]$SkillsMap, [Parameter(Mandatory=$true)][string]$WorkspaceRoot, [string]$RuntimeCacheRoot)
$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = New-Object Text.UTF8Encoding($false)
. (Join-Path $PSScriptRoot 'installer-runtime.ps1')
$runtime = Get-SzygPython -CacheRoot $RuntimeCacheRoot
$arguments = @('-X','utf8','-B',(Join-Path $PSScriptRoot 'workbuddy_init.py'),'--workspace-root',$WorkspaceRoot)
if ($SkillsMap) { $arguments += @('--skills-map',$SkillsMap) } else { $arguments += @('--skill',$Skill,'--skill-root',$SkillRoot) }
& $runtime @arguments
if ($LASTEXITCODE -ne 0) { throw 'Initialization stopped; existing projects are preserved.' }
