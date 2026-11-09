@echo off
setlocal
cd /d "%~dp0"
echo Building DanielEtterna with Reform Dan images...

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
py -m PyInstaller --clean --noconfirm --onefile --windowed --name DanielEtterna ^
  --icon "src\icon.ico" ^
  --add-data "src\icon.ico;." ^
  --add-data "src\nomenclatures\images;nomenclatures\images" ^
  src\daniel_etterna.py

if errorlevel 1 (
    echo ERROR: Executable build failed.
    exit /b 1
)
echo.
echo Build complete: dist\DanielEtterna.exe
pause
