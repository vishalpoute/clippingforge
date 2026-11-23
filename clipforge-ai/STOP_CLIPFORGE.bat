@echo off
setlocal
"%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe" -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\stop.ps1" %*
set "rc=%errorlevel%"
if not "%rc%"=="0" if "%~1"=="" pause
exit /b %rc%
