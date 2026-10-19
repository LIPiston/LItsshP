"""Terminal session model: screen state, input, and image rendering.

Rendering through ``QQuickPaintedItem`` proved unreliable with Qt's GPU scene
graph (paint callbacks were not scheduled), so the terminal is rasterised into
a QImage on the GUI thread and published through a QQuickImageProvider. That
path is deterministic across render backends, works for HiDPI, and keeps all
terminal state in one Python object that QML can drive.
"""

from __future__ import annotations

import re
import time

from PySide6.QtCore import (Property, QObject, QPointF, QRectF, Qt, QTimer,
                            Signal, Slot)
from PySide6.QtGui import (QColor, QFont, QFontMetricsF, QGuiApplication, QImage,
                           QPainter, QRawFont)
from PySide6.QtQuick import QQuickImageProvider

from pyte.streams import Stream
from wcwidth import wcswidth

from .screen import TerminalScreen

_CUBE = (0, 95, 135, 175, 215, 255)

# Session logs keep the printable text. Escape sequences are removed rather
# than replayed, because the log is for reading and grepping, not for a
# faithful terminal replay.
_ANSI_RE = re.compile(
    r"\x1b\[[0-9;?]*[ -/]*[@-~]"      # CSI
    r"|\x1b\][^\x07\x1b]*(?:\x07|\x1b\\)"  # OSC
    r"|\x1b[()][A-Za-z0-9]"           # charset selection
    r"|\x1b[@-Z\\-_]"                 # two-byte escapes
)
_CTRL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")

ANSI_NAMES = {
    "black": 0, "red": 1, "green": 2, "brown": 3, "blue": 4,
    "magenta": 5, "cyan": 6, "white": 7,
    "brightblack": 8, "brightred": 9, "brightgreen": 10, "brightbrown": 11,
    "brightblue": 12, "brightmagenta": 13, "brightcyan": 14, "brightwhite": 15,
}

DEFAULT_PALETTE = [
    "#1b1b22", "#e06c75", "#98c379", "#e5c07b", "#61afef",
    "#c678dd", "#56b6c2", "#dcdfe4",
    "#5c6370", "#ff7b86", "#a7e08c", "#f0cf8e", "#7cc4ff",
    "#d79ae8", "#6fd3dd", "#ffffff",
]


def _named_index(name: str) -> int | None:
    if not name or name == "default":
        return None
    if name.startswith("#"):
        try:
            return int(name[1:], 16)
        except ValueError:
            return None
    return ANSI_NAMES.get(name)


