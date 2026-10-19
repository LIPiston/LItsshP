# Skill: Fixing Defects

How to run down a failure in LItsshP. The order matters: most apparent UI bugs
are either a binding error, a platform rendering quirk, or a child process that
never started.

## 0. Classify first

| Symptom | Likely layer | Go to |
| --- | --- | --- |
| Blank/black terminal, but the session says connected | rendering | §2 |
| Typing does nothing, output still arrives | input translation | §3 |
| Text field shows a caret but no glyphs | known rendering defect | §4 |
| Host missing from the sidebar | config parsing | §5 |
| "Property 'x' is not a function" in the console | missing `@Slot` | §6 |
| Dialog/sheet opened but is invisible | animation dependency | §4 |
| Transfer stuck at 0% | meter scraping or ConPTY spawn | §7 |
| App crashes shortly after start/close | QObject lifetime | §8 |

Start every investigation by running the gates:

```bash
.venv/Scripts/python -m compileall -q app
.venv/Scripts/python docs/skills/reference/qml_load_gate.py
.venv/Scripts/python docs/skills/reference/session_features_gate.py
```

A QML binding error is the single most common cause of "the UI is broken", and
the gate prints it with a file and line number. `session_features_gate.py`
covers the renderer-adjacent state (search hits, log text, saved layout) that
breaks without producing a QML warning.

## 1. Read the console

Run from a terminal, not by double-clicking, so QML warnings are visible:

```bash
.venv/Scripts/python -m app.main
```

`file:///...Main.qml:42: TypeError: ...` names the file and line. Warnings
from the vendored md3 module about `Member enabled ... overrides a member of
the base object` are pre-existing and harmless; TypeErrors are not.

## 2. Blank terminal

Work down this list; each step has a different fix.

1. **Is the process alive?** The tab dot and status bar show `connecting`,
   `connected`, `closed` or `failed`. A `failed` state means `tssh` never
   spawned — run `tssh <alias>` directly and read the error.
2. **Is output arriving?** `TerminalModel.feed` appends to `pyte`; if
   `historySize` grows but the screen is black, the problem is rendering.
3. **Is the viewport set?** `setViewport` must be called after the QML `Image`
   has a size. `TerminalPane.syncViewport` runs on `onWidthChanged`,
   `onHeightChanged`, `onModelChanged` and at completion. A zero-size viewport
   produces a 1×1 raster.
4. **Is the image provider registered?** `main.py` calls
   `engine.addImageProvider("terminal", controller.imageProvider())`. Without
   it, every `Image` stays empty with no error.
5. **Is `fillMode` right?** It must be `Image.Stretch`; `Pad` draws the raster
   at raw pixel size and clips on HiDPI.

## 3. Keys do nothing

`TerminalPane.Keys.onPressed` runs first: it handles `Ctrl+Shift+C/V/A`,
`Shift+PgUp/PgDn/Up/Down` and `Ctrl+Home/End`, then hands everything else to
`TerminalModel.handleKey`. If a key is swallowed, check that block order.

`handleKey` maps key codes to VT sequences and, for `Ctrl+<letter>`, sends the
control byte. A prompt that ignores Ctrl+C usually means a window-level
`Shortcut` grabbed it first — the app deliberately defines no `Ctrl+C`
shortcut, and that must stay true (invariant 8).

Mouse input has its own rule: when the running program enabled mouse
reporting (`TerminalModel.mouseReporting`), events are forwarded to it, and
only `Shift` forces local selection. Right-click behaves the same way: with
mouse reporting on and no `Shift`, the press is forwarded and no app menu
opens.

## 4. Text fields, sheets and animation-dependent UI

Two layout shapes are deliberate here, and both were adopted after something
looked wrong on screen. Each has a measured story rather than a guess:

- **Text fields that can overflow use a clipped `Item` plus a `TextEdit`
  moved by `y`.** The composer and the raw-block editor are written this way.
  The original Flickable-based layout showed no text in the app; a minimal
  `Flickable` + `TextEdit` case does render on this machine, so the trigger is
  not fully isolated. Keep the working shape (invariant 7) and verify with real
  multi-line input.
- **Progress is drawn, not animated.** md3's `LinearProgress` eases
  `_visualValue` toward `value`; measured with 30 ms updates it read `0.348`
  while the value was `0.6`, and only settled when updates stopped. For a
  transfer bar that is simply wrong, so the surfaces size a `Rectangle` from
  the fraction (invariant 6). Sheets likewise become visible immediately.

If you suspect a rendering fault, reproduce it in a minimal QML file instead of
rewriting working code, and compare with `QT_QUICK_BACKEND=software` to rule
out the GPU path. Record what you actually observed, not what you expected.

## 5. A host is missing

`ConfigStore.hosts()` only lists **concrete** aliases: wildcards (`*`, `?`,
`[`) are skipped, `Match` blocks are ignored, `#!! HideHost yes` hides a host,
and the first occurrence of an alias wins across `Include`d files. Check the
raw file for those cases before touching the parser.

To see what the app parsed, without the UI:

```python
from app.config import ConfigStore
for h in ConfigStore().hosts(include_hidden=True):
    print(h.alias, h.hostname, h.port, h.user, h.group_labels, h.hidden)
```

(Point `LITSSHP_CONFIG` at the file in question.) Then check
`replace_raw_block` and `set_option` if the *edit* did not stick.

## 6. "is not a function" / property is undefined

Every method QML calls must be decorated with `@Slot` (with a `result=` when it
returns a value). A missing decorator turns the method into a plain Python
attribute that QML cannot invoke. Note that the error appears at the call site
in QML, not when the app starts.

Similarly, a QML binding to a plain slot never re-evaluates. If a value is
computed by a slot but must track changes, expose a notifying `Property`
instead — `activeModel` exists for exactly this reason.

## 7. Transfers

- **Stuck at 0%**: no meter reached the scraper. Confirm the transfer really
  runs under ConPTY (`sftp_client._transfer`), because sftp only prints its
  meter when it owns a TTY. `sftp -b -` never does.
- **`dest open ... Failure` on upload**: usually the source and destination
  are the same file. Use a separate destination.
- **Windows paths mangled**: sftp's batch parser eats backslashes inside
  quotes. `_quote_local` converts to forward slashes; keep that.
- **Download fails on a new folder**: `get` writes into an existing directory.
  `_download` creates the destination and falls back to `%TEMP%\LItsshP` when
  it is not writable.
- **Cancel does nothing**: `cancel()` must stay a `@Slot` and must write
  `\x03` into the transfer PTY.

## 8. Crashes and lifetime

- The controller must outlive the QML engine's teardown: `main.py` deletes the
  engine before the controller, and the QML gate parents the controller to the
  engine. Without either, bindings evaluate against a deleted object and the
  process can crash after a clean-looking run.
- `Session` owns `PtySession` and `TerminalModel`; `closeTab` stops the PTY,
  unregisters the image, then deletes both. Skipping the unregister leaves the
  provider holding a dangling model.
- In shrink-wrapped test scripts, Qt wrappers obtained from
  `childItems()` can lose their C++ object; keep references alive explicitly.

## 9. Reporting a fix

When you have a fix, state three things: what the root cause was, which
invariant it violated (see [Invariants](reference/invariants.md)), and which
gate now covers it. If no gate covers it, say so plainly instead of implying
it is tested.
