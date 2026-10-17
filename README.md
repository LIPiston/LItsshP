# LItsshP

A flat, Termius-style GUI for [trzsz-ssh (tssh)](https://github.com/trzsz/trzsz-ssh).
It is **not** a reimplementation of an SSH client: every session is a real
`tssh <alias>` process running inside a pseudoterminal, so ProxyJump,
`encPassword`, trzsz transfers, `#!!` options and everything else tssh does keep
working exactly as they do in the CLI.

Sessions are not stored in a separate database. Both the GUI and the CLI read
and write the same `~/.ssh/config`, so a host added here is immediately usable
with `tssh <alias>` and vice versa.

```
┌────────────────┬──────────────────────────────────────────────┐
│  LItsshP       │  ● localtest  ✕  │  ● prod-web  ✕            │
│  tssh · ~/.ssh │──────────────────────────────────────────────│
│  2 hosts       │  LIPiston@host  ~                             │
│  [search]      │  $ ls --color=always /                        │
│  All  lab  web │  bin  boot  dev  etc  home  ...               │
│  ▸ localtest   │──────────────────────────────────────────────│
│  ▸ prod-web    │  tssh localtest        ~/.ssh/config          │
│  New host  ⚙   │                                               │
└────────────────┴──────────────────────────────────────────────┘
```

## Requirements

- Windows 10/11 (the PTY layer uses ConPTY via `pywinpty`)
- Python 3.10+
- [tssh](https://github.com/trzsz/trzsz-ssh) on `PATH` (or set `LITSSHP_TSSH`
  to the executable)
- An OpenSSH client — tssh shells out to `ssh`

## Install and run

```bat
py -3 -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
run.bat
```

Or directly:

```bat
.venv\Scripts\python -m app.main
```

## How it maps onto tssh

| GUI concept | tssh / OpenSSH equivalent |
| --- | --- |
| Host list | every concrete `Host` block in `~/.ssh/config` (and any `Include`d files) |
| Groups | `#!! GroupLabels prod web` |
| Hidden hosts | `#!! HideHost yes` |
| Password field | `#!! encPassword <hex>` plus `#!! encQuestionAnswer1`, byte-compatible with tssh |
| Advanced tab | `ProxyJump`, `ProxyCommand`, `IdentityFile`, `IdentitiesOnly` |
| Raw block editor | the literal text of the block, written back verbatim |

Passwords are encoded with tssh's own scheme — a fixed AES-256-GCM key whose
only purpose is obfuscation, not protection. Anyone who can read the config can
decode it, exactly as with tssh itself.

Editing a host does not rewrite unrelated blocks: untouched hosts stay
byte-identical, including comments, ordering, CRLF line endings and a UTF-8 BOM.

## Interface

Everything is flat: one accent colour, hairline separators, no elevation or
shadows. Material 3 components come from
[material-components-qml](https://github.com/sudoevolve/material-components-qml.git),
vendored under `third_party/md3`, with its C++ style singletons reimplemented in
Python (`app/style.py`) so no C++ toolchain is needed.

### Keyboard

| Shortcut | Action |
| --- | --- |
| `Ctrl+T` | focus the host search |
| `Ctrl+N` | new host |
| `Ctrl+W` | close the active tab (asks first if the session is running) |
| `Ctrl+Tab` / `Ctrl+Shift+Tab` | next / previous tab |
| `Ctrl+,` | settings |
| `Ctrl+B` | toggle the sidebar |
| `Ctrl+Shift+P` | command palette |
| `Ctrl+R` | reconnect the active session |
| `Ctrl+Shift+R` | reload hosts from disk |
| `Ctrl+Shift+C` / `Ctrl+Shift+V` | copy selection / paste |
| `Shift+PgUp` / `Shift+PgDn` | scroll back / forward (bare PgUp/PgDn go to the app) |
| `Ctrl+Home` / `Ctrl+End` | top of scrollback / live view |

Inside the terminal, `Shift` overrides mouse reporting so you can always select
text while a full-screen app (vim, htop, tmux) is grabbing the mouse.

### Host actions

Right-click any host in the sidebar for a context menu:

| Item | Action |
| --- | --- |
| Edit | open the host sheet (general / advanced / raw block) |
| Transfer files | open a separate SFTP window for that host |
| Delete | ask for confirmation, then remove the block from `~/.ssh/config` |

Delete is two-step: the dialog names the host and spells out what is removed,
and nothing is written until it is accepted. Other hosts and their stored
passwords are left byte-identical.

### Transfer files

The transfer window is a separate top-level window with a local pane on the
left and the remote pane on the right. Click a row to tick it, double-click a
folder to enter it, then use **Upload ↑** / **Download ↓**. Directories transfer
recursively.

Transfers go through the OpenSSH `sftp` client in batch mode, invoking the same
`~/.ssh/config` entry the session uses, so ProxyJump, `IdentityFile` and agent
settings all apply. This deliberately avoids trzsz, which would require `trz`
and `tsz` to be installed on the server first; plain SFTP works against any
OpenSSH server.

## Architecture

```
app/
  main.py            entry point: QML singletons, image provider, window geometry
  controller.py      QML-facing controller: hosts, tabs, settings, sessions
  config.py          byte-preserving ~/.ssh/config parser and writer (+ Include)
  secret.py          tssh-compatible encPassword encode/decode
  pty_session.py     tssh process in a ConPTY; reader thread + GUI-side timer
  screen.py          pyte screen subclass: scrollback, alt screen, mouse modes
  terminal_model.py  grid → QImage renderer, key/mouse input, selection
  terminal_theme.py  terminal palette derived from the Material scheme
  sftp_client.py     batch-mode sftp for the transfer window (listing, upload…)
  style.py           Python port of the library's StyleManager / ColorHelper
  qml/               Main, HostSidebar, Workspace, TerminalPane, TransferWindow…
third_party/md3/     vendored material-components-qml QML module
```

The terminal is rasterised in Python and handed to QML through an image
provider (`image://terminal/<id>?<revision>`). PTY output is read on a worker
thread and only enqueued; a timer on the GUI thread drains the queue, feeds
pyte and repaints, so no Qt object is ever touched off-thread.

## Configuration

LItsshP itself stores only UI preferences in `%APPDATA%\LItsshP\state.json`
(window geometry, theme, font). Hosts and credentials never leave
`~/.ssh/config`.

Environment overrides, useful for testing against a scratch config:

- `LITSSHP_CONFIG` — path to the config file (default `~/.ssh/config`)
- `LITSSHP_TSSH` — path to the tssh executable
- `LITSSHP_SFTP` — path to the `sftp` executable used by the transfer window
- `LITSSHP_STATE` — path to the UI state file
