"""
Tests for common/grouping.py - group_chunks_by_sentences() and group_chunks_by_speaker_only().
"""


def _chunk(text, start, end, speaker=None):
    return {"text": text, "timestamp": (start, end), "speaker": speaker}


class TestIsSentenceEnd:
    def test_period(self):
        from common.grouping import is_sentence_end

        assert is_sentence_end("Hello world.")

    def test_question(self):
        from common.grouping import is_sentence_end

        assert is_sentence_end("How are you?")

    def test_exclamation(self):
        from common.grouping import is_sentence_end

        assert is_sentence_end("Great!")

    def test_semicolon(self):
        from common.grouping import is_sentence_end

        assert is_sentence_end("Done;")

    def test_plain_text_false(self):
        from common.grouping import is_sentence_end

        assert not is_sentence_end("Hello world")


class TestIsStrongPause:
    def test_comma(self):
        from common.grouping import is_strong_pause

        assert is_strong_pause("however,")

    def test_colon(self):
        from common.grouping import is_strong_pause

        assert is_strong_pause("result:")

    def test_plain_text_false(self):
        from common.grouping import is_strong_pause

        assert not is_strong_pause("hello")


class TestGroupChunksBySentences:
    def test_empty_returns_empty(self):
        from common.grouping import group_chunks_by_sentences

        assert group_chunks_by_sentences([]) == []

    def test_single_chunk_with_period(self):
        from common.grouping import group_chunks_by_sentences

        chunks = [_chunk("Hello.", 0, 1, "A")]
        result = group_chunks_by_sentences(chunks)
        assert len(result) == 1
        assert result[0]["text"] == "Hello."

    def test_speaker_change_splits(self):
        from common.grouping import group_chunks_by_sentences

        chunks = [
            _chunk("Hello.", 0, 1, "A"),
            _chunk("World.", 1, 2, "B"),
        ]
        result = group_chunks_by_sentences(chunks)
        assert len(result) == 2

    def test_max_chars_with_comma_splits(self):
        from common.grouping import group_chunks_by_sentences

        # After a comma chunk, next chunk pushes over max_chars -> split
        chunks = [
            _chunk("A" * 40 + ",", 0, 1, "A"),
            _chunk("B" * 41, 1, 2, "A"),
        ]
        result = group_chunks_by_sentences(chunks)
        assert len(result) >= 2

    def test_absolute_limit_splits(self):
        from common.grouping import group_chunks_by_sentences

        chunks = [
            _chunk("A" * 100, 0, 1, "A"),
            _chunk("B" * 100, 1, 2, "A"),
        ]
        result = group_chunks_by_sentences(chunks)
        assert len(result) >= 2

    def test_list_timestamps_normalized_to_tuples(self):
        from common.grouping import group_chunks_by_sentences

        chunks = [{"text": "Hello.", "timestamp": [0, 1], "speaker": "A"}]
        result = group_chunks_by_sentences(chunks)
        assert isinstance(result[0]["timestamp"], tuple)


class TestGroupChunksBySpeakerOnly:
    def test_empty_returns_empty(self):
        from common.grouping import group_chunks_by_speaker_only

        assert group_chunks_by_speaker_only([]) == []

    def test_single_speaker_all_grouped(self):
        from common.grouping import group_chunks_by_speaker_only

        chunks = [
            _chunk("Hello", 0, 1, "A"),
            _chunk("world", 1, 2, "A"),
        ]
        result = group_chunks_by_speaker_only(chunks)
        assert len(result) == 1

    def test_speaker_change_splits(self):
        from common.grouping import group_chunks_by_speaker_only

        chunks = [
            _chunk("Hello", 0, 1, "A"),
            _chunk("World", 1, 2, "B"),
        ]
        result = group_chunks_by_speaker_only(chunks)
        assert len(result) == 2

    def test_empty_chunks_ignored(self):
        from common.grouping import group_chunks_by_speaker_only

        chunks = [
            _chunk("Hello", 0, 1, "A"),
            _chunk("  ", 1, 2, "A"),  # empty text -> ignored
            _chunk("World", 2, 3, "A"),
        ]
        result = group_chunks_by_speaker_only(chunks)
        assert len(result) == 1
