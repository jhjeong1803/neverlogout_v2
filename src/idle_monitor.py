"""
Idle Monitor — jiggler-aware user idle detection.

Runs in a daemon thread started by main.py when the intPC checkbox is enabled.

Problem
-------
GetLastInputInfo (Windows API) counts pyautogui synthetic mouse moves as real
input, so the jiggler would permanently reset the idle clock, making idle
detection useless. This module works around it:

  Mouse:    Compare position each poll. Changed AND jiggle_in_progress is NOT
            set → real user movement → reset last_real_input_time.

  Keyboard: If the Windows input tick advanced but the mouse did NOT move (or
            jiggle_in_progress is set, meaning the tick advance came from the
            jiggler) → keyboard activity, which is never synthetic → reset
            last_real_input_time.

is_user_idle() checks:  time.time() - last_real_input_time[0] >= IDLE_THRESHOLD
"""

import ctypes
import time
import threading

try:
    import pyautogui
    _PYAUTOGUI_AVAILABLE = True
except ImportError:
    _PYAUTOGUI_AVAILABLE = False

from constants import IDLE_POLL_INTERVAL, IDLE_THRESHOLD


# ---------------------------------------------------------------------------
# Windows API helper
# ---------------------------------------------------------------------------

class _LASTINPUTINFO(ctypes.Structure):
    _fields_ = [
        ("cbSize", ctypes.c_uint),
        ("dwTime", ctypes.c_uint),   # milliseconds since boot (wraps ~49 days)
    ]


def _get_input_tick() -> int:
    """
    Return the Windows tick (ms since boot) of the last user input event.
    Returns 0 on non-Windows platforms so the module degrades gracefully.
    """
    try:
        lii = _LASTINPUTINFO()
        lii.cbSize = ctypes.sizeof(_LASTINPUTINFO)
        ctypes.windll.user32.GetLastInputInfo(ctypes.byref(lii))  # type: ignore[attr-defined]
        return lii.dwTime
    except AttributeError:
        return 0  # Not on Windows (Linux dev environment)


def _get_mouse_pos() -> tuple[int, int]:
    """Return current (x, y). Falls back to (0, 0) when pyautogui unavailable."""
    if _PYAUTOGUI_AVAILABLE:
        pos = pyautogui.position()
        return (pos.x, pos.y)
    return (0, 0)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def is_user_idle(last_real_input_time: list[float]) -> bool:
    """
    Return True if no real user input has been seen for >= IDLE_THRESHOLD seconds.

    Args:
        last_real_input_time: Single-element list [float] shared with main.py.
                              A list is used so any thread can mutate index 0
                              without a lock (float assignment is atomic in CPython).
    """
    return time.time() - last_real_input_time[0] >= IDLE_THRESHOLD


def run_idle_monitor(
    stop_event: threading.Event,
    jiggle_in_progress: threading.Event,
    last_real_input_time: list[float],
) -> None:
    """
    Idle monitor loop. Intended to run as a daemon thread.

    Args:
        stop_event:           Set by main.py to terminate this thread.
        jiggle_in_progress:   Event set by jiggler.py around its mouse move.
                              When set, a mouse position change is synthetic
                              and must NOT reset last_real_input_time.
        last_real_input_time: Single-element list [float] shared with main.py
                              and intpc_keepalive. Updated here; read by
                              is_user_idle().
    """
    prev_mouse = _get_mouse_pos()
    prev_tick  = _get_input_tick()

    while not stop_event.wait(timeout=IDLE_POLL_INTERVAL):
        now       = time.time()
        cur_mouse = _get_mouse_pos()
        cur_tick  = _get_input_tick()

        mouse_moved   = cur_mouse != prev_mouse
        tick_advanced = cur_tick  != prev_tick

        if mouse_moved and not jiggle_in_progress.is_set():
            # Real mouse movement — jiggler was not active during this move.
            last_real_input_time[0] = now

        elif tick_advanced and not mouse_moved:
            # Input tick advanced with no mouse movement → keyboard activity.
            # Keyboard is never synthetic, so no jiggle filter needed.
            last_real_input_time[0] = now

        prev_mouse = cur_mouse
        prev_tick  = cur_tick
