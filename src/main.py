"""
KeepAlive Tool — entry point and tkinter GUI.

Starts and stops three independent daemon threads based on checkbox state:
  Module 1: Mouse Jiggler       (jiggler.py)
  Module 2: HIS Keepalive       (his_keepalive.py)
  Module 3: intPC Keepalive     (intpc_keepalive.py)
  Support: Idle Monitor         (idle_monitor.py)

Run with --dry-run to log would-be actions without clicking or moving.
"""

import argparse
import os
import sys
import threading
import time
import tkinter as tk
from tkinter import font as tkfont

# Suppress pyautogui fail-safe (moving mouse to screen corner must not abort
# the tool while it is running unattended).
try:
    import pyautogui
    pyautogui.FAILSAFE = False
except ImportError:
    pyautogui = None  # will surface as an error only when a module tries to click

from constants import LOG_MAX_LINES, WINDOW_ALWAYS_ON_TOP

STAMP = "JJH 2026.03"

# ---------------------------------------------------------------------------
# Icon path helper — works both in development and inside a PyInstaller bundle
# ---------------------------------------------------------------------------

def _icon_path() -> str:
    """Return the absolute path to keepalive.ico, whether bundled or not."""
    if getattr(sys, "frozen", False):
        # Running inside a PyInstaller .exe — resources are in sys._MEIPASS
        base = sys._MEIPASS  # type: ignore[attr-defined]
    else:
        # Development: icon lives in build/ next to src/
        base = os.path.join(os.path.dirname(__file__), "..", "build")
    return os.path.join(base, "keepalive.ico")
from jiggler import run_jiggler
from logger import Logger

# Optional modules — not yet implemented; checkboxes are disabled until present.
try:
    from his_keepalive import run_his_keepalive
    HIS_AVAILABLE = True
except ImportError:
    HIS_AVAILABLE = False

try:
    from intpc_keepalive import run_intpc_keepalive
    from idle_monitor import run_idle_monitor
    INTPC_AVAILABLE = True
except ImportError:
    INTPC_AVAILABLE = False


# ---------------------------------------------------------------------------
# Argument parsing
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="keepalive",
        description="Keep HIS and intPC sessions alive on Windows.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Log would-be clicks/moves without actually performing them.",
    )
    return parser.parse_args()


# ---------------------------------------------------------------------------
# Application
# ---------------------------------------------------------------------------

