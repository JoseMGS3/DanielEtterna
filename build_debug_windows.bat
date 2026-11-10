@echo off
setlocal
set "DANIEL_DEBUG_CONSOLE=1"
call "%~dp0build_windows.bat"
exit /b %errorlevel%
