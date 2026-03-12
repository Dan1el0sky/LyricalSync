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

        if existing_lyrics_text or richsync_data:
            if progress_store and video_id:
                progress_store[video_id] = {"status": "Aligning lyrics with Stable Whisper...", "percent": 75}
            print("Force aligning existing lyrics using Stable Whisper...")

            # Strategy 1: We have perfectly human-synced LRC line timestamps!
            if richsync_data:
                print("Richsync LRC data found! overriding whisper segments completely to fix echo/chorus misalignment...")

                # We know the exact start time of each line. We will uniformly distribute the words
                # inside the line until the next line starts (or a max of 5 seconds later).
                # This guarantees the chorus and echoes perfectly sync to the human-made LRC file!
                for i, line_data in enumerate(richsync_data):
                    start_ts = line_data.get("ts", 0.0)
                    text = line_data.get("text", "").strip()
                    if not text: continue

                    if i + 1 < len(richsync_data):
                        end_ts = richsync_data[i+1].get("ts", start_ts + 5.0)
                    else:
                        end_ts = start_ts + 5.0

                    # We don't want lines dragging into massive gaps
                    end_ts = min(end_ts, start_ts + 7.0)

                    # Split into words and distribute evenly
                    words = text.split()
                    w_dur = (end_ts - start_ts) / len(words) if words else 0

                    current_seg_words = []
                    for w_idx, w in enumerate(words):
                        w_start = start_ts + w_idx * w_dur
                        w_end = w_start + w_dur

                        word_dict = {
                            "word": w,
                            "start": w_start,
                            "end": w_end,
                            "chars": []
                        }

                        c_dur = w_dur / len(w) if len(w) > 0 else 0
                        for idx_c, c in enumerate(w):
                            word_dict["chars"].append({
                                "char": c,
                                "start": w_start + idx_c * c_dur,
                                "end": w_start + (idx_c + 1) * c_dur
                            })
                        current_seg_words.append(word_dict)

                    final_segments.append({
                        "start": start_ts,
                        "end": end_ts,
                        "text": text,
                        "words": current_seg_words
                    })
            else:
                text_to_align = existing_lyrics_text

                # model.align REQUIRES a language. We can use whisper's built-in language detection on the first 30s
                # to figure out if it's Korean, English, etc.
                import whisper

                # Create a padded/trimmed 30s chunk to detect language
                audio_for_lang = whisper.pad_or_trim(waveform.flatten())

                # Make log-Mel spectrogram and move to the same device as the model
                mel = whisper.log_mel_spectrogram(audio_for_lang, n_mels=self.model.dims.n_mels if hasattr(self.model, 'dims') else 80).to(self.model.device)

                # Detect the spoken language
                _, probs = self.model.detect_language(mel)
                detected_lang = max(probs, key=probs.get)
                print(f"Detected language: {detected_lang}")

                # Do NOT use vad=True for align(), it aggressively removes silence frames which
                # desyncs the audio timeline and causes "Failed to align the last X words" errors!
                # Using fast_mode=True can sometimes cause dropped segments on extremely long gaps.
                # However, it is required for speed and avoiding OOM on 4GB VRAM.
                # We will handle the output carefully.
                result = self.model.align(waveform, text_to_align, language=detected_lang, vad=False, fast_mode=True)

                for segment in result.segments:
                    # If stable_whisper failed to align this segment (empty words list), skip it to prevent crash.
                    if not getattr(segment, 'words', None):
                        continue

                    # To prevent a single sentence from spanning a 15-second gap like in "As It Was",
                    # we will detect if the gap BETWEEN two consecutive words is > 4.0 seconds,
                    # and if so, split the segment there.

                    current_seg_words = []
                    current_seg_start = segment.words[0].start if getattr(segment, 'words', None) else segment.start

                    for i, word in enumerate(segment.words):
                        w_text = word.word.strip()
                        if not w_text:
                            continue

                        # Apply global offset (-0.2s) to fix Whisper feeling "late"
                        global_offset = -0.2
                        w_start = max(0.0, word.start + global_offset)
                        w_end = max(0.0, word.end + global_offset)

                        # Look back to the previous word
                        prev_end = current_seg_words[-1]["end"] if current_seg_words else segment.start

                        # Look ahead to the next valid word in the segment
                        next_start = None
                        for j in range(i + 1, len(segment.words)):
                            if segment.words[j].word.strip():
                                next_start = segment.words[j].start
                                break

                        # Fix for "oooooh" where the "o" is long but Whisper only aligned the short "h" ending.
                        # If this word is short (< 0.5s), but there's a significant gap (> 0.5s) BEFORE it,
                        # stretch the word's start time backwards into the gap to capture the vowel note.
                        if w_end - w_start < 0.5 and (w_start - prev_end) > 0.5:
                            # Don't stretch backwards more than 3.0 seconds to prevent weird UI artifacts
                            w_start = max(prev_end + 0.1, w_start - 3.0)

                        # Smooth out extremely fast, skipped, or flashed words by filling the gap slightly forward
                        if w_end - w_start < 0.2:
                            pad_target = w_start + 0.3
                            if next_start is not None and pad_target > next_start:
                                w_end = max(w_end, next_start - 0.05)
                            else:
                                w_end = max(w_end, pad_target)

                        # If a word extends massively into an instrumental gap (e.g. stretching 10 seconds),
                        # we only cap it if the next word is more than 5.0 seconds away to preserve long 6-second held notes like "Ohhh"
                        if next_start is not None and next_start - w_start > 5.0:
                            if w_end - w_start > 2.0:
                                # It's highly likely stretching erroneously across the gap
                                w_end = w_start + 2.0
                        elif next_start is None:
                            # Last word of the segment
                            if w_end - w_start > 3.0:
                                # If it's the very last word of a sentence, cap the tail to 2.0s
                                w_end = w_start + 2.0

                        # If there's a huge gap before this word, push the previous words as a segment and start fresh
                        if current_seg_words and (w_start - current_seg_words[-1]["end"] > 4.0):
                            # Ensure we don't end exactly at start time (causes zero duration)
                            seg_end = current_seg_words[-1]["end"]
                            if seg_end <= current_seg_start:
                                seg_end = current_seg_start + 0.1
                            final_segments.append({
                                "start": current_seg_start,
                                "end": seg_end,
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
                        seg_end = current_seg_words[-1]["end"]
                        if seg_end <= current_seg_start:
                            seg_end = current_seg_start + 0.1
                        final_segments.append({
                            "start": current_seg_start,
                            "end": seg_end,
                            "text": " ".join([w["word"] for w in current_seg_words]),
                            "words": current_seg_words
                        })

        else:
            if progress_store and video_id:
                progress_store[video_id] = {"status": "No lyrics found. Transcribing audio...", "percent": 60}
            print("No lyrics provided! Transcribing audio with Stable Whisper...")

            # Allow auto-language detection and use VAD to ignore instrumental sections.
            result = self.model.transcribe(waveform, language=None, word_timestamps=True, vad=True)

            for segment in result.segments:
                current_seg_words = []
                current_seg_start = segment.words[0].start if segment.words else segment.start

                for i, word in enumerate(segment.words):
                    w_text = word.word.strip()
                    if not w_text:
                        continue

                    # Apply global offset (-0.2s) to fix Whisper feeling "late"
                    global_offset = -0.2
                    w_start = max(0.0, word.start + global_offset)
                    w_end = max(0.0, word.end + global_offset)

                    prev_end = current_seg_words[-1]["end"] if current_seg_words else segment.start

                    next_start = None
                    for j in range(i + 1, len(segment.words)):
                        if segment.words[j].word.strip():
                            next_start = segment.words[j].start
                            break

                    if w_end - w_start < 0.5 and (w_start - prev_end) > 0.5:
                        w_start = max(prev_end + 0.1, w_start - 3.0)

                    if w_end - w_start < 0.2:
                        pad_target = w_start + 0.3
                        if next_start is not None and pad_target > next_start:
                            w_end = max(w_end, next_start - 0.05)
                        else:
                            w_end = max(w_end, pad_target)

                    if next_start is not None and next_start - w_start > 5.0:
                        if w_end - w_start > 2.0:
                            w_end = w_start + 2.0
                    elif next_start is None:
                        if w_end - w_start > 3.0:
                            w_end = w_start + 2.0

                    if current_seg_words and (w_start - current_seg_words[-1]["end"] > 4.0):
                        seg_end = current_seg_words[-1]["end"]
                        if seg_end <= current_seg_start:
                            seg_end = current_seg_start + 0.1
                        final_segments.append({
                            "start": current_seg_start,
                            "end": seg_end,
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
                    seg_end = current_seg_words[-1]["end"]
                    if seg_end <= current_seg_start:
                        seg_end = current_seg_start + 0.1
                    final_segments.append({
                        "start": current_seg_start,
                        "end": seg_end,
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
