# Skill: Quick Start

First fifteen minutes: a green toolchain, orientation, and a safe first change.

## 1. Prerequisites

- Windows 10/11 (the PTY layer is ConPTY through `pywinpty`)
- Python 3.10+
- `tssh` on `PATH` — `winget install trzsz.tssh`
- The OpenSSH client (`ssh`, `sftp`) — ships with Windows

Check the two binaries before anything else; most "it does not connect"
reports are one of them missing:

```bash
tssh -V        # prints "trzsz ssh <version>"
sftp -h        # prints usage; sftp has no -V flag
```

## 2. Green baseline

```bash
py -3 -m venv .venv
.venv/Scripts/python -m pip install -r requirements.txt
.venv/Scripts/python -m compileall -q app
.venv/Scripts/python docs/skills/reference/qml_load_gate.py
.venv/Scripts/python docs/skills/reference/config_roundtrip_gate.py
```

(PowerShell and `cmd` accept `.venv\Scripts\python`; the blocks here use the
forward-slash form because they are meant for Git Bash, where a backslash is an
escape character.)

Expected: compileall silent, then

```
PASS qml load gate
PASS config round-trip gate
```

Both gates run offscreen against a temp directory and are safe to run at any
time. If either fails, fix that before touching anything else — they cover the
two most common breakages (a renamed controller member, a config write that
disturbs unrelated text).

## 3. Run it

```bat
run.bat
```

`run.bat` insists on the `.venv` next to it and prints the install commands if
it is missing. To keep the real configuration out of reach while experimenting:

```bash
LITSSHP_CONFIG=/tmp/litsshp-home/.ssh/config \
LITSSHP_STATE=/tmp/litsshp-home/state.json \
.venv/Scripts/python -m app.main
```

Create that scratch config with one host pointing at any reachable server. On
this machine `sshd` is running locally:

```
Host localtest
    HostName 127.0.0.1
    Port 22
    User <your windows user>
    IdentityFile ~/.ssh/id_ed25519
    IdentitiesOnly yes
    StrictHostKeyChecking no
```

## 4. Orientation in sixty seconds

- `app/main.py` — registers `StyleManager`/`ColorHelper`, the `image://terminal`
  provider and the `App` context property, then loads `app/qml/Main.qml`.
- `app/controller.py` — the only Python object QML knows. Start reading
  [the API sheet](reference/qml-api.md) here.
- `app/config.py` — the config reader/writer. Treat it as delicate: it
  preserves the file byte for byte outside the block being edited.
- `app/terminal_model.py` + `app/screen.py` — the terminal. Read
  [Terminal rendering](terminal-rendering.md) before changing either.
- `app/sftp_client.py` — the transfer window's backend; see
  [File transfers](file-transfers.md).
- `app/qml/` — one file per surface. `Main` owns the window and the overlays,
  `Workspace` owns tabs/panes/composer, `HostSidebar` the left rail.

## 5. A safe first change

Pick something cosmetic and visible, and walk the whole loop once:

1. Change a label or a colour in a QML file (for example the composer
   placeholder in `CommandComposer.qml`).
2. Run the QML gate — it must still pass.
3. Run the app against the scratch config and confirm the change on screen.
4. If the change is user-visible, update the README section that describes it
   (see [Updating documentation](updating-docs.md)).

## 6. Things that surprise newcomers

- **Progress bars are hand-drawn `Rectangle`s, not md3's `LinearProgress`.**
  That control eases its visual value toward the target over 200 ms, which
  reads several points low while a transfer is streaming. Correctness never
  waits on an animation completing (invariant 6).
- **Text fields that can overflow use a clipped `Item` and a moved
  `TextEdit`, not a `Flickable`.** The composer and the raw-block editor are
  written that way; copy them instead of inventing a third layout
  (invariant 7).
- **A tab is a real `tssh` process.** There is no simulated session; to debug
  a session problem, run `tssh <alias>` in a normal terminal first.
- **`~/.ssh/config` is the database.** Editing the GUI edits that file; the
  tssh CLI sees the change immediately, and so does the next GUI start.
