@echo off
echo ======================================
echo   Break Reminder - Build EXE
echo ======================================
echo.

python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found. Please install Python 3.8+
    pause
    exit /b 1
)

echo [1/3] Installing dependencies...
pip install pyqt5 pyinstaller --quiet
if errorlevel 1 (
    echo [ERROR] pip install failed.
    pause
    exit /b 1
)

echo [2/3] Cleaning old build files...
if exist build   rd /s /q build
if exist dist    rd /s /q dist
if exist *.spec  del /q *.spec

echo [3/3] Building EXE (may take 1-2 minutes)...
pyinstaller --onefile --noconsole --name "BreakReminder" main.py

echo.
if exist "dist\BreakReminder.exe" (
    echo [SUCCESS] EXE created: dist\BreakReminder.exe
) else (
    echo [FAILED] Build failed. Check errors above.
)
echo.
pause
