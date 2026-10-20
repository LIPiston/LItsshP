# Reference: Architecture

LItsshP is a Qt Quick front end wrapped around the `tssh` binary. It is not an
SSH implementation: every session is a real `tssh <alias>` process in a
pseudo-terminal, and the app only contributes screen rendering, input
translation and UI. That single decision is why ProxyJump, agent forwarding,
`encPassword`, trzsz transfers and `#!!` options all behave exactly as they do
on the command line.

## Layers

```
QML (app/qml/)
  Main ─ HostSidebar ─ Workspace ─ TerminalPane
       ├ HostEditorSheet / SettingsSheet / TunnelSheet / CommandPalette
       ├ KeyManagerSheet / SnippetSheet / split picker
       ├ TransferIndicator / TransferPopover
       └ TransferWindow (separate top-level window)

Python (app/)
  controller.py      QML-facing facade: hosts, tabs, settings, transfers, tunnels
  config.py          ~/.ssh/config parser + byte-preserving writer (+ Include)
  secret.py          tssh encPassword encode/decode
  paths.py           home, config, state, logs, tssh/sftp discovery
  pty_session.py     tssh in a ConPTY, reader thread, GUI-side drain timer
  screen.py          pyte Screen subclass: scrollback, alt screen, mouse modes
  terminal_model.py  grid → QImage, key/mouse translation, selection, search, log
  terminal_theme.py  terminal palette derived from the active Pebrel theme
  sftp_client.py     SFTP listing (batch) and transfers (ConPTY + meter scraping)
  tunnel.py          forward specs + one supervised `tssh -N` per host
  keys.py            key inventory, local fingerprints, ssh-keygen/keyscan wrappers
  theme.py           Pebrel palettes, skin tokens, colour math, radius ladder
  style.py           md3's StyleManager / ColorHelper, resolved from theme.py
  main.py            entry point: singletons, image provider, window geometry

third_party/md3/     vendored material-components-qml QML module
```

## Terminal data path

The renderer is deliberately unusual, and the reason is a platform defect
documented in [Terminal rendering](../terminal-rendering.md).

```
tssh -- ConPTY --(reader thread)--> deque --(QTimer 8 ms)--> Stream.feed
                                                                  |
                                                                  v
                                                         TerminalScreen (pyte)
                                                                  |
                                        (QTimer 12 ms, dirty flag) v
                                                     QImage  (GUI thread)
                                                                  |
                                          QQuickImageProvider "image://terminal/<id>?<rev>"
                                                                  |
                                                                  v
                                                        QML Image (Stretch)
```

- `PtySession` never touches Qt from the reader thread; it only appends chunks
  into a lock-protected deque. A timer on the GUI thread drains it and emits
  `dataReceived`.
- `TerminalModel.feed()` runs `pyte.Stream` over the text, then schedules a
  repaint. Rendering rasterises runs of equally styled cells into one QImage.
- The image provider keys on the session id; the revision in the query string
  forces QML to re-request the texture. `Image.fillMode: Stretch` is required
  because the raster already carries the device pixel ratio.
- Input goes the other way through `handleKey` / `mousePress` / `mouseRelease`:
  key codes become VT sequences (or control bytes for Ctrl+letter), mouse
  events become xterm reports when the running program asked for them.

### Search, log and scroll state in the renderer

`TerminalModel` keeps three pieces of view state that are not part of pyte's
screen:

- **Search** stores hits in *absolute* row coordinates (scrollback rows
  followed by live rows, via `Screen.all_rows()`), so a hit keeps pointing at
  the same text while output is appended and the view scrolls. Fed output
  re-runs the query only over the live screen; scrollback rows never change.
  Highlights are painted per cell as a translucent overlay in `_paint_row`.
- **Selection** is also an overlay: the themed transparent colour is filled
  over the cell rectangle, and the text keeps its original foreground. It is
  not reverse video — that would make the selection colour depend on the
  cell's own colours.
