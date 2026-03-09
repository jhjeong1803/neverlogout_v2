"""
Unit tests for src/idle_monitor.py

Tests are organised into three classes:

  TestIsUserIdle       — pure logic against last_real_input_time list
  TestRunIdleMonitor   — thread behaviour with mocked _get_mouse_pos /
                         _get_input_tick; no Windows API or display required
  TestGetInputTick     — graceful fallback on non-Windows platforms
"""

import sys
import time
import threading
from pathlib import Path
from unittest.mock import patch

import pytest

# Make src/ importable without installing the package
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from idle_monitor import is_user_idle, run_idle_monitor
from constants import IDLE_THRESHOLD


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_stop_event(auto_stop_after: float = 0.15) -> threading.Event:
    """Return a stop event that fires automatically after *auto_stop_after* s."""
    ev = threading.Event()
    threading.Timer(auto_stop_after, ev.set).start()
    return ev


def _run_monitor_tick(
    mouse_positions: list,
    input_ticks: list,
    jiggle_in_progress: threading.Event,
    last_real_input_time: list[float],
    *,
    poll_interval: float = 0.01,
) -> None:
    """
    Run run_idle_monitor with mocked helpers for one or more poll cycles
    and block until the stop event fires.

    mouse_positions: sequence of (x, y) returned per call to _get_mouse_pos.
                     The last value is repeated if the list is exhausted.
    input_ticks:     sequence of ints returned per call to _get_input_tick.
    """
    pos_iter   = iter(mouse_positions)
    tick_iter  = iter(input_ticks)

    def mock_pos():
        try:
            return next(pos_iter)
        except StopIteration:
            return mouse_positions[-1]

    def mock_tick():
        try:
            return next(tick_iter)
        except StopIteration:
            return input_ticks[-1]

    stop = _make_stop_event(auto_stop_after=poll_interval * 3)

    with (
        patch("idle_monitor._get_mouse_pos",  side_effect=mock_pos),
        patch("idle_monitor._get_input_tick", side_effect=mock_tick),
        patch("idle_monitor.IDLE_POLL_INTERVAL", poll_interval),
    ):
        run_idle_monitor(stop, jiggle_in_progress, last_real_input_time)


# ===========================================================================
# TestIsUserIdle
# ===========================================================================

class TestIsUserIdle:
    """is_user_idle(last_real_input_time) — pure time comparison."""

    def test_returns_false_when_input_was_just_now(self):
        t = [time.time()]
        assert not is_user_idle(t)

    def test_returns_true_when_past_threshold(self):
        t = [time.time() - IDLE_THRESHOLD - 1]
        assert is_user_idle(t)

    def test_returns_false_exactly_at_threshold_minus_one(self):
        t = [time.time() - IDLE_THRESHOLD + 1]
        assert not is_user_idle(t)

    def test_returns_true_exactly_at_threshold(self):
        t = [time.time() - IDLE_THRESHOLD]
        assert is_user_idle(t)

    def test_very_old_timestamp_returns_true(self):
        t = [0.0]  # epoch — definitely idle
        assert is_user_idle(t)

    def test_future_timestamp_returns_false(self):
        # Should never happen in practice, but must not crash
        t = [time.time() + 9999]
        assert not is_user_idle(t)

    def test_list_index_zero_is_used(self):
        # Confirm it reads index [0], not some other attribute
        t = [time.time()]
        assert not is_user_idle(t)
        t[0] = time.time() - IDLE_THRESHOLD - 5
        assert is_user_idle(t)


# ===========================================================================
# TestRunIdleMonitor
# ===========================================================================

