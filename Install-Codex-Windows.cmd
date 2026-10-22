@echo off
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0install.ps1"
if errorlevel 1 (
  echo Installation needs attention. Read the message above.
  pause
  exit /b 1
)
echo Installed. Open the team folder shown in the receipt in Codex.
pause
