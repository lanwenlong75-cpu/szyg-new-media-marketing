param([string]$SkillsRoot, [string]$WorkspaceRoot, [string]$RecipientHome,
      [string]$RuntimeCacheRoot, [switch]$NoOpenFolder)
$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = New-Object Text.UTF8Encoding($false)
$env:PYTHONIOENCODING = 'utf-8'
$env:PYTHONUTF8 = '1'
. (Join-Path $PSScriptRoot 'installer-runtime.ps1')
$runtime = Get-SzygPython -CacheRoot $RuntimeCacheRoot
$installArgs = @('-X', 'utf8', '-B', (Join-Path $PSScriptRoot 'install.py'), '--upgrade-existing', '--archive-legacy')
if ($SkillsRoot) { $installArgs += @('--skills-root', $SkillsRoot) }
if ($WorkspaceRoot) { $installArgs += @('--workspace-root', $WorkspaceRoot) }
if ($RecipientHome) { $installArgs += @('--home', $RecipientHome) }
$output = & $runtime @installArgs
if ($LASTEXITCODE -ne 0) { throw 'Installation stopped. Existing data is preserved; read the message above.' }
$receipt = ($output -join "`n") | ConvertFrom-Json
Write-Output ($output -join "`n")
Write-Host ('Team ready: ' + $receipt.team)
Write-Host 'Read START-HERE.md in that folder, then add the team or employee folder as a local project in Codex.'
if (-not $NoOpenFolder) { Start-Process -FilePath 'explorer.exe' -ArgumentList @('"' + $receipt.team + '"') }
