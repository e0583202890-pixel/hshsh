@echo off
REM ============================================================
REM  KICKLIPS Studio - double-click launcher
REM  Just run this file. First run installs everything (a few
REM  minutes); later runs start in seconds and open your browser.
REM ============================================================
cd /d "%~dp0"
powershell -ExecutionPolicy Bypass -NoProfile -File "%~dp0start.ps1"
echo.
echo The app has stopped. You can close this window.
pause
