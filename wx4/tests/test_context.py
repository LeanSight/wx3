"""
Tests for wx4/context.py - PipelineContext dataclass and Step type alias.
"""

import dataclasses
from pathlib import Path


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
        assert ctx.skip_enhance is False
        assert ctx.force is False
        assert ctx.language is None
        assert ctx.speakers is None
        assert ctx.speaker_names == {}
        assert ctx.videooutput is False
        assert ctx.enhanced is None
        assert ctx.transcript_txt is None
        assert ctx.transcript_json is None
        assert ctx.srt is None
        assert ctx.video_out is None
        assert ctx.cache_hit is False
        assert ctx.cv is None

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
