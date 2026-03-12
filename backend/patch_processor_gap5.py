import re

with open("processor.py", "r") as f:
    code = f.read()

# Apply a global -0.15s offset to w_start and w_end, clamped at 0.0
# inside both the align and transcribe loops.

old_logic = """                    w_start = word.start
                    w_end = word.end"""

new_logic = """                    # Apply global offset (-0.2s) to fix Whisper feeling "late"
                    global_offset = -0.2
                    w_start = max(0.0, word.start + global_offset)
                    w_end = max(0.0, word.end + global_offset)"""

code = code.replace(old_logic, new_logic)

with open("processor.py", "w") as f:
    f.write(code)

print("Patched global offset logic.")
