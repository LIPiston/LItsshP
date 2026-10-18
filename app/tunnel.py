"""Port forwarding: spec parsing and supervised ``tssh -N`` processes.

Two facts shape this module:

* A forwarding rule lives in ``~/.ssh/config``, so **the session itself already
  applies it** when it connects. There is no second process to start while a
  tab is open, and starting one would only race the session for the port.
* A rule is therefore a property of a connection. Unless it is marked
  persistent, it ends when the session ends.

``TunnelManager`` models a host, not a rule: ``tssh -N <alias>`` opens every
forward declared for that alias, so one process per host is the honest unit.
An entry is in one of these states:

``session``   an open session provides the forwards; no process of ours
``pending``   persistent, waiting for the session to release the ports
``starting``  our own ``tssh -N`` was launched, not yet confirmed
``running``   our process outlived the settle window
``failed``    tssh reported a problem (or died) and the entry explains why
``stopped``   stopped on request

Marking a ``session`` entry persistent means "restart it as our own process
once the session goes away", which is the only moment the port is free.
"""

from __future__ import annotations

import os
import re
import socket
import time

from PySide6.QtCore import Property, QObject, QTimer, Signal

from . import paths
from .pty_session import PtySession

# How long a ``-N`` process must stay alive before it is called running:
# ssh prints nothing on success, and a refusal (bad auth, unknown host) is
# reported within the first moments of the connection attempt.
SETTLE_MS = 1500
# A session's listeners are not necessarily gone the instant its PTY exits, so
# a persistent tunnel retries the bind for a short window.
RETRY_MS = 250
RETRY_ATTEMPTS = 8

_KIND_FLAGS = {"L": "-L", "R": "-R", "D": "-D"}
_KIND_NAMES = {"L": "Local", "R": "Remote", "D": "Dynamic"}

# tssh colourises warnings; the UI shows them as plain text.
_ANSI_RE = re.compile(r"\x1b\[[0-9;]*[A-Za-z]|\x1b\][^\x07]*\x07")


def _plain(text: str) -> str:
    return _ANSI_RE.sub("", text).strip()


def kind_flag(kind: str) -> str:
    return _KIND_FLAGS.get(str(kind).upper(), "-L")


def kind_name(kind: str) -> str:
    return _KIND_NAMES.get(str(kind).upper(), "Local")


def _split_spec(spec: str) -> list[str]:
    """Split on colons outside ``[...]`` so bracketed IPv6 survives."""
    parts: list[str] = []
    depth = 0
    current = ""
    for ch in spec:
        if ch == "[":
            depth += 1
        elif ch == "]":
            depth = max(0, depth - 1)
        if ch == ":" and depth == 0:
            parts.append(current)
            current = ""
        else:
            current += ch
    parts.append(current)
    return parts


def _unbracket(value: str) -> str:
    if value.startswith("[") and value.endswith("]"):
        return value[1:-1]
    return value


def _valid_port(value: str) -> bool:
    return value.isdigit() and 0 < int(value) < 65536


def parse_forward_spec(kind: str, spec: str) -> dict:
    """Describe a forwarding spec without normalising the text.

    Returns ``{valid, bind, port, target_host, target_port, error}``. An
    invalid result is advisory only: the raw spec is still what reaches tssh,
    because OpenSSH understands forms this parser deliberately does not (Unix
    sockets, ``none`` bindings) and it should be the one to decide.
    """
    kind = str(kind).upper()
    text = (spec or "").strip()
    result = {"valid": False, "kind": kind, "bind": "", "port": 0,
              "target_host": "", "target_port": 0, "error": ""}
    if not text:
        result["error"] = "Empty forwarding spec"
        return result

    parts = _split_spec(text)
    if kind == "D":
        if len(parts) == 1:
            bind, port = "", parts[0]
        elif len(parts) == 2:
            bind, port = _unbracket(parts[0]), parts[1]
        else:
            result["error"] = "Dynamic forwarding takes [bind:]port"
            return result
        if not _valid_port(port):
            result["error"] = f"'{port}' is not a valid port"
            return result
        result.update(valid=True, bind=bind or "127.0.0.1", port=int(port))
        return result

    if len(parts) == 3:
        bind, port, host, hostport = "", parts[0], parts[1], parts[2]
    elif len(parts) == 4:
        bind, port, host, hostport = (_unbracket(parts[0]), parts[1],
                                      parts[2], parts[3])
    else:
        result["error"] = "Expected [bind:]port:host:hostport"
        return result

    if not _valid_port(port):
        result["error"] = f"'{port}' is not a valid listen port"
        return result
    if not host:
        result["error"] = "Target host is missing"
        return result
    if not _valid_port(hostport):
        result["error"] = f"'{hostport}' is not a valid target port"
        return result

    result.update(valid=True, bind=bind or "127.0.0.1", port=int(port),
                  target_host=host, target_port=int(hostport))
    return result


