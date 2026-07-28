@echo off
REM Genere dist\TaskPilotMcp.exe : le serveur MCP des logs seul, autonome.
REM L'app Qt se construit avec build.bat — les deux exes sont independants.
cd /d "%~dp0"

echo [1/4] Verification de PyInstaller...
python -c "import PyInstaller" 2>nul || python -m pip install "pyinstaller>=6.11"

echo [2/4] SDK MCP (non embarque dans l'exe Qt)...
python -m pip install -r requirements-mcp.txt

echo [3/4] Build...
python -m PyInstaller --noconfirm taskpilot-mcp.spec

echo [4/4] Verification du dialogue stdio...
python tools\smoke_mcp.py dist\TaskPilotMcp.exe || goto :error

echo.
echo Termine. Executable : dist\TaskPilotMcp.exe
pause
exit /b 0

:error
echo.
echo ECHEC : l'executable ne repond pas au protocole MCP.
pause
exit /b 1
