@echo off
setlocal

echo Starting setup and launch script...

:: Check for required tools
where python >nul 2>nul
if %errorlevel% neq 0 (
    echo Python is required but not installed. Please install it.
    pause
    exit /b 1
)

where npm >nul 2>nul
if %errorlevel% neq 0 (
    echo npm is required but not installed. Please install it.
    pause
    exit /b 1
)

where ffmpeg >nul 2>nul
if %errorlevel% neq 0 (
    echo ffmpeg is required but not installed. Please install it.
    echo A winget install will be attempted.
    winget install --id=Gyan.FFmpeg  -e --accept-package-agreements --accept-source-agreements
    if %errorlevel% neq 0 (
        echo Please install ffmpeg manually.
        pause
        exit /b 1
    )
)

echo Setting up backend...
cd backend
if not exist "venv" (
    python -m venv venv
)
call venv\Scripts\activate.bat
python -m pip install --upgrade pip
pip install -r requirements.txt
cd ..

echo Setting up frontend...
cd frontend
call npm install
cd ..

echo Starting services...
:: Start backend in a new window to keep it running
start "Backend" cmd /c "cd backend & call venv\Scripts\activate.bat & uvicorn main:app --host 0.0.0.0 --port 8000"

:: Start frontend in this window
cd frontend
call npm start

echo Services started.
pause
