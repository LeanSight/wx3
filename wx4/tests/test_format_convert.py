"""
Tests for wx4/format_convert.py - ms_to_seconds() and assemblyai_words_to_chunks().
"""

import pytest


class TestMsToSeconds:
    def test_zero_ms(self):
        from wx4.format_convert import ms_to_seconds

        assert ms_to_seconds(0) == 0.0

    def test_500_ms(self):
        from wx4.format_convert import ms_to_seconds

        assert ms_to_seconds(500) == 0.5

    def test_1000_ms(self):
        from wx4.format_convert import ms_to_seconds

        assert ms_to_seconds(1000) == 1.0

    def test_1234_ms_is_1_234(self):
        from wx4.format_convert import ms_to_seconds

        assert ms_to_seconds(1234) == pytest.approx(1.234)


class TestAssemblyaiWordsToChunks:
    def _word(self, text, start, end, speaker=None):
        w = {"text": text, "start": start, "end": end}
        if speaker is not None:
            w["speaker"] = speaker
        return w

    def test_empty_list(self):
        from wx4.format_convert import assemblyai_words_to_chunks

        assert assemblyai_words_to_chunks([]) == []

    def test_single_word_structure(self):
        from wx4.format_convert import assemblyai_words_to_chunks

        chunks = assemblyai_words_to_chunks([self._word("hello", 0, 500, "A")])
        assert len(chunks) == 1
        chunk = chunks[0]
        assert "text" in chunk
        assert "timestamp" in chunk
        assert "speaker" in chunk

    def test_timestamps_in_seconds(self):
        from wx4.format_convert import assemblyai_words_to_chunks

        chunks = assemblyai_words_to_chunks([self._word("hi", 0, 500, "A")])
        assert chunks[0]["timestamp"] == (0.0, 0.5)

    def test_speaker_preserved(self):
        from wx4.format_convert import assemblyai_words_to_chunks

        chunks = assemblyai_words_to_chunks([self._word("hi", 0, 500, "A")])
        assert chunks[0]["speaker"] == "A"

    def test_missing_speaker_defaults_to_UNKNOWN(self):
        from wx4.format_convert import assemblyai_words_to_chunks

        chunks = assemblyai_words_to_chunks([{"text": "hi", "start": 0, "end": 500}])
        assert chunks[0]["speaker"] == "UNKNOWN"

    def test_multiple_words_list_length(self):
        from wx4.format_convert import assemblyai_words_to_chunks

        words = [self._word(f"w{i}", i * 100, (i + 1) * 100, "A") for i in range(5)]
        chunks = assemblyai_words_to_chunks(words)
        assert len(chunks) == 5
