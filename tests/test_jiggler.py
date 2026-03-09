"""
Unit tests for src/jiggler.py

Classes:
  TestSetKeepAwake   — _set_keep_awake() calls SetThreadExecutionState correctly
  TestJigglerLoop    — run_jiggler thread behaviour (mouse move, dry-run, stop)
"""

import sys
import threading
from pathlib import Path
from unittest.mock import MagicMock, call, patch

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import jiggler
from jiggler import _set_keep_awake, run_jiggler

_ES_CONTINUOUS       = 0x80000000
_ES_SYSTEM_REQUIRED  = 0x00000001
_ES_DISPLAY_REQUIRED = 0x00000002


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class _BoolVar:
    def __init__(self, value: bool = True):
        self._v = value
    def get(self) -> bool:
        return self._v


def _make_stop_event(auto_stop_after: float = 0.15) -> threading.Event:
    ev = threading.Event()
    threading.Timer(auto_stop_after, ev.set).start()
    return ev


def _run_jiggler(*, enabled=True, dry_run=False, stop_after=0.15, interval_patch=0.02):
    """Run one cycle of run_jiggler with patched interval and mocked pyautogui."""
    messages = []
    enabled_var = _BoolVar(enabled)
    stop_event = _make_stop_event(stop_after)
    jiggle_lock = threading.Lock()
    jiggle_in_progress = threading.Event()

    with (
        patch.object(jiggler, "JIGGLE_INTERVAL", interval_patch),
        patch.object(jiggler, "_PYAUTOGUI_AVAILABLE", True),
        patch.object(jiggler, "pyautogui") as mock_pag,
        patch("jiggler._set_keep_awake") as mock_awake,
    ):
        run_jiggler(
            stop_event, jiggle_lock, jiggle_in_progress,
            enabled_var, messages.append, dry_run=dry_run,
        )
    return messages, mock_pag, mock_awake


# ===========================================================================
# TestSetKeepAwake
# ===========================================================================

class TestSetKeepAwake:
    """_set_keep_awake() passes the right flags to SetThreadExecutionState."""

    def test_enable_sets_display_and_system_flags(self):
        mock_fn = MagicMock()
        with patch("ctypes.windll", create=True) as mock_windll:
            mock_windll.kernel32.SetThreadExecutionState = mock_fn
            _set_keep_awake(True)
        expected = _ES_CONTINUOUS | _ES_SYSTEM_REQUIRED | _ES_DISPLAY_REQUIRED
        mock_fn.assert_called_once_with(expected)

    def test_disable_sets_continuous_only(self):
        mock_fn = MagicMock()
        with patch("ctypes.windll", create=True) as mock_windll:
            mock_windll.kernel32.SetThreadExecutionState = mock_fn
            _set_keep_awake(False)
        mock_fn.assert_called_once_with(_ES_CONTINUOUS)

    def test_no_exception_on_non_windows(self):
        """_set_keep_awake must be silent when ctypes.windll is absent (Linux)."""
        # windll is absent on Linux; _set_keep_awake catches AttributeError.
        _set_keep_awake(True)   # must not raise
        _set_keep_awake(False)  # must not raise


# ===========================================================================
# TestJigglerLoop
# ===========================================================================

class TestJigglerLoop:
    """run_jiggler thread: keep-awake lifecycle and mouse move behaviour."""

    def test_keep_awake_enabled_on_start(self):
        _, _, mock_awake = _run_jiggler()
        assert mock_awake.call_args_list[0] == call(True)

    def test_keep_awake_disabled_on_stop(self):
        _, _, mock_awake = _run_jiggler()
        assert mock_awake.call_args_list[-1] == call(False)

    def test_mouse_moved_when_enabled(self):
        _, mock_pag, _ = _run_jiggler(enabled=True)
        mock_pag.moveRel.assert_called()

    def test_no_mouse_move_when_disabled(self):
        _, mock_pag, _ = _run_jiggler(enabled=False)
        mock_pag.moveRel.assert_not_called()

    def test_dry_run_logs_without_moving(self):
        messages, mock_pag, _ = _run_jiggler(dry_run=True)
        mock_pag.moveRel.assert_not_called()
        assert any("DRY RUN" in m for m in messages)

    def test_thread_stops_on_stop_event(self):
        """run_jiggler must return (not hang) when stop_event is set."""
        done = threading.Event()
        stop_event = threading.Event()
        stop_event.set()  # set immediately

        def _target():
            with (
                patch.object(jiggler, "JIGGLE_INTERVAL", 60),
                patch.object(jiggler, "_PYAUTOGUI_AVAILABLE", True),
                patch.object(jiggler, "pyautogui"),
                patch("jiggler._set_keep_awake"),
            ):
                run_jiggler(
                    stop_event, threading.Lock(), threading.Event(),
                    _BoolVar(True), lambda _: None,
                )
            done.set()

        threading.Thread(target=_target, daemon=True).start()
        assert done.wait(timeout=1.0), "run_jiggler did not exit after stop_event was set"

    def test_jiggle_in_progress_cleared_after_move(self):
        """jiggle_in_progress must be cleared even if pyautogui raises."""
        jiggle_in_progress = threading.Event()
        stop_event = _make_stop_event(0.1)
        messages = []

        with (
            patch.object(jiggler, "JIGGLE_INTERVAL", 0.02),
            patch.object(jiggler, "_PYAUTOGUI_AVAILABLE", True),
            patch.object(jiggler, "pyautogui") as mock_pag,
            patch("jiggler._set_keep_awake"),
        ):
            mock_pag.moveRel.side_effect = RuntimeError("boom")
            run_jiggler(
                stop_event, threading.Lock(), jiggle_in_progress,
                _BoolVar(True), messages.append,
            )

        assert not jiggle_in_progress.is_set()
        assert any("error" in m.lower() for m in messages)

    def test_error_during_move_does_not_kill_thread(self):
        """A pyautogui error must be logged and retried, not propagated."""
        stop_event = _make_stop_event(0.1)
        messages = []

        with (
            patch.object(jiggler, "JIGGLE_INTERVAL", 0.02),
            patch.object(jiggler, "_PYAUTOGUI_AVAILABLE", True),
            patch.object(jiggler, "pyautogui") as mock_pag,
            patch("jiggler._set_keep_awake"),
        ):
            mock_pag.moveRel.side_effect = RuntimeError("boom")
            run_jiggler(  # must return without raising
                stop_event, threading.Lock(), threading.Event(),
                _BoolVar(True), messages.append,
            )

        assert any("error" in m.lower() for m in messages)
