# Reference: Verification gates

There is no automated test suite in this repository. Verification is a small
set of runnable gates plus a manual pass; this sheet lists exactly what exists
and what each check proves.

## Gate 1 — imports compile

```bash
.venv/Scripts/python -m compileall -q app
```

Proves the Python modules parse. It does not prove anything about QML.

## Gate 2 — QML tree loads with no binding errors

```bash
.venv/Scripts/python docs/skills/reference/qml_load_gate.py
```

Loads `app/qml/Main.qml` offscreen and fails on any `TypeError`,
`ReferenceError` or `not defined` warning. This is the gate that catches a
renamed controller member, a misspelled property, or a binding that evaluated
against `null` because its model was not ready.

Expected output ends with `PASS qml load gate` and exit 0. The gate points
`LITSSHP_CONFIG` / `LITSSHP_STATE` at a temp directory, so it is safe to run at
any time.

Note the pattern it encodes: the controller is parented to the engine
(`controller.setParent(engine)`) before loading, because otherwise the QML
tree evaluates bindings against a deleted controller during teardown and logs
a burst of TypeErrors after an otherwise clean run.

## Gate 3 — config writer preserves unedited text

```bash
.venv/Scripts/python docs/skills/reference/config_roundtrip_gate.py
```

Writes a synthetic config with a BOM, CRLF endings, a comment and two hosts,
edits one host, and asserts: BOM kept, CRLF kept, the other block
byte-identical, the edited value present, the `#!!` extension written, and
`encPassword` round-tripping. Runs entirely in a temp directory.

Expected output ends with `PASS config round-trip gate` and exit 0.

## Gate 4 — manual session smoke

Needs a reachable SSH host. On this machine `sshd` listens on `127.0.0.1:22`
and key auth for the current user works, so a `localtest` block like the one
below is enough:

```
Host localtest
    HostName 127.0.0.1
    Port 22
    User <you>
    IdentityFile ~/.ssh/id_ed25519
    IdentitiesOnly yes
    StrictHostKeyChecking no
```

Point the app at a scratch config so the real one is untouched:

```bash
LITSSHP_CONFIG=/tmp/litsshp-home/.ssh/config \
LITSSHP_STATE=/tmp/litsshp-home/state.json \
.venv/Scripts/python -m app.main
```

Then confirm, in this order:

1. the host appears in the sidebar; clicking it opens a tab and connects;
2. typed output appears (proves the image-provider path, not just the PTY);
3. `Ctrl+Shift+C` copies a drag-selection and `Ctrl+Shift+V` pastes it;
4. right-click gives Copy / Paste / Select all / Clear selection;
5. `Ctrl+Shift+E` focuses the composer; text is visible while typing
   (invariant 7); `Ctrl+Enter` sends and the lines execute;
6. `seq 1 400` produces scrollback; `Shift+PgUp` scrolls, `Ctrl+End` returns;
7. a full-screen program (`vim`, `htop`) renders, and `Shift`-drag selects
   text while the program is tracking the mouse.

## Gate 5 — manual transfer smoke

Requires the OpenSSH `sftp` client (bundled with Windows) and a host that
accepts SFTP. Cross-machine loopback works: point `HostName` at `127.0.0.1`
and use a temp folder as the "remote" side.

1. Right-click a host → **Transfer files**. The window opens with the local
   pane at the profile directory (or `%TEMP%\LItsshP` if unwritable) and the
   remote pane at `~`.
2. Select a file locally, **Upload ↑**. The tab strip shows
   `this PC → host` with a moving percentage; the footer bar in the transfer
   window moves too.
3. Select a remote file, **Download ↓**. The label reads `host → this PC` and
   the file lands in the path shown in the local pane's header.
4. Open the `swap_vert` popover: the finished transfer appears under RECENT
   with the same route label and a relative time.
5. Type a path that does not exist yet in the local pane (e.g.
   `D:\incoming`), download into it, and confirm the folder is created — or,
   if it genuinely cannot be created, that the status line says why and the
   file lands in `%TEMP%\LItsshP`.
6. Close the window mid-transfer: it must cancel rather than leave a stray
   `sftp` process.

## Gate 6 — manual config safety

Only ever after setting `LITSSHP_CONFIG` to a **copy**:

1. Edit a host, save, and `git diff`-style compare the file against the copy:
   other blocks must be byte-identical.
2. Delete a host and confirm the neighbouring blocks (and their blank-line
   separation) are unchanged and that no dangling separator is left at EOF.
3. Use **Edit raw block** to change one option and confirm only that block
   changed.
4. Confirm the file still resolves the host with the client tssh delegates to:
   `ssh -F <copy> -G <alias>` (tssh itself has no `-G`).

## What is not covered

- No automated UI interaction tests. Behaviour of the composer, popover and
  selection is verified by the manual passes above.
- No automated transfer test. `sftp_client` is exercised by hand, because the
  meter only exists under a real ConPTY.
- No test touches the real `~/.ssh/config`; if you add one, it must copy the
  file to a temp path first.
