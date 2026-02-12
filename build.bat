@echo off
REM Build Twist QC Automation .exe (run on Windows only)
REM Prerequisites: Python 3.13, pip install -r requirements.txt

echo === Building Twist QC Automation ===
echo.

REM Step 1: Pre-download PaddleOCR models (if not already cached)
echo Downloading PaddleOCR models (if needed)...
python -c "from providers.paddleocr_provider import _get_ocr; _get_ocr()"
if errorlevel 1 (
    echo ERROR: Failed to download PaddleOCR models.
    pause
    exit /b 1
)

REM Step 2: Install PyInstaller
pip install pyinstaller

REM Step 3: Build the .exe
pyinstaller twist_qc_gui.spec --clean

echo.
echo Build complete. Output: dist\TwistQC\
echo Zip the dist\TwistQC folder for distribution.
pause
