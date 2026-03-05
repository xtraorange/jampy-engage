# Jampy Engage Application Launcher
# This script activates the virtual environment and starts the web application

Write-Host "Starting Jampy Engage..." -ForegroundColor Green

# Change to the script directory (in case it's run from elsewhere)
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $scriptDir

# Activate the virtual environment
$venvPath = Join-Path $scriptDir ".venv\Scripts\Activate.ps1"
if (Test-Path $venvPath) {
    & $venvPath
    if ($LASTEXITCODE -ne 0) {
        Write-Host "Error: Could not activate virtual environment" -ForegroundColor Red
        Read-Host "Press Enter to exit"
        exit 1
    }
} else {
    Write-Host "Error: Virtual environment not found at $venvPath" -ForegroundColor Red
    Write-Host "Make sure the .venv folder exists and contains the virtual environment" -ForegroundColor Yellow
    Read-Host "Press Enter to exit"
    exit 1
}

# Start the Flask application
Write-Host "Virtual environment activated. Starting application..." -ForegroundColor Green
python -m src.ui

# Keep the window open if there's an error
if ($LASTEXITCODE -ne 0) {
    Write-Host ""
    Write-Host "Application exited with error code $LASTEXITCODE" -ForegroundColor Red
    Read-Host "Press Enter to exit"
}