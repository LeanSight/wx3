"""
Tests for wx4/cache_io.py - file_key(), load_cache(), save_cache().
"""

import json
import time
from pathlib import Path


class TestFileKey:
    def test_format_is_name_pipe_size_pipe_mtime(self, tmp_path):
        from wx4.cache_io import file_key

        f = tmp_path / "test.wav"
        f.write_bytes(b"data")
        key = file_key(f)
        parts = key.split("|")
        assert len(parts) == 3
        assert parts[0] == "test.wav"
        assert parts[1] == "4"  # 4 bytes

    def test_two_equal_files_same_key(self, tmp_path):
        from wx4.cache_io import file_key

        f = tmp_path / "a.wav"
        f.write_bytes(b"data")
        assert file_key(f) == file_key(f)

    def test_different_content_different_key(self, tmp_path):
        from wx4.cache_io import file_key

        f1 = tmp_path / "a.wav"
        f2 = tmp_path / "b.wav"
        f1.write_bytes(b"data1")
        time.sleep(0.02)
        f2.write_bytes(b"data22")
        assert file_key(f1) != file_key(f2)


class TestLoadCache:
    def test_missing_file_returns_empty_dict(self, tmp_path):
        from wx4.cache_io import load_cache

        assert load_cache(tmp_path / "nonexistent.json") == {}

    def test_corrupt_json_returns_empty_dict(self, tmp_path):
        from wx4.cache_io import load_cache

        f = tmp_path / "cache.json"
        f.write_text("not json", encoding="utf-8")
        assert load_cache(f) == {}

    def test_valid_json_loaded_correctly(self, tmp_path):
        from wx4.cache_io import load_cache

        f = tmp_path / "cache.json"
        f.write_text(json.dumps({"key": "value"}), encoding="utf-8")
        assert load_cache(f) == {"key": "value"}

    def test_custom_path_used(self, tmp_path):
        from wx4.cache_io import load_cache

        custom = tmp_path / "custom_cache.json"
        custom.write_text(json.dumps({"x": 1}), encoding="utf-8")
        assert load_cache(custom) == {"x": 1}


class TestSaveCache:
    def test_file_written_as_json(self, tmp_path):
        from wx4.cache_io import save_cache

        f = tmp_path / "cache.json"
        save_cache({"a": 1}, f)
        assert f.exists()
        assert json.loads(f.read_text(encoding="utf-8")) == {"a": 1}

    def test_roundtrip_save_then_load(self, tmp_path):
        from wx4.cache_io import load_cache, save_cache

        f = tmp_path / "cache.json"
        original = {"key": "val", "num": 42}
        save_cache(original, f)
        assert load_cache(f) == original

    def test_custom_path_used(self, tmp_path):
        from wx4.cache_io import save_cache

        custom = tmp_path / "my_cache.json"
        save_cache({"test": True}, custom)
        assert custom.exists()
