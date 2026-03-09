"""
Unit tests for src/intpc_keepalive.py

Classes:
  TestIsProcessRunning    — _is_process_running() psutil logic
  TestFindIntpcWindow     — _find_intpc_window() EnumWindows logic
  TestBringToFront        — _bring_to_front() win32gui call and failure handling
  TestIntpcLoopSkipCases  — process absent / window absent / user active → skip
  TestIntpcLoopForeground — bring-to-front path and stay-in-foreground path
  TestIntpcLoopDetection  — popup present/absent, dry_run
  TestIntpcThreadLifecycle — stop_event, lock hygiene, multi-cycle
"""

import sys
import threading
import time
from pathlib import Path
from unittest.mock import MagicMock, call, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import intpc_keepalive
from intpc_keepalive import (
    _bring_to_front,
    _find_intpc_window,
    _is_process_running,
    run_intpc_keepalive,
)
from constants import INTPC_CLICK_X, INTPC_CLICK_Y, INTPC_PROCESS_NAME, INTPC_WINDOW_TITLE


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class _BoolVar:
    def __init__(self, value: bool = True) -> None:
        self._value = value
    def get(self) -> bool:
        return self._value


def _make_stop_event(auto_stop_after: float = 0.12) -> threading.Event:
    ev = threading.Event()
    threading.Timer(auto_stop_after, ev.set).start()
    return ev


# Patch targets — all internal helpers are patched at the module level so
# the main loop sees the mocked versions without needing win32gui / psutil.
_PATCHES = dict(
    process_running="intpc_keepalive._is_process_running",
    find_window="intpc_keepalive._find_intpc_window",
    is_foreground="intpc_keepalive._is_foreground",
    bring_to_front="intpc_keepalive._bring_to_front",
    user_idle="intpc_keepalive.is_user_idle",
    capture="intpc_keepalive.capture_screenshot",
    detect="intpc_keepalive.check_detection_points",
    pyautogui="intpc_keepalive.pyautogui",
    interval="intpc_keepalive.INTPC_CHECK_INTERVAL",
)


def _run_intpc(
    *,
    process_running: bool = True,
    hwnd: int = 1,
    already_foreground: bool = True,
    user_idle: bool = True,
    bring_success: bool = True,
    popup_detected: bool = False,
    enabled: bool = True,
    dry_run: bool = False,
    stop_after: float = 0.12,
) -> tuple[list[str], MagicMock]:
    """
    Run run_intpc_keepalive with fully mocked environment.
    Returns (log_messages, mock_pyautogui).
    """
    messages: list[str] = []
    enabled_var = _BoolVar(enabled)
    jiggle_lock = threading.Lock()
    last_real_input_time = [time.time() - 300 if user_idle else time.time()]
    stop_event = _make_stop_event(auto_stop_after=stop_after)

    with (
        patch(_PATCHES["interval"], 0.01),
        patch(_PATCHES["process_running"], return_value=process_running),
        patch(_PATCHES["find_window"], return_value=hwnd),
        patch(_PATCHES["is_foreground"], return_value=already_foreground),
        patch(_PATCHES["bring_to_front"], return_value=bring_success),
        patch(_PATCHES["user_idle"], return_value=user_idle),
        patch(_PATCHES["capture"], return_value=MagicMock()),
        patch(_PATCHES["detect"], return_value=popup_detected),
        patch(_PATCHES["pyautogui"]) as mock_pag,
    ):
        run_intpc_keepalive(
            stop_event,
            jiggle_lock,
            last_real_input_time,
            enabled_var,
            messages.append,
            dry_run=dry_run,
        )

    return messages, mock_pag


# ===========================================================================
# TestIsProcessRunning
# ===========================================================================

class TestIsProcessRunning:
    """_is_process_running() — psutil process enumeration."""

    def test_returns_false_when_psutil_unavailable(self):
        with patch.object(intpc_keepalive, "_PSUTIL_AVAILABLE", False):
            assert _is_process_running() is False

    def test_detects_matching_process(self):
        fake_proc = MagicMock()
        fake_proc.info = {"name": INTPC_PROCESS_NAME}
        with (
            patch.object(intpc_keepalive, "_PSUTIL_AVAILABLE", True),
            patch("intpc_keepalive.psutil") as mock_psutil,
        ):
            mock_psutil.process_iter.return_value = [fake_proc]
            assert _is_process_running() is True

    def test_case_insensitive_match(self):
        fake_proc = MagicMock()
        fake_proc.info = {"name": INTPC_PROCESS_NAME.upper()}
        with (
            patch.object(intpc_keepalive, "_PSUTIL_AVAILABLE", True),
            patch("intpc_keepalive.psutil") as mock_psutil,
        ):
            mock_psutil.process_iter.return_value = [fake_proc]
            assert _is_process_running() is True

    def test_returns_false_when_process_absent(self):
        fake_proc = MagicMock()
        fake_proc.info = {"name": "notepad.exe"}
        with (
            patch.object(intpc_keepalive, "_PSUTIL_AVAILABLE", True),
            patch("intpc_keepalive.psutil") as mock_psutil,
        ):
            mock_psutil.process_iter.return_value = [fake_proc]
            assert _is_process_running() is False

    def test_returns_false_when_no_processes(self):
        with (
            patch.object(intpc_keepalive, "_PSUTIL_AVAILABLE", True),
            patch("intpc_keepalive.psutil") as mock_psutil,
        ):
            mock_psutil.process_iter.return_value = []
            assert _is_process_running() is False


