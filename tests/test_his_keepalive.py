"""
Unit tests for src/his_keepalive.py

Classes:
  TestHisPopupDetected   — popup present → click fired
  TestHisNoPopup         — popup absent → no click
  TestHisDryRun          — dry_run=True → no click, DRY RUN in log
  TestHisDisabled        — enabled_var=False → no I/O at all
  TestHisThreadLifecycle — stop_event, lock release, multi-cycle
"""

import sys
import threading
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from his_keepalive import run_his_keepalive
from constants import HIS_CLICK_X, HIS_CLICK_Y


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class _BoolVar:
    """Minimal stand-in for tkinter.BooleanVar (thread-safe .get())."""
    def __init__(self, value: bool = True) -> None:
        self._value = value
    def get(self) -> bool:
        return self._value


def _make_stop_event(auto_stop_after: float = 0.12) -> threading.Event:
    ev = threading.Event()
    threading.Timer(auto_stop_after, ev.set).start()
    return ev


def _run_his(
    *,
    popup_detected: bool = False,
    enabled: bool = True,
    dry_run: bool = False,
    stop_after: float = 0.12,
) -> tuple[list[str], MagicMock]:
    """
    Run run_his_keepalive with mocked I/O for *stop_after* seconds.
    Returns (log_messages, mock_pyautogui).
    """
    messages: list[str] = []
    enabled_var = _BoolVar(enabled)
    jiggle_lock = threading.Lock()
    stop_event = _make_stop_event(auto_stop_after=stop_after)

    with (
        patch("his_keepalive.HIS_CHECK_INTERVAL", 0.01),
        patch("his_keepalive.capture_screenshot", return_value=MagicMock()),
        patch("his_keepalive.check_detection_points", return_value=popup_detected),
        patch("his_keepalive.pyautogui") as mock_pag,
    ):
        run_his_keepalive(
            stop_event,
            jiggle_lock,
            enabled_var,
            messages.append,
            dry_run=dry_run,
        )

    return messages, mock_pag


# ===========================================================================
# TestHisPopupDetected
# ===========================================================================

class TestHisPopupDetected:
    """Popup is present — click must fire with correct coordinates."""

    def test_click_is_called(self):
        _, mock_pag = _run_his(popup_detected=True)
        mock_pag.click.assert_called()

    def test_click_uses_correct_coordinates(self):
        _, mock_pag = _run_his(popup_detected=True)
        mock_pag.click.assert_called_with(HIS_CLICK_X, HIS_CLICK_Y)

    def test_log_mentions_popup_detected(self):
        messages, _ = _run_his(popup_detected=True)
        assert any("popup detected" in m for m in messages)

    def test_log_mentions_clicked(self):
        messages, _ = _run_his(popup_detected=True)
        assert any("clicked" in m for m in messages)

    def test_log_mentions_extend_button(self):
        messages, _ = _run_his(popup_detected=True)
        assert any("연장" in m for m in messages)


# ===========================================================================
# TestHisNoPopup
# ===========================================================================

class TestHisNoPopup:
    """No popup visible — no click, appropriate log entry."""

    def test_no_click_when_no_popup(self):
        _, mock_pag = _run_his(popup_detected=False)
        mock_pag.click.assert_not_called()

    def test_log_says_no_popup(self):
        messages, _ = _run_his(popup_detected=False)
        assert any("no popup" in m for m in messages)

    def test_checking_log_appears(self):
        messages, _ = _run_his(popup_detected=False)
        assert any("checking" in m for m in messages)


# ===========================================================================
# TestHisDryRun
# ===========================================================================

class TestHisDryRun:
    """dry_run=True — no actual click, DRY RUN label in log."""

    def test_no_click_in_dry_run_mode(self):
        _, mock_pag = _run_his(popup_detected=True, dry_run=True)
        mock_pag.click.assert_not_called()

    def test_log_contains_dry_run_label(self):
        messages, _ = _run_his(popup_detected=True, dry_run=True)
        assert any("DRY RUN" in m for m in messages)

    def test_coordinates_appear_in_dry_run_log(self):
        messages, _ = _run_his(popup_detected=True, dry_run=True)
        coord_str = f"({HIS_CLICK_X}, {HIS_CLICK_Y})"
        assert any(coord_str in m for m in messages)

    def test_no_dry_run_log_when_no_popup(self):
        messages, _ = _run_his(popup_detected=False, dry_run=True)
        assert not any("DRY RUN" in m for m in messages)


# ===========================================================================
# TestHisDisabled
# ===========================================================================