class KeepAliveApp:
    """
    Owns the tkinter root window, all shared state, and thread lifecycle.
    """

    def __init__(self, root: tk.Tk, dry_run: bool) -> None:
        self.root = root
        self.dry_run = dry_run

        # ------------------------------------------------------------------
        # Shared state (passed into every module thread)
        # ------------------------------------------------------------------
        self.jiggle_lock = threading.Lock()
        # Set around the actual pyautogui move; idle monitor checks this flag
        # to filter synthetic mouse movement from real user input.
        self.jiggle_in_progress = threading.Event()
        # Updated by idle_monitor; intpc_keepalive reads it via is_user_idle()
        self.last_real_input_time: list[float] = [time.time()]

        # Per-module stop events — cleared on start, set on stop.
        self._jiggle_stop   = threading.Event()
        self._his_stop      = threading.Event()
        self._intpc_stop    = threading.Event()
        self._idle_stop     = threading.Event()

        # ------------------------------------------------------------------
        # GUI
        # ------------------------------------------------------------------
        self._build_gui()

    # ------------------------------------------------------------------
    # GUI construction
    # ------------------------------------------------------------------

    def _build_gui(self) -> None:
        root = self.root
        root.title("KeepAlive")
        root.resizable(False, False)
        root.attributes("-topmost", WINDOW_ALWAYS_ON_TOP)

        # Window icon (silently skip if the .ico is missing in dev)
        try:
            root.iconbitmap(_icon_path())
        except Exception:
            pass

        # ---- Checkbox frame ----
        cb_frame = tk.Frame(root, padx=10, pady=8)
        cb_frame.pack(fill=tk.X)

        self.jiggle_var = tk.BooleanVar(value=False)
        self.his_var    = tk.BooleanVar(value=False)
        self.intpc_var  = tk.BooleanVar(value=False)

        tk.Checkbutton(
            cb_frame, text="Mouse Jiggle",
            variable=self.jiggle_var,
        ).pack(anchor=tk.W)

        tk.Checkbutton(
            cb_frame, text="HIS" + ("" if HIS_AVAILABLE else "  (not yet available)"),
            variable=self.his_var,
            state=tk.NORMAL if HIS_AVAILABLE else tk.DISABLED,
        ).pack(anchor=tk.W)

        tk.Checkbutton(
            cb_frame, text="intPC" + ("" if INTPC_AVAILABLE else "  (not yet available)"),
            variable=self.intpc_var,
            state=tk.NORMAL if INTPC_AVAILABLE else tk.DISABLED,
        ).pack(anchor=tk.W)

        # ---- Separator ----
        tk.Frame(root, height=1, bg="#cccccc").pack(fill=tk.X, padx=6)

        # ---- Log area ----
        log_frame = tk.Frame(root, padx=6, pady=6)
        log_frame.pack(fill=tk.BOTH, expand=True)

        mono = tkfont.Font(family="Courier", size=9)
        scrollbar = tk.Scrollbar(log_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self._log_text = tk.Text(
            log_frame,
            height=12,
            width=52,
            font=mono,
            state="disabled",
            bg="#1e1e1e",
            fg="#d4d4d4",
            insertbackground="#d4d4d4",
            relief=tk.FLAT,
            yscrollcommand=scrollbar.set,
            wrap=tk.WORD,
        )
        self._log_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.config(command=self._log_text.yview)

        # ---- Logger ----
        self.logger = Logger(self._log_text)

        # ---- Checkbox trace callbacks ----
        self.jiggle_var.trace_add("write", self._on_jiggle_toggle)
        self.his_var.trace_add("write",    self._on_his_toggle)
        self.intpc_var.trace_add("write",  self._on_intpc_toggle)

        # ---- Stamp ----
        stamp_font = tkfont.Font(family="Courier", size=8)
        tk.Label(
            root,
            text=STAMP,
            font=stamp_font,
            fg="#888888",
            bg=root.cget("bg"),
            anchor=tk.E,
            padx=6,
        ).pack(fill=tk.X)

        # ---- Window close ----
        root.protocol("WM_DELETE_WINDOW", self._on_close)

        # ---- Size & position ----
        root.update_idletasks()
        root.geometry("420x305")

        self.logger.log("KeepAlive ready." + (" [DRY RUN]" if self.dry_run else ""))

    # ------------------------------------------------------------------
    # Checkbox callbacks
    # ------------------------------------------------------------------

    def _on_jiggle_toggle(self, *_) -> None:
        if self.jiggle_var.get():
            self._jiggle_stop.clear()
            t = threading.Thread(
                target=run_jiggler,
                args=(
                    self._jiggle_stop,
                    self.jiggle_lock,
                    self.jiggle_in_progress,
                    self.jiggle_var,
                    self.logger.log,
                ),
                kwargs={"dry_run": self.dry_run},
                daemon=True,
                name="jiggler",
            )
            t.start()
            self.logger.log("Mouse Jiggle enabled.")
        else:
            self._jiggle_stop.set()
            self.logger.log("Mouse Jiggle disabled.")

    def _on_his_toggle(self, *_) -> None:
        if not HIS_AVAILABLE:
            return
        if self.his_var.get():
            self._his_stop.clear()
            t = threading.Thread(
                target=run_his_keepalive,
                args=(
                    self._his_stop,
                    self.jiggle_lock,
                    self.his_var,
                    self.logger.log,
                ),
                kwargs={"dry_run": self.dry_run},
                daemon=True,
                name="his_keepalive",
            )
            t.start()
            self.logger.log("HIS keepalive enabled.")
        else:
            self._his_stop.set()
            self.logger.log("HIS keepalive disabled.")

    def _on_intpc_toggle(self, *_) -> None:
        if not INTPC_AVAILABLE:
            return
        if self.intpc_var.get():
            self._intpc_stop.clear()
            self._idle_stop.clear()

            idle_t = threading.Thread(
                target=run_idle_monitor,
                args=(
                    self._idle_stop,
                    self.jiggle_in_progress,
                    self.last_real_input_time,
                ),
                daemon=True,
                name="idle_monitor",
            )
            idle_t.start()

            intpc_t = threading.Thread(
                target=run_intpc_keepalive,
                args=(
                    self._intpc_stop,
                    self.jiggle_lock,
                    self.last_real_input_time,
                    self.intpc_var,
                    self.logger.log,
                ),
                kwargs={"dry_run": self.dry_run},
                daemon=True,
                name="intpc_keepalive",
            )
            intpc_t.start()
            self.logger.log("intPC keepalive enabled.")
        else:
            self._intpc_stop.set()
            self._idle_stop.set()
            self.logger.log("intPC keepalive disabled.")

    # ------------------------------------------------------------------
    # Shutdown
    # ------------------------------------------------------------------

    def _on_close(self) -> None:
        # Signal all threads to stop, then destroy the window.
        self._jiggle_stop.set()
        self._his_stop.set()
        self._intpc_stop.set()
        self._idle_stop.set()
        self.root.destroy()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    args = parse_args()
    root = tk.Tk()
    KeepAliveApp(root, dry_run=args.dry_run)
    root.mainloop()


if __name__ == "__main__":
    main()
