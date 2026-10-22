param([string]$Root='', [int]$Port=8790, [switch]$NoOpen)
$ErrorActionPreference='Stop'
if(-not $Root){$Root=Join-Path ([Environment]::GetFolderPath('MyDocuments')) '新媒体运营工作区'}
$skillPath=Split-Path $PSScriptRoot -Parent
$runtimePython=Join-Path $env:USERPROFILE '.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
$pythonPath=$null
$candidates=@($runtimePython)
$candidateCommand=Get-Command python -ErrorAction SilentlyContinue
if($candidateCommand -and $candidateCommand.Source -notmatch 'WindowsApps'){$candidates+= $candidateCommand.Source}
$candidateCommand=Get-Command python3 -ErrorAction SilentlyContinue
if($candidateCommand -and $candidateCommand.Source -notmatch 'WindowsApps'){$candidates+= $candidateCommand.Source}
foreach($candidatePath in $candidates){
    if(Test-Path -LiteralPath $candidatePath){
        & $candidatePath -c 'import sys;sys.exit(0 if sys.version_info >= (3,10) else 1)' 2>$null
        if($LASTEXITCODE -eq 0){$pythonPath=$candidatePath;break}
    }
}
if(-not $pythonPath){throw 'Python 3.10+ not found. Install Python, or ask the AI assistant to initialize this Skill with its Python runtime.'}
$opsPath=Join-Path $skillPath 'scripts\ops.py'
& $pythonPath -X utf8 $opsPath init --root $Root --port $Port
if($LASTEXITCODE -ne 0){throw 'Workspace initialization failed.'}
$launchArgs=@('-X','utf8',$opsPath,'start','--root',$Root,'--port',"$Port")
if(-not $NoOpen){$launchArgs+= '--open'}
& $pythonPath @launchArgs
if($LASTEXITCODE -ne 0){throw 'Workbench did not start; existing services and files were preserved.'}
