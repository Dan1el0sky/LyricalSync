# LyricalSync
A letter-synced music program

## Overview
LyricalSync automatically downloads songs, fetches lyrics, and generates character/word precise alignments so you can follow along with the music in real-time. It uses a robust backend to pull lyrics and sync them perfectly with the audio using AI alignment.

## Architecture
- **Frontend**: React frontend (using Tailwind CSS v3)
- **Backend**: FastAPI with Python. For a detailed breakdown of how the backend operates, see the newly updated [Backend Documentation](BACKEND_DOCS.md).

## Getting Started
To get the backend dependencies set up:

```bash
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
sudo apt-get install -y ffmpeg
```

You can start the program by using the included startup scripts:
- `./start.sh` (Linux/Mac)
- `start.bat` (Windows)
