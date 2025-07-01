@echo off
REM Historical Options Chain Viewer - Windows Setup Script

echo Setting up Historical Options Chain Viewer...
echo ============================================

REM Check Python version
python --version
if errorlevel 1 (
    echo ERROR: Python not found. Please install Python 3.8 or higher.
    pause
    exit /b 1
)

REM Create virtual environment if it doesn't exist
if not exist "venv" (
    echo Creating virtual environment...
    python -m venv venv
    echo Virtual environment created
) else (
    echo Virtual environment already exists
)

REM Activate virtual environment
echo Activating virtual environment...
call venv\Scripts\activate.bat

REM Upgrade pip
echo Upgrading pip...
python -m pip install --upgrade pip

REM Install requirements
echo Installing requirements...
pip install -r requirements.txt

REM Create necessary directories
echo Creating directories...
if not exist "data" mkdir data
if not exist "logs" mkdir logs

REM Copy .env.sample to .env if it doesn't exist
if not exist ".env" (
    echo Creating .env file from template...
    copy .env.sample .env
    echo Please edit .env file with your Polygon.io credentials
) else (
    echo .env file already exists
)

echo.
echo Setup complete!
echo.
echo Next steps:
echo 1. Edit .env file with your Polygon.io credentials:
echo    - POLYGON_API_KEY (required)
echo    - POLYGON_S3_ACCESS_KEY (optional but recommended)
echo    - POLYGON_S3_SECRET_KEY (optional but recommended)
echo.
echo 2. Test your setup:
echo    python tests\test_api.py
echo.
echo 3. Run the application:
echo    streamlit run app.py
echo.
echo For more information, see README.md
pause