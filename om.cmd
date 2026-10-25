@echo off
rem Windows twin of ./om : run ObjectManager (desktop client) against an environment.
rem   om validate build\PXKN\types pxknexception --env shared-dev
rem   om dump relationships --env shared-dev --dry-run
rem Needs the client folder (openpages-tools-client\ with bin\ObjectManager.cmd or .bat, and lib\) and Java 21.
setlocal
cd /d "%~dp0"
set PYTHONUTF8=1
if not exist ".venv\Scripts\python.exe" (
  echo Run: powershell -ExecutionPolicy Bypass -File setup_venv.ps1
  exit /b 1
)
".venv\Scripts\python.exe" skills\openpages-solutions\scripts\om.py %*
exit /b %ERRORLEVEL%