- **Log** output is a text copy of the byte stream with escape sequences
  stripped and each `\r`-redrawn line reduced to its final revision. The file
  handle is owned by the controller (`_open_log` / `_close_log`) and handed to
  the model, which buffers and flushes it — every second, at 8 KB and on
  detach, so the file tracks a live session instead of appearing only at close.

Both search and log are fed from `feed()`, i.e. the same GUI-thread drain that
drives rendering, so neither can see a half-fed chunk.

### Cell grid, wide characters and the fallback font

The grid is fixed by the primary font: `cell_w` is exactly
`horizontalAdvance("W")` and `cell_h` is the font height. The advance is used
without padding — a multiplier as small as `1.02` accumulates into visible
rightward drift over a long line, and a second colour run then starts at the
wrong place.

pyte represents a full-width character (CJK, full-width punctuation) as one
cell holding the character plus a **following stub cell with `data == ""`**;
the cursor advances two columns. Painting therefore asks `_cell_span()`
(`wcswidth`), skips a zero-width stub (it must not advance the grid again),
and draws a wide glyph centred in its two-column box, because a font's own
advance for `中` is usually narrower than `2 * cell_w`. Search works on the
same mapping: `_row_text()` returns the characters together with the column
and span of each one, so a hit is reported as `(row, column, column_span)`
rather than as a character index.

Font fallback is **per glyph and explicit**. `QFont.setFamilies([primary,
fallback])` reads like a fallback chain but is only a *resolution* order: with
`["Cascadia Mono", "Microsoft YaHei"]` Qt still drew `中` with the system CJK
font, and swapping the second entry changed no pixel. `TerminalModel` instead
keeps a `QRawFont` for the primary, asks `supportsCharacter()` per character
(cached in `_glyph_cache`), and draws those characters with a separate `QFont`
built from the `fontFallback` setting — one per regular/bold/italic/bold-italic
face. The cell width never comes from the fallback, so the grid stays stable
when the fallback changes.

The fast path is preserved: a run is drawn with a single `drawText` call only
when every glyph is one column wide and none needs the fallback. A run is
split at any style, selection, search-mark or fallback boundary, and only then
drawn glyph by glyph (roughly 35 ms instead of 4.5 ms per 124×40 frame, which
is why the split is conditional).


## Session lifecycle

A `Session` is a tab: PTY process, model, and the state the controller keeps
about it (attempt count, pending commands, log handle).

```
openHost ──► tssh <alias> ──► PtySession.started ──► state = connected
                                      │                    │
                                      │                    ├─ _send_startup: pending
                                      │                    │  commands, then #!! StartupCommand
                                      └─ PtySession.exited ──► state = closed
                                                    │
                                     exit 205/255 and autoReconnect?
                                                    │
                                            backoff 1,2,4,8,16,30 s
                                                    │
                                              _reconnect (max 5)
```

`_cancel_reconnect` is called by `closeTab` and a deliberate `reconnectActive`,
and it sets `suppress_reconnect`; that flag is what keeps `_on_exit` from
scheduling a restart of a session the user ended.

The split is one extra integer, `_split`, an index into `_tabs`. `Workspace.qml`
lays out two `TerminalPane` instances when `splitActive` is true; everything
else (tabs, composer, broadcast, logging, tunnels) treats them as ordinary
tabs. `closeTab` clears or decrements `_split` so it can never point at a
stale index.

## Key management

`app/keys.py` is a thin wrapper over the OpenSSH toolchain, with one piece of
real logic: fingerprints are computed locally — `SHA256:` + base64 of the
SHA-256 of the base64-decoded public blob — instead of parsing
`ssh-keygen -lf`. That keeps listing working for passphrase-protected keys and
on machines where `ssh-keygen` is missing, and it produces the same string the
tool prints.

```
~/.ssh/*.pub ──► _public_parts ──► _blob_fingerprint ──► KeyManagerSheet rows
IdentityFile paths ──► list_keys (referencedBy)
ssh-keygen -t/-b/-N ──► generate_key (refuses to overwrite, chmod 600)
known_hosts ──► known_hosts_entries (hashed |1| rows included)
ssh-keyscan ──► scan_host ──► trust_host (dedup append)
ssh-keygen -R ──► remove_known_hosts
```

