import requests
import json
import urllib.parse
import re

class LyricsFetcher:
    def __init__(self):
        self.mxm_token = "23120632420387b337c7ab0fa1e6fdbbf4bdfa57db9dfd0f28246e"

    def _get_mxm_token(self):
        url = "https://apic-desktop.musixmatch.com/ws/1.1/token.get?app_id=web-desktop-app-v1.0"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Musixmatch/0.10.4",
            "Cookie": "x-mxm-token-guid=12345678-1234-1234-1234-123456789012"
        }
        try:
            response = requests.get(url, headers=headers)
            data = response.json()
            if data["message"]["header"]["status_code"] == 200:
                self.mxm_token = data["message"]["body"]["user_token"]
                return self.mxm_token
        except Exception as e:
            pass
        return self.mxm_token

    def fetch_mxm_lyrics(self, title, artist):
        token = self._get_mxm_token()

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

            # 1. Try richsync
            richsync_url = f"https://apic-desktop.musixmatch.com/ws/1.1/track.richsync.get?app_id=web-desktop-app-v1.0&track_id={track_id}&usertoken={token}"
            richsync_res = requests.get(richsync_url, headers=headers).json()
            richsync_body = richsync_res.get("message", {}).get("body", {}).get("richsync", {}).get("richsync_body")

            if richsync_body:
                try:
                    return {"source": "musixmatch", "synced": True, "type": "richsync", "data": json.loads(richsync_body)}
                except:
                    return {"source": "musixmatch", "synced": True, "type": "richsync_text", "data": richsync_body}

            # 2. Try subtitle
            lyrics_url = f"https://apic-desktop.musixmatch.com/ws/1.1/track.subtitle.get?app_id=web-desktop-app-v1.0&track_id={track_id}&usertoken={token}"
            lyrics_res = requests.get(lyrics_url, headers=headers).json()

            subtitle_body = lyrics_res.get("message", {}).get("body", {}).get("subtitle", {}).get("subtitle_body")
            if subtitle_body:
                return {"source": "musixmatch", "synced": True, "type": "lrc", "data": subtitle_body}

            # 3. Try plain lyrics
            plain_url = f"https://apic-desktop.musixmatch.com/ws/1.1/track.lyrics.get?app_id=web-desktop-app-v1.0&track_id={track_id}&usertoken={token}"
            plain_res = requests.get(plain_url, headers=headers).json()
            lyrics_body = plain_res.get("message", {}).get("body", {}).get("lyrics", {}).get("lyrics_body")
            if lyrics_body:
                return {"source": "musixmatch", "synced": False, "type": "text", "data": lyrics_body.split("*******")[0].strip()}

        except Exception as e:
            pass

        return None

    def fetch_lrclib(self, title, artist):
        # Alternative to Genius since Genius is blocking API/scraping from this IP easily
        # LRCLIB provides synced lyrics reliably
        url = f"https://lrclib.net/api/get?artist_name={urllib.parse.quote(artist)}&track_name={urllib.parse.quote(title)}"
        try:
            res = requests.get(url)
            if res.status_code == 200:
                data = res.json()
                if data.get("syncedLyrics"):
                    return {"source": "lrclib", "synced": True, "type": "lrc", "data": data["syncedLyrics"]}
                elif data.get("plainLyrics"):
                    return {"source": "lrclib", "synced": False, "type": "text", "data": data["plainLyrics"]}
        except Exception:
            pass
        return None

    def get_lyrics(self, title, artist):
        res = self.fetch_mxm_lyrics(title, artist)
        if res:
            return res
        res = self.fetch_lrclib(title, artist)
        return res
