"""
Module 2: HIS Keepalive

Every HIS_CHECK_INTERVAL seconds, captures a full-screen screenshot and checks
hardcoded pixel coordinates for the HIS session timeout popup. If detected,
clicks the "연장" (Extend) button to dismiss it and stay logged in.

HIS runs as a native desktop application and does NOT need to be in the
foreground — the popup appears on top regardless of window Z-order.

Thread model:
  - Runs in a daemon thread; exits when stop_event is set.
  - Acquires jiggle_lock around the screenshot + click cycle so the jiggler
    does not move the mouse mid-click. The lock is released immediately after
    the cycle completes.
  - Uses stop_event.wait(timeout=HIS_CHECK_INTERVAL) so the thread wakes
    immediately on shutdown rather than sleeping a full interval.
"""

import threading

try:
    import pyautogui
    _PYAUTOGUI_AVAILABLE = True
except ImportError:
    pyautogui = None  # type: ignore[assignment]
    _PYAUTOGUI_AVAILABLE = False

from constants import (
    HIS_CHECK_INTERVAL,
    HIS_CLICK_X,
    HIS_CLICK_Y,
    HIS_COLOR_TOLERANCE,
    HIS_DETECTION_POINTS,
)
from screen_utils import capture_screenshot, check_detection_points


def run_his_keepalive(
    stop_event: threading.Event,
    jiggle_lock: threading.Lock,
    enabled_var,        # tkinter.BooleanVar — read-only, thread-safe
    log_fn,             # callable(str) -> None
    dry_run: bool = False,
) -> None:
    """
    HIS keepalive loop. Intended to run in a daemon thread started by main.py.

    Args:
        stop_event:   Set by main.py to terminate the thread.
        jiggle_lock:  Shared Lock; held here during screenshot+click so the
                      jiggler cannot move the mouse mid-cycle.
        enabled_var:  tkinter BooleanVar reflecting the HIS checkbox state.
        log_fn:       Function to append a timestamped message to the GUI log.
        dry_run:      If True, log would-be clicks without actually clicking.
    """
    while not stop_event.wait(timeout=HIS_CHECK_INTERVAL):
        if not enabled_var.get():
            continue

        with jiggle_lock:
            # Re-check enabled state in case checkbox was unticked while
            # we were waiting for the lock.
            if not enabled_var.get():
                continue

            log_fn("HIS: checking for timeout popup…")

            img = capture_screenshot()
            popup_detected = check_detection_points(
                img, HIS_DETECTION_POINTS, HIS_COLOR_TOLERANCE
            )

            if popup_detected:
                if dry_run:
                    log_fn(
                        f"[DRY RUN] HIS popup detected — would click ({HIS_CLICK_X}, {HIS_CLICK_Y})"
                    )
                else:
                    pyautogui.click(HIS_CLICK_X, HIS_CLICK_Y)
                    log_fn(
                        f"HIS popup detected — clicked 연장 at ({HIS_CLICK_X}, {HIS_CLICK_Y})"
                    )
            else:
                log_fn("HIS: no popup detected.")