def format_forward_label(kind: str, spec: str) -> str:
    """Readable one-liner for lists: ``127.0.0.1:8080 → localhost:80``."""
    parsed = parse_forward_spec(kind, spec)
    if not parsed["valid"]:
        return spec or "(empty)"
    listen = f"{parsed['bind']}:{parsed['port']}"
    if ":" in parsed["bind"] and not parsed["bind"].startswith("["):
        listen = f"[{parsed['bind']}]:{parsed['port']}"
    if str(kind).upper() == "D":
        return f"{listen} → SOCKS"
    target = parsed["target_host"]
    if ":" in target and not target.startswith("["):
        target = f"[{target}]"
    return f"{listen} → {target}:{parsed['target_port']}"


def tunnel_argv(alias: str) -> list[str]:
    """The exact command a tunnel runs, also shown in the UI.

    No explicit ``-L``/``-R``/``-D``: ``tssh -N <alias>`` opens whatever the
    config declares, which is precisely the set the UI lists. Passing one of
    them as well would make tssh bind the same port twice.
    """
    argv = ["tssh"]
    if os.environ.get("LITSSHP_CONFIG"):
        argv += ["-F", str(paths.ssh_config())]
    argv += ["-N", alias]
    return argv


def port_available(kind: str, spec: str) -> str:
    """Empty string when the local listen address can be bound, else why not.

    Only local forwards and SOCKS bind on this machine; a remote forward binds
    on the server and cannot be probed from here.
    """
    parsed = parse_forward_spec(kind, spec)
    if not parsed["valid"] or str(kind).upper() == "R":
        return ""
    bind = parsed["bind"] or "127.0.0.1"
    try:
        infos = socket.getaddrinfo(bind, parsed["port"], 0, socket.SOCK_STREAM)
    except OSError as exc:
        return f"Cannot resolve {bind}: {exc}"
    family, socktype, proto, _, sockaddr = infos[0]
    probe = socket.socket(family, socktype, proto)
    try:
        # No SO_REUSEADDR here: on Windows it lets a second socket bind an
        # address that is already being listened on, so the probe would report
        # "free" for exactly the conflict it exists to catch.
        probe.bind(sockaddr)
    except OSError:
        return f"{bind}:{parsed['port']} is already in use"
    finally:
        probe.close()
    return ""


