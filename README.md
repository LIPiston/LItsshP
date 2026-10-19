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
| Plain password | `#!! Password <text>` is kept in that form when edited, not converted |
| Startup command | `#!! StartupCommand <text>` — LItsshP's own option, typed once the shell is ready |
| Advanced tab | `ProxyJump`, `ProxyCommand`, `IdentityFile`, `IdentitiesOnly` |
| Port forwarding | `LocalForward`, `RemoteForward`, `DynamicForward` in the host's block |
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
| `Ctrl+Shift+T` | port forwarding panel |
| `Ctrl+F` | search the active terminal's scrollback |
| `Ctrl+Shift+D` | split the terminal (opens a chooser for the second pane) |
| `Ctrl+Shift+O` | reopen the tabs of the previous session |
| `Ctrl+R` | reconnect the active session |
| `Ctrl+Shift+R` | reload hosts from disk |
| `Ctrl+Shift+C` / `Ctrl+Shift+V` | copy selection / paste |
| `Ctrl+Shift+A` | select the visible screen |
| `Ctrl+Shift+E` | focus the command composer |
| `Shift+PgUp` / `Shift+PgDn` | scroll back / forward (bare PgUp/PgDn go to the app) |
| `Ctrl+Home` / `Ctrl+End` | top of scrollback / live view |

`Ctrl+C` alone is never intercepted while it could be SIGINT; only
`Ctrl+Shift+C` copies. Right-clicking the terminal offers Copy / Paste /
Select all / Clear selection, and keeps passing the click to vim, tmux and
friends when they are tracking the mouse (`Shift`+right-click always shows the
app menu).

The sidebar header doubles as the title bar: drag it to move the window,
double-click to maximize.

### Command composer

A strip under the terminal holds a command (or a short block of commands) that
can be prepared while a session is busy. It does not intercept normal typing —
keys still go to the terminal unless the field has focus. Enter inserts a
newline, `Ctrl+Enter` sends, and `Ctrl+Up` / `Ctrl+Down` recall earlier entries.
Toggle it from the keyboard icon in the tab strip, with `Ctrl+Shift+E`, or in
Settings.

Sent lines are typed to the shell exactly as if entered by hand, so line
continuations and multi-line blocks behave normally instead of sitting in a
paste buffer.

### Search, logs and reconnects

`Ctrl+F` opens a search bar over the active terminal. It searches the
scrollback as well as the visible screen, highlights every hit (the current one
more strongly), and `Enter` / `Shift+Enter` move between them. Search is
case-insensitive until the `Aa` button is pressed. `Escape` closes the bar and
leaves the scroll position where the last hit was found.

Two things that make a long-lived session survivable are in Settings:

- **Session log** appends each session's printable output to a file under
  `%APPDATA%\LItsshP\logs`. Escape sequences are stripped and a line redrawn
  with carriage returns keeps its last revision, so the file reads like the
  screen rather than like raw PTY traffic. The button next to the switch opens
  the folder.
- **Auto-reconnect** restarts a session that was dropped, with a capped
  backoff (1, 2, 4, 8, 16 seconds, then every 30 s, giving up after five
  attempts). Only a drop is retried: tssh's keep-alive timeout (exit 205) and
  transport failure (255). A shell you exited with `exit`, a tab you closed and
  a session you reconnected deliberately are left alone.

The keep-alive interval (Off / 15 / 30 / 60 seconds) is passed as
`ServerAliveInterval` when the host's own config does not set one, so an
explicit value in `~/.ssh/config` always wins.

### Fonts, Chinese text and fallback

Settings offers a terminal font and a **fallback for missing glyphs**. Most
programming fonts ship no CJK, so without a fallback `中文`, `日本語` and
full-width punctuation come from whatever font the system happens to pick —
often a serif that looks nothing like the terminal text. Choosing a fallback
makes those characters come from the named family while everything else stays
in the primary font.

The substitution is per character: a glyph is drawn with the fallback only if
the primary font has no glyph for it. Qt's `setFamilies` list looks like it
does this, but it only orders family *resolution* — the same CJK font is used
no matter what the second entry says — so the terminal checks coverage with
`QRawFont.supportsCharacter` and paints the exceptions itself. The cell size
always comes from the primary font, so switching the fallback never reflows the
grid. The menu lists only families that actually contain a CJK glyph; if the
saved default is not installed, the first installed one is used instead.

Full-width characters occupy two columns, with the glyph centred in that box.
This matters beyond looks: line-drawing and table output from tools like `htop`
or `vim` aligns only if every wide glyph advances exactly two cells.

### Split panes

`Ctrl+Shift+D` (or **Split** in the status bar) opens a chooser listing open
tabs and idle hosts; picking one shows it beside the active session. The two
panes are ordinary tabs, so closing a split returns to a single pane without
losing either shell.

The split toolbar names both hosts, has a **Broadcast** switch and a close
button. With Broadcast on, the command composer types into both panes, which is
the usual way to run one command on two servers. Output, search, logging and
reconnect stay per-pane; the split itself is not duplicated into another
window.

### Snippets and startup commands

A snippet is a named command (or short block) stored in `state.json`. The
command palette lists them, and choosing one types it into the active session.
**Manage snippets** in the palette opens the editor, which can also run a
snippet immediately.

A host can additionally carry a startup command in the host editor, saved as
`#!! StartupCommand`. It is typed once the shell has reported itself ready, not
passed as a remote command, so `cd /srv/app`, `tmux attach` or a `source` run
exactly as if typed. The option is LItsshP's own: `tssh` ignores it, so keep
anything the CLI must also do in the shell's own profile.

### SSH keys and known hosts

