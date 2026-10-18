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
       ├ TransferIndicator / TransferPopover
       └ TransferWindow (separate top-level window)

Python (app/)
  controller.py      QML-facing facade: hosts, tabs, settings, transfers, tunnels
  config.py          ~/.ssh/config parser + byte-preserving writer (+ Include)
  secret.py          tssh encPassword encode/decode
  paths.py           home, config, state, tssh/sftp discovery
  pty_session.py     tssh in a ConPTY, reader thread, GUI-side drain timer
  screen.py          pyte Screen subclass: scrollback, alt screen, mouse modes
  terminal_model.py  grid → QImage, key/mouse translation, selection
  terminal_theme.py  terminal palette derived from the Material scheme
  sftp_client.py     SFTP listing (batch) and transfers (ConPTY + meter scraping)
  tunnel.py          forward specs + one supervised `tssh -N` per host
  style.py           Python ports of md3's StyleManager / ColorHelper
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

The QML pages take colours from `Main.qml`'s flat tokens (`flatSurface`,
`flatPanel`, `flatHover`, `flatSelected`, `hairline`, `radiusSmall`,
`radiusMedium`) and from `Theme.color` of the md3 module. The terminal palette
is derived from the same Material scheme by `terminal_theme.py`, which is what
makes the window read as one surface rather than a themed shell around a black
box.