class TerminalModel(QObject):
    """One terminal: pyte screen + PTY plumbing + rendering."""

    sourceChanged = Signal()
    titleChanged = Signal()
    gridChanged = Signal()
    sessionExited = Signal(int)
    selectionChanged = Signal()
    activityChanged = Signal()
    searchChanged = Signal()

    def __init__(self, session_id: int, parent: QObject | None = None):
        super().__init__(parent)
        self.session_id = session_id
        self._screen = TerminalScreen(120, 32)
        self._stream = Stream(self._screen, strict=False)
        self._pty = None

        self._family = "Cascadia Mono"
        # Qt's `setFamilies` list is a *resolution* order (use the second only
        # if the first is missing entirely), not a per-glyph fallback: with
        # ["Cascadia Mono", "Microsoft YaHei"] a Chinese glyph still came from
        # the system default (measured: SimSun), whatever the user picked.
        # So the fallback is applied here, per character, against the
        # coverage of the primary font.
        self._fallback = ""
        self._pixel_size = 14
        self._glyph_cache: dict[str, bool] = {}
        self._raw_primary: QRawFont | None = None
        self._font = QFont(self._family)
        self._font.setStyleHint(QFont.Monospace)
        self._font.setPixelSize(self._pixel_size)
        self._font.setFixedPitch(True)
        self._metrics = QFontMetricsF(self._font)
        self._cell_w = max(6.0, self._metrics.horizontalAdvance("W"))
        self._cell_h = max(10.0, self._metrics.height())
        self._bold_font = QFont(self._font)
        self._bold_font.setBold(True)
        self._italic_font = QFont(self._font)
        self._italic_font.setItalic(True)
        self._bold_italic_font = QFont(self._font)
        self._bold_italic_font.setBold(True)
        self._bold_italic_font.setItalic(True)
        self._fallback_font = QFont(self._font)
        self._fallback_bold = QFont(self._bold_font)
        self._fallback_italic = QFont(self._italic_font)
        self._fallback_bold_italic = QFont(self._bold_italic_font)

        self._width = 800
        self._height = 480
        self._dpr = 1.0

        self._fg = QColor("#e6e1e7")
        self._bg = QColor("#141218")
        self._cursor_color = QColor("#cdc0ec")
        self._selection_color = QColor(205, 192, 236, 80)
        # Search highlights: the active hit is stronger than the rest, so
        # "next" is visible without moving the viewport again.
        self._search_color = QColor(255, 213, 79, 150)
        self._search_dim_color = QColor(255, 213, 79, 60)
        self._palette = [QColor(c) for c in DEFAULT_PALETTE]

        self._scrollback = 0
        self._selection_anchor: tuple[int, int] | None = None
        self._selection_cursor: tuple[int, int] | None = None
        self._dragging = False
        self._copy_on_select = True

        self._title = ""
        self._revision = 0
        self._image = QImage(1, 1, QImage.Format_ARGB32_Premultiplied)
        self._dirty = True
        self._cursor_on = True
        self._last_output = time.monotonic()

        # Search state. Hits are stored in absolute row coordinates (row 0 is
        # the oldest remembered line) so they stay valid as the screen scrolls
        # and as output appends rows behind them.
        self._search_query = ""
        self._search_hits: list[tuple[int, int, int]] = []   # (row, col, length)
        self._search_index = -1
        self._search_case = False

        # Session log. The file is opened by the controller, which owns the
        # policy (enabled setting, folder); the model only writes text.
        self._log_file = None
        self._log_buffer: list[str] = []

        # Buffered output would otherwise only reach disk when the buffer
        # passes 8 KB or the session ends, leaving a log that looks empty
        # while the session is alive. A slow tick keeps the file current
        # without a write per PTY chunk.
        self._log_timer = QTimer(self)
        self._log_timer.setInterval(1000)
        self._log_timer.timeout.connect(self.flushLog)

        self._paint_timer = QTimer(self)
        self._paint_timer.setSingleShot(True)
        self._paint_timer.setInterval(12)
        self._paint_timer.timeout.connect(self._render)

        self._blink_timer = QTimer(self)
        self._blink_timer.setInterval(530)
        self._blink_timer.timeout.connect(self._blink)

        self._state_poll = QTimer(self)
        self._state_poll.setInterval(120)
        self._state_poll.timeout.connect(self._poll_pty)

        # `idle` flips on a timer rather than on data, because the transition
        # happens by the absence of output: nothing else would fire a signal.
        self._idle_state = True
        self._idle_timer = QTimer(self)
        self._idle_timer.setInterval(300)
        self._idle_timer.timeout.connect(self._poll_idle)

    # -------------------------------------------------------------- lifecycle

    def attachPty(self, pty) -> None:
        self._pty = pty
        pty.dataReceived.connect(self.feed)
        pty.exited.connect(self._on_exit)
        self._state_poll.start()
        self._blink_timer.start()
        self._last_output = time.monotonic()
        self._idle_state = False
        self._idle_timer.start()

    def detachPty(self) -> None:
        self._state_poll.stop()
        self._blink_timer.stop()
        self._idle_timer.stop()
        self._pty = None

    def _poll_idle(self) -> None:
        idle = self._get_idle()
        if idle != self._idle_state:
            self._idle_state = idle
            self.activityChanged.emit()

    def _poll_pty(self) -> None:
        if self._pty is None:
            return
        if not self._pty.running:
            self._state_poll.stop()

    def _on_exit(self, status: int) -> None:
        self._state_poll.stop()
        self.sessionExited.emit(status)

    # ------------------------------------------------------------- properties

    def _get_source(self) -> str:
        return f"image://terminal/{self.session_id}?{self._revision}"

    source = Property(str, _get_source, notify=sourceChanged)

    def _get_title(self) -> str:
        return self._title

    title = Property(str, _get_title, notify=titleChanged)

    def _get_columns(self) -> int:
        return self._screen.columns

    columns = Property(int, _get_columns, notify=gridChanged)

    def _get_rows(self) -> int:
        return self._screen.lines

    rows = Property(int, _get_rows, notify=gridChanged)

    def _get_alt(self) -> bool:
        return self._screen.alt_active

    altScreen = Property(bool, _get_alt, notify=gridChanged)

    def _get_mouse_reporting(self) -> bool:
        """Whether the running app is tracking the mouse (vim, tmux, htop)."""
        return self._screen.mouse_mode != "off"

    mouseReporting = Property(bool, _get_mouse_reporting, notify=gridChanged)

    def _get_history(self) -> int:
        return self._screen.history_size

    historySize = Property(int, _get_history, notify=gridChanged)

    def _get_scrollback(self) -> int:
        return self._scrollback

    scrollbackOffset = Property(int, _get_scrollback, notify=sourceChanged)

    def _get_has_selection(self) -> bool:
        return bool(self._selection_text())

    hasSelection = Property(bool, _get_has_selection, notify=selectionChanged)

    def _get_idle(self) -> bool:
        """True when the session has produced no output for a moment.

        Drives the composer's "send" affordance; it is advisory only, since a
        shell at a prompt that is busy running a command also looks idle.
        """
        return (time.monotonic() - self._last_output) > 0.35

    idle = Property(bool, _get_idle, notify=activityChanged)

    # ------------------------------------------------------------------ input

    @Slot(str)
    def feed(self, data: str) -> None:
        if not data:
            return
        self._last_output = time.monotonic()
        self._cursor_on = True
        before = self._screen.history_size
        self._stream.feed(data)
        added = self._screen.history_size - before
        if self._scrollback:
            self._scrollback = min(self._screen.history_size, self._scrollback + added)
        self._append_log(data)
        # Appending rows shifts absolute search positions; re-running a short
        # query over the live screen is cheaper than tracking the shift, and
        # scrollback rows never change once written.
        if self._search_query:
            self._run_search(keep_index=True)
        self._schedule_render(full=True)
        self.activityChanged.emit()

        title = self._screen.title
        if title and title != self._title and "conhost.exe" not in title:
            self._title = title
            self.titleChanged.emit()

    def _schedule_render(self, full: bool = False) -> None:
        self._dirty = True
        if not self._paint_timer.isActive():
            self._paint_timer.start()

    def _blink(self) -> None:
        if self._scrollback or self._screen.cursor.hidden:
            return
        self._cursor_on = not self._cursor_on
        self._schedule_render()

    # ------------------------------------------------------------------ write

    def _send(self, data: str) -> None:
        if self._scrollback:
            self.scrollToBottom()
        if self._pty is not None:
            self._pty.write(data)

    @Slot(int, str, int, result=bool)
    def handleKey(self, key: int, text: str, modifiers: int) -> bool:
        ctrl = bool(modifiers & Qt.ControlModifier.value)
        alt = bool(modifiers & Qt.AltModifier.value)
        shift = bool(modifiers & Qt.ShiftModifier.value)

        if ctrl and shift:
            if key == Qt.Key_C.value:
                self.copySelection()
                return True
            if key == Qt.Key_V.value:
                self.pasteClipboard()
                return True

        navigation = {
            Qt.Key_Up.value: "\x1b[A",
            Qt.Key_Down.value: "\x1b[B",
            Qt.Key_Right.value: "\x1b[C",
            Qt.Key_Left.value: "\x1b[D",
            Qt.Key_Home.value: "\x1b[H",
            Qt.Key_End.value: "\x1b[F",
            Qt.Key_Insert.value: "\x1b[2~",
            Qt.Key_Delete.value: "\x1b[3~",
            Qt.Key_PageUp.value: "\x1b[5~",
            Qt.Key_PageDown.value: "\x1b[6~",
            Qt.Key_Backtab.value: "\x1b[Z",
            Qt.Key_Escape.value: "\x1b",
            Qt.Key_Tab.value: "\t",
            Qt.Key_Return.value: "\r",
            Qt.Key_Enter.value: "\r",
            Qt.Key_Backspace.value: "\x7f",
        }
        if key in navigation:
            sequence = navigation[key]
            self._send(("\x1b" + sequence) if alt else sequence)
            return True

        if Qt.Key_F1.value <= key <= Qt.Key_F12.value:
            n = key - Qt.Key_F1.value + 1
            sequence = {
                1: "\x1bOP", 2: "\x1bOQ", 3: "\x1bOR", 4: "\x1bOS",
                5: "\x1b[15~", 6: "\x1b[17~", 7: "\x1b[18~", 8: "\x1b[19~",
                9: "\x1b[20~", 10: "\x1b[21~", 11: "\x1b[23~", 12: "\x1b[24~",
            }[n]
            self._send(sequence)
            return True

        if ctrl and text:
            ch = text.lower()
            if "a" <= ch <= "z":
                self._send(chr(ord(ch) - ord("a") + 1))
                return True
            extra = {" ": "\x00", "[": "\x1b", "\\": "\x1c", "]": "\x1d",
                     "^": "\x1e", "_": "\x1f", "?": "\x7f"}
            if ch in extra:
                self._send(extra[ch])
                return True

        if text:
            self._send(("\x1b" + text) if alt else text)
            return True
        return False

    # ------------------------------------------------------------------ mouse

    def _cell(self, x: float, y: float) -> tuple[int, int]:
        col = int((x - 8) / self._cell_w)
        row = int((y - 6) / self._cell_h)
        return (max(0, min(self._screen.columns - 1, col)),
                max(0, min(self._screen.lines - 1, row)))

    def _mouse_report(self, cb: int, col: int, row: int, release: bool,
                      motion: bool = False) -> str:
        code = 3 if release else cb
        if motion and not release:
            code += 32
        if self._screen.mouse_sgr:
            return f"\x1b[<{code};{col + 1};{row + 1}{'m' if release else 'M'}"
        code += 32
        return f"\x1b[M{chr(code + 32)}{chr(col + 33)}{chr(row + 33)}"

    def _mouse_passthrough(self, modifiers: int) -> bool:
        return self._screen.mouse_mode != "off" and not (modifiers & Qt.ShiftModifier.value)

    @Slot(float, float, int, int)
    def mousePress(self, x: float, y: float, button: int, modifiers: int) -> None:
        col, row = self._cell(x, y)
        if self._mouse_passthrough(modifiers):
            cb = {Qt.LeftButton.value: 0, Qt.MiddleButton.value: 1,
                  Qt.RightButton.value: 2}.get(button)
            if cb is not None:
                self._send(self._mouse_report(cb, col, row, False))
            return

        if button == Qt.LeftButton.value:
            self._selection_anchor = (col, row)
            self._selection_cursor = (col, row)
            self._dragging = True
            self.selectionChanged.emit()
        elif button == Qt.MiddleButton.value:
            self.pasteClipboard()
        self._schedule_render()

    @Slot(float, float, int, int)
    def mouseMove(self, x: float, y: float, buttons: int, modifiers: int) -> None:
        col, row = self._cell(x, y)
        if self._mouse_passthrough(modifiers) and self._screen.mouse_mode in ("drag", "move") \
                and buttons & Qt.LeftButton.value:
            self._send(self._mouse_report(0, col, row, False, motion=True))
            return
        if self._dragging and buttons & Qt.LeftButton.value:
            self._selection_cursor = (col, row)
            self._schedule_render()

    @Slot(float, float, int, int)
    def mouseRelease(self, x: float, y: float, button: int, modifiers: int) -> None:
        col, row = self._cell(x, y)
        if self._mouse_passthrough(modifiers):
            if button == Qt.LeftButton.value:
                self._send(self._mouse_report(0, col, row, True))
            return
        if button == Qt.LeftButton.value and self._dragging:
            self._selection_cursor = (col, row)
            self._dragging = False
            if self.hasSelection:
                if self._copy_on_select:
                    self.copySelection()
            else:
                self._selection_anchor = None
                self._selection_cursor = None
            self.selectionChanged.emit()
            self._schedule_render()

    @Slot(float, float)
    def mouseDoubleClick(self, x: float, y: float) -> None:
        col, row = self._cell(x, y)
        offset = 0 if self._screen.alt_active else self._scrollback
        rows = self._screen.history_view(offset)
        if row >= len(rows):
            return
        line = rows[row]
        is_word = lambda c: c.data.isalnum() or c.data in "_-./@:~="
        start = end = col
        while start > 0 and is_word(line[start - 1]):
            start -= 1
        while end < len(line) - 1 and is_word(line[end + 1]):
            end += 1
        self._selection_anchor = (start, row)
        self._selection_cursor = (end + 1, row)
        self.selectionChanged.emit()
        self._schedule_render()
        if self._copy_on_select:
            self.copySelection()

    @Slot(float, float, int, int)
    def wheel(self, x: float, y: float, delta: int, modifiers: int) -> None:
        steps = int(delta / 120) or (1 if delta > 0 else -1)
        if self._mouse_passthrough(modifiers):
            col, row = self._cell(x, y)
            button = 64 if steps > 0 else 65
            for _ in range(abs(steps)):
                self._send(self._mouse_report(button, col, row, False))
            return
        self.scrollLines(steps * 3)

    # -------------------------------------------------------------- selection

    def _selection_range(self):
        if self._selection_anchor is None or self._selection_cursor is None:
            return None
        a, b = self._selection_anchor, self._selection_cursor
        if a[1] > b[1] or (a[1] == b[1] and a[0] > b[0]):
            a, b = b, a
        return a, b

    def _selection_text(self) -> str:
        rng = self._selection_range()
        if rng is None:
            return ""
        (sx, sy), (ex, ey) = rng
        offset = 0 if self._screen.alt_active else self._scrollback
        rows = self._screen.history_view(offset)
        out: list[str] = []
        for y in range(sy, ey + 1):
            if y >= len(rows):
                break
            line = rows[y]
            start = sx if y == sy else 0
            end = ex if y == ey else len(line)
            out.append("".join(line[x].data for x in range(start, min(end, len(line)))).rstrip())
        return "\n".join(out)

    @Slot(result=str)
    def selectedText(self) -> str:
        return self._selection_text()

    @Slot()
    def copySelection(self) -> None:
        text = self._selection_text()
        if text:
            QGuiApplication.clipboard().setText(text)

    @Slot(result=bool)
    def copySelectionIfAny(self) -> bool:
        """Copy and report whether anything was copied (for UI feedback)."""
        text = self._selection_text()
        if not text:
            return False
        QGuiApplication.clipboard().setText(text)
        return True

    @Slot()
    def clearSelection(self) -> None:
        self._selection_anchor = None
        self._selection_cursor = None
        self.selectionChanged.emit()
        self._schedule_render()

    @Slot()
    def selectAll(self) -> None:
        """Select the whole visible viewport (not the entire scrollback)."""
        rows = self._screen.lines
        last = max(0, rows - 1)
        self._selection_anchor = (0, 0)
        self._selection_cursor = (max(0, self._screen.columns - 1), last)
        self.selectionChanged.emit()
        self._schedule_render()
        if self._copy_on_select:
            self.copySelection()

    @Slot(result=bool)
    def hasClipboardText(self) -> bool:
        return bool(QGuiApplication.clipboard().text())

    @Slot()
    def pasteClipboard(self) -> None:
        text = QGuiApplication.clipboard().text()
        if not text:
            return
        if self._screen.bracketed_paste:
            text = "\x1b[200~" + text + "\x1b[201~"
        self._send(text)

    @Slot(str)
    def sendText(self, text: str) -> None:
        """Send text verbatim to the session, honouring bracketed paste."""
        if not text:
            return
        if self._screen.bracketed_paste:
            text = "\x1b[200~" + text + "\x1b[201~"
        self._send(text)

    @Slot(str, bool)
    def runCommand(self, text: str, clear_first: bool = False) -> None:
        """Send a composed block as if each line had been typed and entered.

        Deliberately *not* bracketed paste: the composer exists to queue work
        ahead of time, so every line has to execute. A bracketed paste would
        leave the block sitting at the prompt until someone pressed Enter.
        Line continuations still behave normally, because the shell sees the
        same sequence it would from a keyboard.
        """
        if not text:
            return
        normalized = text.replace("\r\n", "\n").replace("\r", "\n").rstrip("\n")
        if not normalized:
            return
        if clear_first:
            normalized = "\x15" + normalized
        self._send(normalized.replace("\n", "\r") + "\r")

    @Slot(bool)
    def setCopyOnSelect(self, enabled: bool) -> None:
        self._copy_on_select = bool(enabled)

    @Slot(int)
    def scrollLines(self, delta: int) -> None:
        """Positive ``delta`` scrolls back into history, negative returns to the live view."""
        if self._screen.alt_active:
            return
        self._scrollback = max(0, min(self._screen.history_size,
                                      self._scrollback + delta))
        self._schedule_render()

    @Slot()
    def scrollToBottom(self) -> None:
        if self._scrollback:
            self._scrollback = 0
            self._schedule_render()

    # ----------------------------------------------------------------- search

    def _get_search_query(self) -> str:
        return self._search_query

    searchQuery = Property(str, _get_search_query, notify=searchChanged)

    def _get_search_count(self) -> int:
        return len(self._search_hits)

    searchCount = Property(int, _get_search_count, notify=searchChanged)

    def _get_search_current(self) -> int:
        """1-based position of the highlighted hit, 0 when there is none."""
        return self._search_index + 1 if self._search_index >= 0 else 0

    searchCurrent = Property(int, _get_search_current, notify=searchChanged)

    @Slot(str, bool)
    def setSearch(self, query: str, case_sensitive: bool = False) -> None:
        """Highlight ``query`` across scrollback and select the newest hit."""
        self._search_query = query or ""
        self._search_case = bool(case_sensitive)
        self._run_search(keep_index=False)
        if self._search_hits:
            self._jump_to(len(self._search_hits) - 1)

    @Slot()
    def clearSearch(self) -> None:
        if not self._search_query and not self._search_hits:
            return
        self._search_query = ""
        self._search_hits = []
        self._search_index = -1
        self.searchChanged.emit()
        self._schedule_render()

    @Slot(int)
    def nextMatch(self, delta: int = 1) -> None:
        if not self._search_hits:
            return
        index = self._search_index + (1 if delta >= 0 else -1)
        self._jump_to(index % len(self._search_hits))

    def _run_search(self, keep_index: bool) -> None:
        needle = self._search_query
        if not needle:
            self._search_hits = []
            self._search_index = -1
            self.searchChanged.emit()
            self._schedule_render()
            return

        rows = self._screen.all_rows()
        hay = needle if self._search_case else needle.lower()
        hits: list[tuple[int, int, int]] = []
        for row_index, row in enumerate(rows):
            text, columns, spans = _row_text(row)
            if not self._search_case:
                text = text.lower()
            start = 0
            while True:
                found = text.find(hay, start)
                if found < 0:
                    break
                # A match is expressed in characters; the highlight is painted
                # in columns, and a wide character covers two of them.
                first = columns[found]
                width = sum(spans[found:found + len(needle)])
                hits.append((row_index, first, width))
                start = found + max(1, len(needle))

        self._search_hits = hits
        if not keep_index or self._search_index >= len(hits):
            self._search_index = len(hits) - 1 if hits else -1
        self.searchChanged.emit()
        self._schedule_render()

    def _jump_to(self, index: int) -> None:
        if not (0 <= index < len(self._search_hits)):
            return
        self._search_index = index
        row = self._search_hits[index][0]
        history = self._screen.history_size
        # Absolute row -> scrollback offset. Live rows (row >= history) sit at
        # offset 0, so a match in the visible screen does not scroll at all.
        if row < history:
            self._scrollback = history - row
        else:
            self._scrollback = 0
        self.searchChanged.emit()
        self._schedule_render()

    def _row_marks(self, y: int) -> dict[int, int]:
        """Highlight strength per column for one viewport row.

        ``2`` is the match the user jumped to, ``1`` every other match, so the
        active hit is distinguishable without a second colour.
        """
        if not self._search_hits:
            return {}
        offset = 0 if self._screen.alt_active else self._scrollback
        take = min(offset, self._screen.history_size)
        absolute = self._screen.history_size - take + y
        marks: dict[int, int] = {}
        for index, (row, col, length) in enumerate(self._search_hits):
            if row != absolute:
                continue
            strength = 2 if index == self._search_index else 1
            for x in range(col, col + length):
                marks[x] = max(marks.get(x, 0), strength)
        return marks

    # ------------------------------------------------------------------- log

    def attachLog(self, handle) -> None:
        """Start appending printable output to an open text file."""
        self._log_file = handle
        self._log_buffer = []
        self._log_timer.start()

    def detachLog(self) -> None:
        self._log_timer.stop()
        self.flushLog()
        self._log_file = None

    @Slot()
    def flushLog(self) -> None:
        if self._log_file is None or not self._log_buffer:
            return
        try:
            self._log_file.write("".join(self._log_buffer))
            self._log_file.flush()
        except (OSError, ValueError):
            self._log_file = None
        self._log_buffer = []

    def _append_log(self, data: str) -> None:
        if self._log_file is None:
            return
        text = _ANSI_RE.sub("", data)
        # Carriage returns redraw a line; keeping only the last revision is
        # closer to what the user saw, and avoids a log full of half-drawn
        # progress bars.
        parts = text.split("\n")
        cleaned = []
        for part in parts:
            # A PTY ends lines with "\r\n", so the segment after the final
            # carriage return is the content, not the trailing blank.
            segment = part.rstrip("\r").split("\r")[-1]
            cleaned.append(_CTRL_RE.sub("", segment))
        self._log_buffer.append("\n".join(cleaned))
        if sum(len(piece) for piece in self._log_buffer) > 8192:
            self.flushLog()

    # ---------------------------------------------------------------- viewport

    def _make_font(self, bold: bool = False, italic: bool = False,
                   family: str | None = None) -> QFont:
        font = QFont(family or self._family)
        font.setStyleHint(QFont.Monospace)
        font.setPixelSize(self._pixel_size)
        font.setFixedPitch(True)
        font.setBold(bold)
        font.setItalic(italic)
        return font

    def _needs_fallback(self, text: str) -> bool:
        """Whether the primary font lacks a glyph for ``text``.

        Results are cached per character: a screen repaint asks this for every
        non-ASCII glyph and the answer cannot change while the fonts do not.
        """
        if not self._fallback or not self._raw_primary:
            return False
        for ch in text:
            known = self._glyph_cache.get(ch)
            if known is None:
                known = self._raw_primary.supportsCharacter(ch)
                self._glyph_cache[ch] = known
            if not known:
                return True
        return False

    @Slot(str, int, str)
    def setFont(self, family: str, pixel_size: int,
                fallback: str = "") -> None:
        """Set the primary family and an optional fallback for missing glyphs.

        The cell width always comes from the primary font. A fallback glyph is
        centred in its cell box when painted, never allowed to widen the grid:
        one Chinese character on a line must not shift everything after it.
        """
        self._family = family or "Cascadia Mono"
        fallback = (fallback or "").strip()
        self._fallback = fallback if fallback != self._family else ""
        self._pixel_size = max(8, int(pixel_size))
        self._glyph_cache = {}

        self._font = self._make_font()
        self._metrics = QFontMetricsF(self._font)
        # Exact advance, no padding factor: a run is drawn as one string, and
        # a 1.02 multiplier made the last glyph of a full-width line sit
        # ~15 px past its column (measured at 80 chars). Grid and font
        # advance have to agree for the columns to stay aligned.
        self._cell_w = max(6.0, self._metrics.horizontalAdvance("W"))
        self._cell_h = max(10.0, self._metrics.height())

        self._raw_primary = QRawFont.fromFont(self._font)
        self._bold_font = self._make_font(bold=True)
        self._italic_font = self._make_font(italic=True)
        self._bold_italic_font = self._make_font(bold=True, italic=True)
        self._fallback_font = self._make_font(family=self._fallback)
        self._fallback_bold = self._make_font(bold=True, family=self._fallback)
        self._fallback_italic = self._make_font(italic=True, family=self._fallback)
        self._fallback_bold_italic = self._make_font(bold=True, italic=True,
                                                     family=self._fallback)

        self._update_grid()
        # The viewport is unchanged, so setViewport() won't re-enter: tell QML
        # the grid changed or the pane keeps rendering the old column count.
        self.gridChanged.emit()
        self._schedule_render()

    @Slot(str, str, str, str, "QVariantList")
    def applyTheme(self, fg: str, bg: str, cursor: str, selection: str,
                   palette: list) -> None:
        self._fg = QColor(fg)
        self._bg = QColor(bg)
        self._cursor_color = QColor(cursor)
        # build_palette hands over #AARRGGBB; QColor parses that directly. Keep
        # the default when the string is unusable rather than painting an
        # invalid colour.
        candidate = QColor(selection)
        if candidate.isValid():
            self._selection_color = candidate
        if palette:
            self._palette = [QColor(c) for c in palette]
        self._schedule_render()

    @Slot(float, float, float)
    def setViewport(self, width: float, height: float, dpr: float) -> None:
        if (abs(width - self._width) < 1 and abs(height - self._height) < 1
                and abs(dpr - self._dpr) < 0.01):
            return
        self._width = max(40.0, width)
        self._height = max(40.0, height)
        self._dpr = max(1.0, dpr)
        self._update_grid()
        self._schedule_render()

    def _update_grid(self) -> None:
        cols = max(20, int((self._width - 8) // self._cell_w))
        rows = max(4, int((self._height - 4) // self._cell_h))
        if cols == self._screen.columns and rows == self._screen.lines:
            return
        self._screen.resize(lines=rows, columns=cols)
        if self._pty is not None:
            self._pty.resize(cols, rows)
        self.gridChanged.emit()

    # ---------------------------------------------------------------- rendering

    def image(self) -> QImage:
        return self._image

    def _render(self) -> None:
        width = max(1, int(self._width * self._dpr))
        height = max(1, int(self._height * self._dpr))
        img = QImage(width, height, QImage.Format_ARGB32_Premultiplied)
        img.fill(self._bg)

        painter = QPainter(img)
        painter.setRenderHint(QPainter.TextAntialiasing, True)
        painter.scale(self._dpr, self._dpr)
        painter.setFont(self._font)

        offset = 0 if self._screen.alt_active else self._scrollback
        rows = self._screen.history_view(offset)
        selection = self._selection_range()

        for y, row in enumerate(rows):
            self._paint_row(painter, row, y, selection, self._row_marks(y))
        if offset == 0 and not self._screen.cursor.hidden and self._cursor_on:
            self._paint_cursor(painter, rows)
        painter.end()
        img.setDevicePixelRatio(self._dpr)

        self._image = img
        self._revision += 1
        self.sourceChanged.emit()

    def _paint_row(self, painter: QPainter, row: list, y: int, selection,
                   marks: dict[int, int] | None = None) -> None:
        cell_w, cell_h = self._cell_w, self._cell_h
        top = 2 + y * cell_h
        x = 4.0
        run_text: list[str] = []
        run_cells: list = []
        run_spans: list[int] = []
        run_selected: list[bool] = []
        run_mark: list[int] = []
        run_fb: list[bool] = []

        def flush():
            nonlocal x, run_text, run_cells, run_spans, run_selected, run_mark, run_fb
            if not run_cells:
                return
            attr = run_cells[0]
            fg = self._fg_for(attr)
            bg = self._bg_for(attr)
            width = cell_w * sum(run_spans)
            rect = QRectF(x, top, width, cell_h)
            if bg is not None:
                painter.fillRect(rect, bg)
            # The selection is an overlay, not a colour swap: reversing the
            # cell would hide its own background and produce different results
            # for every program. The themed alpha colour keeps the text
            # readable and matches the accent chosen in Settings.
            if run_selected[0]:
                painter.fillRect(rect, self._selection_color)
            if run_mark[0]:
                painter.fillRect(rect, self._search_color
                                 if run_mark[0] == 2 else self._search_dim_color)
            font = self._font_for(attr)
            painter.setFont(font)
            painter.setPen(fg)
            # One draw call per run is several times cheaper than one per
            # glyph, and ASCII runs are what a frame is made of. It is only
            # valid when the whole run is one width and one font: a wide
            # glyph, or any glyph the primary lacks, needs its own placement.
            if all(span == 1 for span in run_spans) and not any(run_fb):
                # A run only gets here when every glyph is the primary
                # font's, so one font is right for all of them.
                painter.drawText(rect, int(Qt.AlignLeft | Qt.AlignVCenter),
                                 "".join(run_text))
            else:
                cursor_x = x
                for text, span in zip(run_text, run_spans):
                    if not text.strip():
                        cursor_x += cell_w * span
                        continue
                    glyph_font = self._font_for(attr, text)
                    painter.setFont(glyph_font)
                    metrics = QFontMetricsF(glyph_font)
                    if span == 1:
                        painter.drawText(QRectF(cursor_x, top, cell_w, cell_h),
                                         int(Qt.AlignLeft | Qt.AlignVCenter), text)
                    else:
                        # A wide glyph occupies two columns, but the font's own
                        # advance is usually narrower than 2 * cell_w. Centre it
                        # in its two-cell box so the next glyph does not creep
                        # left; drawing each glyph keeps every column on the
                        # grid instead of letting the run accumulate drift.
                        advance = metrics.horizontalAdvance(text)
                        baseline = top + (cell_h + metrics.ascent()
                                          - metrics.descent()) / 2
                        painter.drawText(
                            QPointF(cursor_x + (cell_w * span - advance) / 2,
                                    baseline), text)
                    cursor_x += cell_w * span
                painter.setFont(font)
            self._decorate(painter, attr, x, top, width, fg)
            x += width
            run_text = []
            run_cells = []
            run_spans = []
            run_selected = []
            run_mark = []
            run_fb = []

        for col, cell in enumerate(row):
            span = _cell_span(cell)
            if span == 0:
                # The stub cell of a wide glyph: its columns were already
                # counted with the glyph, so it must not advance the grid.
                continue
            selected = selection is not None and _inside(selection, y, col)
            mark = (marks or {}).get(col, 0)
            fallback = self._needs_fallback(cell.data)
            if run_cells and (not _same_style(run_cells[-1], cell)
                              or run_selected[-1] != selected
                              or run_mark[-1] != mark
                              or run_fb[-1] != fallback):
                flush()
            run_text.append(cell.data)
            run_cells.append(cell)
            run_spans.append(span)
            run_selected.append(selected)
            run_mark.append(mark)
            run_fb.append(fallback)
        flush()

    def _paint_cursor(self, painter: QPainter, rows: list) -> None:
        cx, cy = self._screen.cursor.x, self._screen.cursor.y
        if cy >= len(rows) or cx >= len(rows[cy]):
            return
        attr = rows[cy][cx]
        span = _cell_span(attr) or 1
        rect = QRectF(4 + cx * self._cell_w, 2 + cy * self._cell_h,
                      self._cell_w * span, self._cell_h)
        painter.fillRect(rect, self._fg if attr.reverse else self._cursor_color)
        if attr.data.strip():
            painter.setFont(self._font_for(attr, attr.data))
            painter.setPen(self._bg if attr.reverse else self._bg_for(attr) or self._bg)
            painter.drawText(rect, int(Qt.AlignHCenter | Qt.AlignVCenter), attr.data)

    def _decorate(self, painter: QPainter, attr, x: float, top: float,
                  width: float, fg: QColor) -> None:
        if not (attr.underscore or attr.strikethrough):
            return
        painter.setPen(fg)
        if attr.underscore:
            painter.drawLine(int(x), int(top + self._cell_h - 2),
                             int(x + width), int(top + self._cell_h - 2))
        if attr.strikethrough:
            painter.drawLine(int(x), int(top + self._cell_h / 2),
                             int(x + width), int(top + self._cell_h / 2))

    def _font_for(self, attr, text: str = "") -> QFont:
        bold = bool(attr.bold)
        italic = bool(attr.italics)
        if text and self._needs_fallback(text):
            if bold and italic:
                return self._fallback_bold_italic
            if bold:
                return self._fallback_bold
            if italic:
                return self._fallback_italic
            return self._fallback_font
        if bold and italic:
            return self._bold_italic_font
        if bold:
            return self._bold_font
        if italic:
            return self._italic_font
        return self._font

    def _fg_for(self, attr) -> QColor:
        color = self._resolve(attr.fg)
        if attr.reverse:
            bg = self._bg_for(attr)
            return bg if bg is not None else self._bg
        return color or self._fg

    def _bg_for(self, attr) -> QColor | None:
        color = self._resolve(attr.bg)
        if attr.reverse:
            return self._fg
        return color

    def _resolve(self, name: str) -> QColor | None:
        idx = _named_index(name)
        if idx is None:
            return None
        if idx < 16:
            return self._palette[idx]
        if idx < 232:
            i = idx - 16
            return QColor(_CUBE[i // 36], _CUBE[(i // 6) % 6], _CUBE[i % 6])
        level = 8 + (idx - 232) * 10
        return QColor(level, level, level)


class TerminalImageProvider(QQuickImageProvider):
    def __init__(self):
        super().__init__(QQuickImageProvider.Image)
        self._models: dict[int, TerminalModel] = {}

    def register(self, model: TerminalModel) -> None:
        self._models[model.session_id] = model

    def unregister(self, model: TerminalModel) -> None:
        self._models.pop(model.session_id, None)

    def requestImage(self, image_id, size, requested_size):  # noqa: N802
        key = image_id.split("?")[0]
        try:
            session = int(key)
        except ValueError:
            return QImage(1, 1, QImage.Format_ARGB32_Premultiplied)
        model = self._models.get(session)
        if model is None:
            return QImage(1, 1, QImage.Format_ARGB32_Premultiplied)
        return model.image()


def _same_style(a, b) -> bool:
    return (a.fg == b.fg and a.bg == b.bg and a.bold == b.bold
            and a.italics == b.italics and a.underscore == b.underscore
            and a.strikethrough == b.strikethrough and a.reverse == b.reverse)


def _cell_span(cell) -> int:
    """Columns a cell occupies: 2 for a wide glyph, 0 for its stub.

    pyte writes a full-width character into one cell and leaves the cell after
    it with empty data. Treating that empty cell as one column is what made
    CJK text drift left against the grid.
    """
    data = cell.data
    if not data:
        return 0
    return 2 if wcswidth(data) == 2 else 1


def _row_text(row) -> tuple[str, list[int], list[int]]:
    """(text, column of each character, columns each character occupies).

    A search match is found in the text, but the highlight is painted by
    column. With wide characters those two indices differ, so the mapping has
    to be carried alongside the text.
    """
    chars: list[str] = []
    columns: list[int] = []
    spans: list[int] = []
    for col, cell in enumerate(row):
        if not cell.data:
            continue
        for ch in cell.data:
            chars.append(ch)
            columns.append(col)
            spans.append(2 if wcswidth(ch) == 2 else 1)
    return "".join(chars), columns, spans


def _inside(rng, y: int, x: int) -> bool:
    (sx, sy), (ex, ey) = rng
    if y < sy or y > ey:
        return False
    if sy == ey:
        return sx <= x < ex
    if y == sy:
        return x >= sx
    if y == ey:
        return x < ex
    return True
