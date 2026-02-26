"""
Tests for wx4/audio_enhance.py - apply_clearvoice().
cv is duck-typed: callable + .write method.
"""

from unittest.mock import MagicMock, sentinel


class TestApplyClearvoice:
    def test_calls_cv_callable_with_input_path(self, tmp_path):
        from wx4.audio_enhance import apply_clearvoice

        cv = MagicMock()
        cv.return_value = sentinel.enhanced
        src = tmp_path / "in.wav"
        dst = tmp_path / "out.wav"
        apply_clearvoice(src, dst, cv)
        cv.assert_called_once_with(input_path=str(src), online_write=False, progress_callback=None)

    def test_passes_progress_callback_to_cv(self, tmp_path):
        from wx4.audio_enhance import apply_clearvoice

        cv = MagicMock()
        cv.return_value = sentinel.enhanced
        cb = MagicMock()
        apply_clearvoice(tmp_path / "in.wav", tmp_path / "out.wav", cv, progress_callback=cb)
        assert cv.call_args.kwargs["progress_callback"] is cb

    def test_calls_cv_write_with_output_path(self, tmp_path):
        from wx4.audio_enhance import apply_clearvoice

        cv = MagicMock()
        cv.return_value = sentinel.enhanced
        src = tmp_path / "in.wav"
        dst = tmp_path / "out.wav"
        apply_clearvoice(src, dst, cv)
        cv.write.assert_called_once_with(sentinel.enhanced, output_path=str(dst))

    def test_online_write_is_false(self, tmp_path):
        from wx4.audio_enhance import apply_clearvoice

        cv = MagicMock()
        cv.return_value = sentinel.enhanced
        apply_clearvoice(tmp_path / "in.wav", tmp_path / "out.wav", cv)
        assert cv.call_args.kwargs["online_write"] is False

    def test_returns_true_on_success(self, tmp_path):
        from wx4.audio_enhance import apply_clearvoice

        cv = MagicMock()
        cv.return_value = sentinel.enhanced
        result = apply_clearvoice(tmp_path / "in.wav", tmp_path / "out.wav", cv)
        assert result is True

    def test_exception_from_cv_propagates(self, tmp_path):
        from wx4.audio_enhance import apply_clearvoice

        cv = MagicMock(side_effect=RuntimeError("cv failed"))
        try:
            apply_clearvoice(tmp_path / "in.wav", tmp_path / "out.wav", cv)
            assert False, "Should have raised"
        except RuntimeError:
            pass

    def test_exception_from_cv_write_propagates(self, tmp_path):
        from wx4.audio_enhance import apply_clearvoice

        cv = MagicMock()
        cv.return_value = sentinel.enhanced
        cv.write.side_effect = RuntimeError("write failed")
        try:
            apply_clearvoice(tmp_path / "in.wav", tmp_path / "out.wav", cv)
            assert False, "Should have raised"
        except RuntimeError:
            pass
