"""
Tests for wx4/pipeline.py - Pipeline class and build_steps() factory.
"""

import dataclasses
from pathlib import Path
from unittest.mock import MagicMock, call, patch

import pytest

from wx4.context import PipelineConfig, PipelineContext


def _ctx(tmp_path) -> PipelineContext:
    src = tmp_path / "audio.mp3"
    src.write_bytes(b"audio")
    return PipelineContext(src=src)


# ---------------------------------------------------------------------------
# TestNamedStep
# ---------------------------------------------------------------------------


class TestNamedStep:
    def test_callable_delegates_to_fn(self, tmp_path):
        from wx4.pipeline import NamedStep

        ctx = _ctx(tmp_path)
        fn = MagicMock(return_value=ctx)
        step = NamedStep(name="my_step", fn=fn)
        result = step(ctx)
        fn.assert_called_once_with(ctx)
        assert result is ctx

    def test_name_attribute(self):
        from wx4.pipeline import NamedStep

        step = NamedStep(name="my_step", fn=lambda ctx: ctx)
        assert step.name == "my_step"

    def test_output_path_returns_none_when_no_output_fn(self, tmp_path):
        from wx4.pipeline import NamedStep

        ctx = _ctx(tmp_path)
        step = NamedStep(name="s", fn=lambda c: c)
        assert step.output_path(ctx) is None

    def test_output_path_computed_from_fn(self, tmp_path):
        from wx4.pipeline import NamedStep

        ctx = _ctx(tmp_path)
        expected = ctx.src.parent / "out.json"
        step = NamedStep(
            name="s", fn=lambda c: c, output_fn=lambda c: c.src.parent / "out.json"
        )
        assert step.output_path(ctx) == expected


# ---------------------------------------------------------------------------
# TestPipeline (plain steps still work)
# ---------------------------------------------------------------------------


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
        step.assert_called_once()
        # step receives ctx with step_progress injected; src must be unchanged
        assert step.call_args.args[0].src == ctx.src
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


# ---------------------------------------------------------------------------
# TestPipelineCallbacks
# ---------------------------------------------------------------------------


def _make_cb():
    cb = MagicMock()
    cb.on_pipeline_start = MagicMock()
    cb.on_step_start = MagicMock()
    cb.on_step_end = MagicMock()
    cb.on_step_skipped = MagicMock()
    cb.on_pipeline_end = MagicMock()
    return cb


class TestPipelineCallbacks:
    def test_on_pipeline_start_called_with_step_names(self, tmp_path):
        from wx4.pipeline import NamedStep, Pipeline

        ctx = _ctx(tmp_path)
        cb = _make_cb()
        step = NamedStep(name="alpha", fn=lambda c: c)
        Pipeline([step], callbacks=[cb]).run(ctx)
        cb.on_pipeline_start.assert_called_once_with(["alpha"], ctx)

    def test_on_step_start_called_for_each_step(self, tmp_path):
        from wx4.pipeline import NamedStep, Pipeline

        ctx = _ctx(tmp_path)
        cb = _make_cb()
        s1 = NamedStep(name="s1", fn=lambda c: c)
        s2 = NamedStep(name="s2", fn=lambda c: c)
        Pipeline([s1, s2], callbacks=[cb]).run(ctx)
        assert cb.on_step_start.call_count == 2
        names_called = [c.args[0] for c in cb.on_step_start.call_args_list]
        assert names_called == ["s1", "s2"]

    def test_on_step_end_called_for_each_step(self, tmp_path):
        from wx4.pipeline import NamedStep, Pipeline

        ctx = _ctx(tmp_path)
        cb = _make_cb()
        s1 = NamedStep(name="s1", fn=lambda c: c)
        s2 = NamedStep(name="s2", fn=lambda c: c)
        Pipeline([s1, s2], callbacks=[cb]).run(ctx)
        assert cb.on_step_end.call_count == 2

    def test_on_step_skipped_called_when_output_exists(self, tmp_path):
        from wx4.pipeline import NamedStep, Pipeline

        ctx = _ctx(tmp_path)
        out = tmp_path / "out.json"
        out.write_text("{}", encoding="utf-8")
        cb = _make_cb()
        step = NamedStep(name="transcribe", fn=MagicMock(), output_fn=lambda c: out)
        Pipeline([step], callbacks=[cb]).run(ctx)
        cb.on_step_skipped.assert_called_once()
        cb.on_step_start.assert_not_called()
        step.fn.assert_not_called()

    def test_multiple_callbacks_all_called(self, tmp_path):
        from wx4.pipeline import NamedStep, Pipeline

        ctx = _ctx(tmp_path)
        cb1 = _make_cb()
        cb2 = _make_cb()
        step = NamedStep(name="s", fn=lambda c: c)
        Pipeline([step], callbacks=[cb1, cb2]).run(ctx)
        cb1.on_step_start.assert_called_once()
        cb2.on_step_start.assert_called_once()

    def test_exception_in_step_does_not_call_on_step_end(self, tmp_path):
        from wx4.pipeline import NamedStep, Pipeline

        ctx = _ctx(tmp_path)
        cb = _make_cb()
        step = NamedStep(name="boom", fn=MagicMock(side_effect=RuntimeError("oops")))
        with pytest.raises(RuntimeError):
            Pipeline([step], callbacks=[cb]).run(ctx)
        cb.on_step_end.assert_not_called()

    def test_on_pipeline_end_called(self, tmp_path):
        from wx4.pipeline import NamedStep, Pipeline

        ctx = _ctx(tmp_path)
        cb = _make_cb()
        Pipeline([NamedStep(name="s", fn=lambda c: c)], callbacks=[cb]).run(ctx)
        cb.on_pipeline_end.assert_called_once()


