import unittest
import torch
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from processor import AudioProcessor

class DummyModel:
    def __call__(self, x):
        return torch.randn(1, 10, 28), None

class TestAudioProcessorAlignment(unittest.TestCase):
    def test_align_words_does_not_drop_chars(self):
        ap = AudioProcessor()
        ap.device = torch.device('cpu')
        ap.bundle = type('DummyBundle', (), {'sample_rate': 16000})
        ap.dictionary = {'a': 1, 'b': 2, 'c': 3, '*': 4}
        ap.model = DummyModel()

        def fake_compute(emission, transcript, dictionary):
            # transcript is ['a', 'b', '*', 'c', 'c', 'a', '*'] (len=7)
            # a=1, b=2, c=3, *=4
            alignments = torch.tensor([[1, 2, 2, 4, 3, 3, 3, 3, 1, 1, 4]], dtype=torch.int32)
            scores = torch.ones((1, 11))
            return alignments[0], scores[0]

        ap.compute_alignments = fake_compute

        waveform = torch.zeros((1, 16000))
        sample_rate = 16000
        words = ["ab", "cca"]

        res = ap._align_words(waveform, sample_rate, words, offset_time=0.0)

        self.assertEqual(len(res), 2)
        self.assertEqual(res[0]["word"], "ab")
        self.assertEqual(len(res[0]["chars"]), 2) # 'a', 'b'
        self.assertEqual(res[1]["word"], "cca")
        self.assertEqual(len(res[1]["chars"]), 3) # 'c', 'c', 'a'

if __name__ == '__main__':
    unittest.main()
