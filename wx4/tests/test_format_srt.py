"""
Tests for wx4/format_srt.py - chunks_to_srt() and words_to_srt().
"""

from pathlib import Path
from unittest.mock import patch


def _chunk(text, start, end, speaker=None):
    return {"text": text, "timestamp": (start, end), "speaker": speaker}


class TestFormatTimestamp:
    def test_zero_seconds(self):
        from wx4.format_srt import _format_timestamp

        assert _format_timestamp(0.0) == "00:00:00,000"

    def test_one_hour(self):
        from wx4.format_srt import _format_timestamp

        assert _format_timestamp(3600.0) == "01:00:00,000"

    def test_milliseconds(self):
        from wx4.format_srt import _format_timestamp

        assert _format_timestamp(1.234) == "00:00:01,234"


class TestChunksToSrt:
    def test_empty_list_returns_empty_string(self):
        from wx4.format_srt import chunks_to_srt

        assert chunks_to_srt([]) == ""

    def test_sequential_index_from_1(self):
        from wx4.format_srt import chunks_to_srt

        chunks = [_chunk("Hello.", 0, 1, "A"), _chunk("World.", 1, 2, "A")]
        srt = chunks_to_srt(chunks)
        lines = srt.strip().split("\n")
        assert lines[0] == "1"
        # find second entry index
        idx = next(i for i, l in enumerate(lines) if l == "2")
        assert lines[idx] == "2"

    def test_timestamp_formatted_srt_style(self):
        from wx4.format_srt import chunks_to_srt

        chunks = [_chunk("Hi.", 0.0, 1.234, "A")]
        srt = chunks_to_srt(chunks)
        assert "00:00:00,000 --> 00:00:01,234" in srt

    def test_speaker_in_brackets(self):
        from wx4.format_srt import chunks_to_srt

        chunks = [_chunk("Hello world.", 0, 1, "A")]
        srt = chunks_to_srt(chunks)
        assert "[A] Hello world." in srt

    def test_speaker_replaced_by_name_map(self):
        from wx4.format_srt import chunks_to_srt

        chunks = [_chunk("Hello world.", 0, 1, "A")]
        srt = chunks_to_srt(chunks, speaker_names={"A": "Marcel"})
        assert "[Marcel] Hello world." in srt
        assert "[A]" not in srt

    def test_chunk_without_speaker_no_brackets(self):
        from wx4.format_srt import chunks_to_srt

        chunks = [_chunk("Hello.", 0, 1, None)]
        srt = chunks_to_srt(chunks)
        assert "[" not in srt


class TestWordsToSrt:
    def test_sentences_mode_calls_group_sentences(self):
        from wx4.format_srt import words_to_srt

        words = [{"text": "hi.", "start": 0, "end": 500, "speaker": "A"}]
        with patch("wx4.format_srt.group_chunks_by_sentences") as mock_grp:
            mock_grp.return_value = [_chunk("hi.", 0.0, 0.5, "A")]
            words_to_srt(words, mode="sentences")
        mock_grp.assert_called_once()

    def test_speaker_only_mode_calls_group_speaker_only(self):
        from wx4.format_srt import words_to_srt

        words = [{"text": "hi.", "start": 0, "end": 500, "speaker": "A"}]
        with patch("wx4.format_srt.group_chunks_by_speaker_only") as mock_grp:
            mock_grp.return_value = [_chunk("hi.", 0.0, 0.5, "A")]
            words_to_srt(words, mode="speaker-only")
        mock_grp.assert_called_once()

    def test_invalid_mode_raises_value_error(self):
        from wx4.format_srt import words_to_srt

        words = [{"text": "hi.", "start": 0, "end": 500, "speaker": "A"}]
        try:
            words_to_srt(words, mode="bad-mode")
            assert False, "Should have raised ValueError"
        except ValueError:
            pass

    def test_writes_file_when_output_file_given(self, tmp_path):
        from wx4.format_srt import words_to_srt

        words = [{"text": "hi.", "start": 0, "end": 500, "speaker": "A"}]
        out = tmp_path / "out.srt"
        words_to_srt(words, output_file=str(out), mode="speaker-only")
        assert out.exists()

    def test_returns_srt_string(self):
        from wx4.format_srt import words_to_srt

        words = [{"text": "hi.", "start": 0, "end": 500, "speaker": "A"}]
        result = words_to_srt(words, mode="speaker-only")
        assert isinstance(result, str)
        assert "hi." in result
