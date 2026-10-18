# Skill: File Transfers

The transfer window (`app/qml/TransferWindow.qml` + `app/sftp_client.py`) plus
the progress surfaces in the main window. Read this before changing any of
them.

## Why plain SFTP

tssh's own transfer path (`--upload-file`, trzsz `tsz`) requires `trz`/`tsz` on
the **remote** host. For a file manager that is too high a bar, so the window
speaks plain SFTP through the OpenSSH client, reusing the same config entry
(initialized, `ProxyJump`, `IdentityFile`, agent) as the session.

## Two execution paths

| Path | Commands | Mechanism |
| --- | --- | --- |
| metadata | `pwd`, `ls -la`, `rm`, `mkdir`, `rename` | `sftp -b -` via `subprocess.run`, output parsed from stdout |
| transfers | `put -R`, `get -R` | `PTY(50, 200, backend=ConPTY)`; script queued up front |

The split is not stylistic. **sftp only draws its progress meter when it owns
a TTY**, and `-b -` mode is silent. Transfers therefore run under ConPTY and
the meter is scraped; metadata stays in batch mode because its output is clean
and parseable.

`-R` makes directory transfers recursive and is a no-op for plain files, so a
mixed selection needs no per-item branching.

## Meter scraping

`_MeterState` consumes the PTY stream and:

- strips ANSI sequences;
- splits on `\r` **and** `\n`, carrying the trailing partial line between
  chunks (the meter redraws with `\r`, so chunk boundaries land mid-line);
- detects per-file headers (`uploading …`, `downloading …`) to count files;
- matches `name 42% 1.2MB 3.4MB/s 00:03` and emits
  `progressChanged(label, fraction, detail)`;
- accumulates completed file sizes so a multi-file transfer reports one
  fraction of the total (`_total(sizes)`; `-1` when any size is unknown, in
  which case the per-file percentage is used);
- records failure hints (`permission denied`, `not found`, `broken pipe`, …).

`fraction` is clamped to 0..1 by the controller and by the UI. A finished
transfer emits `1.0` with a summary before `operationDone`.

If a transfer ends with exit status 0 *and* no failure hint, it is reported as
successful. Both conditions matter: sftp can exit 0 after printing a per-file
error.

## Path quoting

- **Remote**: `_quote_remote` wraps in double quotes and escapes `\` and `"`.
- **Local**: `_quote_local` first converts `\` to `/`. sftp's batch parser
  treats backslash as an escape inside quotes, so `C:\Users` would arrive as
  `C:Users`. sftp accepts forward slashes on Windows, so this is safe.

Do not remove the normalisation because "Windows paths should keep
backslashes" — they must not, in this particular string.

## Starting folders and fallbacks

| Pane | Start | Fallback |
| --- | --- | --- |
| local | `paths.home()` (profile) | `%TEMP%\LItsshP` when the profile is not writable |
| remote | `pwd` result | `~`, then `/`, then `/tmp` — first one that lists |

`listLocalResult` also treats a **not-yet-existing** folder as usable when its
nearest existing ancestor is writable, because users type a download target
that does not exist yet. A folder that cannot be read at all returns
`{ok: false, …, fallback}`, and the pane moves to the fallback while showing
why.

`_download` mirrors this on the transfer side: create the destination, probe
it with `paths.is_writable`, and fall back to `%TEMP%\LItsshP` if that fails.
It only reports failure when even the temp folder cannot be created.

## Progress surfaces

| Surface | File | Data source |
| --- | --- | --- |
| tab-strip indicator | `TransferIndicator.qml` | `App.transfers`, first entry |
| running-count badge + popover | `Workspace.qml`, `TransferPopover.qml` | `App.transferCount`, `App.transfers`, `App.transferHistory` |
| footer bar in the window | `TransferWindow.qml` | `progressChanged` via `onProgress` |

All three are plain `Rectangle`s sized from a property — no `Behaviour`, no
`LinearProgress` (see invariant 6).

`AppController` keeps `_transfers` keyed by the client object and a bounded
`_transfer_log` (40 entries). Each entry stores `direction` (`Upload` /
`Download`) but displays `route` (`this PC → host` / `host → this PC`), derived
by `_route()`. Keep that separation: the internal direction is convenient;
the label is what the user asked for.

## Adding an operation

1. Add a `@Slot` on `SftpClient` that returns immediately and starts a thread.
2. Metadata-style operations: build batch lines and call `self._run(lines)`.
3. Transfer-style operations (anything with a meter): build lines and call
   `self._transfer(label, lines, total)`.
4. Emit `operationDone(what, ok, message)` in every path, including the
   early-exit ones, or the UI stays `busy`.
5. Add the QML control to `TransferWindow.qml`'s footer or pane, and disable
   it while `busy`.

## Cancel and lifetime

`TransferWindow.onClosing` calls `sftp.cancel()`, which writes `\x03` to the
transfer PTY. `_transfer` polls `isalive()` at 20 Hz with a 900 s deadline and
reports `"Cancelled"` on cancel. Do not remove the poll: the reader thread can
exit while the process lingers, and without it the UI would hang in `busy`.

## Manual check

Follow [Verification gates](reference/verification.md) Gate 5. In
particular, verify both directions produce the correct route label, and that
closing the window mid-transfer leaves no stray `sftp` process
(`tasklist | findstr sftp`).
