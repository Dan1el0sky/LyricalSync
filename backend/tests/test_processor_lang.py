import unittest
import torch
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from processor import AudioProcessor

class TestAudioProcessorLang(unittest.TestCase):
    def test_stable_whisper_lang_detect(self):
        ap = AudioProcessor()
        ap.device = torch.device('cpu')

        class MockWord:
            def __init__(self, w, s, e):
                self.word = w
                self.start = s
                self.end = e

        class MockSegment:
            def __init__(self):
                self.start = 0.0
                self.end = 1.0
                self.text = "Hello world"
                self.words = [MockWord("Hello", 0.0, 0.5), MockWord("world", 0.5, 1.0)]

        class MockResult:
            def __init__(self):
                self.segments = [MockSegment()]

        class MockModel:
            def __init__(self):
                self.device = torch.device('cpu')
                self.last_lang = None
            def align(self, audio, text, language=None, vad=False, fast_mode=False):
                self.last_lang = language
                return MockResult()
            def detect_language(self, mel):
                return None, {'en': 0.1, 'ko': 0.9} # Simulate Korean detected!

        ap.model = MockModel()

        import numpy as np
        from pydub import AudioSegment
        audio = np.zeros(16000 * 2, dtype=np.float32)
        segment = AudioSegment(audio.tobytes(), frame_rate=16000, sample_width=4, channels=1)
        segment.export("mock6.mp3", format="mp3")

        result = ap.process("mock6.mp3", existing_lyrics_text="Hello world")

        # Verify the model received 'ko'
        self.assertEqual(ap.model.last_lang, 'ko')

        os.remove("mock6.mp3")

if __name__ == '__main__':
    unittest.main()