class TunnelEntry(QObject):
    """The forwarding state of one host: its session, its process, or both."""

    changed = Signal()

    def __init__(self, alias: str, rules: list[dict], parent: QObject | None = None):
        super().__init__(parent)
        self.alias = alias
        self.rules = rules
        self.persist = False
        # Sessions currently providing these forwards. A second tab on the same
        # host does not overwrite the first: both are released independently.
        self.session_ids: set[int] = set()
        self.state = "session"          # see module docstring
        self.error = ""
        self.started_at = time.time()
        self.command = tunnel_argv(alias)
        self._output: list[str] = []
        self._attempts = 0
        self._retry = QTimer(self)
        self._retry.setSingleShot(True)
        self._retry.timeout.connect(self._spawn)

        self._pty = PtySession(self)
        self._pty.dataReceived.connect(self._on_data)
        self._pty.exited.connect(self._on_exit)
        self._pty.failure.connect(self._on_failure)

        self._settle = QTimer(self)
        self._settle.setSingleShot(True)
        self._settle.setInterval(SETTLE_MS)
        self._settle.timeout.connect(self._on_settle)

    @property
    def key(self) -> str:
        return self.alias

    @property
    def owns_process(self) -> bool:
        return self._pty.running

    # ------------------------------------------------------------------ start

    def attach_session(self, session_id: int, persist: bool) -> None:
        """Record that an open session already provides these forwards."""
        if session_id:
            self.session_ids.add(session_id)
        self.persist = bool(persist) or self.persist
        self.state = "session"
        self.error = ""
        self.changed.emit()

    def notify_port_free(self) -> None:
        """The session ended: claim the ports now if persistence was asked for.

        Retries for a short window because the session's listener is torn down
        asynchronously by the OS.
        """
        if not self.persist:
            self.state = "stopped"
            self.changed.emit()
            return
        self.session_ids.clear()
        self.state = "pending"
        self._attempts = 0
        self.changed.emit()
        self._retry.start(RETRY_MS)

    def _spawn(self) -> None:
        conflict = self._conflict()
        if conflict:
            self._attempts += 1
            if self._attempts < RETRY_ATTEMPTS:
                self._retry.start(RETRY_MS)
                return
            self.state = "failed"
            self.error = conflict
            self.changed.emit()
            return

        self.state = "starting"
        self.error = ""
        self.started_at = time.time()
        self._output.clear()
        self.changed.emit()
        if not self._pty.start(self.command, cols=100, rows=24):
            self.state = "failed"
            self.error = "Could not start tssh for the tunnel"
            self.changed.emit()
            return
        self._settle.start()

    def _conflict(self) -> str:
        for rule in self.rules:
            message = port_available(rule.get("kind", "L"), rule.get("spec", ""))
            if message:
                return message
        return ""

    def stop(self) -> None:
        self._retry.stop()
        self._settle.stop()
        self._pty.stop()
        self.state = "stopped"
        self.changed.emit()

    def set_persist(self, persist: bool) -> None:
        self.persist = bool(persist)
        if not self.persist and self.state == "pending":
            # Nothing to keep alive and no session left to inherit from.
            self._retry.stop()
            self.state = "stopped"
        self.changed.emit()

    # --------------------------------------------------------------- process

    def _on_data(self, chunk: str) -> None:
        for line in chunk.replace("\r", "").split("\n"):
            clean = _plain(line)
            if clean:
                self._output.append(clean)
        del self._output[:-200]
        # tssh does not honour ExitOnForwardFailure and exits 0 after printing
        # a bind warning, so a log line is the only evidence the rule failed.
        if self.state in ("starting", "running") and self._bind_failed():
            self.state = "failed"
            self.error = self._explain(None)
            self._settle.stop()
            self._pty.stop()
            self.changed.emit()

    def _bind_failed(self) -> bool:
        for line in self._output:
            low = line.lower()
            if "forward" in low and ("failed" in low or "cannot" in low):
                return True
        return False

    def _on_settle(self) -> None:
        if self.state != "starting":
            return
        if self._bind_failed():
            self.state = "failed"
            self.error = self._explain(None)
            self._pty.stop()
            self.changed.emit()
            return
        if self._pty.running:
            self.state = "running"
            self.changed.emit()

    def _on_exit(self, status: int) -> None:
        self._settle.stop()
        if self.state == "stopped":
            return
        self.state = "failed"
        self.error = self._explain(status)
        self.changed.emit()

    def _on_failure(self, message: str) -> None:
        self._settle.stop()
        self.state = "failed"
        self.error = message
        self.changed.emit()

    def _explain(self, status: int | None) -> str:
        for line in reversed(self._output):
            low = line.lower()
            if any(word in low for word in
                   ("error", "denied", "refused", "failed", "cannot", "could not")):
                return line
        if self._output:
            return self._output[-1]
        return f"tssh exited with status {status}"

    # ------------------------------------------------------------------- read

    def to_dict(self) -> dict:
        return {
            "key": self.key,
            "alias": self.alias,
            "state": self.state,
            "persist": self.persist,
            "sessionIds": sorted(self.session_ids),
            "error": self.error,
            "command": " ".join(self.command),
            "startedAt": self.started_at,
            "rules": [
                {
                    "kind": rule.get("kind", "L"),
                    "kindName": kind_name(rule.get("kind", "L")),
                    "spec": rule.get("spec", ""),
                    "label": format_forward_label(rule.get("kind", "L"),
                                                  rule.get("spec", "")),
                    "source": rule.get("source", ""),
                }
                for rule in self.rules
            ],
        }


