@echo off
setlocal
cd /d "%~dp0"
echo Building DanielEtterna with Reform Dan assets...

if not exist "src\nomenclatures\images\beta-low.webp" (
    echo ERROR: Reform Dan artwork is missing from src\nomenclatures\images
    exit /b 1
)

py -m PyInstaller --clean --noconfirm --onefile --windowed --name DanielEtterna ^
  --icon "src\icon.ico" ^
  --add-data "src\icon.ico;." ^
  --add-data "src\nomenclatures\images;nomenclatures\images" ^
  src\daniel_etterna.py

if errorlevel 1 (
    echo Build failed. Install dependencies with:
    echo py -m pip install -r requirements.txt
    exit /b 1
)
echo.
echo Build complete: dist\DanielEtterna.exe
pause
