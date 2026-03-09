"""
Module 3: intPC Keepalive

Every INTPC_CHECK_INTERVAL seconds:
  1. Check if the intPC process is running (psutil). If not, log and skip.
  2. If running and NOT already in the foreground, bring it to front —
     but only if the user has been idle for >= IDLE_THRESHOLD seconds.
     If the user is active, skip this cycle entirely.
  3. With intPC in the foreground, capture a screenshot and check hardcoded
     pixel coordinates for the session timeout popup.
  4. If popup detected, click "연장" (Extend) to dismiss it.
  5. Leave intPC in the foreground after clicking (do not restore prior window).

Thread model:
  - Runs in a daemon thread; exits when stop_event is set.
  - Acquires jiggle_lock around the screenshot + click cycle so the jiggler
    does not move the mouse mid-click.
  - Uses stop_event.wait(timeout=INTPC_CHECK_INTERVAL) for clean shutdown.

Window management:
  - win32gui.FindWindow / EnumWindows to locate the intPC window by partial
    title match (INTPC_WINDOW_TITLE).
  - win32gui.SetForegroundWindow to bring it to front.
  - win32gui.GetForegroundWindow to check current foreground window.

Graceful degradation:
  - pywin32 (win32gui) is not available in the Linux dev environment.
    All win32gui calls are guarded so the module imports cleanly on Linux
    and logs a warning if window management is unavailable at runtime.
"""

import threading

try:
    import psutil
    _PSUTIL_AVAILABLE = True
except ImportError:
    _PSUTIL_AVAILABLE = False

try:
    import pyautogui
    _PYAUTOGUI_AVAILABLE = True
except ImportError:
    pyautogui = None  # type: ignore[assignment]
    _PYAUTOGUI_AVAILABLE = False

try:
    import win32gui
    _WIN32GUI_AVAILABLE = True
except ImportError:
    win32gui = None  # type: ignore[assignment]
    _WIN32GUI_AVAILABLE = False

from constants import (
    INTPC_CHECK_INTERVAL,
    INTPC_CLICK_X,
    INTPC_CLICK_Y,
    INTPC_COLOR_TOLERANCE,
    INTPC_DETECTION_POINTS,
    INTPC_PROCESS_NAME,
    INTPC_WINDOW_TITLE,
)
from idle_monitor import is_user_idle
from screen_utils import capture_screenshot, check_detection_points


# ---------------------------------------------------------------------------
# Window helpers
# ---------------------------------------------------------------------------

def _find_intpc_window() -> int:
    """
    Return the HWND of the intPC window, or 0 if not found / win32gui absent.

    Searches all top-level windows for a title containing INTPC_WINDOW_TITLE
    (case-insensitive partial match).
    """
    if not _WIN32GUI_AVAILABLE:
        return 0

    found: list[int] = []

    def _enum_callback(hwnd: int, _: None) -> None:
        title = win32gui.GetWindowText(hwnd)
        if INTPC_WINDOW_TITLE.lower() in title.lower():
            found.append(hwnd)

    win32gui.EnumWindows(_enum_callback, None)
    return found[0] if found else 0


def _is_foreground(hwnd: int) -> bool:
    """Return True if *hwnd* is the current foreground window."""
    if not _WIN32GUI_AVAILABLE or not hwnd:
        return False
    return win32gui.GetForegroundWindow() == hwnd


def _bring_to_front(hwnd: int) -> bool:
    """
    Attempt to set *hwnd* as the foreground window.
    Returns True on success, False if the call raised or win32gui is absent.
    """
    if not _WIN32GUI_AVAILABLE or not hwnd:
        return False
    try:
        win32gui.SetForegroundWindow(hwnd)
        return True
    except Exception:  # noqa: BLE001 — win32gui can raise various errors
        return False


def _is_process_running() -> bool:
    """Return True if INTPC_PROCESS_NAME is among the running processes."""
    if not _PSUTIL_AVAILABLE:
        return False
    target = INTPC_PROCESS_NAME.lower()
    return any(
        p.info["name"].lower() == target
        for p in psutil.process_iter(["name"])
        if p.info["name"]
    )


# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------

def run_intpc_keepalive(
    stop_event: threading.Event,
    jiggle_lock: threading.Lock,
    last_real_input_time: list[float],  # shared with idle_monitor
    enabled_var,                         # tkinter.BooleanVar — read-only
    log_fn,                              # callable(str) -> None
    dry_run: bool = False,
) -> None:
    """
    intPC keepalive loop. Intended to run in a daemon thread started by main.py.

    Args:
        stop_event:           Set by main.py to terminate the thread.
        jiggle_lock:          Shared Lock; held during screenshot + click cycle.
        last_real_input_time: Single-element list [float] updated by idle_monitor.
        enabled_var:          tkinter BooleanVar reflecting the intPC checkbox.
        log_fn:               Function to append a timestamped message to the GUI log.
        dry_run:              If True, log would-be actions without performing them.
    """
    while not stop_event.wait(timeout=INTPC_CHECK_INTERVAL):
        if not enabled_var.get():
            continue

        # ------------------------------------------------------------------ #
        # Step 1: process check                                               #
        # ------------------------------------------------------------------ #
        if not _is_process_running():
            log_fn(f"intPC: {INTPC_PROCESS_NAME} not running — skipping.")
            continue

        # ------------------------------------------------------------------ #
        # Step 2: foreground check + conditional bring-to-front              #
        # ------------------------------------------------------------------ #
        hwnd = _find_intpc_window()

        if not hwnd:
            log_fn("intPC: window not found — skipping.")
            continue

        already_foreground = _is_foreground(hwnd)

        if not already_foreground:
            if not is_user_idle(last_real_input_time):
                log_fn("intPC: window not in foreground but user is active — skipping.")
                continue

            # User is idle — safe to bring intPC to front.
            if dry_run:
                log_fn("[DRY RUN] intPC: would bring window to foreground.")
            else:
                success = _bring_to_front(hwnd)
                if success:
                    log_fn("intPC: brought window to foreground.")
                else:
                    log_fn("intPC: failed to bring window to foreground — skipping.")
                    continue

        # ------------------------------------------------------------------ #
        # Step 3 & 4: screenshot + popup detection + optional click           #
        # ------------------------------------------------------------------ #
        with jiggle_lock:
            # Re-check enabled state in case checkbox was unticked while
            # we were waiting for the lock.
            if not enabled_var.get():
                continue

            log_fn("intPC: checking for timeout popup…")

            if _PYAUTOGUI_AVAILABLE:
                pyautogui.moveTo(5, 5, duration=0)
            img = capture_screenshot()
            popup_detected = check_detection_points(
                img, INTPC_DETECTION_POINTS, INTPC_COLOR_TOLERANCE
            )

            if popup_detected:
                if dry_run:
                    log_fn(
                        f"[DRY RUN] intPC popup detected — would click ({INTPC_CLICK_X}, {INTPC_CLICK_Y})"
                    )
                else:
                    pyautogui.click(INTPC_CLICK_X, INTPC_CLICK_Y)
                    log_fn(
                        f"intPC popup detected — clicked 연장 at ({INTPC_CLICK_X}, {INTPC_CLICK_Y})"
                    )
            else:
                log_fn("intPC: no popup detected.")
