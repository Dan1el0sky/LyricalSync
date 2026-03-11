import stable_whisper
import asyncio

async def run_test():
    from processor import AudioProcessor
    import numpy as np
    from pydub import AudioSegment

    # Create dummy audio file
    audio = np.zeros(16000 * 5, dtype=np.float32)
    segment = AudioSegment(
        audio.tobytes(),
        frame_rate=16000,
        sample_width=4,
        channels=1
    )
    segment.export("dummy.mp3", format="mp3")

    ap = AudioProcessor()

    text = "Holdin' me back."
    result = ap.process("dummy.mp3", text)

    import json
    print("Success. Example segment structure:")
    print(json.dumps(result["segments"][0], indent=2))

asyncio.run(run_test())
