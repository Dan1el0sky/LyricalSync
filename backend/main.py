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

@app.post("/api/process")
async def process_song(request: DownloadRequest):
    video_id = request.video_id
    title = request.title
    artist = request.artist
    url = f"https://music.youtube.com/watch?v={video_id}"
    output_dir = "."

    output_path = os.path.join(output_dir, f"{video_id}.mp3")

    # Download if needed
    if not os.path.exists(output_path):
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
            raise HTTPException(status_code=500, detail=f"Download failed: {str(e)}")

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
            # Strip [00:00.00] tags from LRC so the aligner doesn't try to align the digits
            lyrics_text = re.sub(r'\[\d{2}:\d{2}\.\d{2,3}\]', '', lyrics["data"])
        elif lyrics.get("type") == "richsync":
            richsync_data = lyrics["data"]
            # Convert richsync to plain text for alignment fallback
            lyrics_text = "\n".join([line.get("text", "") for line in richsync_data if "text" in line])

    try:
        # Run synchronous audio processing in thread to not block fastapi
        result = await asyncio.to_thread(ap.process, output_path, lyrics_text, richsync_data)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Audio processing failed: {str(e)}")

    return {
        "status": "success",
        "video_id": video_id,
        "lyrics_source": lyrics,
        "alignment": result
    }