# ===========================================================================
# TestFindIntpcWindow
# ===========================================================================

class TestFindIntpcWindow:
    """_find_intpc_window() — EnumWindows title search."""

    def test_returns_zero_when_win32gui_unavailable(self):
        with patch.object(intpc_keepalive, "_WIN32GUI_AVAILABLE", False):
            assert _find_intpc_window() == 0

    def test_returns_hwnd_when_title_matches(self):
        def fake_enum(callback, param):
            callback(42, None)  # hwnd=42 with matching title

        with (
            patch.object(intpc_keepalive, "_WIN32GUI_AVAILABLE", True),
            patch("intpc_keepalive.win32gui") as mock_w,
        ):
            mock_w.EnumWindows.side_effect = fake_enum
            mock_w.GetWindowText.return_value = f"prefix {INTPC_WINDOW_TITLE} suffix"
            result = _find_intpc_window()

        assert result == 42

    def test_returns_zero_when_no_title_matches(self):
        def fake_enum(callback, param):
            callback(99, None)

        with (
            patch.object(intpc_keepalive, "_WIN32GUI_AVAILABLE", True),
            patch("intpc_keepalive.win32gui") as mock_w,
        ):
            mock_w.EnumWindows.side_effect = fake_enum
            mock_w.GetWindowText.return_value = "Unrelated Window"
            result = _find_intpc_window()

        assert result == 0

    def test_title_match_is_case_insensitive(self):
        def fake_enum(callback, param):
            callback(7, None)

        with (
            patch.object(intpc_keepalive, "_WIN32GUI_AVAILABLE", True),
            patch("intpc_keepalive.win32gui") as mock_w,
        ):
            mock_w.EnumWindows.side_effect = fake_enum
            mock_w.GetWindowText.return_value = INTPC_WINDOW_TITLE.upper()
            result = _find_intpc_window()

        assert result == 7


# ===========================================================================
# TestBringToFront
# ===========================================================================

