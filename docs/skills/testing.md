# Skill: Testing and Verification

This repository has no test suite. Verification means running the gates and
doing the manual passes that cover the parts gates cannot reach. This page is
about how to run them, when to add one, and how to report results honestly.

## The gates

| Gate | Command | Proves | Runtime |
| --- | --- | --- | --- |
| compile | `.venv/Scripts/python -m compileall -q app` | Python parses | < 2 s |
| QML load | `.venv/Scripts/python docs/skills/reference/qml_load_gate.py` | the whole QML tree loads with no binding errors | ~3 s |
| config | `.venv/Scripts/python docs/skills/reference/config_roundtrip_gate.py` | the writer preserves unrelated text; secrets round-trip | < 2 s |
| forwarding | `.venv/Scripts/python docs/skills/reference/forward_roundtrip_gate.py` | accumulating forwards round-trip and stay host-scoped | < 2 s |
| session features | `.venv/Scripts/python docs/skills/reference/session_features_gate.py` | password form is preserved; search, log and layout behave | ~3 s |

All five are safe at any time: the QML gate uses an offscreen platform and
temp config/state paths, and the others write only to a temp directory. None of
them touches the real `~/.ssh` — keep it that way (invariant 12).

Run all five before and after any change. "It looks right" is not a result;
paste the actual output.

## Manual passes

Three manual passes exist, all described step by step in
[reference/verification](reference/verification.md):

- **Gate 4/4b — session smoke**: connect, type, copy/paste, composer,
  scrollback, full-screen mouse handoff; then search, session log,
  auto-reconnect, keep-alive, split/broadcast, snippets/startup and layout
  restore.
- **Gate 5 — transfer smoke**: upload, download, route labels, popover,
  permission fallback, cancel.
- **Gate 7 — key management**: fingerprints against `ssh-keygen -lf`, key
  creation, install-on-host, known-host removal. This one edits the real
  `~/.ssh`, so only run it where that is acceptable.

They need a reachable SSH host. `sshd` is running on this machine, so a
`localtest` block on `127.0.0.1` is enough.

## Adding automated coverage

There is no test framework installed and no `pyproject.toml`. If you add one,
the cheapest useful shape is what the gates already do: a script under
`docs/skills/reference/` that asserts and exits non-zero.

Guidelines for a new gate:

1. **Never touch real state.** Set `LITSSHP_CONFIG` / `LITSSHP_STATE` /
   `LITSSHP_LOGS` to a `tempfile.mkdtemp()` path before importing `app`. Those
   cover the config, the state file and logs; they do **not** redirect
   `~/.ssh`, so pass an explicit folder to anything in `app/keys.py`.
2. **Test a guarantee, not an implementation detail.** Name the invariant it
   protects (see [Invariants](reference/invariants.md)) in the docstring.
3. **Print one line per check**, `PASS name` / `FAIL name`, then a one-line
   summary and an exit code. The existing gates are the template.
4. **Fail loudly on an exception.** A traceback exiting non-zero is fine; a
   swallowed exception is not.
5. **Scope a text assertion to the thing under test.** Checking a whole config
   file for the absence of `encPassword` fails whenever another host has one,
   and passes for the wrong reason in other cases. Extract the block (see
   `block()` in `session_features_gate.py`) and assert on that.

### Testing QML behaviour from Python

The pattern the manual harnesses use, and the pitfalls that come with it:

```python
engine = QQmlApplicationEngine()
engine.addImageProvider("terminal", controller.imageProvider())
controller.setParent(engine)          # keeps bindings valid during teardown
engine.addImportPath(str(ROOT / "third_party"))
engine.rootContext().setContextProperty("App", controller)
engine.load(QUrl.fromLocalFile(str(ROOT / "app" / "qml" / "Main.qml")))
window = engine.rootObjects()[0]
```

- `findChildren(QQuickItem)` does **not** return `Repeater` delegates. Walk
  `childItems()` instead, and keep a Python reference to every wrapper you
  keep, because the C++ object can be destroyed when the wrapper is collected.
- `itemAt()` on a QML `Repeater` cannot be called from Python (the return type
  is `QQuickItem*`, not a `QVariant`). Ask the controller, or use
  `childItems()`.
- Drive Qt with `QTimer.singleShot` chains rather than sleeps, and call
  `app.exec()`; bindings and timers only run inside the event loop.
- Set `QT_QPA_PLATFORM=offscreen` and `QT_QUICK_BACKEND=software` for
  headless runs. Do not assert on pixels from the offscreen backend.

### Testing transfers

The meter only exists under a real ConPTY, so a transfer test must spawn one:

1. Create a temp "remote" folder and a payload file.
2. Point a `localtest`-style host at `127.0.0.1`, and use the POSIX form of
   the temp path (`C:\...` becomes `/C:/...` in sftp's view of a Windows sftp
   server).
3. Upload into a **separate** directory — uploading a file into its own
   directory produces `dest open ... Failure`.
4. Wait for `operationDone`, then assert the file exists at the destination.
5. Always `cancel()` and delete the client; a live PTY blocks process exit.

## What not to assert

- Do not assert on QML animations or timers having advanced; they do not run
  reliably here.
- Do not assert on exact pixel colours from a screenshot; the DPR and the
  backend change the result.
- Do not assert that a transfer reached a percentage mid-flight. Fast
  loopback transfers finish before the first sample; assert on the final
  `operationDone` and on the history entry instead.

## Reporting

When you finish a task, say exactly this: which gates you ran, their output,
which manual passes you did (and on what kind of host), and what remains
unverified. If a gate failed and you fixed it, give its output after the fix.
