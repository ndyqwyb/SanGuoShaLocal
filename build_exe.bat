@echo off
setlocal

cd /d "%~dp0"

echo [1/3] Installing/Upgrading PyInstaller...
py -m pip install --upgrade pyinstaller
if errorlevel 1 goto :error

echo [2/3] Cleaning old build outputs...
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist
if exist main.spec del /q main.spec

echo [3/3] Building Windows EXE from main.py...
py -m PyInstaller --noconfirm --onefile --windowed --name sanguosha main.py
if errorlevel 1 goto :error

echo.
echo Build succeeded.
echo EXE path: %cd%\dist\sanguosha.exe
echo.
pause
exit /b 0

:error
echo.
echo Build failed. Please check messages above.
echo.
pause
exit /b 1
