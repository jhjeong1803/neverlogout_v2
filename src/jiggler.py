"""
Module 1: Mouse Jiggler

Moves the mouse +1px right then -1px left every JIGGLE_INTERVAL seconds to
prevent OS idle/sleep. Coordinates with Modules 2 and 3 via jiggle_lock to
avoid moving the mouse during an active click cycle.

Thread model:
  - Runs in a daemon thread; exits when stop_event is set.
  - Uses stop_event.wait(timeout=JIGGLE_INTERVAL) so the thread wakes
    immediately on shutdown rather than sleeping a full interval.
  - Acquires jiggle_lock around the actual mouse move so Modules 2/3 can
    hold the lock during their screenshot+click cycles without conflict.
  - Sets jiggle_in_progress around the literal mouse move so the idle
    monitor can distinguish synthetic jiggler movement from real user input.
  - Calls SetThreadExecutionState(ES_DISPLAY_REQUIRED | ES_SYSTEM_REQUIRED)
    on entry and clears it on exit — mouse movement alone does not suppress
    the Windows display timeout.
"""

import ctypes
import threading

try:
    import pyautogui
    _PYAUTOGUI_AVAILABLE = True
except ImportError:
    pyautogui = None  # type: ignore[assignment]
    _PYAUTOGUI_AVAILABLE = False

from constants import JIGGLE_INTERVAL

# ---------------------------------------------------------------------------
# Windows SetThreadExecutionState — prevents display/system sleep
# ---------------------------------------------------------------------------

_ES_CONTINUOUS       = 0x80000000
_ES_SYSTEM_REQUIRED  = 0x00000001
_ES_DISPLAY_REQUIRED = 0x00000002


def _set_keep_awake(enable: bool) -> None:
    """
    Ask Windows to keep the display and system awake (enable=True) or release
    that request (enable=False).

    SetThreadExecutionState is the correct API for preventing screensaver /
    display timeout — mouse movement alone does not suppress display sleep.
    Silently ignored on non-Windows platforms.
    """
    try:
        flags = _ES_CONTINUOUS
        if enable:
            flags |= _ES_SYSTEM_REQUIRED | _ES_DISPLAY_REQUIRED
        ctypes.windll.kernel32.SetThreadExecutionState(flags)  # type: ignore[attr-defined]
    except AttributeError:
        pass  # Not on Windows (Linux dev environment)


def run_jiggler(
    stop_event: threading.Event,
    jiggle_lock: threading.Lock,
    jiggle_in_progress: threading.Event,
    enabled_var,        # tkinter.BooleanVar — read-only, thread-safe
    log_fn,             # callable(str) -> None
    dry_run: bool = False,
) -> None:
    """
    Jiggler loop. Intended to run in a daemon thread started by main.py.

    Args:
        stop_event:          Set by main.py to terminate the thread.
        jiggle_lock:         Shared Lock; held by Modules 2/3 during clicks.
        jiggle_in_progress:  Shared Event; set around the actual mouse move
                             so the idle monitor can filter synthetic input.
        enabled_var:         tkinter BooleanVar reflecting the checkbox state.
        log_fn:              Function to append a message to the GUI log.
        dry_run:             If True, log the would-be action instead of moving.
    """
    _set_keep_awake(True)
    try:
        while not stop_event.wait(timeout=JIGGLE_INTERVAL):
            # stop_event.wait returns False on timeout (keep looping),
            # True if the event was set (stop requested — while condition exits).

            if not enabled_var.get():
                continue

            # Wait for the lock: if Module 2 or 3 is mid-click-cycle, block here
            # until they release. The lock is held only briefly by the jiggler.
            with jiggle_lock:
                # Re-check enabled state in case checkbox was unticked while
                # we were waiting for the lock.
                if not enabled_var.get():
                    continue

                # Signal idle monitor: the move about to happen is synthetic.
                jiggle_in_progress.set()
                try:
                    if dry_run:
                        log_fn("[DRY RUN] Would jiggle mouse +1px / -1px")
                    elif _PYAUTOGUI_AVAILABLE:
                        pyautogui.moveRel(1, 0, duration=0)
                        pyautogui.moveRel(-1, 0, duration=0)
                except Exception as exc:  # noqa: BLE001
                    log_fn(f"Jiggler: error during move — {exc}. Will retry next cycle.")
                finally:
                    # Always clear the flag, even if pyautogui raises.
                    jiggle_in_progress.clear()
    finally:
        _set_keep_awake(False)
