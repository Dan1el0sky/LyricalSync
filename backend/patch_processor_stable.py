import re

with open("processor.py", "r") as f:
    code = f.read()

new_code = """import os
import torch
import json
import re
from unidecode import unidecode
import stable_whisper

class AudioProcessor:
    def __init__(self):
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.model = None

    def load_model(self):
        if not self.model:
            print(f"Loading Stable Whisper model on {self.device}...")
            # Use 'base' or 'small' depending on accuracy vs speed requirements
            self.model = stable_whisper.load_model('base', device=self.device.type)

    def process(self, audio_path, existing_lyrics_text=None, richsync_data=None, video_id=None, progress_store=None):
        if progress_store and video_id:
            progress_store[video_id] = {"status": "Loading Stable Whisper model...", "percent": 55}
        self.load_model()

        print(f"Processing {audio_path}...")

        # Load audio using pydub instead of torchaudio to completely bypass OS-specific ffmpeg libav link errors
        from pydub import AudioSegment
        import numpy as np

        try:
            audio = AudioSegment.from_file(audio_path)
            # stable-whisper expects 16kHz mono float32 numpy array
            if audio.frame_rate != 16000:
                audio = audio.set_frame_rate(16000)
            if audio.channels > 1:
                audio = audio.set_channels(1)

            samples = np.array(audio.get_array_of_samples(), dtype=np.float32)
            max_val = np.abs(samples).max()
            if max_val > 0:
                samples = samples / max_val
            waveform = samples
        except Exception as e:
            print(f"Error loading audio via pydub: {e}")
            raise e

        final_segments = []

        if existing_lyrics_text:
            if progress_store and video_id:
                progress_store[video_id] = {"status": "Aligning lyrics with Stable Whisper...", "percent": 75}
            print("Force aligning existing lyrics using Stable Whisper...")

            # Reconstruct richsync if available, otherwise just use raw text
            text_to_align = existing_lyrics_text

            result = self.model.align(waveform, text_to_align, language='en')

            # Convert stable-whisper result into expected JSON format
            for segment in result.segments:
                seg_dict = {
                    "start": segment.start,
                    "end": segment.end,
                    "text": segment.text.strip(),
                    "words": []
                }
                for word in segment.words:
                    word_dict = {
                        "word": word.word.strip(),
                        "start": word.start,
                        "end": word.end,
                        # Character level timings can be approximated evenly since frontend handles `chars` array
                        "chars": []
                    }
                    w_text = word.word.strip()
                    if len(w_text) > 0:
                        w_dur = word.end - word.start
                        c_dur = w_dur / len(w_text)
                        for i, c in enumerate(w_text):
                            word_dict["chars"].append({
                                "char": c,
                                "start": word.start + i * c_dur,
                                "end": word.start + (i + 1) * c_dur
                            })
                    seg_dict["words"].append(word_dict)
                final_segments.append(seg_dict)

        else:
            if progress_store and video_id:
                progress_store[video_id] = {"status": "No lyrics found. Transcribing audio...", "percent": 60}
            print("No lyrics provided! Transcribing audio with Stable Whisper...")

            result = self.model.transcribe(waveform, language='en', word_timestamps=True)

            for segment in result.segments:
                seg_dict = {
                    "start": segment.start,
                    "end": segment.end,
                    "text": segment.text.strip(),
                    "words": []
                }
                for word in segment.words:
                    word_dict = {
                        "word": word.word.strip(),
                        "start": word.start,
                        "end": word.end,
                        "chars": []
                    }
                    w_text = word.word.strip()
                    if len(w_text) > 0:
                        w_dur = word.end - word.start
                        c_dur = w_dur / len(w_text)
                        for i, c in enumerate(w_text):
                            word_dict["chars"].append({
                                "char": c,
                                "start": word.start + i * c_dur,
                                "end": word.start + (i + 1) * c_dur
                            })
                    seg_dict["words"].append(word_dict)
                final_segments.append(seg_dict)

        # Inject instrumental gaps
        segments_with_gaps = []
        last_end = 0.0
        gap_threshold = 5.0

        for seg in final_segments:
            if seg["start"] - last_end >= gap_threshold:
                segments_with_gaps.append({
                    "is_instrumental": True,
                    "start": last_end,
                    "end": seg["start"],
                    "text": "🎵",
                    "words": []
                })
            seg["is_instrumental"] = False
            segments_with_gaps.append(seg)
            last_end = seg["end"]

        duration = len(waveform) / 16000
        return {
            "segments": segments_with_gaps,
            "language": "en",
            "duration": duration
        }

processor = AudioProcessor()
"""

with open("processor.py", "w") as f:
    f.write(new_code)
