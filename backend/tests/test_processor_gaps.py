import unittest
import torch
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from processor import AudioProcessor

class TestAudioProcessorGaps(unittest.TestCase):
    def test_stable_whisper_split_gaps(self):
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
                self.end = 20.0
                self.text = "Hello there my friend"
                # "Hello there" [0-1s], gap of 10s, "my friend" [11-12s]
                # And "friend" lasts 5 seconds, which should be capped to 1.0
                self.words = [
                    MockWord("Hello", 0.0, 0.5),
                    MockWord("there", 0.5, 1.0),
                    MockWord("my", 11.0, 11.5),
                    MockWord("friend", 11.5, 16.5)
                ]

        class MockResult:
            def __init__(self):
                self.segments = [MockSegment()]

        class MockModel:
            def align(self, audio, text, language=None):
                return MockResult()

        ap.model = MockModel()

        import numpy as np
        from pydub import AudioSegment
        audio = np.zeros(16000 * 2, dtype=np.float32)
        segment = AudioSegment(audio.tobytes(), frame_rate=16000, sample_width=4, channels=1)
        segment.export("mock2.mp3", format="mp3")

        result = ap.process("mock2.mp3", existing_lyrics_text="Hello there my friend")

        segments = result["segments"]
        # Expected:
        # [0]: "Hello there" (0.0 to 1.0)
        # [1]: Instrumental (1.0 to 11.0)
        # [2]: "my friend" (11.0 to 12.5) -> friend capped to 1.0 instead of 5.0

        self.assertEqual(len(segments), 3)
        self.assertEqual(segments[0]["text"], "Hello there")
        self.assertEqual(segments[0]["words"][-1]["end"], 1.0)

        self.assertEqual(segments[1]["is_instrumental"], True)
        self.assertEqual(segments[1]["start"], 1.0)
        self.assertEqual(segments[1]["end"], 11.0)

        self.assertEqual(segments[2]["text"], "my friend")
        self.assertEqual(segments[2]["words"][-1]["end"], 12.5) # 11.5 + 1.0 cap

        os.remove("mock2.mp3")

if __name__ == '__main__':
    unittest.main()
