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

## Gate 3b — forwarding rules round-trip and stay scoped

```bash
.venv/Scripts/python docs/skills/reference/forward_roundtrip_gate.py
```

Covers the accumulating directives (`LocalForward`/`RemoteForward`/
`DynamicForward`): multiple lines read as a list, positional rewrite that keeps
comments between them, removal that deletes only the directive line, an
unrelated block staying byte-identical, BOM/CRLF preserved, `Host *` rules
reported as inherited and never rewritten, `ClearAllForwardings` reported, and
the spec parser's accept/reject cases.

Expected output ends with `PASS forward round-trip gate` and exit 0.

## Gate 3d — session features (password form, search, log, layout)

```bash
.venv/Scripts/python docs/skills/reference/session_features_gate.py
```

One script, four groups of checks:

- **password form** — a plain `#!! Password` stays plain and keeps its value;
  saving it as `encrypted` produces `encPassword` and removes the plain line;
  clearing removes `encPassword`/`encQuestionAnswer1` but keeps a
  `PasswordCommand`. Assertions are scoped to the host's own block, so another
  host's bytes cannot make a check pass.
- **search** — every hit in scrollback plus the live screen is found, the
  newest is selected, next/previous wrap, the default is case-insensitive and
  the case-sensitive option narrows it.
- **render** — selecting paints the themed translucent colour over the cell
  and clearing restores the plain background, proving the selection is an
  overlay rather than a reverse-video swap; a search match changes the pixel
  too.
- **log** — a `\r`-redrawn progress line keeps its last revision, escape
  sequences are gone, printable text survives, and the file is already
  current before the session ends (a flush timer writes it every second;
  without it the log stayed empty until close). (The `\r\n` line-ending case is
  covered here: a PTY ends lines that way, and an early version dropped every
  line because of it.)
- **wide cells** — a full-width character reports a span of 2 and the cell
  after it is a stub (span 0); `_row_text` maps `AB中文CD` to columns
  `0,1,2,4,6,7` with spans `1,1,2,2,1,1`; the rendered glyphs land on the
  column grid and nothing is painted past the last character; `selectedText`
  rebuilds the wide characters; a search for `文C` is reported at column 4
  with a span of 3, and `中文` covers four columns.
- **fallback font** — the configured family is kept, one equal to the primary
  is ignored, and (with a stub `QRawFont` that covers everything but CJK) only
  a missing glyph takes the fallback path: `A` uses `_font`, `中` uses
  `_fallback_font`, and a mixed row `AB中文CD` draws per glyph for `中`/`文`
  only. With no fallback configured nothing is substituted. `fontFallback` has
  a default that can render `中`, every family offered by `fallbackFonts()`
  contains `中`, the default resolves to an installed family, and
  `setSetting` persists the choice. A default family that is not installed
  (simulated by patching `DEFAULT_SETTINGS`) is replaced by the first offered
  family, or by `""` when nothing is installed.
- **file names** — a host alias containing `/`, `*` and the like becomes a
  usable log file name.
- **layout** — a saved layout is written, a second controller sees it, and
  `restoreLayout()` skips an alias that is not in the config.
- **keys** — `ssh-keygen` creates an ed25519 key, a second generation is
  refused, the listed fingerprint equals `ssh-keygen -lf` output, a named
  known_hosts entry is removed while its neighbour survives, a row is removed
  by line (the hashed case), and deleting a pair removes both halves. All of it
  happens in the gate's temp `.ssh` folder, never the real one.

Expected output ends with `PASS session features gate` and exit 0. It runs in
a temp directory and never touches the real `~/.ssh`.

On Windows this gate uses the native platform plugin rather than `offscreen`,
because the offscreen plugin there loads no font database at all: every glyph
becomes a tofu box drawn over the cell pixel probes read, so the selection and
search-mark checks fail for a reason unrelated to the code. Nothing is shown
either way — only a `QGuiApplication` and an offscreen `QImage` exist.

## Gate 3c — port-forward smoke (manual, local sshd)

1. Add `LocalForward 18080 localhost:22` to a host whose `HostName` is
   `127.0.0.1`, open that host, and confirm `127.0.0.1:18080` accepts a
   connection while the tab is open.
2. Close the tab and confirm the port is released — the session owned it.
3. Reopen, tick **Keep running** in the forwarding panel, close the tab, and
   confirm the port is *still* open (the app now owns it via `tssh -N`).
4. Occupy the port before opening the panel to confirm the conflict is reported
   instead of failing silently. tssh prints a bind warning and still exits 0, so
   the warning line — not the exit code — is what the panel reacts to.
5. Confirm `ssh -F ~/.ssh/config -G <alias>` shows the same `localforward`
   lines the editor wrote.

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
   text while the program is tracking the mouse;
