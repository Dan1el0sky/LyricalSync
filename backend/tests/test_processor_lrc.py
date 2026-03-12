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

        # We don't need a mock model because it should bypass Whisper entirely!
        import numpy as np
        from pydub import AudioSegment
        audio = np.zeros(16000 * 2, dtype=np.float32)
        segment = AudioSegment(audio.tobytes(), frame_rate=16000, sample_width=4, channels=1)
        segment.export("mock5.mp3", format="mp3")

        richsync = [
            {"ts": 5.0, "text": "This is an echoing chorus"},
            {"ts": 8.0, "text": "Another line"}
        ]

        result = ap.process("mock5.mp3", existing_lyrics_text="This is an echoing chorus\nAnother line", richsync_data=richsync)

        segments = result["segments"]

        # Since it bypassed Whisper, "This is an echoing chorus" should start EXACTLY at 5.0
        # And since the next line is 8.0, it ends at 8.0.

        # Segment 0: Instrumental gap from 0 to 5.0
        self.assertEqual(segments[0]["is_instrumental"], True)
        self.assertEqual(segments[0]["end"], 5.0)

        # Segment 1: "This is an echoing chorus"
        self.assertEqual(segments[1]["text"], "This is an echoing chorus")
        self.assertEqual(segments[1]["start"], 5.0)

        # Segment 2: "Another line"
        self.assertEqual(segments[2]["text"], "Another line")
        self.assertEqual(segments[2]["start"], 8.0)

        os.remove("mock5.mp3")

if __name__ == '__main__':
    unittest.main()