class TestBringToFront:
    """_bring_to_front() — SetForegroundWindow call and error handling."""

    def test_returns_false_when_win32gui_unavailable(self):
        with patch.object(intpc_keepalive, "_WIN32GUI_AVAILABLE", False):
            assert _bring_to_front(1) is False

    def test_returns_false_for_zero_hwnd(self):
        with patch.object(intpc_keepalive, "_WIN32GUI_AVAILABLE", True):
            assert _bring_to_front(0) is False

    def _setup_bring_mock(self, mock_w, mock_proc, mock_api, mock_con, hwnd=5):
        """Common mock setup for _bring_to_front tests."""
        mock_w.GetWindowPlacement.return_value = (0, 1, 0, (0, 0), (0, 0, 0, 0))
        mock_con.SW_SHOWMINIMIZED = 2  # placement[1]==1, so ShowWindow not called
        mock_proc.GetWindowThreadProcessId.return_value = (1, 2)
        mock_api.GetCurrentThreadId.return_value = 2  # same tid → no attach
        # Simulate foreground switch succeeding: GetForegroundWindow returns hwnd.
        mock_w.GetForegroundWindow.return_value = hwnd

    def test_calls_set_foreground_window(self):
        with (
            patch.object(intpc_keepalive, "_WIN32GUI_AVAILABLE", True),
            patch("intpc_keepalive.win32gui") as mock_w,
            patch("intpc_keepalive.win32process") as mock_proc,
            patch("intpc_keepalive.win32api") as mock_api,
            patch("intpc_keepalive.win32con") as mock_con,
        ):
            self._setup_bring_mock(mock_w, mock_proc, mock_api, mock_con)
            _bring_to_front(5)
            mock_w.SetForegroundWindow.assert_called_once_with(5)

    def test_calls_keybd_event_alt_trick(self):
        """Alt keydown+keyup must be sent before SetForegroundWindow."""
        with (
            patch.object(intpc_keepalive, "_WIN32GUI_AVAILABLE", True),
            patch("intpc_keepalive.win32gui") as mock_w,
            patch("intpc_keepalive.win32process") as mock_proc,
            patch("intpc_keepalive.win32api") as mock_api,
            patch("intpc_keepalive.win32con") as mock_con,
        ):
            self._setup_bring_mock(mock_w, mock_proc, mock_api, mock_con)
            _bring_to_front(5)
            # keybd_event must be called twice: Alt down then Alt up.
            assert mock_api.keybd_event.call_count == 2

    def test_returns_true_on_success(self):
        with (
            patch.object(intpc_keepalive, "_WIN32GUI_AVAILABLE", True),
            patch("intpc_keepalive.win32gui") as mock_w,
            patch("intpc_keepalive.win32process") as mock_proc,
            patch("intpc_keepalive.win32api") as mock_api,
            patch("intpc_keepalive.win32con") as mock_con,
        ):
            self._setup_bring_mock(mock_w, mock_proc, mock_api, mock_con)
            assert _bring_to_front(5) is True

    def test_returns_false_when_foreground_unchanged(self):
        """Return False when GetForegroundWindow != hwnd after the attempt."""
        with (
            patch.object(intpc_keepalive, "_WIN32GUI_AVAILABLE", True),
            patch("intpc_keepalive.win32gui") as mock_w,
            patch("intpc_keepalive.win32process") as mock_proc,
            patch("intpc_keepalive.win32api") as mock_api,
            patch("intpc_keepalive.win32con") as mock_con,
        ):
            self._setup_bring_mock(mock_w, mock_proc, mock_api, mock_con)
            mock_w.GetForegroundWindow.return_value = 999  # different window
            assert _bring_to_front(5) is False

    def test_returns_false_on_exception(self):
        with (
            patch.object(intpc_keepalive, "_WIN32GUI_AVAILABLE", True),
            patch("intpc_keepalive.win32gui") as mock_w,
        ):
            mock_w.GetWindowPlacement.side_effect = Exception("access denied")
            assert _bring_to_front(5) is False


# ===========================================================================
# TestIntpcLoopSkipCases
# ===========================================================================

class TestIntpcLoopSkipCases:
    """Cycles that should be skipped before any screenshot is taken."""

    def test_skips_when_process_not_running(self):
        messages, mock_pag = _run_intpc(process_running=False)
        assert any("not running" in m for m in messages)
        mock_pag.click.assert_not_called()

    def test_no_screenshot_when_process_not_running(self):
        stop_event = _make_stop_event(0.06)
        with (
            patch(_PATCHES["interval"], 0.01),
            patch(_PATCHES["process_running"], return_value=False),
            patch(_PATCHES["capture"]) as mock_cap,
            patch(_PATCHES["detect"]),
            patch(_PATCHES["pyautogui"]),
        ):
            run_intpc_keepalive(
                stop_event,
                threading.Lock(),
                [time.time()],
                _BoolVar(True),
                lambda m: None,
            )
        mock_cap.assert_not_called()

    def test_skips_when_window_not_found(self):
        messages, mock_pag = _run_intpc(hwnd=0)
        assert any("not found" in m for m in messages)
        mock_pag.click.assert_not_called()

    def test_no_screenshot_when_window_not_found(self):
        stop_event = _make_stop_event(0.06)
        with (
            patch(_PATCHES["interval"], 0.01),
            patch(_PATCHES["process_running"], return_value=True),
            patch(_PATCHES["find_window"], return_value=0),
            patch(_PATCHES["capture"]) as mock_cap,
            patch(_PATCHES["detect"]),
            patch(_PATCHES["pyautogui"]),
        ):
            run_intpc_keepalive(
                stop_event,
                threading.Lock(),
                [time.time()],
                _BoolVar(True),
                lambda m: None,
            )
        mock_cap.assert_not_called()

    def test_skips_when_user_active_and_not_foreground(self):
        messages, mock_pag = _run_intpc(
            already_foreground=False, user_idle=False
        )
        assert any("user is active" in m for m in messages)
        mock_pag.click.assert_not_called()

    def test_no_screenshot_when_user_active_and_not_foreground(self):
        stop_event = _make_stop_event(0.06)
        with (
            patch(_PATCHES["interval"], 0.01),
            patch(_PATCHES["process_running"], return_value=True),
            patch(_PATCHES["find_window"], return_value=1),
            patch(_PATCHES["is_foreground"], return_value=False),
            patch(_PATCHES["user_idle"], return_value=False),
            patch(_PATCHES["capture"]) as mock_cap,
            patch(_PATCHES["detect"]),
            patch(_PATCHES["pyautogui"]),
        ):
            run_intpc_keepalive(
                stop_event,
                threading.Lock(),
                [time.time()],
                _BoolVar(True),
                lambda m: None,
            )
        mock_cap.assert_not_called()

    def test_skips_when_bring_to_front_fails(self):
        messages, mock_pag = _run_intpc(
            already_foreground=False, user_idle=True, bring_success=False
        )
        assert any("failed" in m for m in messages)
        mock_pag.click.assert_not_called()

    def test_skips_when_disabled(self):
        messages, mock_pag = _run_intpc(enabled=False)
        mock_pag.click.assert_not_called()


