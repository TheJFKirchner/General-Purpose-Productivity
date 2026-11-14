@echo off
rem Double-click to start Launchpad in its own window.
rem Keep this console open while you use the app; closing it stops Launchpad.
rem To use your normal browser instead of a window, change the last line to: python -m app.launch --browser
rem Options go after the file name (or on that line): --cwd <project folder> to plan in another project,
rem --fake for the zero-token demo. Session files go to <project>\.launchpad\ (git-ignored).
title Launchpad
cd /d "%~dp0"
python -m app.launch %*
if errorlevel 1 (
  echo.
  echo Launchpad stopped with an error. See the message above.
  pause
)
