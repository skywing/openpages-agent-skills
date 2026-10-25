@echo off
rem Windows twin of ./op : run a skill script with the project venv.
rem   op op.py ping        op verify_spec specs\pxkn.yaml        op tutorial next
rem UTF-8 mode: the scripts read and write UTF-8 text (arrows, accents) without naming the encoding;
rem Windows would otherwise use cp1252 and fail on those characters.
setlocal
cd /d "%~dp0"
set PYTHONUTF8=1
set "PY=.venv\Scripts\python.exe"
if "%~1"=="" goto usage
if not exist "%PY%" (
  echo Run: powershell -ExecutionPolicy Bypass -File setup_venv.ps1
  exit /b 1
)
set "SCRIPT=%~1"
if /i not "%SCRIPT:~-3%"==".py" set "SCRIPT=%SCRIPT%.py"
shift
set "ARGS="
:collect
if "%~1"=="" goto run
set ARGS=%ARGS% %1
shift
goto collect
:run
for %%D in (skills\openpages-solutions\scripts skills\openpages-tutorial\scripts) do (
  if exist "%%D\%SCRIPT%" (
    "%PY%" "%%D\%SCRIPT%"%ARGS%
    exit /b %ERRORLEVEL%
  )
)
echo no such script: %SCRIPT%
:usage
echo usage: op ^<script^>[.py] [args...]     e.g. op op.py ping    op tutorial next
for %%D in (skills\openpages-solutions\scripts skills\openpages-tutorial\scripts) do (
  if exist "%%D" (echo scripts in %%D: & dir /b "%%D\*.py")
)
exit /b 2
