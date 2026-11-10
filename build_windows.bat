@echo off
setlocal
cd /d "%~dp0"
set "APP_BINARY_NAME=DanielEtterna"
set "APP_WINDOW_MODE=--windowed"
if /I "%DANIEL_DEBUG_CONSOLE%"=="1" (
    set "APP_BINARY_NAME=DanielEtterna-Debug"
    set "APP_WINDOW_MODE=--console"
)
echo Building %APP_BINARY_NAME% with Reform Dans and XDC1...

echo Building XDC1 C++ engine...
call "%~dp0build_xdc1.bat"
if errorlevel 1 (
    echo ERROR: XDC1 compilation failed. The 2.0 switch needs an engine executable.
    exit /b 1
)


if not exist "src\nomenclatures\images\beta-low.webp" (
    echo ERROR: Reform Dan files are missing.
    exit /b 1
)

echo Installing the Windows-compatible SVG renderer...
py -m pip install -r requirements.txt
if errorlevel 1 (
    echo ERROR: Dependency installation failed.
    exit /b 1
)

echo Converting all 50 numbered SVG Dan badges to PNG...
py scripts\prepare_reform_png.py
if errorlevel 1 (
    echo ERROR: Failed to create PNG Dan badges. Build stopped.
    exit /b 1
)

echo Packaging the app, SVGs, PNGs and WebP images...
py -m PyInstaller --clean --noconfirm --onefile %APP_WINDOW_MODE% --name %APP_BINARY_NAME% ^
  --icon "src\icon.ico" ^
  --add-data "src\icon.ico;." ^
  --add-data "src\xdc1.exe;." ^
  --add-data "src\nomenclatures\images;nomenclatures\images" ^
  src\daniel_etterna.py

if errorlevel 1 (
    echo ERROR: Executable build failed.
    exit /b 1
)
echo.
echo Build complete: dist\%APP_BINARY_NAME%.exe
pause
