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
        # Allow user to set their own Musixmatch token via env var
        self.mxm_token = os.getenv("MUSIXMATCH_TOKEN", "")
        # Allow user to set their own Genius access token
        self.genius_token = os.getenv("GENIUS_ACCESS_TOKEN", "")

        # If no custom mxm token, we'll try to get one using the desktop API
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
            if data["message"]["header"]["status_code"] == 200:
                return data["message"]["body"]["user_token"]
        except Exception as e:
            pass
        # Fallback to a hardcoded desktop token if request fails/captcha'd
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
            print(f"Musixmatch error: {e}")

        return None

    def fetch_genius_lyrics(self, title, artist):
        query = f"{title} {artist}"

        # If user provided a Genius API token, use their official API to search
        song_url = None
        if self.genius_token:
            search_api_url = f"https://api.genius.com/search?q={urllib.parse.quote(query)}"
            headers = {"Authorization": f"Bearer {self.genius_token}"}
            try:
                res = requests.get(search_api_url, headers=headers)
                if res.status_code == 200:
                    hits = res.json().get("response", {}).get("hits", [])
                    if hits:
                        song_url = hits[0]["result"]["url"]
            except Exception as e:
                print(f"Genius API error: {e}")

        # If API search failed or no token provided, fallback to standard web scraping search
        if not song_url:
            search_html_url = f"https://genius.com/api/search/multi?per_page=1&q={urllib.parse.quote(query)}"
            headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
            try:
                res = requests.get(search_html_url, headers=headers)
                res_json = res.json()
                sections = res_json.get("response", {}).get("sections", [])
                for section in sections:
                    if section["type"] == "song":
                        hits = section.get("hits", [])
                        if hits:
                            song_url = hits[0]["result"]["url"]
            except Exception as e:
                # If direct search API blocks us, try DDG HTML fallback
                try:
                    ddg_url = f"https://html.duckduckgo.com/html/?q=site:genius.com {urllib.parse.quote(query)} lyrics"
                    res = requests.get(ddg_url, headers=headers)
                    soup = BeautifulSoup(res.text, "html.parser")
                    for a in soup.find_all('a', class_='result__url'):
                        href = a.get('href', '')
                        if 'genius.com' in href and not '/artists/' in href and not '/albums/' in href:
                            song_url = href
                            if song_url.startswith("//"): song_url = "https:" + song_url
                            elif song_url.startswith("/l/?uddg="):
                                qs = urllib.parse.parse_qs(urllib.parse.urlparse(song_url).query)
                                song_url = qs.get("uddg", [None])[0]
                            break
                except:
                    pass

        # If we successfully found a song URL from Genius, scrape the lyrics container
        if song_url:
            headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
            try:
                page = requests.get(song_url, headers=headers)
                soup = BeautifulSoup(page.text, "html.parser")
                lyrics_divs = soup.find_all("div", attrs={"data-lyrics-container": "true"})
                if lyrics_divs:
                    for br in soup.find_all("br"):
                        br.replace_with("\n")

                    # Use separator='\n' to prevent words in separate spans from getting merged without spaces
                    # (e.g. <span>threw</span><span>a</span> -> threw a)
                    lyrics_text = "\n".join([div.get_text(separator="\n", strip=True) for div in lyrics_divs])

                    # Remove [Verse 1], [Chorus], etc
                    lyrics_text = re.sub(r'\[.*?\]', '', lyrics_text)

                    # Genius often injects a header like "101 ContributorsTranslationsPortuguêsCall Me Maybe Lyrics"
                    # before the actual first line of the song. We remove everything up to and including the first "Lyrics\n"
                    # or "Lyrics " at the start of the text block.
                    lyrics_text = re.sub(r'^.*?Lyrics\s*\n?', '', lyrics_text, count=1, flags=re.IGNORECASE|re.DOTALL)

                    # Fix multiple consecutive newlines
                    lyrics_text = re.sub(r'\n{3,}', '\n\n', lyrics_text)
                    return {"source": "genius", "synced": False, "type": "text", "data": lyrics_text.strip()}
            except Exception as e:
                print(f"Genius scrape error: {e}")

        return None

    def get_lyrics(self, title, artist):
        # 1. Try Musixmatch (Custom Token or Anonymous Desktop Token)
        res = self.fetch_mxm_lyrics(title, artist)
        if res:
            print("Successfully found lyrics from Musixmatch.")
            return res

        # 2. Try Genius (Custom Token or Anonymous Web Scrape)
        print("Musixmatch failed. Falling back to Genius...")
        res = self.fetch_genius_lyrics(title, artist)
        if res:
            print("Successfully found lyrics from Genius.")
            return res

        # 3. Both failed. Returning None will trigger Whisper Transcription in processor.py
        print("Genius failed. Falling back to complete Whisper transcription...")
        return None