8. `Ctrl+F`, type a string that appears several times in both scrollback and
   the live screen: every hit is highlighted, the count is right, Enter and
   Shift+Enter wrap, the `Aa` toggle narrows an all-lowercase query, and
   Escape closes the bar;
9. drag a selection across normal, bold and reverse-video text: the highlight
   keeps the themed colour and the glyphs stay readable (invariant 13).

## Gate 4b — manual session features

Same host as Gate 4. Each of these is UI behaviour a gate cannot reach:

1. **Session log**: enable it in Settings, run `printf 'a\nb\n'`, open the log
   folder, and confirm the file has one line per output line with no escape
   sequences and no duplicated `\r\n` blanks.
2. **Auto-reconnect**: connect, then kill the remote side (`pkill -f
   'sshd: <you>'` on the loopback host) and watch the toast and the retry
   timing. Then exit a shell normally with `exit` and confirm it stays closed.
3. **Keep-alive**: with a host that sets `ServerAliveInterval 0`, set 30 s in
   Settings and confirm the session's command line still has no `-o
   ServerAliveInterval` (the host's explicit value wins). On a host that does
   not set it, `-o ServerAliveInterval=30` must appear.
4. **Split**: `Ctrl+Shift+D`, pick another tab, both panes render and accept
   input; **Broadcast** with the composer puts the line in both; **Unsplit**
   leaves both tabs alive; closing one pane leaves the other usable.
5. **Snippets**: create one with two lines, choose it from the palette, and
   confirm the commands appear at the prompt. Then edit an existing host and
   give it a startup command: reopen it and confirm the command is typed once
   after the shell is ready, not before the login prompt.
6. **Layout restore**: open two tabs and a split, quit, relaunch, and press
   **Reopen last session** on the empty state. Then delete one of the two hosts
   from a scratch config and confirm the restore skips it instead of opening a
   failing tab.
7. **Chinese and the fallback font**: with a primary font that has no CJK
   (`Cascadia Mono`, `Consolas`), run
   `printf 'A中文B\n'` and `printf 'あア한\n'`. Set **Fallback for missing
   glyphs** to `Microsoft YaHei`, then to `KaiTi` / `SimSun`: the Chinese
   glyph *shapes* must change while the ASCII stays identical, and the ASCII
   after each wide glyph must stay on its column (columns 0, 1, 4). Set the
   fallback to **None** and confirm the characters still appear (the system
   fallback takes over) but are no longer the chosen family. Run `htop` or a
   tool that draws Chinese in a table and confirm the columns stay aligned.

On a Windows build the gate runs the pixel checks on the native platform
plugin; when only `offscreen` is available, expect the selection/search pixel
checks to fail for lack of a font database and read the CJK geometry checks
instead.

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

## Gate 7 — manual key management

`app/keys.py` works on the real `~/.ssh`; there is no override. Run these on a
machine (or a temporary `HOME`) whose keys you can afford to change, and read
invariant 12 first.

1. **Keys** in the sidebar lists `id_ed25519` and friends. Compare one row's
   fingerprint with `ssh-keygen -lf ~/.ssh/id_ed25519.pub`; they must be
   identical (`SHA256:…`).
2. Create an ed25519 key with a passphrase and a comment. Confirm the file
   appears with `-rw-------` permissions, that the fingerprint on the new row
   matches `ssh-keygen -lf`, and that creating the same name again is refused
   rather than overwriting.
3. **Copy public** puts the `ssh-ed25519 …` line on the clipboard.
4. **Install on host** against a loopback host: the session opens, the line is
   appended to `~/.ssh/authorized_keys`, and running it twice does not add a
   second copy.
5. Known hosts: a hashed entry (`HashKnownHosts yes`) is listed as `(hashed)`.
   **Forget** on it works because the row is deleted by line; on a named row
   the whole host is removed. Either way the next connection asks to verify the
   host key again.
6. **Trust a host**: scan `127.0.0.1`, confirm the fingerprint matches
   `ssh-keyscan -t ed25519 127.0.0.1 | ssh-keygen -lf -`, then **Trust** and
   check the line appears once even after scanning twice.
7. Delete a generated test key and confirm both halves are gone.

## What is not covered

- No automated UI interaction tests. Behaviour of the composer, popover,
  split, search bar and selection is verified by the manual passes above.
- No automated transfer or reconnect test. `sftp_client` and the drop/reconnect
  path need a real process and a real ConPTY, so they are exercised by hand.
- No gate touches the real `~/.ssh/config`; if you add one, it must copy the
  file to a temp path first. The same rule applies to `~/.ssh` itself — see
  invariant 12.
