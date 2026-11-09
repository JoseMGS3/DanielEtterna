@echo off
setlocal EnableExtensions
cd /d "%~dp0"
set "ROOT_DIR=%CD%"

rem Build only the native XDC1 engine; the legacy app remains unchanged.
where cl >nul 2>nul
if errorlevel 1 (
    set "VCVARS="
    for %%E in (BuildTools Community Professional Enterprise) do (
        if not defined VCVARS if exist "%ProgramFiles%\Microsoft Visual Studio\2022\%%E\VC\Auxiliary\Build\vcvars64.bat" (
            set "VCVARS=%ProgramFiles%\Microsoft Visual Studio\2022\%%E\VC\Auxiliary\Build\vcvars64.bat"
        )
        if not defined VCVARS if exist "%ProgramFiles(x86)%\Microsoft Visual Studio\2022\%%E\VC\Auxiliary\Build\vcvars64.bat" (
            set "VCVARS=%ProgramFiles(x86)%\Microsoft Visual Studio\2022\%%E\VC\Auxiliary\Build\vcvars64.bat"
        )
    )
    if not defined VCVARS (
        echo ERROR: MSVC C++ 2022 Build Tools not found.
        echo Install Visual Studio 2022 Build Tools with Desktop development with C++.
        exit /b 1
    )
    call "%VCVARS%" >nul
    if errorlevel 1 exit /b 1
)

if not exist "build\xdc1" mkdir "build\xdc1"
cl /nologo /O2 /std:c++17 /EHsc /W4 /Fo"build\xdc1\\" /Fe"src\xdc1.exe" "xdc1\xdc1.cpp"
if errorlevel 1 (
    echo ERROR: XDC1 compilation failed.
    exit /b 1
)
echo Built src\xdc1.exe successfully.
exit /b 0
