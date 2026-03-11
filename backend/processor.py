import os
# Force PyTorch and torchaudio to download the huge 1.18GB models to the local project folder
# instead of the user's C:\Users\...\.cache\ directory.
os.environ["TORCH_HOME"] = os.path.join(os.path.dirname(os.path.abspath(__file__)), "models")

import torch
import torchaudio
import json
import re
from unidecode import unidecode
from torchaudio.pipelines import MMS_FA

class AudioProcessor:
    def __init__(self):
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.bundle = MMS_FA
        self.model = None
        self.labels = None
        self.dictionary = None

    def load_model(self):
        if not self.model:
            print(f"Loading torchaudio MMS Forced Alignment model on {self.device}...")
            self.model = self.bundle.get_model()
            self.model.to(self.device)
            self.labels = self.bundle.get_labels(star="*")
            self.dictionary = self.bundle.get_dict(star="*")

    def compute_alignments(self, emission, transcript, dictionary):
        targets = torch.tensor([[dictionary[c] for c in transcript]], dtype=torch.int32)
        alignments, scores = torchaudio.functional.forced_align(emission.unsqueeze(0), targets, blank=0)
        return alignments[0], scores[0]

    def _clean_text(self, text):
        text = unidecode(text).lower()
        text = re.sub(r'[^a-z0-9 ]', '', text)
        return text.strip()

    def _align_words(self, waveform, sample_rate, words, offset_time=0.0):
        if sample_rate != self.bundle.sample_rate:
            resampler = torchaudio.transforms.Resample(orig_freq=sample_rate, new_freq=self.bundle.sample_rate)
            waveform = resampler(waveform)

        with torch.inference_mode():
            emission, _ = self.model(waveform.to(self.device))
        emission = emission[0].cpu() # shape (frames, num_labels)

        transcript = []
        word_spans = []

        for w in words:
            cleaned = self._clean_text(w)
            if not cleaned: continue

            span_start = len(transcript)
            for c in cleaned:
                if c in self.dictionary:
                    transcript.append(c)
            transcript.append('*')
            span_end = len(transcript)

            word_spans.append({
                "word": w,
                "clean": cleaned,
                "start_idx": span_start,
                "end_idx": span_end - 1
            })

        if not transcript:
            return []

        try:
            alignments, scores = self.compute_alignments(emission, transcript, self.dictionary)
            from torchaudio.functional import merge_tokens
            token_spans = merge_tokens(alignments, scores)
        except Exception as e:
            print("Forced alignment chunk failed, returning evenly spaced timings. Error:", e)
            return self._fake_align(words, waveform.shape[1]/self.bundle.sample_rate, offset_time)

        frame_dur = 1.0 / 50.0

        aligned_words = []
        for span in word_spans:
            if span["clean"] == "": continue

            start_frame = None
            end_frame = None
            char_timings = []

            for idx in range(span["start_idx"], span["end_idx"]):
                if idx < len(token_spans):
                    tspan = token_spans[idx]
                    c_start = (tspan.start * frame_dur) + offset_time
                    c_end = (tspan.end * frame_dur) + offset_time

                    if start_frame is None:
                        start_frame = c_start
                    end_frame = c_end

                    char_timings.append({
                        "char": transcript[idx],
                        "start": c_start,
                        "end": c_end
                    })

            if start_frame is not None and end_frame is not None:
                aligned_words.append({
                    "word": span["word"],
                    "start": start_frame,
                    "end": end_frame,
                    "chars": char_timings
                })

        return aligned_words

    def _fake_align(self, words, duration, offset_time=0.0):
        total_chars = sum(len(w) for w in words)
        char_dur = duration / total_chars if total_chars > 0 else 0

        aligned_words = []
        current_time = offset_time
        for w in words:
            w_start = current_time
            char_timings = []
            for c in w:
                char_timings.append({"char": c, "start": current_time, "end": current_time + char_dur})
                current_time += char_dur
            aligned_words.append({
                "word": w,
                "start": w_start,
                "end": current_time,
                "chars": char_timings
            })
        return aligned_words

    def process(self, audio_path, existing_lyrics_text=None, richsync_data=None, video_id=None, progress_store=None):
        if progress_store and video_id:
            progress_store[video_id] = {"status": "Loading audio processing model...", "percent": 55}
        self.load_model()

        print(f"Processing {audio_path}...")

        # Load audio using pydub instead of torchaudio to completely bypass OS-specific ffmpeg libav link errors
        from pydub import AudioSegment
        import numpy as np

        try:
            audio = AudioSegment.from_file(audio_path)
            sample_rate = audio.frame_rate

            # Convert to mono
            if audio.channels > 1:
                audio = audio.set_channels(1)

            # Convert to raw data
            samples = np.array(audio.get_array_of_samples(), dtype=np.float32)

            # Normalize to [-1.0, 1.0]
            max_val = np.abs(samples).max()
            if max_val > 0:
                samples = samples / max_val

            waveform = torch.from_numpy(samples).unsqueeze(0) # shape: (1, samples)

        except Exception as e:
            print(f"Error loading audio via pydub: {e}")
            raise e

        final_segments = []

        if existing_lyrics_text:
            if progress_store and video_id:
                progress_store[video_id] = {"status": "Force aligning lyrics...", "percent": 65}
            print("Force aligning existing lyrics using torchaudio MMS_FA (chunked to save memory/prevent lag)...")

            # Total audio duration
            total_duration = waveform.shape[1] / sample_rate

            chunks_to_process = []

            # Strategy 1: Use exact Musixmatch phrase timings to chunk the audio
            if richsync_data:
                print("Richsync data found! Chunking audio exactly by phrase timestamps...")
                for i, line_data in enumerate(richsync_data):
                    start_ts = line_data.get("ts", 0.0)
                    end_ts = line_data.get("te", 0.0)
                    text = line_data.get("text", "").strip()
                    if not text: continue

                    # If Musixmatch didn't give an end timestamp for the phrase, guess based on next phrase
                    if end_ts == 0.0 or end_ts <= start_ts:
                        if i + 1 < len(richsync_data):
                            end_ts = richsync_data[i+1].get("ts", start_ts + 5.0)
                        else:
                            end_ts = total_duration

                    # Add slight padding so we don't clip words on the absolute edge
                    pad = 0.5
                    c_start = max(0.0, start_ts - pad)
                    c_end = min(total_duration, end_ts + pad)

                    chunks_to_process.append({
                        "text": text,
                        "start_sec": c_start,
                        "end_sec": c_end,
                        "offset": c_start
                    })

            # Strategy 2: We only have plain text. Use Whisper to find timestamps, then align words exactly.
            else:
                if progress_store and video_id:
                    progress_store[video_id] = {"status": "Transcribing audio to find safe chunks...", "percent": 75}
                print("No richsync found. Transcribing audio with Whisper to find safe chunks to align...")

                import whisper_timestamped as whisper
                w_model = whisper.load_model("base", device="cpu" if self.device.type=="cpu" else "cuda")
                w_audio = whisper.load_audio(audio_path)
                results = whisper.transcribe(w_model, w_audio, language="en")

                # Create chunks based on whisper segments
                chunk_duration_target = 30.0
                current_chunk_segments = []
                current_chunk_start = 0.0

                lines = [l.strip() for l in existing_lyrics_text.split('\n') if l.strip()]
                whisper_segments = results.get("segments", [])

                # Match whisper segments to the plain text lyrics lines
                # Simply chunk the lyrics text based on duration matching the segments

                total_words = sum(len(line.split()) for line in lines)
                words_per_sec = total_words / total_duration if total_duration > 0 else 1

                current_line_idx = 0

                for segment in whisper_segments:
                    seg_start = segment["start"]
                    seg_end = segment["end"]

                    if len(current_chunk_segments) == 0:
                        current_chunk_start = seg_start

                    current_chunk_segments.append(segment)

                    if seg_end - current_chunk_start >= chunk_duration_target:
                        chunk_expected_words = int((seg_end - current_chunk_start) * words_per_sec)
                        chunk_lines = []
                        chunk_words_count = 0

                        while current_line_idx < len(lines):
                            line = lines[current_line_idx]
                            w_count = len(line.split())
                            if chunk_words_count + w_count > chunk_expected_words * 1.5 and chunk_lines:
                                break
                            chunk_lines.append(line)
                            chunk_words_count += w_count
                            current_line_idx += 1

                        if chunk_lines:
                            # Pad slightly to allow word boundary freedom
                            pad = 0.5
                            chunks_to_process.append({
                                "text": " \n ".join(chunk_lines), # Use newline to keep track later
                                "start_sec": max(0.0, current_chunk_start - pad),
                                "end_sec": min(total_duration, seg_end + pad),
                                "offset": max(0.0, current_chunk_start - pad)
                            })

                        current_chunk_segments = []

                # Append left overs
                if current_chunk_segments or current_line_idx < len(lines):
                    chunk_lines = []
                    while current_line_idx < len(lines):
                        chunk_lines.append(lines[current_line_idx])
                        current_line_idx += 1

                    if not current_chunk_segments:
                        start_sec = max(0.0, total_duration - 10.0)
                        end_sec = total_duration
                    else:
                        start_sec = max(0.0, current_chunk_start - 0.5)
                        end_sec = total_duration

                    if chunk_lines:
                        chunks_to_process.append({
                            "text": " \n ".join(chunk_lines),
                            "start_sec": start_sec,
                            "end_sec": end_sec,
                            "offset": start_sec
                        })


            # Execute chunked alignments
            total_chunks = len(chunks_to_process)
            for chunk_idx, chunk in enumerate(chunks_to_process):
                if progress_store and video_id:
                    progress_store[video_id] = {"status": f"Aligning chunk {chunk_idx + 1}/{total_chunks}...", "percent": 75 + int((chunk_idx / total_chunks) * 20)}
                start_sample = int(chunk["start_sec"] * sample_rate)
                end_sample = int(chunk["end_sec"] * sample_rate)
                chunk_waveform = waveform[:, start_sample:end_sample]

                lines_in_chunk = chunk["text"].split(" \n ")
                all_words = []
                word_to_line = {}
                word_idx = 0

                for line_idx, line in enumerate(lines_in_chunk):
                    words = line.strip().split()
                    for w in words:
                        all_words.append(w)
                        word_to_line[word_idx] = line_idx
                        word_idx += 1

                aligned_words = self._align_words(chunk_waveform, sample_rate, all_words, offset_time=chunk["offset"])

                lines_data = {}
                for i, aw in enumerate(aligned_words):
                    if i >= len(word_to_line): break
                    l_idx = word_to_line[i]
                    if l_idx not in lines_data:
                        lines_data[l_idx] = {
                            "text": lines_in_chunk[l_idx],
                            "start": aw["start"],
                            "end": aw["end"],
                            "words": []
                        }
                    lines_data[l_idx]["words"].append(aw)
                    lines_data[l_idx]["end"] = aw["end"]

                for l_idx in sorted(lines_data.keys()):
                    final_segments.append(lines_data[l_idx])

        else:
            if progress_store and video_id:
                progress_store[video_id] = {"status": "No lyrics found. Transcribing audio...", "percent": 60}
            print("No lyrics provided! Falling back to fast whisper transcription...")
            import whisper_timestamped as whisper
            w_model = whisper.load_model("base", device="cpu" if self.device.type=="cpu" else "cuda")
            w_audio = whisper.load_audio(audio_path)
            results = whisper.transcribe(w_model, w_audio, language="en")

            for segment in results["segments"]:
                seg_dict = {
                    "start": segment["start"],
                    "end": segment["end"],
                    "text": segment["text"].strip(),
                    "words": []
                }
                if "words" in segment:
                    for word in segment["words"]:
                        char_timings = []
                        w_text = word["text"]
                        w_dur = word["end"] - word["start"]
                        c_dur = w_dur / len(w_text) if len(w_text) > 0 else 0
                        for i, c in enumerate(w_text):
                            char_timings.append({
                                "char": c,
                                "start": word["start"] + i * c_dur,
                                "end": word["start"] + (i + 1) * c_dur
                            })

                        word_dict = {
                            "word": w_text,
                            "start": word["start"],
                            "end": word["end"],
                            "chars": char_timings
                        }
                        seg_dict["words"].append(word_dict)
                final_segments.append(seg_dict)

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

        return {
            "segments": segments_with_gaps,
            "language": "en",
            "duration": waveform.shape[1] / sample_rate
        }

processor = AudioProcessor()
