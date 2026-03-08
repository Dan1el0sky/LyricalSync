#!/bin/bash

# Ensure we exit on error
set -e

echo "Starting setup and launch script..."

# Check dependencies
if ! command -v python3 &> /dev/null; then
    echo "Python3 is required but not installed. Please install it."
    exit 1
fi

if ! command -v npm &> /dev/null; then
    echo "npm is required but not installed. Please install it."
    exit 1
fi

if ! command -v ffmpeg &> /dev/null; then
    echo "ffmpeg is required but not installed. Attempting to install..."
    if command -v apt-get &> /dev/null; then
        sudo apt-get update -y
        sudo apt-get install ffmpeg -y
    elif command -v brew &> /dev/null; then
        brew install ffmpeg
    else
        echo "Please install ffmpeg manually."
        exit 1
    fi
fi

# Setup backend
echo "Setting up backend..."
cd backend
if [ ! -d "venv" ]; then
    python3 -m venv venv
fi
source venv/bin/activate
pip install --upgrade pip -y || pip install --upgrade pip
pip install -r requirements.txt -y || pip install -r requirements.txt
cd ..

# Setup frontend
echo "Setting up frontend..."
cd frontend
npm install -y || npm install
cd ..

# Start services
echo "Starting services..."
cd backend
source venv/bin/activate
# Run backend in background
uvicorn main:app --host 0.0.0.0 --port 8000 &
BACKEND_PID=$!
cd ..

cd frontend
# Run frontend
npm start &
FRONTEND_PID=$!
cd ..

echo "Services started. Backend PID: $BACKEND_PID, Frontend PID: $FRONTEND_PID"
echo "Press Ctrl+C to stop both services."

# Wait for user interrupt
trap "kill $BACKEND_PID $FRONTEND_PID; exit" INT TERM
wait
