"""
Tests for wx4/context.py - PipelineContext dataclass and Step type alias.
"""

import dataclasses
from pathlib import Path


class TestPipelineConfig:
    def test_minimal_construction_no_args(self):
        from wx4.context import PipelineConfig

        cfg = PipelineConfig()
        assert cfg.skip_enhance is False
        assert cfg.videooutput is False
        assert cfg.compress_ratio is None

    def test_is_frozen(self):
        import pytest
        from wx4.context import PipelineConfig

        cfg = PipelineConfig()
        with pytest.raises((AttributeError, dataclasses.FrozenInstanceError)):
            cfg.skip_enhance = True

    def test_can_construct_with_flags(self):
        from wx4.context import PipelineConfig

        cfg = PipelineConfig(skip_enhance=True, videooutput=True, compress_ratio=0.4)
        assert cfg.skip_enhance is True
        assert cfg.videooutput is True
        assert cfg.compress_ratio == 0.4

    def test_skip_normalize_defaults_to_false(self):
        from wx4.context import PipelineConfig

        assert PipelineConfig().skip_normalize is False

    def test_can_set_skip_normalize(self):
        from wx4.context import PipelineConfig

        cfg = PipelineConfig(skip_normalize=True)
        assert cfg.skip_normalize is True


class TestPipelineContext:
    def test_minimal_construction_with_src(self, tmp_path):
        from wx4.context import PipelineContext

        src = tmp_path / "test.wav"
        ctx = PipelineContext(src=src)
        assert ctx.src == src

    def test_defaults_are_correct(self, tmp_path):
        from wx4.context import PipelineContext

        ctx = PipelineContext(src=tmp_path / "test.wav")
        assert ctx.srt_mode == "speaker-only"
        assert ctx.output_m4a is True
        assert ctx.force is False
        assert ctx.language is None
        assert ctx.speakers is None
        assert ctx.speaker_names == {}
        assert ctx.enhanced is None
        assert ctx.normalized is None
        assert ctx.transcript_txt is None
        assert ctx.transcript_json is None
        assert ctx.srt is None
        assert ctx.video_out is None
        assert ctx.cache_hit is False
        assert ctx.cv is None
        assert ctx.compress_ratio is None
        assert ctx.video_compressed is None

    def test_replace_creates_new_instance(self, tmp_path):
        from wx4.context import PipelineContext

        ctx = PipelineContext(src=tmp_path / "test.wav")
        ctx2 = dataclasses.replace(ctx, srt_mode="sentences")
        assert ctx.srt_mode == "speaker-only"
        assert ctx2.srt_mode == "sentences"
        assert ctx is not ctx2

    def test_timings_dict_independent(self, tmp_path):
        from wx4.context import PipelineContext

        ctx1 = PipelineContext(src=tmp_path / "test.wav")
        ctx2 = PipelineContext(src=tmp_path / "test.wav")
        ctx1.timings["a"] = 1.0
        assert "a" not in ctx2.timings

    def test_cache_dict_independent(self, tmp_path):
        from wx4.context import PipelineContext

        ctx1 = PipelineContext(src=tmp_path / "test.wav")
        ctx2 = PipelineContext(src=tmp_path / "test.wav")
        ctx1.cache["x"] = 99
        assert "x" not in ctx2.cache


class TestStep:
    def test_step_type_alias_accepts_lambda(self, tmp_path):
        from wx4.context import PipelineContext, Step

        ctx = PipelineContext(src=tmp_path / "test.wav")
        step: Step = lambda c: c
        result = step(ctx)
        assert result is ctx


class TestPipelineContextWhisperFields:
    def test_transcribe_backend_defaults_to_assemblyai(self, tmp_path):
        from wx4.context import PipelineContext

        ctx = PipelineContext(src=tmp_path / "test.wav")
        assert ctx.transcribe_backend == "assemblyai"

    def test_hf_token_defaults_to_none(self, tmp_path):
        from wx4.context import PipelineContext

        ctx = PipelineContext(src=tmp_path / "test.wav")
        assert ctx.hf_token is None

    def test_whisper_model_defaults_to_large_v3(self, tmp_path):
        from wx4.context import PipelineContext

        ctx = PipelineContext(src=tmp_path / "test.wav")
        assert ctx.whisper_model == "openai/whisper-large-v3"

    def test_device_defaults_to_auto(self, tmp_path):
        from wx4.context import PipelineContext

        ctx = PipelineContext(src=tmp_path / "test.wav")
        assert ctx.device == "auto"

    def test_can_set_whisper_backend(self, tmp_path):
        from wx4.context import PipelineContext

        ctx = PipelineContext(src=tmp_path / "test.wav", transcribe_backend="whisper")
        assert ctx.transcribe_backend == "whisper"

    def test_can_set_hf_token(self, tmp_path):
        from wx4.context import PipelineContext

        ctx = PipelineContext(src=tmp_path / "test.wav", hf_token="hf_abc123")
        assert ctx.hf_token == "hf_abc123"

    def test_can_set_whisper_model(self, tmp_path):
        from wx4.context import PipelineContext

        ctx = PipelineContext(
            src=tmp_path / "test.wav", whisper_model="openai/whisper-small"
        )
        assert ctx.whisper_model == "openai/whisper-small"

    def test_can_set_device(self, tmp_path):
        from wx4.context import PipelineContext

        ctx = PipelineContext(src=tmp_path / "test.wav", device="cpu")
        assert ctx.device == "cpu"
