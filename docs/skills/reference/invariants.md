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

## 10. Forwarding is a property of a connection

A forwarding rule lives in the host's config block, so the session's own
`tssh <alias>` already applies it. The app never spawns a second `tssh -N` while
a session for that host is open — two processes would bind the same port.

When the session ends, a non-persistent forward ends with it. Only a rule the
user marked **keep running** is taken over by `tssh -N`, and even those stop
when the app exits.

- Enforced in: `TunnelManager.start`/`stop_session` and
  `TunnelEntry.notify_port_free`, called from `AppController.openHost`,
  `closeTab`, `_on_exit`, `_reconnect` and `shutdown`.
- Practical rules: never pass `-L`/`-R`/`-D` to the tunnel process (the config
  already declares them); never trust tssh's exit code to signal a forwarding
  failure — it prints a warning and exits 0, so the output is what is checked;
  when a persistent tunnel already owns the host's ports, the session is
  spawned with `-o ClearAllForwardings=yes` so the two do not fight for them.
- Checked by: `forward_roundtrip_gate.py` (rules and parser) and the manual
  port-forward smoke in [Verification](verification.md).

## 11. The editor never silently converts the password form

`#!! encPassword`, `#!! Password` and `#!! PasswordCommand` are three distinct
stored forms, and tssh resolves them in that order. Saving a host keeps the
form it found:

- an encrypted password is written back encrypted (new nonce only when the
  text actually changed);
- a plain `#!! Password` stays plain — no `encPassword` is introduced;
- clearing the field removes both forms the editor can show but leaves a
  `PasswordCommand` alone, because the editor never displayed that command and
  deleting it would break a working login.

`HostEntry.password_source` (`encrypted` / `plain` / `command` / `answer` / ``)
is what carries the decision from `config.py` to `HostEditorSheet.qml`; the
sheet sends it back in `saveHost`. `has_password` is true for a
`PasswordCommand` too, since a host that has one does not need a typed secret.

- Enforced in: `ConfigStore._password_source` and `_write_password`.
- Checked by: `session_features_gate.py` (plain stays plain, encrypted
  converts, clearing keeps `PasswordCommand`).

## 12. Tests never touch the real `~/.ssh`

`LITSSHP_CONFIG` redirects the config, but nothing redirects `~/.ssh` itself:
`keys.list_keys()`, `known_hosts_entries()`, `remove_known_hosts()` and
`generate_key()` all default to `paths.ssh_dir()`. A gate that calls one of
them without an override edits the developer's real keys.

- Enforced in: every gate sets `LITSSHP_CONFIG`, `LITSSHP_STATE` and
  `LITSSHP_LOGS` to a `tempfile.mkdtemp()` path before importing `app`;
  `keys` functions accept an explicit `folder` / `path` for the rest.
- Practical rule: when adding a check that touches keys or known hosts, pass a
  temp path explicitly. There is no environment variable for `known_hosts`.
- Symptom when broken: `~/.ssh/known_hosts.old` appears, or a real entry
  disappears. If that happens, `shell.old` is the backup — restore it before
  doing anything else.

## 13. View state is painted as an overlay, not by inverting the cell

Selection and search highlights are filled over the cell rectangle with a
translucent themed colour in `_paint_row`; the glyph keeps its own colour.
Reverse video is wrong here twice over: the visible colour would depend on
what the program printed, and an inverted run has to break whenever cell
attributes change, which fragments the painted runs.

Runs therefore also break on `run_selected` / `run_mark` transitions, and both
colours come from `applyTheme` (`selection` is `#AARRGGBB`).

- Enforced in: `TerminalModel._paint_row` and `_render`.
- Checked by: `session_features_gate.py` (a selected cell's pixel changes to
  the themed colour and clearing restores it; a search match changes the
  pixel), and by a manual drag-selection over normal, bold and reverse-video
  text — the highlight must look the same and the text must stay readable.

## 14. The UI never opens a session on its own at launch

`state.json` records the last layout, but nothing is dialled until the user
asks: **Reopen last session** in the empty state, the palette entry, or
`Ctrl+Shift+O`. `restoreLayout()` is the only path that consumes `_saved_layout`,
and it skips aliases that are no longer in the config.

The saved layout is also guarded against being erased: `_save_state` only
writes `layout` while `_tabs` is non-empty, and `shutdown()` saves before it
stops and clears the tabs.

- Enforced in: `AppController._save_state`, `shutdown`, `restoreLayout`.
- Checked by: `session_features_gate.py` (a fresh state has no layout; a saved
  one survives into a second controller; an unknown alias is skipped).

## 15. One character may occupy two columns, and the grid never drifts

The cell width is exactly `horizontalAdvance("W")` of the primary font, with
no padding factor. A multiplier such as `1.02` looks harmless but accumulates:
80 columns overshot by 15 px, and every run after the first started at the
wrong place. Do not reintroduce one to "make text look roomier" — change the
font size instead.

A wide glyph (CJK, full-width punctuation) is one cell holding the character
followed by a stub cell with `data == ""`; it spans **two** columns. Painting,
selection text, the cursor block and search hits must all agree:

- `_cell_span()` returns `wcswidth(data)`, so a stub is `0` and is skipped
  before it advances the grid a second time;
- a wide glyph is centred inside its two-column box, since the font's own
  advance is narrower than `2 * cell_w`;
- a search hit is `(row, column, column_span)`, mapped from character indexes
  by `_row_text()`, not a character offset.

- Enforced in: `TerminalModel._paint_row`, `_paint_cursor`, `_run_search`.
- Checked by: `session_features_gate.py` (spans, column mapping, a `文C` hit
  reported at columns 4–6, the glyphs landing on the grid) and by typing
  Chinese into a real session: the following ASCII text must sit on its
  columns.

## 16. Fallback glyphs are chosen per character, never by `setFamilies`

`QFont.setFamilies([primary, fallback])` is a *resolution* order, not a
per-glyph fallback: with `["Cascadia Mono", "Microsoft YaHei"]` Qt still drew
`中` with the system CJK font, and swapping the second family for `SimSun` or
`KaiTi` changed no pixel. Reaching for it again will silently ignore the user's
choice.

`TerminalModel` therefore keeps a `QRawFont` for the primary, asks
`supportsCharacter()` per character (cached in `_glyph_cache`), and paints a
character the primary lacks with a `QFont` built from `fontFallback`. The cell
width stays the primary font's, so the grid does not move when the fallback
changes.

- Enforced in: `TerminalModel._needs_fallback`, `_font_for`, `_paint_row`.
- Checked by: `session_features_gate.py` (a stub raw font proves the decision
  without depending on installed fonts; only `中`/`文` take the per-glyph path)
  and by picking a fallback in Settings and watching the Chinese glyph shape
  change in a live session.