class TunnelManager(QObject):
    """Owns one forwarding entry per host."""

    changed = Signal()

    def __init__(self, parent: QObject | None = None):
        super().__init__(parent)
        self._entries: dict[str, TunnelEntry] = {}

    # ------------------------------------------------------------------ rules

    def set_rules(self, alias: str, rules: list[dict]) -> None:
        """Refresh the rule list an existing entry reports."""
        entry = self._entries.get(alias)
        if entry is not None:
            entry.rules = rules
            self.changed.emit()

    # ------------------------------------------------------------------ start

    def start(self, alias: str, rules: list[dict], *,
              persist: bool = False, session_id: int = 0) -> dict:
        if not alias:
            return {"ok": False, "error": "A host is required"}
        if not rules:
            return {"ok": False, "error": f"{alias} has no forwarding rules"}

        entry = self._entries.get(alias)
        if entry is not None and entry.state in ("starting", "running"):
            entry.set_persist(persist or entry.persist)
            return {"ok": True, "key": alias, "already": True}

        if entry is not None and entry.state == "session":
            entry.rules = list(rules)
            entry.attach_session(session_id, persist)
            self.changed.emit()
            return {"ok": True, "key": alias, "viaSession": True}

        entry = entry or TunnelEntry(alias, list(rules), self)
        entry.rules = list(rules)
        entry.changed.connect(self.changed)
        self._entries[alias] = entry

        if session_id:
            entry.attach_session(session_id, persist)
        else:
            entry.persist = bool(persist)
            entry.session_ids.clear()
            entry.state = "pending"
            entry._retry.start(0)
        self.changed.emit()
        return {"ok": True, "key": alias, "viaSession": bool(session_id)}

    def stop(self, alias: str) -> None:
        entry = self._entries.pop(alias, None)
        if entry is None:
            return
        entry.stop()
        entry.changed.disconnect(self.changed)
        entry.deleteLater()
        self.changed.emit()

    def stop_all(self) -> None:
        for alias in list(self._entries):
            self.stop(alias)

    def stop_session(self, session_id: int) -> None:
        """Release the forwarding owned by one session.

        A host with other live sessions keeps its forwards: the remaining
        session is still providing them. Once the last one goes, a
        non-persistent entry disappears and a persistent one spawns its own
        ``tssh -N`` now that the port is on its way out.
        """
        for alias, entry in list(self._entries.items()):
            if session_id not in entry.session_ids:
                continue
            entry.session_ids.discard(session_id)
            if entry.state != "session":
                continue
            if entry.session_ids:
                entry.changed.emit()
                self.changed.emit()
                continue
            if entry.persist:
                entry.notify_port_free()
            else:
                self.stop(alias)

    def session_closed(self, session_id: int) -> None:
        self.stop_session(session_id)

    def set_persist(self, alias: str, persist: bool) -> bool:
        entry = self._entries.get(alias)
        if entry is None:
            return False
        entry.set_persist(persist)
        return True

    def owns_process(self, alias: str) -> bool:
        """Whether a ``tssh -N`` of ours is holding this host's ports."""
        entry = self._entries.get(alias)
        return bool(entry and entry.state in ("pending", "starting", "running"))

    # ------------------------------------------------------------------- read

    def active_keys(self) -> list[str]:
        return [k for k, e in self._entries.items()
                if e.state in ("session", "pending", "starting", "running")]

    def _get_tunnels(self) -> list:
        return [e.to_dict() for e in self._entries.values()]

    tunnels = Property("QVariantList", _get_tunnels, notify=changed)

    def _get_count(self) -> int:
        return len(self._entries)

    count = Property(int, _get_count, notify=changed)

    def _get_active(self) -> bool:
        return bool(self.active_keys())

    active = Property(bool, _get_active, notify=changed)
