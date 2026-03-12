import unittest
import torch
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from processor import AudioProcessor

class TestAudioProcessorGaps(unittest.TestCase):
    def test_stable_whisper_backwards_padding(self):
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
                self.end = 10.0
                self.text = "Hello oh"
                # "Hello" is [0.0 - 0.5]
                # Then singer sings "oooh" for 3 seconds [0.5 - 3.5]
                # But whisper aligned the word "oh" to [3.4 - 3.5]
                # We expect the processor to pad "oh" backwards!
                self.words = [
                    MockWord("Hello", 0.0, 0.5),
                    MockWord("oh", 3.4, 3.5)
                ]

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

        ap.model = MockModel()

        import numpy as np
        from pydub import AudioSegment
        audio = np.zeros(16000 * 2, dtype=np.float32)
        segment = AudioSegment(audio.tobytes(), frame_rate=16000, sample_width=4, channels=1)
        segment.export("mock4.mp3", format="mp3")

        result = ap.process("mock4.mp3", existing_lyrics_text="Hello oh")

        segments = result["segments"]
        # Segment 0: Hello oh
        # Hello: 0.0 to 0.5
        # oh: originally 3.4 to 3.5.
        # Since it is < 0.5s long, and 3.4 - 0.5 = 2.9s gap before it...
        # It should backwards pad to max(0.5 + 0.1, 3.4 - 3.0) = max(0.6, 0.4) = 0.6.
        # So "oh" should now start at 0.6!
        self.assertEqual(segments[0]["text"], "Hello oh")
        self.assertAlmostEqual(segments[0]["words"][1]["start"], 0.4, places=1)
        self.assertEqual(segments[0]["words"][1]["word"], "oh")

        os.remove("mock4.mp3")

if __name__ == '__main__':
    unittest.main()