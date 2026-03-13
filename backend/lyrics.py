import requests
import json
import urllib.parse
import re
import os
from bs4 import BeautifulSoup
from dotenv import load_dotenv

load_dotenv()

class LyricsFetcher:
    def __init__(self):
        self.mxm_token = os.getenv("MUSIXMATCH_TOKEN", "")
        self.genius_token = os.getenv("GENIUS_ACCESS_TOKEN", "")

        if not self.mxm_token:
            self.mxm_token = self._get_anonymous_mxm_token()

    def _get_anonymous_mxm_token(self):
        url = "https://apic-desktop.musixmatch.com/ws/1.1/token.get?app_id=web-desktop-app-v1.0"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Musixmatch/0.10.4",
            "Cookie": "x-mxm-token-guid=12345678-1234-1234-1234-123456789012"
        }
        try:
            response = requests.get(url, headers=headers)
            data = response.json()
            if data.get("message", {}).get("header", {}).get("status_code") == 200:
                return data["message"]["body"]["user_token"]
        except Exception:
            pass
        return "23120632420387b337c7ab0fa1e6fdbbf4bdfa57db9dfd0f28246e"

    def fetch_mxm_lyrics(self, title, artist):
        token = self.mxm_token
        query = f"{title} {artist}"
        encoded_query = urllib.parse.quote(query)

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Musixmatch/0.10.4"
        }

        search_url = f"https://apic-desktop.musixmatch.com/ws/1.1/track.search?app_id=web-desktop-app-v1.0&q={encoded_query}&page_size=1&page=1&usertoken={token}"

        try:
            res = requests.get(search_url, headers=headers).json()
            track_list = res.get("message", {}).get("body", {}).get("track_list", [])
            if not track_list:
                return None
            track_id = track_list[0]["track"]["track_id"]

            def safe_extract(res_json, key1, key2):
                body = res_json.get("message", {}).get("body", {})
                if not isinstance(body, dict): return None
                return body.get(key1, {}).get(key2)

            # 1. Try richsync
            richsync_url = f"https://apic-desktop.musixmatch.com/ws/1.1/track.richsync.get?app_id=web-desktop-app-v1.0&track_id={track_id}&usertoken={token}"
            richsync_res = requests.get(richsync_url, headers=headers).json()
            richsync_body = safe_extract(richsync_res, "richsync", "richsync_body")

            if richsync_body:
                try:
                    return {"source": "musixmatch", "synced": True, "type": "richsync", "data": json.loads(richsync_body)}
                except Exception:
                    return {"source": "musixmatch", "synced": True, "type": "richsync_text", "data": richsync_body}

            # 2. Try subtitle (LRC)
            lyrics_url = f"https://apic-desktop.musixmatch.com/ws/1.1/track.subtitle.get?app_id=web-desktop-app-v1.0&track_id={track_id}&usertoken={token}"
            lyrics_res = requests.get(lyrics_url, headers=headers).json()

            subtitle_body = safe_extract(lyrics_res, "subtitle", "subtitle_body")
            if subtitle_body:
                return {"source": "musixmatch", "synced": True, "type": "lrc", "data": subtitle_body}

            # 3. Try plain lyrics
            plain_url = f"https://apic-desktop.musixmatch.com/ws/1.1/track.lyrics.get?app_id=web-desktop-app-v1.0&track_id={track_id}&usertoken={token}"
            plain_res = requests.get(plain_url, headers=headers).json()
            lyrics_body = safe_extract(plain_res, "lyrics", "lyrics_body")
            if lyrics_body:
                text = lyrics_body.split("*******")[0].strip()
                return {"source": "musixmatch", "synced": False, "type": "text", "data": text}

        except Exception as e:
            print(f"Musixmatch error: {e}")

        return None

    def fetch_lrclib_lyrics(self, title, artist):
        query = f"{title} {artist}"
        url = f"https://lrclib.net/api/search?q={urllib.parse.quote(query)}"
        headers = {"User-Agent": "LyricalSync/1.0 (https://github.com/lyricalsync)"}

        try:
            res = requests.get(url, headers=headers)
            if res.status_code == 200:
                data = res.json()
                if data and isinstance(data, list) and len(data) > 0:
                    best_match = data[0]
                    # Prefer synced lyrics (LRC)
                    if best_match.get('syncedLyrics'):
                        return {"source": "lrclib", "synced": True, "type": "lrc", "data": best_match['syncedLyrics']}
                    elif best_match.get('plainLyrics'):
                        text = re.sub(r'\[.*?\]', '', best_match['plainLyrics'])
                        text = re.sub(r'\n{3,}', '\n\n', text)
                        return {"source": "lrclib", "synced": False, "type": "text", "data": text.strip()}
        except Exception as e:
            print(f"LRCLIB error: {e}")

        return None

    def get_lyrics(self, title, artist):
        res = self.fetch_lrclib_lyrics(title, artist)
        if res and res.get("data"):
            print("Successfully found lyrics from LRCLIB.")
            return res

        print("LRCLIB failed. Falling back to Musixmatch...")
        res = self.fetch_mxm_lyrics(title, artist)
        if res and res.get("data"):
            print("Successfully found lyrics from Musixmatch.")
            return res

        print("Musixmatch failed. Falling back to complete Whisper transcription...")
        return None
