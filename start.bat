@echo off
REM Jampy Engage Application Launcher
REM This script activates the virtual environment and starts the web application

echo Starting Jampy Engage...

REM Change to the script directory (in case it's run from elsewhere)
cd /d "%~dp0"

REM Activate the virtual environment
call .venv\Scripts\activate.bat

REM Check if activation was successful
if errorlevel 1 (
    echo Error: Could not activate virtual environment
    echo Make sure the .venv folder exists and contains the virtual environment
    pause
    exit /b 1
)

REM Start the Flask application
echo Virtual environment activated. Starting application...
python -m src.ui

REM Keep the window open if there's an error
if errorlevel 1 (
    echo.
    echo Application exited with error code %errorlevel%
    pause
)