# ===========================================================================
# TestIntpcLoopForeground
# ===========================================================================

class TestIntpcLoopForeground:
    """Bring-to-front logic and already-in-foreground path."""

    def test_bring_to_front_called_when_idle_and_not_foreground(self):
        stop_event = _make_stop_event(0.12)
        with (
            patch(_PATCHES["interval"], 0.01),
            patch(_PATCHES["process_running"], return_value=True),
            patch(_PATCHES["find_window"], return_value=1),
            patch(_PATCHES["is_foreground"], return_value=False),
            patch(_PATCHES["user_idle"], return_value=True),
            patch(_PATCHES["bring_to_front"]) as mock_btf,
            patch(_PATCHES["capture"], return_value=MagicMock()),
            patch(_PATCHES["detect"], return_value=False),
            patch(_PATCHES["pyautogui"]),
        ):
            run_intpc_keepalive(
                stop_event,
                threading.Lock(),
                [time.time()],
                _BoolVar(True),
                lambda m: None,
            )
        mock_btf.assert_called()

    def test_bring_to_front_not_called_when_already_foreground(self):
        stop_event = _make_stop_event(0.12)
        with (
            patch(_PATCHES["interval"], 0.01),
            patch(_PATCHES["process_running"], return_value=True),
            patch(_PATCHES["find_window"], return_value=1),
            patch(_PATCHES["is_foreground"], return_value=True),
            patch(_PATCHES["user_idle"], return_value=True),
            patch(_PATCHES["bring_to_front"]) as mock_btf,
            patch(_PATCHES["capture"], return_value=MagicMock()),
            patch(_PATCHES["detect"], return_value=False),
            patch(_PATCHES["pyautogui"]),
        ):
            run_intpc_keepalive(
                stop_event,
                threading.Lock(),
                [time.time()],
                _BoolVar(True),
                lambda m: None,
            )
        mock_btf.assert_not_called()

    def test_bring_to_front_log_appears(self):
        messages, _ = _run_intpc(already_foreground=False, user_idle=True)
        assert any("foreground" in m for m in messages)

    def test_dry_run_bring_to_front_logs_only(self):
        stop_event = _make_stop_event(0.12)
        with (
            patch(_PATCHES["interval"], 0.01),
            patch(_PATCHES["process_running"], return_value=True),
            patch(_PATCHES["find_window"], return_value=1),
            patch(_PATCHES["is_foreground"], return_value=False),
            patch(_PATCHES["user_idle"], return_value=True),
            patch(_PATCHES["bring_to_front"]) as mock_btf,
            patch(_PATCHES["capture"], return_value=MagicMock()),
            patch(_PATCHES["detect"], return_value=False),
            patch(_PATCHES["pyautogui"]),
        ):
            messages: list[str] = []
            run_intpc_keepalive(
                stop_event,
                threading.Lock(),
                [time.time()],
                _BoolVar(True),
                messages.append,
                dry_run=True,
            )
        # In dry_run, bring_to_front should NOT be called — only logged.
        mock_btf.assert_not_called()
        assert any("DRY RUN" in m for m in messages)


# ===========================================================================
# TestIntpcLoopDetection
# ===========================================================================