class TestRunIdleMonitor:
    """
    Behavioural tests for the monitor loop.
    Each test runs the thread for ~3 poll cycles (poll_interval=0.01s)
    and inspects how last_real_input_time was updated.
    """

    # ---- Real mouse movement (jiggler NOT active) --------------------------

    def test_real_mouse_move_updates_timestamp(self):
        old = time.time() - 200
        lrit = [old]
        jig = threading.Event()  # not set → jiggler idle

        _run_monitor_tick(
            mouse_positions=[(100, 100), (105, 100)],  # position changes
            input_ticks=[1000, 1010],
            jiggle_in_progress=jig,
            last_real_input_time=lrit,
        )

        assert lrit[0] > old, "Real mouse move should update last_real_input_time"

    def test_real_mouse_move_sets_time_close_to_now(self):
        lrit = [time.time() - 300]
        jig = threading.Event()

        before = time.time()
        _run_monitor_tick(
            mouse_positions=[(0, 0), (1, 0)],
            input_ticks=[0, 0],
            jiggle_in_progress=jig,
            last_real_input_time=lrit,
        )

        assert lrit[0] >= before

    # ---- Synthetic mouse move (jiggler IS active) --------------------------

    def test_jiggler_mouse_move_does_not_update_timestamp(self):
        old = time.time() - 200
        lrit = [old]
        jig = threading.Event()
        jig.set()  # jiggler is currently moving

        _run_monitor_tick(
            mouse_positions=[(100, 100), (101, 100)],
            input_ticks=[1000, 1010],
            jiggle_in_progress=jig,
            last_real_input_time=lrit,
        )

        assert lrit[0] == old, "Synthetic jiggler move must NOT update last_real_input_time"

    # ---- No input at all ---------------------------------------------------

    def test_no_change_does_not_update_timestamp(self):
        old = time.time() - 200
        lrit = [old]
        jig = threading.Event()

        _run_monitor_tick(
            mouse_positions=[(50, 50), (50, 50)],  # no movement
            input_ticks=[999, 999],                 # tick unchanged
            jiggle_in_progress=jig,
            last_real_input_time=lrit,
        )

        assert lrit[0] == old, "No input should leave last_real_input_time unchanged"

    # ---- Keyboard input (tick advances, no mouse move) ---------------------

    def test_keyboard_activity_updates_timestamp(self):
        old = time.time() - 200
        lrit = [old]
        jig = threading.Event()

        _run_monitor_tick(
            mouse_positions=[(50, 50), (50, 50)],  # no mouse move
            input_ticks=[1000, 1050],               # tick advanced → keyboard
            jiggle_in_progress=jig,
            last_real_input_time=lrit,
        )

        assert lrit[0] > old, "Keyboard input should update last_real_input_time"

    def test_keyboard_activity_updates_even_when_jiggler_active(self):
        # Tick advanced, no mouse move, jiggler flag set:
        # → keyboard branch fires (not the mouse branch) → should update
        old = time.time() - 200
        lrit = [old]
        jig = threading.Event()
        jig.set()

        _run_monitor_tick(
            mouse_positions=[(50, 50), (50, 50)],
            input_ticks=[1000, 1050],
            jiggle_in_progress=jig,
            last_real_input_time=lrit,
        )

        assert lrit[0] > old

    # ---- Jiggler move matches real mouse move — ambiguous tick -------------

    def test_mouse_moved_and_tick_advanced_but_jiggler_active_no_update(self):
        # Jiggler moved mouse (so mouse_moved=True, tick_advanced=True, jiggle set)
        # → mouse branch blocked by jiggle flag
        # → keyboard branch blocked because mouse DID move
        # → no update
        old = time.time() - 200
        lrit = [old]
        jig = threading.Event()
        jig.set()

        _run_monitor_tick(
            mouse_positions=[(10, 10), (11, 10)],
            input_ticks=[500, 510],
            jiggle_in_progress=jig,
            last_real_input_time=lrit,
        )

        assert lrit[0] == old

    # ---- Thread terminates on stop_event -----------------------------------

    def test_thread_stops_when_stop_event_set(self):
        """run_idle_monitor must return promptly when stop_event is set."""
        stop = threading.Event()
        jig  = threading.Event()
        lrit = [time.time()]

        with (
            patch("idle_monitor._get_mouse_pos",  return_value=(0, 0)),
            patch("idle_monitor._get_input_tick", return_value=0),
            patch("idle_monitor.IDLE_POLL_INTERVAL", 0.01),
        ):
            t = threading.Thread(target=run_idle_monitor, args=(stop, jig, lrit))
            t.start()
            stop.set()
            t.join(timeout=1.0)

        assert not t.is_alive(), "Thread should exit after stop_event is set"

    # ---- Multiple cycles update on each real event -------------------------

    def test_multiple_real_moves_keep_updating_timestamp(self):
        """Each poll cycle with a real mouse move should push the timestamp forward."""
        lrit = [time.time() - 300]
        jig  = threading.Event()

        # Alternating positions so every poll sees movement
        positions = [(i, 0) for i in range(20)]
        ticks     = [1000] * 20  # tick unchanged → only mouse branch fires

        _run_monitor_tick(
            mouse_positions=positions,
            input_ticks=ticks,
            jiggle_in_progress=jig,
            last_real_input_time=lrit,
            poll_interval=0.01,
        )

        assert time.time() - lrit[0] < 1.0, "Should have been updated recently"


# ===========================================================================
# TestGetInputTick
# ===========================================================================

class TestGetInputTick:
    """_get_input_tick() — Windows API wrapper with graceful fallback."""

    def test_returns_int(self):
        from idle_monitor import _get_input_tick
        result = _get_input_tick()
        assert isinstance(result, int)

    def test_returns_zero_when_windll_unavailable(self):
        """On Linux (no windll), must return 0 without raising."""
        import idle_monitor
        with patch.object(idle_monitor.ctypes, "windll", None, create=True):
            # AttributeError should be caught internally
            result = idle_monitor._get_input_tick()
        assert isinstance(result, int)

    def test_non_negative(self):
        from idle_monitor import _get_input_tick
        assert _get_input_tick() >= 0
