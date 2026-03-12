import unittest
import torch
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from processor import AudioProcessor

class TestAudioProcessorStableWhisper(unittest.TestCase):
    def test_stable_whisper_structure(self):
        ap = AudioProcessor()
        # Mocking the load_model and process methods to return hardcoded stable-whisper style object
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
            def detect_language(self, mel):
                return None, {'en': 1.0}

            def align(self, audio, text, language=None, vad=False, fast_mode=False):
                return MockResult()
            def transcribe(self, audio, language=None, word_timestamps=True, vad=False):
                return MockResult()

        ap.model = MockModel()

        # We need a small mock audio to pass to process
        import numpy as np
        from pydub import AudioSegment
        audio = np.zeros(16000 * 2, dtype=np.float32)
        segment = AudioSegment(audio.tobytes(), frame_rate=16000, sample_width=4, channels=1)
        segment.export("mock.mp3", format="mp3")

        result = ap.process("mock.mp3", existing_lyrics_text="Hello world")

        self.assertIn("segments", result)
        # Because gap_threshold is 5.0, start=0.0 will NOT trigger instrumental gap. Length is 1.
        self.assertEqual(len(result["segments"]), 1)

        self.assertEqual(result["segments"][0]["text"], "Hello world")
        self.assertEqual(len(result["segments"][0]["words"]), 2)
        self.assertEqual(result["segments"][0]["words"][0]["word"], "Hello")
        self.assertEqual(result["segments"][0]["words"][0]["start"], 0.0)
        self.assertAlmostEqual(result["segments"][0]["words"][0]["end"], 0.3, places=1)

        os.remove("mock.mp3")

if __name__ == '__main__':
    unittest.main()
