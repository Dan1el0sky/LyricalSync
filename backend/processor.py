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
            self.labels = self.bundle.get_labels(star=None)
            self.dictionary = self.bundle.get_dict(star=None)

    def compute_alignments(self, emission, transcript, dictionary):
        targets = torch.tensor([dictionary[c] for c in transcript], dtype=torch.int32)
        alignments, scores = torchaudio.functional.forced_align(emission, targets, blank=0)
        return alignments, scores

    def _clean_text(self, text):
        text = unidecode(text).lower()
        text = re.sub(r'[^a-z0-9 ]', '', text)
        return text.strip()

    def _align_words(self, waveform, sample_rate, words):
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

        # torchaudio forced_align returns (frame_alignments, scores)
        # However, due to memory on huge sequences (3 min song), forced_align can fail or take huge RAM.
        # But for 4GB we should be okay for 3-4 minutes.
        try:
            alignments, scores = self.compute_alignments(emission, transcript, self.dictionary)
            alignments = alignments[0]
        except Exception as e:
            print("Forced alignment failed, returning evenly spaced timings. Error:", e)
            # Fallback to evenly spaced fake timings
            return self._fake_align(words, waveform.shape[1]/self.bundle.sample_rate)

        frame_dur = 1.0 / 50.0

        aligned_words = []
        for span in word_spans:
            if span["clean"] == "": continue

            start_frame = None
            end_frame = None
            char_timings = []

            for idx in range(span["start_idx"], span["end_idx"]):
                token_frames = (alignments == idx).nonzero(as_tuple=True)[0]
                if len(token_frames) > 0:
                    c_start = token_frames[0].item() * frame_dur
                    c_end = (token_frames[-1].item() + 1) * frame_dur
                    if start_frame is None: start_frame = c_start
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

    def _fake_align(self, words, duration):
        total_chars = sum(len(w) for w in words)
        char_dur = duration / total_chars if total_chars > 0 else 0

        aligned_words = []
        current_time = 0.0
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

    def process(self, audio_path, existing_lyrics_text=None, richsync_data=None):
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
            print("Force aligning existing lyrics exactly using torchaudio MMS_FA...")
            lines = existing_lyrics_text.split('\n')
            all_words = []
            word_to_line = {}
            word_idx = 0

            for line_idx, line in enumerate(lines):
                words = line.strip().split()
                for w in words:
                    all_words.append(w)
                    word_to_line[word_idx] = line_idx
                    word_idx += 1

            aligned_words = self._align_words(waveform, sample_rate, all_words)

            lines_data = {}
            for i, aw in enumerate(aligned_words):
                if i >= len(word_to_line): break
                l_idx = word_to_line[i]
                if l_idx not in lines_data:
                    lines_data[l_idx] = {
                        "text": lines[l_idx],
                        "start": aw["start"],
                        "end": aw["end"],
                        "words": []
                    }
                lines_data[l_idx]["words"].append(aw)
                lines_data[l_idx]["end"] = aw["end"]

            for l_idx in sorted(lines_data.keys()):
                final_segments.append(lines_data[l_idx])

        else:
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