Installing a public key is deliberately *not* an SFTP write: `pushKey` builds
an idempotent shell line (`grep -qxF` guard, `mkdir -p`, `chmod`) and types it
into the host's session, so it works on a first login where only a password is
available.

## Layout persistence

`_current_layout()` reduces the open tabs to `{tabs: [alias...], active, split}`.
It is written into `state.json` under `layout`, next to the settings, so
nothing about a host is duplicated there — only which aliases were open.

The save is conditional in one direction: it only overwrites the stored layout
while at least one tab is open. Otherwise the first `setSetting` call after
launch (a font change, say) would erase the layout before the user pressed
**Reopen last session**. `shutdown()` therefore saves *before* stopping and
clearing the tabs.

`restoreLayout()` re-checks every alias against the config and skips ones that
no longer exist, then re-applies the active index and the split if they are
still in range.

## Host data path

```
~/.ssh/config (+ Include files)
        |  ConfigStore.reload()
        v
   ConfigFile.lines  (the file as a list of lines, kept verbatim)
        |  _parse()
        v
    Block[]  ->  hosts()  ->  HostEntry[]
                                   |
                        controller._refresh_hosts()
                                   |
                              App.hosts  (QVariantList)
```

Editing follows the same route backwards: `update_host` / `add_host` /
`delete_host` / `replace_raw_block` mutate the line list of the *one* block
involved, then `save()` writes those bytes back. See
[Config and secrets](../config-and-secrets.md).

One subtlety: `_first_value` implements OpenSSH's first-value-wins rule by
walking files in Include order, and `_first_ext` does the same for `#!!`
options. A host shown in the UI is always the effective configuration, not
merely the block it happens to live in.

## Transfer data path

The transfer window is a separate `Window`, so transfers keep running while
the main window is used for terminal work. Two execution paths exist inside
`sftp_client.py`:

| Purpose | Mechanism | Why |
| --- | --- | --- |
| `pwd`, `ls`, `rm`, `mkdir`, `rename` | `sftp -b -` batch mode, captured with `subprocess.run` | clean, parseable stdout, no terminal noise |
| `put -R` / `get -R` | one `PTY(..., backend=ConPTY)`, script written up front | sftp only draws its progress meter when it owns a TTY |

`_MeterState` scrapes that meter (`name 42% 1.2MB ...`), tolerates `\r`-style
redraws and chunk boundaries, and emits `progressChanged(label, fraction,
detail)`. `AppController` turns each client's signals into entries for the tab
strip indicator and the popover list, labelling them by route rather than by
"upload"/"download". See [File transfers](../file-transfers.md).

## Forwarding data path

A forwarding rule is a config directive, not an app-side setting:

```
HostEditorSheet ─ saveHost(forwards) ─ config.py set_options()
                                             |
                                    LocalForward/RemoteForward/DynamicForward
                                             |
     openHost(alias) ──► tssh <alias> already applies them (no extra process)
                                             |
                       closeTab / session exit ──► TunnelManager.stop_session
                                             |            |
                                   not persistent     persistent
                                        |                 |
                                     released      tssh -N <alias>
```

`TunnelManager` keys on the host, not the rule, because `tssh -N <alias>` opens
everything the alias declares. Passing an explicit `-L` alongside a config that
already has one makes tssh bind the same port twice and log a warning while
still exiting 0 — so the manager never adds flags and treats a forwarding
warning in the output, not the exit code, as failure.

## Threading rules

- One GUI thread owns every QObject. Worker threads in `pty_session.py` and
  `sftp_client.py` only run blocking IO and emit Qt signals.
- `SftpClient` methods that QML calls are `@Slot`-decorated, return
  immediately, and start a `threading.Thread`. Forgetting `@Slot` produces
  "Property 'x' is not a function" at the call site, not at import time.
- `TerminalModel` is always mutated on the GUI thread.
- `TunnelEntry` reuses `PtySession`, so tunnel output follows the same reader
  thread → deque → GUI drain path as a session. Its state machine (`session`,
  `pending`, `starting`, `running`, `failed`, `stopped`) only advances on GUI
  thread callbacks and timers.

