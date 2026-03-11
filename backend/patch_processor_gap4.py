import re

with open("processor.py", "r") as f:
    code = f.read()

old_logic_1 = """                for i, word in enumerate(segment.words):
                    w_text = word.word.strip()
                    if not w_text:
                        continue

                    w_start = word.start
                    w_end = word.end

                    # Look ahead to the next valid word in the segment
                    next_start = None
                    for j in range(i + 1, len(segment.words)):
                        if segment.words[j].word.strip():
                            next_start = segment.words[j].start
                            break

                    # Smooth out extremely fast, skipped, or flashed words by filling the gap slightly
                    if w_end - w_start < 0.2:
                        pad_target = w_start + 0.3
                        if next_start is not None and pad_target > next_start:
                            w_end = max(w_end, next_start - 0.05)
                        else:
                            w_end = max(w_end, pad_target)

                    # If a word extends massively into an instrumental gap (e.g. stretching 10 seconds),
                    # we only cap it if the next word is more than 5.0 seconds away to preserve long 6-second held notes like "Ohhh"
                    if next_start is not None and next_start - w_start > 5.0:
                        if w_end - w_start > 2.0:
                            # It's highly likely stretching erroneously across the gap
                            w_end = w_start + 2.0
                    elif next_start is None:
                        # Last word of the segment
                        if w_end - w_start > 3.0:
                            # If it's the very last word of a sentence, cap the tail to 2.0s
                            w_end = w_start + 2.0

                    # If there's a huge gap before this word, push the previous words as a segment and start fresh
                    if current_seg_words and (w_start - current_seg_words[-1]["end"] > 4.0):"""

new_logic_1 = """                for i, word in enumerate(segment.words):
                    w_text = word.word.strip()
                    if not w_text:
                        continue

                    w_start = word.start
                    w_end = word.end

                    # Look back to the previous word
                    prev_end = current_seg_words[-1]["end"] if current_seg_words else segment.start

                    # Look ahead to the next valid word in the segment
                    next_start = None
                    for j in range(i + 1, len(segment.words)):
                        if segment.words[j].word.strip():
                            next_start = segment.words[j].start
                            break

                    # Fix for "oooooh" where the "o" is long but Whisper only aligned the short "h" ending.
                    # If this word is short (< 0.5s), but there's a significant gap (> 0.5s) BEFORE it,
                    # stretch the word's start time backwards into the gap to capture the vowel note.
                    if w_end - w_start < 0.5 and (w_start - prev_end) > 0.5:
                        # Don't stretch backwards more than 3.0 seconds to prevent weird UI artifacts
                        w_start = max(prev_end + 0.1, w_start - 3.0)

                    # Smooth out extremely fast, skipped, or flashed words by filling the gap slightly forward
                    if w_end - w_start < 0.2:
                        pad_target = w_start + 0.3
                        if next_start is not None and pad_target > next_start:
                            w_end = max(w_end, next_start - 0.05)
                        else:
                            w_end = max(w_end, pad_target)

                    # If a word extends massively into an instrumental gap (e.g. stretching 10 seconds),
                    # we only cap it if the next word is more than 5.0 seconds away to preserve long 6-second held notes like "Ohhh"
                    if next_start is not None and next_start - w_start > 5.0:
                        if w_end - w_start > 2.0:
                            # It's highly likely stretching erroneously across the gap
                            w_end = w_start + 2.0
                    elif next_start is None:
                        # Last word of the segment
                        if w_end - w_start > 3.0:
                            # If it's the very last word of a sentence, cap the tail to 2.0s
                            w_end = w_start + 2.0

                    # If there's a huge gap before this word, push the previous words as a segment and start fresh
                    if current_seg_words and (w_start - current_seg_words[-1]["end"] > 4.0):"""

code = code.replace(old_logic_1, new_logic_1)

# Now apply the identical patch to the else block (transcription mode)
old_logic_2 = """                for i, word in enumerate(segment.words):
                    w_text = word.word.strip()
                    if not w_text:
                        continue

                    w_start = word.start
                    w_end = word.end

                    next_start = None
                    for j in range(i + 1, len(segment.words)):
                        if segment.words[j].word.strip():
                            next_start = segment.words[j].start
                            break

                    if w_end - w_start < 0.2:
                        pad_target = w_start + 0.3
                        if next_start is not None and pad_target > next_start:
                            w_end = max(w_end, next_start - 0.05)
                        else:
                            w_end = max(w_end, pad_target)

                    if next_start is not None and next_start - w_start > 5.0:
                        if w_end - w_start > 2.0:
                            w_end = w_start + 2.0
                    elif next_start is None:
                        if w_end - w_start > 3.0:
                            w_end = w_start + 2.0

                    if current_seg_words and (w_start - current_seg_words[-1]["end"] > 4.0):"""

new_logic_2 = """                for i, word in enumerate(segment.words):
                    w_text = word.word.strip()
                    if not w_text:
                        continue

                    w_start = word.start
                    w_end = word.end

                    prev_end = current_seg_words[-1]["end"] if current_seg_words else segment.start

                    next_start = None
                    for j in range(i + 1, len(segment.words)):
                        if segment.words[j].word.strip():
                            next_start = segment.words[j].start
                            break

                    if w_end - w_start < 0.5 and (w_start - prev_end) > 0.5:
                        w_start = max(prev_end + 0.1, w_start - 3.0)

                    if w_end - w_start < 0.2:
                        pad_target = w_start + 0.3
                        if next_start is not None and pad_target > next_start:
                            w_end = max(w_end, next_start - 0.05)
                        else:
                            w_end = max(w_end, pad_target)

                    if next_start is not None and next_start - w_start > 5.0:
                        if w_end - w_start > 2.0:
                            w_end = w_start + 2.0
                    elif next_start is None:
                        if w_end - w_start > 3.0:
                            w_end = w_start + 2.0

                    if current_seg_words and (w_start - current_seg_words[-1]["end"] > 4.0):"""

code = code.replace(old_logic_2, new_logic_2)

with open("processor.py", "w") as f:
    f.write(code)

print("Patched backward gap padding logic.")