class TestIntpcLoopDetection:
    """Popup detection and click dispatch."""

    def test_click_called_when_popup_detected(self):
        _, mock_pag = _run_intpc(popup_detected=True)
        mock_pag.click.assert_called()

    def test_click_uses_correct_coordinates(self):
        _, mock_pag = _run_intpc(popup_detected=True)
        mock_pag.click.assert_called_with(INTPC_CLICK_X, INTPC_CLICK_Y)

    def test_log_mentions_popup_detected(self):
        messages, _ = _run_intpc(popup_detected=True)
        assert any("popup detected" in m for m in messages)

    def test_log_mentions_extend_button(self):
        messages, _ = _run_intpc(popup_detected=True)
        assert any("연장" in m for m in messages)

    def test_no_click_when_no_popup(self):
        _, mock_pag = _run_intpc(popup_detected=False)
        mock_pag.click.assert_not_called()

    def test_log_says_no_popup(self):
        messages, _ = _run_intpc(popup_detected=False)
        assert any("no popup" in m for m in messages)

    def test_dry_run_no_click_on_popup(self):
        _, mock_pag = _run_intpc(popup_detected=True, dry_run=True)
        mock_pag.click.assert_not_called()

    def test_dry_run_log_contains_dry_run_label(self):
        messages, _ = _run_intpc(popup_detected=True, dry_run=True)
        assert any("DRY RUN" in m for m in messages)

    def test_dry_run_log_contains_coordinates(self):
        messages, _ = _run_intpc(popup_detected=True, dry_run=True)
        coord_str = f"({INTPC_CLICK_X}, {INTPC_CLICK_Y})"
        assert any(coord_str in m for m in messages)

    def test_screenshot_taken_when_foreground(self):
        stop_event = _make_stop_event(0.12)
        with (
            patch(_PATCHES["interval"], 0.01),
            patch(_PATCHES["process_running"], return_value=True),
            patch(_PATCHES["find_window"], return_value=1),
            patch(_PATCHES["is_foreground"], return_value=True),
            patch(_PATCHES["user_idle"], return_value=True),
            patch(_PATCHES["bring_to_front"]),
            patch(_PATCHES["capture"], return_value=MagicMock()) as mock_cap,
            patch(_PATCHES["detect"], return_value=False),
            patch(_PATCHES["pyautogui"]),
        ):
            run_intpc_keepalive(
                stop_event,
                threading.Lock(),
                [time.time()],
                _BoolVar(True),
                lambda m: None,
            )
        mock_cap.assert_called()


# ===========================================================================
# TestIntpcThreadLifecycle
# ===========================================================================

class TestIntpcThreadLifecycle:
    """Thread semantics: stop_event, lock hygiene, multi-cycle."""

    def test_thread_stops_on_stop_event(self):
        stop = threading.Event()
        with (
            patch(_PATCHES["interval"], 0.01),
            patch(_PATCHES["process_running"], return_value=False),
            patch(_PATCHES["pyautogui"]),
        ):
            t = threading.Thread(
                target=run_intpc_keepalive,
                args=(
                    stop,
                    threading.Lock(),
                    [time.time()],
                    _BoolVar(True),
                    lambda m: None,
                ),
            )
            t.start()
            stop.set()
            t.join(timeout=1.0)

        assert not t.is_alive(), "Thread should exit after stop_event is set"

    def test_jiggle_lock_released_after_loop(self):
        stop_event = _make_stop_event(0.06)
        jiggle_lock = threading.Lock()

        with (
            patch(_PATCHES["interval"], 0.01),
            patch(_PATCHES["process_running"], return_value=True),
            patch(_PATCHES["find_window"], return_value=1),
            patch(_PATCHES["is_foreground"], return_value=True),
            patch(_PATCHES["user_idle"], return_value=True),
            patch(_PATCHES["bring_to_front"], return_value=True),
            patch(_PATCHES["capture"], return_value=MagicMock()),
            patch(_PATCHES["detect"], return_value=False),
            patch(_PATCHES["pyautogui"]),
        ):
            run_intpc_keepalive(
                stop_event,
                jiggle_lock,
                [time.time()],
                _BoolVar(True),
                lambda m: None,
            )

        acquired = jiggle_lock.acquire(blocking=False)
        assert acquired, "Lock should be released after the loop exits"
        jiggle_lock.release()

    def test_runs_multiple_cycles(self):
        stop_event = _make_stop_event(0.12)
        call_count: list[int] = []

        def fake_capture():
            call_count.append(1)
            return MagicMock()

        with (
            patch(_PATCHES["interval"], 0.01),
            patch(_PATCHES["process_running"], return_value=True),
            patch(_PATCHES["find_window"], return_value=1),
            patch(_PATCHES["is_foreground"], return_value=True),
            patch(_PATCHES["user_idle"], return_value=True),
            patch(_PATCHES["bring_to_front"], return_value=True),
            patch(_PATCHES["capture"], side_effect=fake_capture),
            patch(_PATCHES["detect"], return_value=False),
            patch(_PATCHES["pyautogui"]),
        ):
            run_intpc_keepalive(
                stop_event,
                threading.Lock(),
                [time.time()],
                _BoolVar(True),
                lambda m: None,
            )

        assert len(call_count) > 1, "Expected multiple screenshot cycles"
