@echo off
REM Genere dist\TaskPilot.exe (autonome, sans installation cote utilisateur).
cd /d "%~dp0"

echo [1/3] Verification de PyInstaller...
python -c "import PyInstaller" 2>nul || python -m pip install "pyinstaller==5.13.2"

echo [2/3] Dependances runtime (pywinpty, pyte) embarquees dans l'exe...
python -m pip install -r requirements.txt

echo [3/3] Build...
python -m PyInstaller --noconfirm taskpilot.spec

echo.
echo Termine. Executable : dist\TaskPilot.exe
pause
