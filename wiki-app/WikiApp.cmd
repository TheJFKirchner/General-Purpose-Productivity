@echo off
rem Starts WikiApp on Windows. The first time, setup.py creates the app's Python environment
rem (App Files\.venv) and installs the packages (a minute or two) in this window.
rem After that this window only flashes: it hands straight over to the app, which checks the
rem setup itself without a window and reopens this launcher with WIKIAPP_SETUP=1 when packages
rem need installing.
setlocal
set "APP=%~dp0App Files"
set "VENV=%APP%\.venv\Scripts"

if exist "%VENV%\python.exe" (
    if defined WIKIAPP_SETUP goto check
    goto start
)

rem First start: find Python. "py" comes with Python from python.org; "python" also finds the
rem Microsoft Store one.
set "PY="
py -3 -c "" >nul 2>nul && set "PY=py -3"
if not defined PY (python -c "" >nul 2>nul && set "PY=python")
if not defined PY goto nopython
%PY% "%APP%\setup.py" || goto failed
goto start

:check
"%VENV%\python.exe" "%APP%\setup.py" || goto failed

:start
start "" "%VENV%\pythonw.exe" "%APP%\host\wikiapp.py" %*
exit /b 0

:nopython
echo WikiApp needs Python 3.11 or newer. Install it from https://www.python.org/downloads/
echo (tick "Add python.exe to PATH"), then start WikiApp again.
pause
exit /b 1

:failed
pause
exit /b 1
