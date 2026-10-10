@echo off
REM Requires Python 3.10+ (with tkinter) installed and added to PATH.
pip install pyinstaller

set ICON=
if exist launcher\images\icon.ico set ICON=--icon launcher\images\icon.ico

pyinstaller --onefile --windowed --name GTA_SA_Launcher %ICON% launcher.py

echo.
echo Done. Your launcher is in the "dist" folder: dist\GTA_SA_Launcher.exe
echo Copy it to the root folder of the game.
pause
