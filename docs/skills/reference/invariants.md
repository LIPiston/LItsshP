# Reference: Invariants

These are the guarantees a change must not break. Each lists where it lives in
the code and how it is checked.

## 1. The config file is shared with the CLI, not owned by the GUI

Hosts live in `~/.ssh/config` (plus `Include`d files). LItsshP keeps no host
database of its own; `%APPDATA%\LItsshP\state.json` holds UI preferences only.

- Enforced in: `app/paths.py` (`ssh_config`), `app/config.py`, and
  `AppController` (which never stores hosts in `_settings`).
- Checked by: reading `state.json` after a host edit — it must not contain a
  host list.

## 2. Unrelated config text is byte-identical after an edit

Editing or deleting a host rewrites only the lines of that block. Comments,
blank-line separation, ordering, CRLF line endings and a UTF-8 BOM all
survive. A file with no trailing newline gains exactly one.

- Enforced in: `ConfigFile.save()` (splits with `keepends=True` and
  re-encodes with `surrogateescape`), `set_option`, `remove_block`,
  `replace_raw_block`.
- Checked by: `docs/skills/reference/config_roundtrip_gate.py`.

## 3. tssh's `encPassword` stays byte-compatible

Passwords are written as `#!! encPassword <hex>` and `#!! encQuestionAnswer1`
using AES-256-GCM with the constant key `THE_UNSAFE_KEY_FOR_ENCODING_ONLY`,
`hex(nonce || ciphertext || tag)`. This is obfuscation, not protection — say
so in any user-facing text, as the README does.

- Enforced in: `app/secret.py`.
- Checked by: `config_roundtrip_gate.py` (round-trip via `encode_secret` /
  `decode_secret`) and by opening an existing tssh-written config and reading
  its password.

## 4. A session is a real `tssh` process

Opening a tab spawns `tssh <alias>` in a ConPTY; nothing reimplements SSH,
password entry, jump hosts or trzsz. If `LITSSHP_CONFIG` is set, `-F` is passed
so the spawn agrees with the config that was parsed.

- Enforced in: `PtySession.start` and `AppController._start`.
- Consequence: a bug that only reproduces with the real binary cannot be
  fixed by faking a session in Python; reproduce with `tssh` first.

## 5. No Qt object is touched off the GUI thread

Reader threads in `pty_session.py` and worker threads in `sftp_client.py` only
append to a deque or emit signals. All parsing, screen mutation and painting
happen on the GUI thread.

- Enforced in: the reader/drain split in `pty_session.py`, and
  `threading.Thread(... target=self._upload ...)` starting a slot body that
  only calls `subprocess`/`PTY`.
- Symptom when broken: random crashes or `QObject: Cannot create children for
  a parent in a different thread`.

## 6. Progress and sheet state must not wait on an animation

md3's `LinearProgress` animates `_visualValue` toward `value` over 200 ms. On a
fast, continuously updated transfer that makes the bar read low: measured with
a 30 ms update interval and `value = 0.6`, `_visualValue` was `0.348`, only
catching up once updates stopped. Progress surfaces therefore size a plain
`Rectangle` directly from the reported fraction, and sheets show/hide
immediately instead of animating `opacity` from 0.

This is a responsiveness rule, not a claim that animations are broken — they do
run. The rule is that no visible state may depend on one *completing*, because
a value that trails its target by a frame or two is wrong where a progress bar
is concerned, and an interrupted animation must never leave a sheet unusable.

- Enforced in: `TransferIndicator.qml`, the footer bar in `TransferWindow.qml`,
  `TransferPopover`'s bars, and the `visible`-driven sheets.
- Symptom when broken: a bar that reads 35% while the transfer is at 60%, or a
  sheet whose content is only usable after an animation finishes.

## 7. Text fields that scroll internally keep their own clip and offset

The composer and the raw-block editor place a `TextEdit` inside a clipped
`Item` and move it with `y: -scrollOffset`, updating the offset on caret
movement, rather than nesting it in a `Flickable`. This shape was adopted after
the original Flickable layout showed no text in the running app; a minimal
`Flickable` + `TextEdit` reproduction does render here, so the exact trigger
was never isolated, and the working shape is kept deliberately.

- Enforced in: `CommandComposer.qml`, `HostEditorSheet.qml` (`rawViewport`).
- Practical rule: when adding a text field that can overflow, copy one of
  those two rather than introducing a third pattern, and verify by typing
  multi-line text into it and looking at the glyphs, not just the caret.
- Checked by: [Verification gates](verification.md) Gate 4, step 5.

## 8. Keyboard shortcuts never steal Ctrl+C / Ctrl+V from the terminal

`Ctrl+C` alone must reach the shell as SIGINT. Only `Ctrl+Shift+C` copies and
`Ctrl+Shift+V` pastes, and those are handled inside `TerminalPane` rather than
as window-level `Shortcut`s, so the composer and text fields keep their own
plain clipboard behaviour.

- Enforced in: `Main.qml` (a comment marks the intentional absence),
  `TerminalPane.qml` `Keys.onPressed`.
- Symptom when broken: Ctrl+C in `vim` or `ping` stops working.

## 9. A transfer's route label points at the destination

The UI says `this PC → host` or `host → this PC`, never "upload"/"download".
Internally the direction is still `"Upload"`/`"Download"`; only the label is
translated, in `_route()` in `controller.py` and `routeFor()` in
`TransferWindow.qml`.

- Enforced in: `_route`, `TransferWindow.routeFor`, `TransferIndicator`.
- Checked by: starting both an upload and a download and reading the labels in
  the indicator, the popover and the window footer.