# ---------------------------------------------------------------------------
# TestPipelineResume
# ---------------------------------------------------------------------------


class TestPipelineResume:
    def test_step_skipped_when_output_exists_and_no_force(self, tmp_path):
        from wx4.pipeline import NamedStep, Pipeline

        ctx = _ctx(tmp_path)
        assert ctx.force is False
        out = tmp_path / "result.json"
        out.write_text("{}", encoding="utf-8")
        fn = MagicMock(return_value=ctx)
        step = NamedStep(name="transcribe", fn=fn, output_fn=lambda c: out)
        Pipeline([step]).run(ctx)
        fn.assert_not_called()

    def test_step_not_skipped_when_force_true(self, tmp_path):
        from wx4.pipeline import NamedStep, Pipeline

        ctx = dataclasses.replace(_ctx(tmp_path), force=True)
        out = tmp_path / "result.json"
        out.write_text("{}", encoding="utf-8")
        fn = MagicMock(return_value=ctx)
        step = NamedStep(name="transcribe", fn=fn, output_fn=lambda c: out)
        Pipeline([step]).run(ctx)
        fn.assert_called_once()

    def test_step_not_skipped_when_output_does_not_exist(self, tmp_path):
        from wx4.pipeline import NamedStep, Pipeline

        ctx = _ctx(tmp_path)
        out = tmp_path / "result.json"  # does not exist
        fn = MagicMock(return_value=ctx)
        step = NamedStep(name="transcribe", fn=fn, output_fn=lambda c: out)
        Pipeline([step]).run(ctx)
        fn.assert_called_once()

    def test_ctx_not_modified_when_step_skipped(self, tmp_path):
        from wx4.pipeline import NamedStep, Pipeline

        ctx = _ctx(tmp_path)
        out = tmp_path / "result.json"
        out.write_text("{}", encoding="utf-8")
        # fn would replace ctx with a different one, but it won't run
        new_ctx = dataclasses.replace(ctx, srt_mode="sentences")
        step = NamedStep(
            name="s", fn=MagicMock(return_value=new_ctx), output_fn=lambda c: out
        )
        result = Pipeline([step]).run(ctx)
        assert result.srt_mode == ctx.srt_mode  # unchanged

    def test_step_without_output_fn_never_skipped(self, tmp_path):
        from wx4.pipeline import NamedStep, Pipeline

        ctx = _ctx(tmp_path)
        fn = MagicMock(return_value=ctx)
        # no output_fn -> always runs
        step = NamedStep(name="cache_check", fn=fn)
        Pipeline([step]).run(ctx)
        fn.assert_called_once()


# ---------------------------------------------------------------------------
# TestBuildSteps  (uses .fn to unwrap NamedStep)
# ---------------------------------------------------------------------------