**Keys** at the bottom of the sidebar (or **Manage keys** in Settings) lists
every key pair in `~/.ssh`, including keys referenced by a host's
`IdentityFile` but stored elsewhere. Each row shows the type, size, comment and
the `SHA256:` fingerprint computed from the key blob — the same value
`ssh-keygen -lf` prints.

From there you can:

- create an ed25519 key (or RSA, for old servers) with an optional passphrase
  and comment; an existing file is never overwritten;
- copy a public key, or **install it on a host**, which opens (or reuses) that
  host's session and appends the line to `~/.ssh/authorized_keys` with the
  right permissions — done through the session rather than SFTP because the
  first login still needs a password and the folder may not exist yet;
- delete a key pair (both halves, after confirmation);
- review and **forget** entries in `known_hosts`, including hashed `|1|` rows
  (a hashed row has no readable name, so it is removed by position);
- **Trust a host** scans a host with `ssh-keyscan` and shows its fingerprints,
  which you compare before adding them. Scanning trusts nothing on its own.

Creating a key runs `ssh-keygen`. Listing and fingerprinting do not: the
fingerprint is computed locally from the public blob, so a passphrase-protected
key and a machine without `ssh-keygen` both still list correctly.

### Reopening the last session

LItsshP records the open tabs, the active one and the split in `state.json`,
but never dials out on its own at launch. **Reopen last session** (on the empty
state, in the palette, or `Ctrl+Shift+O`) restores them; hosts that have since
been deleted from the config are skipped. The restore is explicit because a
terminal that connects to production the moment it starts is a surprise on a
metered link, and an unattended launch should not produce login attempts.

### Port forwarding

Rules are ordinary `LocalForward`, `RemoteForward` and `DynamicForward` lines in
the host's block, edited in the host editor. They are visible to `ssh` and
`tssh` on the command line, so a tunnel set up here keeps working outside the
GUI.

A forward is a property of a connection, not a background service. While a host
has an open session, that session provides the rules — no second process is
started, because it would race the session for the same local port. When the
session ends, the forward ends with it.

`Ctrl+Shift+T` (or the `swap_horiz` icon) opens the forwarding panel. Each host
lists the rules it is currently providing, whether they came from the host's own
block or from a `Host *` rule, and its state. **Keep running** is the opt-in to
survive the session: once the tab closes, the app starts its own
`tssh -N <alias>` and hands the ports over. Those processes are still stopped
when the app exits, so nothing keeps listening behind a closed window.

If you reopen a host whose forwards a kept-alive tunnel is already holding, the
new session is started with `ClearAllForwardings=yes` so it does not fight for
the same local ports.

Rules inherited from a wildcard or `Include` block are shown read-only: deleting
them from one host's editor would silently change every other host matching that
block. Forwarding also stops if the host sets `ClearAllForwardings yes`.

### Transfer progress

The tab strip shows a live bar with the current transfer's route
(`this PC → host` or `host → this PC`), a percentage, and a running count. The
`swap_vert` icon opens a list of transfers in flight plus the recent history,
each with the same route label.

Progress is scraped from sftp's own meter: transfers run under a pseudoterminal
because sftp only draws that meter when it owns a terminal. Metadata calls still
use clean batch mode.

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

Both panes open at a usable folder rather than assuming one is available:

- the local pane starts in your profile directory, or in `%TEMP%\LItsshP` when
  the profile is not writable;
- the remote pane starts in the account's `~`, and if that cannot be listed it
  walks `~` → `/` → `/tmp` and opens the first readable one, telling you which
  folder it settled on.

A folder that does not exist yet but could be created counts as usable, so a
download target like `D:\incoming` works before the folder exists. If the
destination really cannot be written, the download falls back to
`%TEMP%\LItsshP` instead of failing, and permission problems are reported in
the status line rather than leaving a blank pane.

The footer also manages the remote folder: **New folder**, **Rename** and
**Delete** run through the same batch `sftp` channel as the listings, so they
need no extra connection. Delete always asks first.

Transfers go through the OpenSSH `sftp` client, invoking the same
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
  sftp_client.py     batch sftp for metadata, PTY-driven transfers with progress
  tunnel.py          forwarding specs + supervised `tssh -N` processes
  keys.py            key listing/fingerprinting, ssh-keygen wrappers, known_hosts
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
(window geometry, theme, font, snippets, the tabs of the last session). Hosts
and credentials never leave `~/.ssh/config`.

Environment overrides, useful for testing against a scratch config:

- `LITSSHP_CONFIG` — path to the config file (default `~/.ssh/config`)
- `LITSSHP_TSSH` — path to the tssh executable
- `LITSSHP_SFTP` — path to the `sftp` executable used by the transfer window
- `LITSSHP_STATE` — path to the UI state file
- `LITSSHP_LOGS` — folder for session logs (default
  `%APPDATA%\LItsshP\logs`)

## Documentation

[`docs/`](docs/README.md) holds the material for working on the code rather
than with it:

- [`docs/skills/`](docs/skills/index.md) — playbooks for setup, defect
  diagnosis, the terminal renderer, transfers and the config writer;
- [`docs/skills/reference/`](docs/skills/reference/index.md) — architecture,
  the invariants every change must preserve, the verification gates and the
  full QML-facing API.

The gates are runnable as they stand and cover the most common breakages:

```bash
.venv/Scripts/python docs/skills/reference/qml_load_gate.py
.venv/Scripts/python docs/skills/reference/config_roundtrip_gate.py
.venv/Scripts/python docs/skills/reference/forward_roundtrip_gate.py
.venv/Scripts/python docs/skills/reference/session_features_gate.py
```

