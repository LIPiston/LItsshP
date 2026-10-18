# Skill: Terminal Rendering

How a session's bytes become pixels, where to change what, and the two platform
defects that shape the design.

## The pipeline

```
PtySession (ConPTY)
   reader thread: pty.read(True) -> deque
   GUI QTimer (8 ms): drain -> dataReceived(str)
        |
        v
TerminalModel.feed(text)
   pyte.Stream.feed -> TerminalScreen
   history grows -> scrollback offset adjusted to keep the view stable
   schedules a repaint (12 ms single-shot)
        |
        v
TerminalModel._render()
   new QImage(width*dpr, height*dpr), fill with bg
   per row: group consecutive cells with equal attributes -> one drawText
   cursor painted when the live view is showing and it is "on"
   revision += 1 -> sourceChanged
        |
        v
QML Image { source: image://terminal/<id>?<revision>; fillMode: Stretch }
```

### Why an image provider and not a painted item

`QQuickPaintedItem` paint callbacks were not scheduled reliably on this
backend. Rasterising into a `QImage` on the GUI thread and publishing it
through `QQuickImageProvider` is deterministic across backends, handles HiDPI
(by setting `devicePixelRatio` on the image), and keeps all terminal state in
one Python object.

- The provider returns the crisp raster; `Image` must use `fillMode:
  Image.Stretch`, never `Pad`.
- Changing the model's `source` revision is what triggers a new texture
  request. If the screen looks stale, the revision is not being bumped.
- `cache: false` on the `Image` avoids Qt holding a stale texture.

## Screen model

`app/screen.py` subclasses `pyte.Screen` to add what pyte lacks:

| Feature | Why it is needed | Implementation |
| --- | --- | --- |
| scrollback | shells produce more than one screen | `deque(maxlen=5000)` filled in `index()` when the primary buffer scrolls |
| alternate screen | `vim`, `tmux`, `less` | `_enter_alt` / `_leave_alt` on private modes 1047 / 1049 |
| mouse reporting | apps expect clicks and wheel | `mouse_mode` / `mouse_sgr` from private modes 1000/1002/1003/1006 |
| bracketed paste | paste must not execute line by line in shells that enable it | `bracketed_paste` from mode 2004 |

`history_view(offset)` returns the viewport `offset` lines above live, padded
with live rows when the offset is larger than the history. Everything that
paints or extracts text goes through it, so scrollback and the live screen use
one code path.

`erase_in_display(3)` clears scrollback (`ESC[3J`) without touching the
screen; this is what `clear` does in many setups.

### Theme-aware palettes are per-cell

Cells hold `pyte` attribute names (`red`, `brightblue`, or `#rrggbb` for
256-colour). `TerminalModel._resolve` maps them to the current palette, so
`applyTheme` only needs to swap the palette list and repaint — no screen
re-parse. `terminal_theme.py` builds that palette from the Material scheme
(`match`) or from a fixed classic set (`classic`).

## Input translation

| Path | File | Rule |
| --- | --- | --- |
| keys | `TerminalModel.handleKey` | nav keys → VT sequences; `Ctrl+letter` → control bytes; `Alt` prefixes `ESC`; `Ctrl+Shift+C/V` copy/paste before any byte is sent |
| local scroll | `TerminalPane.Keys.onPressed` | `Shift+PgUp/PgDn`, `Shift+↑/↓` scroll the view; bare PgUp/PgDn must reach the app |
| mouse | `mousePress/Move/Release/wheel` | forwarded when the app tracks the mouse; `Shift` always means local selection |
| selection | same file | drag selection, double-click word selection, copy-on-select |
| paste | `pasteClipboard` | wraps in `ESC[200~ … ESC[201~` when the app enabled bracketed paste |

`_send()` scrolls back to the live view before writing, because typed input
that goes to a scrolled-back view is invisible.

## The command composer contract

`runCommand(text, clear_first)` sends each line as if typed followed by `\r`,
**not** as a bracketed paste. The composer's purpose is to queue work; a
bracketed paste would sit at the prompt until Enter. If you change this, the
composer's Enter/Ctrl+Enter semantics must change with it.

`TerminalPane` and `Workspace` are the only places that know which pane is
active. `Workspace.activeTerminal()` is a *function* on purpose: a property
binding would evaluate while the `Repeater` has no delegates and stay `null`.

## Changing colours or fonts

1. Colours: `app/terminal_theme.py` (`build_palette`). Keep the ANSI hues
   distinguishable; only bg/fg/cursor/selection should follow the theme.
2. Fonts: `TerminalModel.setFont` recomputes cell metrics and calls
   `_update_grid`, which emits `gridChanged`. The `setFont` docstring notes why
   the signal is emitted explicitly: the viewport did not change, so
   `setViewport` would not re-enter, and QML would keep the old column count.
3. Cell geometry: `_cell_w` is `horizontalAdvance("W") * 1.02` (the fudge
   keeps wide glyphs from clipping); `_cell_h` is the font height. The
   terminal's origin is inset by 4 px horizontally and 2 px vertically — both
   `_paint_row` and `_cell` must agree, or clicks land on the wrong cell.

## Working rules

- Never render off the GUI thread. `_render` allocates a `QImage` and paints;
  a worker thread would also contend with the PTY reader.
- Keep `feed` cheap: it runs per chunk and only appends to `pyte`.
- Any new visible state must be correct without an animation finishing: size
  bars from the value, and make sheets appear immediately (invariant 6). Test
  by resizing the window while output streams — a stale grid or a bar frozen
  behind its percentage is the tell.
- When in doubt about a rendering regression, reproduce it with a minimal QML
  file and compare the default backend with `QT_QUICK_BACKEND=software`.
  Only claim a platform defect if you can show it in that minimal file.
