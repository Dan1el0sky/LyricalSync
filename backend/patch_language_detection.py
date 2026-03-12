import re

with open("processor.py", "r") as f:
    code = f.read()

old_logic = """            else:
                text_to_align = existing_lyrics_text

                # Allow Stable-Whisper to auto-detect language for bilingual songs (e.g. ROSÉ APT. Korean+English).
                # Enable VAD (Voice Activity Detection) so Whisper correctly skips instrumental breaks instead of stretching words!
                result = self.model.align(waveform, text_to_align, language=None, vad=True)"""

new_logic = """            else:
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

                # Enable VAD (Voice Activity Detection) so Whisper correctly skips instrumental breaks instead of stretching words!
                result = self.model.align(waveform, text_to_align, language=detected_lang, vad=True)"""

code = code.replace(old_logic, new_logic)

with open("processor.py", "w") as f:
    f.write(code)

print("Patched language detection!")
