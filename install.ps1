param([string]$SkillsRoot,[string]$WorkspaceRoot)
$ErrorActionPreference='Stop'
$candidates=@((Join-Path $env:USERPROFILE '.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'))
$command=Get-Command py.exe -ErrorAction SilentlyContinue
if($command){$candidates+=$command.Source}
$command=Get-Command python.exe -ErrorAction SilentlyContinue
if($command -and $command.Source -notlike '*WindowsApps*'){$candidates+=$command.Source}
$runtime=$candidates | Where-Object {Test-Path -LiteralPath $_} | Select-Object -First 1
if(-not $runtime){throw 'Python 3.10+ was not found. Ask Codex to configure a local Python runtime, then run this installer again.'}
$installArgs=@('-X','utf8','-B',(Join-Path $PSScriptRoot 'install.py'),'--upgrade-existing','--archive-legacy')
if($SkillsRoot){$installArgs+=@('--skills-root',$SkillsRoot)}
if($WorkspaceRoot){$installArgs+=@('--workspace-root',$WorkspaceRoot)}
& $runtime @installArgs
if($LASTEXITCODE -ne 0){throw 'Installation stopped. Existing data is preserved; read the message above.'}
