@echo off
echo ======================================
echo   Break Reminder - Build EXE
echo ======================================
echo.

python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found. Install Python 3.8+
    pause & exit /b 1
)

echo [1/3] Installing packages...
pip install pyqt5 pyinstaller --quiet
if errorlevel 1 (echo [ERROR] pip failed. & pause & exit /b 1)

echo [2/3] Cleaning old build...
if exist build   rd /s /q build
if exist dist    rd /s /q dist
if exist BreakReminder.spec del /q BreakReminder.spec

echo [3/3] Packing EXE...
pyinstaller --onefile --noconsole --name BreakReminder --hidden-import PyQt5.sip --hidden-import PyQt5.QtCore --hidden-import PyQt5.QtGui --hidden-import PyQt5.QtWidgets main.py

echo.
if exist "dist\BreakReminder.exe" (
    echo [SUCCESS] Done: dist\BreakReminder.exe
) else (
    echo [FAILED] Check errors above.
)
echo.
pause
