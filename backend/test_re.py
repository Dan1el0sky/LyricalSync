import re

lyrics_data = """[00:12.75] My heart rages around like an ocean in my head
[00:18.65] Because there are so many things that I left unsaid
[00:39.50] I can almost feel you
[00:42.10] Wa-, wa-, walking in the distance"""

lyrics_text = re.sub(r'\[\d{2}:\d{2}\.\d{2,3}\]', '', lyrics_data)
print(repr(lyrics_text))
