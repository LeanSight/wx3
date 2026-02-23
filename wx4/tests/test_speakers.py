"""
Tests for wx4/speakers.py - parse_speakers_map().
"""


class TestParseSpeakersMap:
    def test_none_input_returns_empty_dict(self):
        from wx4.speakers import parse_speakers_map

        assert parse_speakers_map(None) == {}

    def test_empty_string_returns_empty_dict(self):
        from wx4.speakers import parse_speakers_map

        assert parse_speakers_map("") == {}

    def test_single_pair(self):
        from wx4.speakers import parse_speakers_map

        assert parse_speakers_map("A=Marcel") == {"A": "Marcel"}

    def test_two_pairs(self):
        from wx4.speakers import parse_speakers_map

        assert parse_speakers_map("A=Marcel,B=Agustin") == {
            "A": "Marcel",
            "B": "Agustin",
        }

    def test_spaces_trimmed(self):
        from wx4.speakers import parse_speakers_map

        assert parse_speakers_map(" A = Marcel ") == {"A": "Marcel"}

    def test_malformed_token_skipped(self):
        from wx4.speakers import parse_speakers_map

        assert parse_speakers_map("A=Marcel,NoEquals,B=Agustin") == {
            "A": "Marcel",
            "B": "Agustin",
        }

    def test_value_with_equals(self):
        from wx4.speakers import parse_speakers_map

        # partition semantics: split only on first '='
        assert parse_speakers_map("A=Mar=cel") == {"A": "Mar=cel"}
