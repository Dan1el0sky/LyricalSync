import os
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from ytmusicapi import YTMusic
import yt_dlp
from pydantic import BaseModel
import asyncio
from fastapi.staticfiles import StaticFiles
from lyrics import LyricsFetcher
from processor import AudioProcessor

app = FastAPI()

# Store progress states for each video_id
progress_store = {}

# Serve current directory so frontend can play audio downloads
app.mount("/downloads", StaticFiles(directory="."), name="downloads")

lf = LyricsFetcher()
ap = AudioProcessor()

# Configure CORS for frontend access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

ytmusic = YTMusic()

class SearchRequest(BaseModel):
    query: str

class DownloadRequest(BaseModel):
    video_id: str
    title: str
    artist: str

class SettingsRequest(BaseModel):
    musixmatch_token: str
    genius_token: str

@app.post("/api/search")
def search_songs(request: SearchRequest):
    try:
        results = ytmusic.search(request.query, filter="songs")
        songs = []
        for res in results:
            if res.get('resultType') == 'song':
                songs.append({
                    "videoId": res.get("videoId"),
                    "title": res.get("title"),
                    "artists": [a["name"] for a in res.get("artists", [])],
                    "album": res.get("album", {}).get("name") if res.get("album") else None,
                    "duration": res.get("duration"),
                    "thumbnail": res.get("thumbnails", [{}])[-1].get("url") if res.get("thumbnails") else None
                })
        return {"songs": songs}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/settings")
def get_settings():
    import os
    from dotenv import load_dotenv
    load_dotenv()
    return {
        "musixmatch_token": os.getenv("MUSIXMATCH_TOKEN", ""),
        "genius_token": os.getenv("GENIUS_ACCESS_TOKEN", "")
    }

@app.post("/api/settings")
def update_settings(request: SettingsRequest):
    from dotenv import set_key
    env_file = ".env"
    import os
    if not os.path.exists(env_file):
        open(env_file, 'a').close()

    set_key(env_file, "MUSIXMATCH_TOKEN", request.musixmatch_token)
    set_key(env_file, "GENIUS_ACCESS_TOKEN", request.genius_token)

    # Reload into lyrics fetcher
    import os
    os.environ["MUSIXMATCH_TOKEN"] = request.musixmatch_token
    os.environ["GENIUS_ACCESS_TOKEN"] = request.genius_token
    lf.mxm_token = request.musixmatch_token if request.musixmatch_token else lf._get_anonymous_mxm_token()
    lf.genius_token = request.genius_token
    return {"status": "success"}

@app.delete("/api/downloads")
def clear_downloads():
    import os
    import glob
    count = 0
    for file in glob.glob("*.mp3"):
        try:
            os.remove(file)
            count += 1
        except:
            pass
    return {"status": "success", "deleted": count}

@app.get("/api/progress/{video_id}")
def get_progress(video_id: str):
    if video_id in progress_store:
        return progress_store[video_id]
    return {"status": "Starting...", "percent": 0}

@app.post("/api/process")
async def process_song(request: DownloadRequest):
    video_id = request.video_id
    title = request.title
    artist = request.artist
    url = f"https://music.youtube.com/watch?v={video_id}"
    output_dir = "."

    progress_store[video_id] = {"status": "Initializing...", "percent": 0}

    output_path = os.path.join(output_dir, f"{video_id}.mp3")

    # Download if needed
    if not os.path.exists(output_path):
        progress_store[video_id] = {"status": "Downloading audio...", "percent": 10}
        ydl_opts = {
            'format': 'bestaudio/best',
            'outtmpl': os.path.join(output_dir, f'{video_id}.%(ext)s'),
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }],
            'quiet': True,
            'no_warnings': True,
        }
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])
        except Exception as e:
            progress_store[video_id] = {"status": "Download failed", "percent": 0}
            raise HTTPException(status_code=500, detail=f"Download failed: {str(e)}")

    progress_store[video_id] = {"status": "Fetching lyrics...", "percent": 30}

    # 1. Fetch Lyrics (to potentially display source lyrics)
    lyrics = lf.get_lyrics(title, artist)

    # 2. Align via torchaudio MMS FA to get exact character timings
    # This aligns the official Musixmatch text to the audio without hallucinating wrong words.
    lyrics_text = ""
    richsync_data = None

    if lyrics:
        if lyrics.get("type") in ["text", "richsync_text"]:
            lyrics_text = lyrics["data"]
        elif lyrics.get("type") == "lrc":
            import re
            # Parse LRC [00:00.00] tags into richsync-like format for accurate chunking
            lyrics_text = re.sub(r'\[\d{2}:\d{2}\.\d{2,3}\]', '', lyrics["data"])

            richsync_data = []
            for line in lyrics["data"].splitlines():
                match = re.search(r'\[(\d{2}):(\d{2}\.\d{2,3})\]', line)
                if match:
                    minutes = int(match.group(1))
                    seconds = float(match.group(2))
                    ts = minutes * 60 + seconds

                    text = re.sub(r'\[\d{2}:\d{2}\.\d{2,3}\]', '', line).strip()
                    if text:
                        richsync_data.append({
                            "ts": ts,
                            "te": 0.0, # Will be guessed in processor.py based on next phrase
                            "text": text
                        })
        elif lyrics.get("type") == "richsync":
            richsync_data = lyrics["data"]
            # Convert richsync to plain text for alignment fallback
            lyrics_text = "\n".join([line.get("text", "") for line in richsync_data if "text" in line])

    progress_store[video_id] = {"status": "Processing audio and aligning lyrics...", "percent": 50}

    try:
        # Run synchronous audio processing in thread to not block fastapi
        result = await asyncio.to_thread(ap.process, output_path, lyrics_text, richsync_data, video_id, progress_store)
    except Exception as e:
        progress_store[video_id] = {"status": "Processing failed", "percent": 0}
        raise HTTPException(status_code=500, detail=f"Audio processing failed: {str(e)}")

    progress_store[video_id] = {"status": "Complete", "percent": 100}

    return {
        "status": "success",
        "video_id": video_id,
        "lyrics_source": lyrics,
        "alignment": result
    }
