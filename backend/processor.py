import os
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

            # align can aggressively stretch words across gaps.
            # Using refine=True improves boundary alignment locally.
            # demucs=True (if installed) or original_split=True are options but we removed demucs.
            result = self.model.align(waveform, text_to_align, language='en')

            # Convert stable-whisper result into expected JSON format
            for segment in result.segments:
                # To prevent a single sentence from spanning a 15-second gap like in "As It Was",
                # we will detect if the gap BETWEEN two consecutive words is > 4.0 seconds,
                # and if so, split the segment there.

                current_seg_words = []
                current_seg_start = segment.words[0].start if segment.words else segment.start

                for i, word in enumerate(segment.words):
                    w_text = word.word.strip()
                    if not w_text:
                        continue

                    w_start = word.start
                    w_end = word.end

                    # Prevent zero-duration skips which make words flash instantly
                    if w_end - w_start < 0.1:
                        w_end = w_start + 0.2

                    # Cap word durations so long instrumentals don't stretch the word "you" for 10 seconds
                    if w_end - w_start > 3.0:
                        w_end = w_start + 1.0

                    # If there's a huge gap before this word, push the previous words as a segment and start fresh
                    if current_seg_words and (w_start - current_seg_words[-1]["end"] > 4.0):
                        final_segments.append({
                            "start": current_seg_start,
                            "end": current_seg_words[-1]["end"],
                            "text": " ".join([w["word"] for w in current_seg_words]),
                            "words": current_seg_words
                        })
                        current_seg_words = []
                        current_seg_start = w_start

                    word_dict = {
                        "word": w_text,
                        "start": w_start,
                        "end": w_end,
                        "chars": []
                    }

                    w_dur = w_end - w_start
                    c_dur = w_dur / len(w_text)
                    for idx_c, c in enumerate(w_text):
                        word_dict["chars"].append({
                            "char": c,
                            "start": w_start + idx_c * c_dur,
                            "end": w_start + (idx_c + 1) * c_dur
                        })
                    current_seg_words.append(word_dict)

                if current_seg_words:
                    final_segments.append({
                        "start": current_seg_start,
                        "end": current_seg_words[-1]["end"],
                        "text": " ".join([w["word"] for w in current_seg_words]),
                        "words": current_seg_words
                    })

        else:
            if progress_store and video_id:
                progress_store[video_id] = {"status": "No lyrics found. Transcribing audio...", "percent": 60}
            print("No lyrics provided! Transcribing audio with Stable Whisper...")

            result = self.model.transcribe(waveform, language='en', word_timestamps=True)

            for segment in result.segments:
                current_seg_words = []
                current_seg_start = segment.words[0].start if segment.words else segment.start

                for i, word in enumerate(segment.words):
                    w_text = word.word.strip()
                    if not w_text:
                        continue

                    w_start = word.start
                    w_end = word.end

                    if w_end - w_start < 0.1:
                        w_end = w_start + 0.2

                    if w_end - w_start > 3.0:
                        w_end = w_start + 1.0

                    if current_seg_words and (w_start - current_seg_words[-1]["end"] > 4.0):
                        final_segments.append({
                            "start": current_seg_start,
                            "end": current_seg_words[-1]["end"],
                            "text": " ".join([w["word"] for w in current_seg_words]),
                            "words": current_seg_words
                        })
                        current_seg_words = []
                        current_seg_start = w_start

                    word_dict = {
                        "word": w_text,
                        "start": w_start,
                        "end": w_end,
                        "chars": []
                    }

                    w_dur = w_end - w_start
                    c_dur = w_dur / len(w_text)
                    for idx_c, c in enumerate(w_text):
                        word_dict["chars"].append({
                            "char": c,
                            "start": w_start + idx_c * c_dur,
                            "end": w_start + (idx_c + 1) * c_dur
                        })
                    current_seg_words.append(word_dict)

                if current_seg_words:
                    final_segments.append({
                        "start": current_seg_start,
                        "end": current_seg_words[-1]["end"],
                        "text": " ".join([w["word"] for w in current_seg_words]),
                        "words": current_seg_words
                    })

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