class TestBuildSteps:
    def _fns(self, steps):
        from wx4.pipeline import NamedStep

        return [s.fn if isinstance(s, NamedStep) else s for s in steps]

    def test_default_has_cache_check_enhance_cache_save_transcribe_srt(self):
        from wx4.pipeline import build_steps
        from wx4.steps import (
            cache_check_step,
            cache_save_step,
            enhance_step,
            srt_step,
            transcribe_step,
        )

        fns = self._fns(build_steps())
        assert cache_check_step in fns
        assert enhance_step in fns
        assert cache_save_step in fns
        assert transcribe_step in fns
        assert srt_step in fns

    def test_skip_enhance_removes_cache_and_enhance_steps(self):
        from wx4.pipeline import build_steps
        from wx4.steps import cache_check_step, cache_save_step, enhance_step

        fns = self._fns(build_steps(PipelineConfig(skip_enhance=True)))
        assert cache_check_step not in fns
        assert enhance_step not in fns
        assert cache_save_step not in fns

    def test_videooutput_appends_video_step(self):
        from wx4.pipeline import NamedStep, build_steps
        from wx4.steps import video_step

        steps = build_steps(PipelineConfig(videooutput=True))
        fns = self._fns(steps)
        assert video_step in fns
        last = steps[-1]
        assert (last.fn if isinstance(last, NamedStep) else last) is video_step

    def test_no_video_step_when_videooutput_false(self):
        from wx4.pipeline import build_steps
        from wx4.steps import video_step

        fns = self._fns(build_steps(PipelineConfig(videooutput=False)))
        assert video_step not in fns

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

        fns = self._fns(
            build_steps(PipelineConfig(skip_enhance=True, videooutput=True))
        )
        assert cache_check_step not in fns
        assert enhance_step not in fns
        assert transcribe_step in fns
        assert srt_step in fns
        assert video_step in fns

    def test_steps_are_named_steps(self):
        from wx4.pipeline import NamedStep, build_steps

        steps = build_steps()
        assert all(isinstance(s, NamedStep) for s in steps)

    def test_enhance_step_has_output_fn(self):
        from wx4.pipeline import NamedStep, build_steps
        from wx4.steps import enhance_step

        steps = build_steps()
        enhance = next(
            s for s in steps if isinstance(s, NamedStep) and s.fn is enhance_step
        )
        assert enhance.output_fn is not None

    def test_transcribe_step_has_output_fn(self):
        from wx4.pipeline import NamedStep, build_steps
        from wx4.steps import transcribe_step

        steps = build_steps()
        tr = next(
            s for s in steps if isinstance(s, NamedStep) and s.fn is transcribe_step
        )
        assert tr.output_fn is not None

    def test_compress_flag_appends_compress_step(self):
        from wx4.pipeline import build_steps
        from wx4.steps import compress_step

        fns = self._fns(build_steps(PipelineConfig(compress_ratio=0.4)))
        assert compress_step in fns

    def test_no_compress_step_when_compress_false(self):
        from wx4.pipeline import build_steps
        from wx4.steps import compress_step

        fns = self._fns(build_steps(PipelineConfig(compress_ratio=None)))
        assert compress_step not in fns

    def test_compress_step_is_last_when_no_videooutput(self):
        from wx4.pipeline import NamedStep, build_steps
        from wx4.steps import compress_step

        steps = build_steps(PipelineConfig(compress_ratio=0.4, videooutput=False))
        last = steps[-1]
        fn = last.fn if isinstance(last, NamedStep) else last
        assert fn is compress_step

    def test_compress_step_is_last_even_with_videooutput(self):
        """compress always goes after video, compressing the ORIGINAL src."""
        from wx4.pipeline import NamedStep, build_steps
        from wx4.steps import compress_step

        steps = build_steps(PipelineConfig(compress_ratio=0.4, videooutput=True))
        last = steps[-1]
        fn = last.fn if isinstance(last, NamedStep) else last
        assert fn is compress_step

    def test_compress_step_has_output_fn(self):
        from wx4.pipeline import NamedStep, build_steps
        from wx4.steps import compress_step

        steps = build_steps(PipelineConfig(compress_ratio=0.4))
        step = next(
            s for s in steps if isinstance(s, NamedStep) and s.fn is compress_step
        )
        assert step.output_fn is not None

    def test_default_has_normalize_step(self):
        from wx4.pipeline import build_steps
        from wx4.steps import normalize_step

        fns = self._fns(build_steps())
        assert normalize_step in fns

    def test_skip_normalize_removes_normalize_step(self):
        from wx4.pipeline import build_steps
        from wx4.steps import normalize_step

        fns = self._fns(build_steps(PipelineConfig(skip_normalize=True)))
        assert normalize_step not in fns

    def test_skip_normalize_keeps_enhance_step(self):
        from wx4.pipeline import build_steps
        from wx4.steps import enhance_step

        fns = self._fns(build_steps(PipelineConfig(skip_normalize=True)))
        assert enhance_step in fns

    def test_skip_normalize_and_skip_enhance_removes_both(self):
        from wx4.pipeline import build_steps
        from wx4.steps import normalize_step, enhance_step

        fns = self._fns(
            build_steps(PipelineConfig(skip_normalize=True, skip_enhance=True))
        )
        assert normalize_step not in fns
        assert enhance_step not in fns

    def test_normalize_comes_before_enhance(self):
        from wx4.pipeline import build_steps, NamedStep
        from wx4.steps import normalize_step, enhance_step

        steps = build_steps()
        fns = self._fns(steps)
        assert fns.index(normalize_step) < fns.index(enhance_step)

    def test_normalize_step_has_output_fn(self):
        from wx4.pipeline import NamedStep, build_steps
        from wx4.steps import normalize_step

        steps = build_steps()
        norm = next(
            s for s in steps if isinstance(s, NamedStep) and s.fn is normalize_step
        )
        assert norm.output_fn is not None


