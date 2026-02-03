@echo off
echo 🪟 Building Garmin Analyzer for Windows...

REM 1. Get the secret location of CustomTkinter
for /f "delims=" %%i in ('python -c "import customtkinter; import os; print(os.path.dirname(customtkinter.__file__))"') do set CTK_PATH=%%i

echo Found CustomTkinter at: %CTK_PATH%

REM 2. Build the app (Now with --icon and correct paths)
python -m PyInstaller --onedir --windowed --name GarminAnalyzer ^
    --icon="runner.ico" ^
    --add-data "%CTK_PATH%;customtkinter/" ^
    --hidden-import fitparse --hidden-import pandas --hidden-import numpy --hidden-import matplotlib ^
    --clean ^
    src/garmin_analyzer/gui.py

echo.
echo ✅ Build complete! 📦 Output: dist\GarminAnalyzer
echo 📦 Zipping into GarminAnalyzer.zip...
powershell Compress-Archive -Path "dist\GarminAnalyzer" -DestinationPath "dist\GarminAnalyzer.zip" -Force
echo ✅ Zip complete!
pause