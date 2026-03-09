"""
Logger: thread-safe timestamped logging to the tkinter GUI log area.

Background daemon threads must not write to tkinter widgets directly —
tkinter is single-threaded. log() schedules every append on the main
thread via widget.after(0, ...), which is safe to call from any thread.
"""

import time
import tkinter as tk
from datetime import datetime

from constants import LOG_MAX_LINES


class Logger:
    """
    Wraps a tkinter Text widget and exposes a single thread-safe log()
    method used by all modules.

    The widget is kept in DISABLED state so users cannot type into it;
    _append() temporarily enables it to insert text, then re-disables it.
    """

    def __init__(self, text_widget: tk.Text, max_lines: int = LOG_MAX_LINES) -> None:
        self._widget = text_widget
        self._max_lines = max_lines

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def log(self, message: str) -> None:
        """
        Append a timestamped message to the GUI log area.

        Thread-safe: may be called from any thread. The actual widget
        update is always executed on the main tkinter thread.
        """
        timestamp = datetime.now().strftime("%H:%M:%S")
        line = f"[{timestamp}] {message}\n"
        # after(0, ...) enqueues the callback on the main event loop.
        self._widget.after(0, lambda l=line: self._append(l))

    # ------------------------------------------------------------------
    # Internal — only ever called on the main thread via after()
    # ------------------------------------------------------------------

    def _append(self, line: str) -> None:
        widget = self._widget
        widget.config(state="normal")
        widget.insert(tk.END, line)

        # Trim oldest lines if we have exceeded the limit
        current_lines = int(widget.index(tk.END).split(".")[0]) - 1
        if current_lines > self._max_lines:
            excess = current_lines - self._max_lines
            widget.delete("1.0", f"{excess + 1}.0")

        widget.see(tk.END)
        widget.config(state="disabled")
