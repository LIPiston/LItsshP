"""A pyte screen with the pieces pyte does not implement.

pyte covers the VT100/xterm core well, but has no alternate screen buffer, no
scrollback and no mouse reporting. tssh sessions need all three: ``vim``,
``tmux`` and ``less`` switch to the alternate screen, the shell needs history,
and tmux/vim expect mouse tracking. The subclass below keeps a primary and an
alternate buffer, records scrolled-off primary lines, and tracks the DEC private
modes used for mouse reporting so the widget can forward events.
"""

from __future__ import annotations

from collections import deque

from pyte import modes as mo
from pyte.screens import Char, Screen

# DEC private modes that are not part of pyte's mode constants. pyte stores
# private mode numbers shifted left by 5, so 1049 lives under 1049 << 5.
ALT_SCREEN = 1047 << 5
ALT_SCREEN_SAVE_CURSOR = 1049 << 5
MOUSE_BUTTON = 1000 << 5
MOUSE_DRAG = 1002 << 5
MOUSE_MOVE = 1003 << 5
MOUSE_SGR = 1006 << 5
BRACKETED_PASTE = 2004 << 5
FOCUS_EVENTS = 1004 << 5


class TerminalScreen(Screen):
    def __init__(self, columns: int, lines: int, history: int = 5000):
        self._history: deque[list[Char]] = deque(maxlen=history)
        self._alt_primary_buffer: dict | None = None
        self._alt_active = False
        self._alt_saved_cursor = False
        super().__init__(columns, lines)

    # ------------------------------------------------------------ scrollback

    @property
    def history_size(self) -> int:
        return len(self._history)

    def history_view(self, offset: int) -> list[list[Char]]:
        """The viewport ``offset`` lines above the live screen (0 = live)."""
        if offset <= 0:
            return [self._line(y) for y in range(self.lines)]
        history = list(self._history)
        take = min(offset, len(history))
        rows = history[len(history) - take:]
        remaining = self.lines - take
        if remaining > 0:
            rows = rows + [self._line(y) for y in range(remaining)]
        return rows

    def clear_history(self) -> None:
        self._history.clear()

    def all_rows(self) -> list[list[Char]]:
        """Scrollback followed by the live screen, oldest first.

        Search needs both halves and their order; ``history_view`` only ever
        returns a viewport's worth of rows.
        """
        return list(self._history) + [self._line(y) for y in range(self.lines)]

    def _line(self, y: int) -> list[Char]:
        row = self.buffer[y]
        return [row[x] for x in range(self.columns)]

    def index(self) -> None:
        """Scroll up one line; archive the top line when the primary buffer scrolls."""
        top, bottom = self.margins or (0, self.lines - 1)
        if not self._alt_active and top == 0 and self.cursor.y == bottom:
            self._history.append(self._line(0))
        super().index()

    def erase_in_display(self, how: int = 0, *args, **kwargs) -> None:
        if how == 3:
            # xterm's "erase saved lines" clears scrollback only.
            self.clear_history()
            return
        super().erase_in_display(how, *args, **kwargs)

    # ------------------------------------------------------- alternate screen

    @property
    def alt_active(self) -> bool:
        return self._alt_active

    def _enter_alt(self, save_cursor: bool) -> None:
        if self._alt_active:
            return
        if save_cursor:
            self.save_cursor()
        self._alt_saved_cursor = save_cursor
        self._alt_primary_buffer = self.buffer
        self.buffer = {}
        self._alt_active = True
        self.cursor.x = 0
        self.cursor.y = 0
        self.dirty.update(range(self.lines))

    def _leave_alt(self) -> None:
        if not self._alt_active:
            return
        self.buffer = self._alt_primary_buffer or {}
        self._alt_primary_buffer = None
        self._alt_active = False
        if self._alt_saved_cursor:
            self.restore_cursor()
        self._alt_saved_cursor = False
        self.dirty.update(range(self.lines))

    def set_mode(self, *modes, **kwargs) -> None:
        if kwargs.get("private"):
            shifted = [m << 5 for m in modes]
            if ALT_SCREEN_SAVE_CURSOR in shifted:
                self._enter_alt(save_cursor=True)
                return
            if ALT_SCREEN in shifted:
                self._enter_alt(save_cursor=False)
                return
        super().set_mode(*modes, **kwargs)

    def reset_mode(self, *modes, **kwargs) -> None:
        if kwargs.get("private"):
            shifted = [m << 5 for m in modes]
            if ALT_SCREEN_SAVE_CURSOR in shifted or ALT_SCREEN in shifted:
                self._leave_alt()
                return
        super().reset_mode(*modes, **kwargs)

    # ------------------------------------------------------------ mouse modes

    @property
    def mouse_mode(self) -> str:
        if MOUSE_MOVE in self.mode:
            return "move"
        if MOUSE_DRAG in self.mode:
            return "drag"
        if MOUSE_BUTTON in self.mode:
            return "button"
        return "off"

    @property
    def mouse_sgr(self) -> bool:
        return MOUSE_SGR in self.mode

    @property
    def bracketed_paste(self) -> bool:
        return BRACKETED_PASTE in self.mode

    @property
    def focus_events(self) -> bool:
        return FOCUS_EVENTS in self.mode

    # ------------------------------------------------------------------ reset

    def reset(self) -> None:
        super().reset()
        self._alt_active = False
        self._alt_primary_buffer = None
        self._alt_saved_cursor = False
