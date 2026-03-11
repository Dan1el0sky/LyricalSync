import stable_whisper

# Load model
model = stable_whisper.load_model('base')

text = "Holdin' me back. Gravity's holdin' me back. I want you to hold out the palm of your hand"
# In memory audio mock
import numpy as np
audio = np.zeros(16000 * 5, dtype=np.float32)

print("Testing alignment...")
result = stable_whisper.align(model, audio, text, language='en')

print("Segments:")
for s in result.segments:
    print(f"[{s.start:.2f} - {s.end:.2f}] {s.text}")
    for w in s.words:
        print(f"  {w.word} ({w.start:.2f} - {w.end:.2f})")

print("Format test complete")
