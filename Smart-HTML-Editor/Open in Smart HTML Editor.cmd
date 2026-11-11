@echo off
rem Smart HTML Editor: drag an .html file onto this file (or run it with the file as the argument).
setlocal
if "%~1"=="" (
  echo Drag an .html file onto "Open in Smart HTML Editor.cmd", or run it with the file path.
  pause
  exit /b 1
)
set "PY=python"
where py >nul 2>nul
if not errorlevel 1 set "PY=py -3"
%PY% "%~dp0editor\she.py" open "%~1"
if errorlevel 1 pause
