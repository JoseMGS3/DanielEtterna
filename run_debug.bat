@echo off
setlocal
cd /d "%~dp0"
set "DANIEL_DEBUG=1"
py src\daniel_etterna.py --debug
if errorlevel 1 (
    echo.
    echo Debug run failed. Check Python and dependencies.
)
pause
