import re

with open("processor.py", "r") as f:
    code = f.read()

# Fix the if condition to check for EITHER existing_lyrics_text OR richsync_data!
old_logic = "        if existing_lyrics_text:"
new_logic = "        if existing_lyrics_text or richsync_data:"

code = code.replace(old_logic, new_logic, 1)

with open("processor.py", "w") as f:
    f.write(code)

print("Patched if condition in processor.py")
