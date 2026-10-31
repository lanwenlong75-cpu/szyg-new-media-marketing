@echo off
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0Prepare-WorkBuddy.ps1"
if errorlevel 1 pause