# ---------------------------------------------------------------------------
# TestStepProgressInjection
# ---------------------------------------------------------------------------


class TestStepProgressInjection:
    """Pipeline injects step_progress into ctx before each step runs."""

    def test_step_receives_step_progress_callable(self, tmp_path):
        from wx4.pipeline import NamedStep, Pipeline

        ctx = _ctx(tmp_path)
        received = {}

        def capture_step(c):
            received["progress"] = c.step_progress
            return c

        Pipeline([NamedStep("test", capture_step)]).run(ctx)
        assert callable(received["progress"])

    def test_step_progress_calls_on_step_progress_on_callback(self, tmp_path):
        from wx4.pipeline import NamedStep, Pipeline

        ctx = _ctx(tmp_path)
        calls = []

        class ProgressCapture:
            def on_pipeline_start(self, names, ctx):
                pass

            def on_step_start(self, name, ctx):
                pass

            def on_step_end(self, name, ctx):
                pass

            def on_step_skipped(self, name, ctx):
                pass

            def on_pipeline_end(self, ctx):
                pass

            def on_step_progress(self, name, done, total):
                calls.append((name, done, total))

        fired_progress = {}

        def step_that_fires_progress(c):
            c.step_progress(3, 10)
            return c

        cb = ProgressCapture()
        Pipeline([NamedStep("enhance", step_that_fires_progress)], callbacks=[cb]).run(
            ctx
        )
        assert calls == [("enhance", 3, 10)]

    def test_step_progress_ignored_when_callback_lacks_method(self, tmp_path):
        """Callbacks without on_step_progress don't raise."""
        from wx4.pipeline import NamedStep, Pipeline

        ctx = _ctx(tmp_path)

        def step_fires_progress(c):
            c.step_progress(1, 5)
            return c

        cb = _make_cb()  # MagicMock without on_step_progress attribute
        del cb.on_step_progress  # ensure attribute is absent
        Pipeline([NamedStep("s", step_fires_progress)], callbacks=[cb]).run(ctx)
        # no exception = pass

    def test_step_progress_injected_per_step_with_correct_name(self, tmp_path):
        from wx4.pipeline import NamedStep, Pipeline

        ctx = _ctx(tmp_path)
        progress_names = []

        class NameCapture:
            def on_pipeline_start(self, names, ctx):
                pass

            def on_step_start(self, name, ctx):
                pass

            def on_step_end(self, name, ctx):
                pass

            def on_step_skipped(self, name, ctx):
                pass

            def on_pipeline_end(self, ctx):
                pass

            def on_step_progress(self, name, done, total):
                progress_names.append(name)

        def step_a(c):
            c.step_progress(1, 1)
            return c

        def step_b(c):
            c.step_progress(1, 1)
            return c

        cb = NameCapture()
        Pipeline(
            [NamedStep("alpha", step_a), NamedStep("beta", step_b)], callbacks=[cb]
        ).run(ctx)
        assert progress_names == ["alpha", "beta"]
