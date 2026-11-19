@echo off
rem Double-click to start the dashboard (the Python analysis server and the page) and open it in your browser.
rem Settings come from dashboard.config.json. Close this window to stop.
cd /d "%~dp0"
call npm run dev -- --open
pause
