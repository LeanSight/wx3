"""
Tests for wx4/pipeline.py - Pipeline class and build_steps() factory.
"""

import dataclasses
from unittest.mock import MagicMock, call, patch

import pytest

from wx4.context import PipelineContext


def _ctx(tmp_path) -> PipelineContext:
    src = tmp_path / "audio.mp3"
    src.write_bytes(b"audio")
    return PipelineContext(src=src)


class TestPipeline:
    def test_empty_steps_returns_context_unchanged(self, tmp_path):
        from wx4.pipeline import Pipeline

        ctx = _ctx(tmp_path)
        result = Pipeline([]).run(ctx)
        assert result is ctx

    def test_single_step_applied(self, tmp_path):
        from wx4.pipeline import Pipeline

        ctx = _ctx(tmp_path)
        new_ctx = dataclasses.replace(ctx, srt_mode="sentences")
        step = MagicMock(return_value=new_ctx)
        result = Pipeline([step]).run(ctx)
        step.assert_called_once_with(ctx)
        assert result.srt_mode == "sentences"

    def test_steps_applied_in_order(self, tmp_path):
        from wx4.pipeline import Pipeline

        ctx = _ctx(tmp_path)
        order = []

        def step_a(c):
            order.append("a")
            return dataclasses.replace(c, srt_mode="a")

        def step_b(c):
            order.append("b")
            return dataclasses.replace(c, srt_mode="b")

        Pipeline([step_a, step_b]).run(ctx)
        assert order == ["a", "b"]

    def test_exception_from_step_propagates(self, tmp_path):
        from wx4.pipeline import Pipeline

        ctx = _ctx(tmp_path)
        boom = MagicMock(side_effect=RuntimeError("boom"))
        with pytest.raises(RuntimeError, match="boom"):
            Pipeline([boom]).run(ctx)


class TestBuildSteps:
    def test_default_has_cache_check_enhance_cache_save_transcribe_srt(self):
        from wx4.pipeline import build_steps
        from wx4.steps import (
            cache_check_step,
            cache_save_step,
            enhance_step,
            srt_step,
            transcribe_step,
        )

        steps = build_steps()
        assert cache_check_step in steps
        assert enhance_step in steps
        assert cache_save_step in steps
        assert transcribe_step in steps
        assert srt_step in steps

    def test_skip_enhance_removes_cache_and_enhance_steps(self):
        from wx4.pipeline import build_steps
        from wx4.steps import cache_check_step, cache_save_step, enhance_step

        steps = build_steps(skip_enhance=True)
        assert cache_check_step not in steps
        assert enhance_step not in steps
        assert cache_save_step not in steps

    def test_videooutput_appends_video_step(self):
        from wx4.pipeline import build_steps
        from wx4.steps import video_step

        steps = build_steps(videooutput=True)
        assert video_step in steps
        assert steps[-1] is video_step

    def test_no_video_step_when_videooutput_false(self):
        from wx4.pipeline import build_steps
        from wx4.steps import video_step

        steps = build_steps(videooutput=False)
        assert video_step not in steps

    def test_all_flags_combined(self):
        from wx4.pipeline import build_steps
        from wx4.steps import (
            cache_check_step,
            cache_save_step,
            enhance_step,
            srt_step,
            transcribe_step,
            video_step,
        )

        steps = build_steps(skip_enhance=True, videooutput=True)
        assert cache_check_step not in steps
        assert enhance_step not in steps
        assert transcribe_step in steps
        assert srt_step in steps
        assert video_step in steps