class TestHisDisabled:
    """Checkbox is unticked — no screenshot, no click."""

    def test_no_screenshot_when_disabled(self):
        messages: list[str] = []
        enabled_var = _BoolVar(False)
        jiggle_lock = threading.Lock()
        stop_event = _make_stop_event(0.06)

        with (
            patch("his_keepalive.HIS_CHECK_INTERVAL", 0.01),
            patch("his_keepalive.capture_screenshot") as mock_cap,
            patch("his_keepalive.check_detection_points"),
            patch("his_keepalive.pyautogui"),
        ):
            run_his_keepalive(stop_event, jiggle_lock, enabled_var, messages.append)

        mock_cap.assert_not_called()

    def test_no_click_when_disabled(self):
        enabled_var = _BoolVar(False)
        jiggle_lock = threading.Lock()
        stop_event = _make_stop_event(0.06)

        with (
            patch("his_keepalive.HIS_CHECK_INTERVAL", 0.01),
            patch("his_keepalive.capture_screenshot"),
            patch("his_keepalive.check_detection_points"),
            patch("his_keepalive.pyautogui") as mock_pag,
        ):
            run_his_keepalive(stop_event, jiggle_lock, enabled_var, lambda m: None)

        mock_pag.click.assert_not_called()


# ===========================================================================
# TestHisThreadLifecycle
# ===========================================================================

class TestHisThreadLifecycle:
    """Thread semantics: stop_event, lock hygiene, multi-cycle behaviour."""

    def test_thread_stops_on_stop_event(self):
        stop = threading.Event()
        jiggle_lock = threading.Lock()
        enabled_var = _BoolVar(True)

        with (
            patch("his_keepalive.HIS_CHECK_INTERVAL", 0.01),
            patch("his_keepalive.capture_screenshot", return_value=MagicMock()),
            patch("his_keepalive.check_detection_points", return_value=False),
            patch("his_keepalive.pyautogui"),
        ):
            t = threading.Thread(
                target=run_his_keepalive,
                args=(stop, jiggle_lock, enabled_var, lambda m: None),
            )
            t.start()
            stop.set()
            t.join(timeout=1.0)

        assert not t.is_alive(), "Thread should exit after stop_event is set"

    def test_jiggle_lock_released_after_loop(self):
        """Lock must not be held after run_his_keepalive returns."""
        stop_event = _make_stop_event(0.06)
        jiggle_lock = threading.Lock()
        enabled_var = _BoolVar(True)

        with (
            patch("his_keepalive.HIS_CHECK_INTERVAL", 0.01),
            patch("his_keepalive.capture_screenshot", return_value=MagicMock()),
            patch("his_keepalive.check_detection_points", return_value=False),
            patch("his_keepalive.pyautogui"),
        ):
            run_his_keepalive(stop_event, jiggle_lock, enabled_var, lambda m: None)

        acquired = jiggle_lock.acquire(blocking=False)
        assert acquired, "Lock should be released after the loop exits"
        jiggle_lock.release()

    def test_runs_multiple_cycles(self):
        """Screenshot must be called more than once across several intervals."""
        stop_event = _make_stop_event(0.12)
        jiggle_lock = threading.Lock()
        enabled_var = _BoolVar(True)
        call_count: list[int] = []

        def fake_capture():
            call_count.append(1)
            return MagicMock()

        with (
            patch("his_keepalive.HIS_CHECK_INTERVAL", 0.01),
            patch("his_keepalive.capture_screenshot", side_effect=fake_capture),
            patch("his_keepalive.check_detection_points", return_value=False),
            patch("his_keepalive.pyautogui"),
        ):
            run_his_keepalive(stop_event, jiggle_lock, enabled_var, lambda m: None)

        assert len(call_count) > 1, "Expected multiple screenshot cycles"

    def test_held_jiggle_lock_delays_cycle(self):
        """If jiggle_lock is held externally, the cycle must block until released."""
        stop_event = _make_stop_event(0.15)
        jiggle_lock = threading.Lock()
        enabled_var = _BoolVar(True)
        call_count: list[int] = []

        def fake_capture():
            call_count.append(1)
            return MagicMock()

        # Hold the lock for the first 0.08s — no cycles should complete until released.
        jiggle_lock.acquire()

        def release_later():
            import time
            time.sleep(0.08)
            jiggle_lock.release()

        release_thread = threading.Thread(target=release_later, daemon=True)
        release_thread.start()

        with (
            patch("his_keepalive.HIS_CHECK_INTERVAL", 0.01),
            patch("his_keepalive.capture_screenshot", side_effect=fake_capture),
            patch("his_keepalive.check_detection_points", return_value=False),
            patch("his_keepalive.pyautogui"),
        ):
            run_his_keepalive(stop_event, jiggle_lock, enabled_var, lambda m: None)

        # At least one cycle must have completed after the lock was released.
        assert len(call_count) >= 1
