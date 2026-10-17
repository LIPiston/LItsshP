"""PTY process management for tssh sessions.

pywinpty's ``read(blocking=True)`` is the only reliable way to get streamed
output, so each session owns a reader thread. The thread never touches Qt
objects: it publishes chunks into a lock-protected queue, and a QTimer on the
GUI thread drains that queue and emits signals. This keeps all parsing and
rendering on the main thread.
"""

from __future__ import annotations

import os
import threading
import time
from collections import deque

from PySide6.QtCore import QObject, QTimer, Signal

from winpty import PTY
from winpty.enums import Backend

from . import paths


class PtySession(QObject):
    dataReceived = Signal(str)
    exited = Signal(int)
    started = Signal(int)
    failure = Signal(str)

    def __init__(self, parent: QObject | None = None):
        super().__init__(parent)
        self._pty: PTY | None = None
        self._reader: threading.Thread | None = None
        self._queue: deque[str] = deque()
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._running = False
        self.exit_status: int | None = None
        self.pid: int | None = None
        self.command: list[str] = []

        self._pump = QTimer(self)
        self._pump.setInterval(8)
        self._pump.timeout.connect(self._drain)

    # ------------------------------------------------------------------ start

    def start(self, argv: list[str], cwd: str | None = None,
              cols: int = 120, rows: int = 32) -> bool:
        self.stop()

        command = paths.find_tssh() if argv[0] == "tssh" else argv[0]
        if not command:
            self.failure.emit(
                "tssh was not found. Install it with 'winget install trzsz.tssh' "
                "or set LITSSHP_TSSH to its path."
            )
            return False

        args = [command] + argv[1:]
        env = dict(os.environ)
        env["TERM"] = "xterm-256color"
        env["COLORTERM"] = "truecolor"
        env.pop("LITSSHP", None)
        env_str = "\0".join(f"{k}={v}" for k, v in env.items()) + "\0"

        try:
            pty = PTY(cols, rows, backend=Backend.ConPTY)
            ok = pty.spawn(command, _build_cmdline(args[1:]), cwd=cwd, env=env_str)
        except Exception as exc:  # noqa: BLE001 - surfaced to the UI
            self.failure.emit(f"Could not start tssh: {exc}")
            return False

        if not ok:
            self.failure.emit("Could not start tssh in a pseudo terminal.")
            return False

        self._pty = pty
        self._queue.clear()
        self._stop.clear()
        self._running = True
        self.exit_status = None
        self.pid = pty.pid
        self.command = args

        self._reader = threading.Thread(target=self._read_loop, args=(pty,), daemon=True)
        self._reader.start()
        self._pump.start()
        self.started.emit(self.pid or 0)
        return True

    # ---------------------------------------------------------------- readers

    def _read_loop(self, pty: PTY) -> None:
        while not self._stop.is_set():
            try:
                chunk = pty.read(True)
            except Exception:
                break
            if not chunk:
                break
            with self._lock:
                self._queue.append(chunk)

    def _drain(self) -> None:
        with self._lock:
            if not self._queue:
                chunks = []
            else:
                chunks = list(self._queue)
                self._queue.clear()
        if chunks:
            self.dataReceived.emit("".join(chunks))

        if self._running and self._pty is not None:
            try:
                alive = self._pty.isalive()
            except Exception:
                alive = False
            if not alive:
                self._finish()

    def _finish(self) -> None:
        if not self._running:
            return
        self._running = False
        self._pump.stop()
        self._stop.set()
        status = 0
        if self._pty is not None:
            try:
                status = self._pty.get_exitstatus() or 0
            except Exception:
                status = 0
        self.exit_status = status
        self.exited.emit(status)

    # ---------------------------------------------------------------- writing

    def write(self, data: str) -> None:
        if not data or self._pty is None or not self._running:
            return
        try:
            self._pty.write(data)
        except Exception:
            pass

    def resize(self, cols: int, rows: int) -> None:
        if self._pty is None or not self._running:
            return
        cols = max(20, int(cols))
        rows = max(4, int(rows))
        try:
            self._pty.set_size(cols, rows)
        except Exception:
            pass

    # ------------------------------------------------------------------ stop

    def stop(self) -> None:
        pty = self._pty
        self._running = False
        self._pump.stop()
        self._stop.set()
        self._pty = None
        if pty is not None:
            try:
                pty.cancel_io()
            except Exception:
                pass
            try:
                if pty.isalive():
                    pty.write("\x03")
                    time.sleep(0.05)
            except Exception:
                pass
            try:
                if pty.isalive() and self.pid:
                    os.kill(self.pid, 9)
            except Exception:
                pass
        self._reader = None

    @property
    def running(self) -> bool:
        return self._running


def _build_cmdline(args: list[str]) -> str:
    """Windows command line for the child, quoting each argument."""
    return " " + subprocess_list2cmdline(args)


def subprocess_list2cmdline(args: list[str]) -> str:
    import subprocess
    return subprocess.list2cmdline(args)
