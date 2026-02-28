from pathlib import Path
import pytest
from wx41.steps.normalize import normalize_step
from wx41.tests.conftest import make_ctx

class TestNormalizeStepWalkingSkeleton:
    def test_happy_path(self, tmp_path, monkeypatch):
        ctx = make_ctx(tmp_path)
        normalized_path = tmp_path / "audio_normalized.m4a"
        
        # Nullables/Mocks for infrastructure
        monkeypatch.setattr("wx41.audio_extract.extract_to_wav", lambda src, dst: True)
        monkeypatch.setattr("wx41.audio_normalize.normalize_lufs", lambda src, dst, **kw: None)
        monkeypatch.setattr("wx41.audio_encode.to_aac", lambda src, dst, **kw: (dst.touch(), True)[1])
        
        result = normalize_step(ctx)
        
        assert result.normalized == normalized_path, f"normalized_path incorrecto: {result.normalized}"
        assert result.normalized.exists(), f"archivo no creado: {result.normalized}"
        assert "normalize" in result.timings, f"timings actuales: {result.timings}"
        assert result.timings["normalize"] >= 0, f"timing invalido: {result.timings['normalize']}"
