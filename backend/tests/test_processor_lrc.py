import unittest
import torch
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from processor import AudioProcessor

class TestAudioProcessorLRC(unittest.TestCase):
    def test_lrc_override(self):
        ap = AudioProcessor()
        ap.device = torch.device('cpu')

        # We don't even need a mock model because it should bypass alignment
        class MockModel:
            def __init__(self):
                self.device = torch.device('cpu')

        ap.model = MockModel()

        import numpy as np
        from pydub import AudioSegment
        audio = np.zeros(16000 * 2, dtype=np.float32)
        segment = AudioSegment(audio.tobytes(), frame_rate=16000, sample_width=4, channels=1)
        segment.export("mock5.mp3", format="mp3")

        richsync_data = [
            {"ts": 0.0, "text": "First line"},
            {"ts": 5.0, "text": "Second line"}
        ]

        result = ap.process("mock5.mp3", richsync_data=richsync_data)

        # Result should have 2 segments, exactly matching the LRC text and times!
        self.assertEqual(len(result["segments"]), 2)
        self.assertEqual(result["segments"][0]["text"], "First line")
        self.assertEqual(result["segments"][0]["start"], 0.0)
        # End is constrained to max + 5.0, so 0.0 + 5.0 = 5.0
        self.assertEqual(result["segments"][0]["end"], 5.0)

        self.assertEqual(result["segments"][1]["text"], "Second line")
        self.assertEqual(result["segments"][1]["start"], 5.0)
        self.assertEqual(result["segments"][1]["end"], 10.0)

        os.remove("mock5.mp3")

if __name__ == '__main__':
    unittest.main()