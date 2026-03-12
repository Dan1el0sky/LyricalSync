with open("requirements.txt", "r") as f:
    lines = f.readlines()

new_lines = []
for line in lines:
    if "torchaudio" in line or "demucs" in line or "whisper-timestamped" in line:
        continue
    new_lines.append(line)

new_lines.append("stable-ts\n")

with open("requirements.txt", "w") as f:
    f.writelines(new_lines)