## Design tokens

`app/theme.py` is the single source of truth. The catalog is **user-editable
YAML** in the application data directory, `paths.themes_dir()` (that is
`%APPDATA%/LItsshP/themes` on Windows, `~/.litsshp/themes` elsewhere) — never
in `~/.ssh`, which is reserved for files the ssh tools themselves read. Two
families ship, each with a dark and a light member:

| family | dark | light |
| --- | --- | --- |
| `catppuccin` | Catppuccin Mocha | Catppuccin Latte |
| `mono` | Mono Dark | Mono Light |

The built-ins are seeded from string constants in `theme.py` on first launch
and then never overwritten, so editing a file on disk wins. A file that fails
to validate is skipped and reported through `load_errors()`; the built-in for
that id still loads, so a typo degrades to the shipped palette instead of a
blank window. Settings → Appearance → **Reload** re-reads the directory
(`StyleManager.reloadThemes()`), and the button surfaces the first error.

Each YAML file declares one *member*: `id`, `label`, `family`,
`appearance` (`dark`/`light`), a `colors` mapping (shell, surface, foreground,
muted, accent, selected, line, six semantic inks, frame) and a 16-entry
`terminal.ansi` table. Members sharing a `family` id are paired, which is what
lets "follow system" switch appearance without changing the user's family. The
full schema is in the module docstring of `app/theme.py`.

`StyleManager` (`app/style.py`) resolves the active family and appearance into
three things:

- `skin` — the chrome tokens: `shell`, `surface`, `panel`, `veil`,
  `surfaceWash`, `hover`, `accent`, `accentSoft`, `ink` / `inkDim` / `inkFaint`,
  `danger` / `ok` / `warn` / `info`, `hairline`, and the radius and row-height
  ladder.
- `currentScheme` (plus `lightScheme` / `darkScheme`) — the same palette mapped
  onto the Material role names the vendored md3 components read. The names
  survive so existing call sites keep working; the values are Pebrel's.
- `paletteName` / `families` / `themeDir` / `themeErrors` — what the settings
  picker draws its swatches from, where the YAML lives, and what failed to
  parse. Swatches come from the resolved palettes, so a preview cannot show a
  colour the theme will not use.

QML reads `Theme.skin.*` for chrome and `Theme.color.*` for the md3 controls.
`Main.qml`'s flat tokens (`flatSurface`, `flatPanel`, `flatHover`,
`flatSelected`, `hairline`, `radiusSmall`, `radiusMedium`) are aliases of
`Theme.skin` kept for the pages that already used them.

Geometry is flush by default, matching Pebrel's built-in presets: the content
card has radius 0 and no gutter, and the sidebar meets it at a single 1px
hairline. The radius ladder is 4 (chip) / 6 (control) / 7 (icon tile) / 8
(overlay) / 14 (launcher); rows are 32 (control) / 38 (dense) / 44 (row).

Plane separation: a hand-written palette may declare `shell == surface`, which
would flatten the window. `theme._planes()` darkens the *shell* by a few
percent in that case rather than lifting the surface, because the surface is
the terminal grid colour and must not move.

Two derived colours need care because a YAML author can pick anything:

- `accent_ink()` picks the glyph colour on a filled accent. Dark families reuse
  the plane colour; light families use white. If neither reaches 4.5:1 — a
  mid-luminance accent like Latte's `#7287fd` — it falls back to `DEEP_INK`
  rather than washing the text out to grey.
- `ink_dim` / `ink_faint` are built separately. Deriving both from the
  palette's `muted` collapses the ink ladder on a monochrome palette, where the
  greys are already close together, so `ink_faint` is blended toward the plane
  and held at 3:1.

Monochrome palettes have no hue to separate states with, so `mono` separates
`danger` / `warn` / `ok` by brightness: danger is the loudest end of the ramp,
ok the quietest.

The terminal palette is derived from the same resolved palette by
`terminal_theme.py`, which is what makes the window read as one surface rather
than a themed shell around a black box.
