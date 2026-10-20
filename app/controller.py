"""QML-facing controller: host list, tabs, settings and terminal sessions."""

from __future__ import annotations

import json
import os
import threading
import time
from pathlib import Path

from PySide6.QtCore import Property, QObject, QTimer, Signal, Slot
from . import paths
from .config import ConfigStore, all_groups
from .pty_session import PtySession
from .sftp_client import SftpClient
from .terminal_model import TerminalImageProvider, TerminalModel
from .tunnel import TunnelManager, format_forward_label, tunnel_argv

DEFAULT_SETTINGS = {
    "fontFamily": "Cascadia Mono",
    # Used only for glyphs the primary font lacks (CJK, box drawing, symbols).
    # Empty means "let Qt's own fallback decide", which is what happened
    # before the option existed. Resolved against the installed fonts by
    # _default_fallback(), so the stored value always names a real family.
    "fontFallback": "Microsoft YaHei",
    "fontSize": 14,
    "theme": "dark",          # dark | light | system
    # Theme family (see app/theme.py). `theme` picks its light or dark member,
    # so switching appearance keeps the family the user chose. Families come
    # from the YAML catalog in the app data directory, not from ~/.ssh.
    "themeFamily": "catppuccin",
    # Optional accent override on top of the family accent. "" means "use the
    # theme". Kept under the old key so existing state files still load.
    "seedColor": "",
    "sidebarWidth": 268,
    "sidebarVisible": True,
    "confirmClose": True,
    "copyOnSelect": True,
    "composerVisible": True,   # command composer strip under the terminal
    "terminalTheme": "match",  # match | classic
    "lastSession": "",
    "sessionLog": False,       # write each session's output to a file
    "autoReconnect": True,     # restart a session that drops
    "keepalive": 30,           # ServerAliveInterval seconds; 0 disables
    "broadcastInput": False,   # type into every split pane
    "snippets": [],            # [{name, command}] shared by the palette
}


class Session:
    """One open tab: a PTY process plus its terminal model."""

    _next_id = 1

    def __init__(self, host: str, pty: PtySession, model: TerminalModel):
        self.id = Session._next_id
        Session._next_id += 1
        self.host = host
        self.title = host
        self.model = model
        self.pty = pty
        self.state = "connecting"   # connecting | connected | closed | failed
        self.exit_status: int | None = None
        self.started_at = time.time()
        self.command = f"tssh {host}"
        self.log_path = ""
        self.log_file = None
        self.reconnect_attempts = 0
        self.reconnect_timer: QTimer | None = None
        self.suppress_reconnect = False
        self.startup_sent = False
        self.pending_commands: list[str] = []


class AppController(QObject):
    hostsChanged = Signal()
    groupsChanged = Signal()
    tabsChanged = Signal()
    activeTabChanged = Signal()
    settingsChanged = Signal()
    toast = Signal(str)
    terminalColorsChanged = Signal()
    transferProgressChanged = Signal()
    transferHistoryChanged = Signal()
    tunnelsChanged = Signal()
    layoutChanged = Signal()
    hostScanFinished = Signal("QVariantMap")

    def __init__(self, parent: QObject | None = None):
        super().__init__(parent)
        self._store = ConfigStore()
        self._hosts: list[dict] = []
        self._groups: list[str] = []
        self._tabs: list[Session] = []
        self._active = -1
        self._settings = dict(DEFAULT_SETTINGS)
        self._images = TerminalImageProvider()
        self._transfers: dict[object, dict] = {}
        self._transfer_log: list[dict] = []
        self._transfer_seq = 0
        self._tunnels = TunnelManager(self)
        self._tunnels.changed.connect(self.tunnelsChanged)
        # Split view: a second session shown beside the active one. Stored as a
        # tab index because a split pane is an ordinary session, just displayed
        # at the same time as another.
        self._split = -1
        self._saved_layout: dict | None = None
        self._scan_seq = 0
        self._load_state()
        self._resolve_default_fallback()
        self._refresh_hosts()

    # --------------------------------------------------------------- settings

    def _state_path(self) -> Path:
        return paths.state_file()

    def _load_state(self) -> None:
        try:
            data = json.loads(self._state_path().read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return
        if isinstance(data, dict):
            for key, value in data.items():
                if key in DEFAULT_SETTINGS:
                    self._settings[key] = value
            geometry = data.get("geometry")
            if isinstance(geometry, dict):
                self._settings["_geometry"] = geometry
            # Open tabs and the split are restored separately: they are not
            # settings, and a state file that names an unknown host must still
            # load (the alias is checked against the config on restore).
            layout = data.get("layout")
            if isinstance(layout, dict):
                self._saved_layout = layout
                self._settings["_layout"] = layout

    def _resolve_default_fallback(self) -> None:
        """Point the default fallback at a family that is installed here.

        The default names a Windows family. A state file written on another
        machine, or a fresh install on one without that family, would otherwise
        leave the setting aimed at a font Qt silently resolves to a Latin-only
        face.
        """
        fallback = str(self._settings.get("fontFallback") or "")
        if fallback == DEFAULT_SETTINGS["fontFallback"]:
            self._settings["fontFallback"] = self._default_fallback()

    def _save_state(self) -> None:
        data = dict(self._settings)
        # The layout describes open tabs, so it is only overwritten while
        # there are some: saving a setting before restoring must not erase the
        # list that restore would have used.
        if self._tabs:
            data["layout"] = self._current_layout()
            self._saved_layout = data["layout"]
        elif self._saved_layout is not None:
            data["layout"] = self._saved_layout
        data.pop("_layout", None)
        try:
            self._state_path().parent.mkdir(parents=True, exist_ok=True)
            self._state_path().write_text(
                json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        except OSError:
            pass

    def _current_layout(self) -> dict:
        """The tabs to reopen: hosts in order, which one was active, the split."""
        return {
            "tabs": [tab.host for tab in self._tabs],
            "active": self._active,
            "split": self._split,
        }

    def _get_can_restore(self) -> bool:
        return bool(getattr(self, "_saved_layout", None))

    canRestore = Property(bool, _get_can_restore, notify=tabsChanged)

    @Slot(result="QVariantMap")
    def restoreLayout(self) -> dict:
        """Reopen the tabs recorded in the last session.

        Hosts are checked against the current config: a tab whose host was
        deleted is skipped instead of opening a failing session. Nothing is
        opened automatically — restoring is an explicit choice, because a
        GUI that dials out on start is surprising on a metered connection.
        """
        layout = getattr(self, "_saved_layout", None) or {}
        aliases = [str(a) for a in layout.get("tabs", []) if isinstance(a, str)]
        opened = 0
        for alias in aliases:
            if self._store.host(alias) is None:
                continue
            if self.openHost(alias) >= 0:
                opened += 1
        if opened == 0:
            return {"ok": False, "error": "No saved session could be restored."}
        active = int(layout.get("active", 0) or 0)
        if 0 <= active < len(self._tabs):
            self._active = active
        split = int(layout.get("split", -1) if layout.get("split") is not None else -1)
        if 0 <= split < len(self._tabs) and split != self._active:
            self._split = split
        self._saved_layout = None
        self._settings.pop("_layout", None)
        self._save_state()
        self.tabsChanged.emit()
        self.activeTabChanged.emit()
        self.layoutChanged.emit()
        return {"ok": True, "opened": opened}

    def _get_settings(self) -> dict:
        return self._settings

    settings = Property("QVariantMap", _get_settings, notify=settingsChanged)

    @Slot(str, "QVariant")
    def setSetting(self, key: str, value) -> None:
        if self._settings.get(key) == value:
            return
        self._settings[key] = value
        self._save_state()
        self.settingsChanged.emit()
        if key in ("fontFamily", "fontSize", "fontFallback"):
            for tab in self._tabs:
                tab.model.setFont(self._settings["fontFamily"],
                                  int(self._settings["fontSize"]),
                                  str(self._settings.get("fontFallback") or ""))
        if key == "copyOnSelect":
            for tab in self._tabs:
                tab.model.setCopyOnSelect(value is not False)
        if key in ("theme", "themeFamily", "seedColor", "terminalTheme"):
            self.terminalColorsChanged.emit()
            self.refreshTerminalThemes()

    # --------------------------------------------------------------- snippets

    def _get_snippets(self) -> list:
        return [dict(item) for item in self._settings.get("snippets", [])]

    snippets = Property("QVariantList", _get_snippets, notify=settingsChanged)

    @Slot("QVariantMap", result="QVariantMap")
    def saveSnippet(self, fields: dict) -> dict:
        """Add or replace a snippet, keyed by its old name when renaming."""
        name = str(fields.get("name", "")).strip()
        command = str(fields.get("command", "")).strip()
        original = str(fields.get("originalName", "") or "").strip()
        if not name:
            return {"ok": False, "error": "A name is required"}
        if not command:
            return {"ok": False, "error": "A command is required"}

        items = [dict(item) for item in self._settings.get("snippets", [])]
        index = next((i for i, item in enumerate(items)
                      if str(item.get("name")) == (original or name)), -1)
        entry = {"name": name, "command": command}
        if index >= 0:
            items[index] = entry
        else:
            items.append(entry)
        self._settings["snippets"] = items
        self._save_state()
        self.settingsChanged.emit()
        return {"ok": True, "name": name}

    @Slot(str, result="QVariantMap")
    def deleteSnippet(self, name: str) -> dict:
        items = [dict(item) for item in self._settings.get("snippets", [])]
        kept = [item for item in items if str(item.get("name")) != name]
        if len(kept) == len(items):
            return {"ok": False, "error": "No such snippet"}
        self._settings["snippets"] = kept
        self._save_state()
        self.settingsChanged.emit()
        return {"ok": True}

    @Slot(str, str)
    def runSnippet(self, name: str, command: str = "") -> None:
        """Type a snippet into the active session, or queue it if none is up.

        A snippet is ordinary typed input, so a command that reads stdin or
        starts a full-screen program behaves normally.
        """
        text = command or next(
            (str(item.get("command", "")) for item in
             self._settings.get("snippets", []) if str(item.get("name")) == name), "")
        if not text:
            self.toast.emit("That snippet has no command")
            return
        if 0 <= self._active < len(self._tabs):
            tab = self._tabs[self._active]
            if tab.pending_commands:
                tab.pending_commands.append(text)
            else:
                tab.model.runCommand(text)
            return
        self.toast.emit("Open a session first")

    def imageProvider(self) -> TerminalImageProvider:
        """Provider the QML engine must register as ``image://terminal``."""
        return self._images

    # ------------------------------------------------------------------ hosts

    @Slot()
    def refreshHosts(self) -> None:
        self._store.reload()
        self._refresh_hosts()

    def _refresh_hosts(self) -> None:
        entries = self._store.hosts()
        self._hosts = [
            {
                "alias": e.alias,
                "hostname": e.hostname,
                "port": e.port,
                "user": e.user,
                "identityFile": e.identity_file,
                "proxyJump": e.proxy_jump,
                "proxyCommand": e.proxy_command,
                "groups": e.group_labels,
                "hasPassword": e.has_password,
                "passwordSource": e.password_source,
                "startupCommand": e.startup_command,
                "source": e.source,
            }
            for e in entries
        ]
        self._groups = all_groups(entries)
        self.hostsChanged.emit()
        self.groupsChanged.emit()

    def _get_hosts(self) -> list:
        return self._hosts

    hosts = Property("QVariantList", _get_hosts, notify=hostsChanged)

    def _get_groups(self) -> list:
        return self._groups

    groups = Property("QVariantList", _get_groups, notify=groupsChanged)

    @Slot(str, result="QVariantMap")
    def host(self, alias: str) -> dict:
        for entry in self._hosts:
            if entry["alias"] == alias:
                return entry
        return {}

    @Slot(str, result=str)
    def hostPassword(self, alias: str) -> str:
        """Decoded stored password, for prefilling the editor."""
        return self._store.password(alias) or ""

    @Slot(str, result=str)
    def hostRawBlock(self, alias: str) -> str:
        return self._store.raw_block(alias)

    @Slot("QVariantMap", result="QVariantMap")
    def saveHost(self, fields: dict) -> dict:
        alias = str(fields.get("alias", "")).strip()
        original = str(fields.get("originalAlias", "") or "").strip()
        clean = {
            "alias": alias,
            "hostname": str(fields.get("hostname", "")),
            "port": str(fields.get("port", "")),
            "user": str(fields.get("user", "")),
            "identity_file": str(fields.get("identityFile", "")),
            "proxy_jump": str(fields.get("proxyJump", "")),
            "proxy_command": str(fields.get("proxyCommand", "")),
            "group_labels": _join_groups(fields.get("groups", "")),
        }
        password = fields.get("password", None)
        if password is not None:
            clean["password"] = str(password)
            clean["password_source"] = str(fields.get("password_source", ""))
        if "startup_command" in fields:
            clean["startup_command"] = str(fields.get("startup_command") or "")
        if "forwards" in fields:
            clean["forwards"] = [
                {"kind": str(r.get("kind", "")), "spec": str(r.get("spec", ""))}
                for r in (fields.get("forwards") or [])
                if isinstance(r, dict)
            ]

        try:
            if original:
                saved = self._store.update_host(original, clean)
            else:
                saved = self._store.add_host(clean)
        except (ValueError, OSError) as exc:
            return {"ok": False, "error": str(exc)}

        for tab in self._tabs:
            if tab.host == original:
                tab.host = saved
        self._refresh_hosts()
        return {"ok": True, "alias": saved}

    @Slot(str, result="QVariantMap")
    def deleteHost(self, alias: str) -> dict:
        try:
            self._store.delete_host(alias)
        except (ValueError, OSError) as exc:
            return {"ok": False, "error": str(exc)}
        self._refresh_hosts()
        return {"ok": True}

    @Slot(str, result="QVariantMap")
    def hostForwards(self, alias: str) -> dict:
        """The host's own forwarding rules plus the ones it inherits."""
        return self._store.forward_rules(alias)

    @Slot(str, str, result="QVariantMap")
    def forwardPreview(self, kind: str, spec: str) -> dict:
        """Parse a spec for the editor's inline validation."""
        from .tunnel import parse_forward_spec
        parsed = parse_forward_spec(kind, spec)
        parsed["label"] = format_forward_label(kind, spec)
        return parsed

    @Slot(str, result=str)
    def tunnelCommand(self, alias: str) -> str:
        """The equivalent command line, shown so the rule is not GUI-only."""
        return " ".join(tunnel_argv(alias))

    def _get_tunnels(self) -> list:
        return self._tunnels.tunnels

    tunnels = Property("QVariantList", _get_tunnels, notify=tunnelsChanged)

    def _get_tunnel_count(self) -> int:
        return self._tunnels.count

    tunnelCount = Property(int, _get_tunnel_count, notify=tunnelsChanged)

    def _get_tunnel_active(self) -> bool:
        return bool(self._tunnels.active_keys())

    tunnelActive = Property(bool, _get_tunnel_active, notify=tunnelsChanged)

    def _host_rules(self, alias: str) -> list[dict]:
        """Every rule that applies to a host, inherited ones included."""
        data = self._store.forward_rules(alias)
        if data.get("disabled"):
            return []
        return data.get("own", []) + data.get("inherited", [])

    @Slot(str, bool, result="QVariantMap")
    def startTunnels(self, alias: str, persist: bool = False) -> dict:
        """Enable forwarding for a host.

        While the host has an open session, that session already applies the
        rules from the config; ``tssh -N`` is only spawned once it closes, and
        only if ``persist`` was asked for. Without persistence the forward is
        simply part of the connection.
        """
        rules = self._host_rules(alias)
        if not rules:
            message = f"{alias} has no forwarding rules"
            self.toast.emit(message)
            return {"ok": False, "error": message}
        result = self._tunnels.start(alias, rules, persist=persist,
                                     session_id=self._session_id(alias))
        if not result.get("ok"):
            self.toast.emit(result.get("error") or "Could not start the tunnel")
        return result

    @Slot(str)
    def stopTunnels(self, alias: str) -> None:
        self._tunnels.stop(alias)

    @Slot(str, bool)
    def setTunnelPersist(self, alias: str, persist: bool) -> None:
        self._tunnels.set_persist(alias, persist)

    def _session_id(self, alias: str) -> int:
        for tab in self._tabs:
            if tab.host == alias:
                return tab.id
        return 0

    # --------------------------------------------------------------- transfer

    @Slot(str, result="QVariant")
    def createSftpClient(self, alias: str) -> object:
        """A fresh SFTP client for the transfer window (owned by QML)."""
        client = SftpClient(alias, self)
        client.progressChanged.connect(
            lambda label, fraction, detail, c=client: self._on_transfer_progress(
                c, label, fraction, detail))
        client.operationDone.connect(
            lambda what, ok, message, c=client: self._on_transfer_done(
                c, what, ok, message))
        return client

    def _on_transfer_progress(self, client, label: str, fraction: float,
                              detail: str) -> None:
        entry = self._transfers.get(client)
        if entry is None:
            self._transfer_seq += 1
            entry = {"id": self._transfer_seq, "alias": client.alias,
                     "direction": label, "route": _route(client.alias, label),
                     "fraction": 0.0, "detail": detail,
                     "started": time.time(), "status": "running"}
            self._transfers[client] = entry
        entry["direction"] = label
        entry["fraction"] = float(fraction)
        entry["detail"] = detail
        self.transferProgressChanged.emit()

    def _on_transfer_done(self, client, what: str, ok: bool, message: str) -> None:
        entry = self._transfers.pop(client, None)
        if entry is not None:
            entry["status"] = "done" if ok else "failed"
            entry["fraction"] = 1.0 if ok else entry["fraction"]
            entry["error"] = "" if ok else (message.split("\n")[0] if message else "")
            self._transfer_log.insert(0, entry)
            del self._transfer_log[40:]
            self.transferHistoryChanged.emit()
        self.transferProgressChanged.emit()

    def _get_transfers(self) -> list:
        return [
            {
                "id": t["id"],
                "alias": t["alias"],
                "label": t["direction"],
                "route": t["route"],
                "fraction": max(0.0, min(1.0, t["fraction"])),
                "detail": t["detail"],
            }
            for t in self._transfers.values()
        ]

    transfers = Property("QVariantList", _get_transfers, notify=transferProgressChanged)

    def _get_transfer_active(self) -> bool:
        return bool(self._transfers)

    transferActive = Property(bool, _get_transfer_active, notify=transferProgressChanged)

    def _get_transfer_history(self) -> list:
        return [
            {
                "id": t["id"],
                "alias": t["alias"],
                "label": t["direction"],
                "route": t["route"],
                "status": t["status"],
                "detail": t.get("error") or t["detail"],
                "ago": _ago(t["started"]),
            }
            for t in self._transfer_log
        ]

    transferHistory = Property("QVariantList", _get_transfer_history,
                               notify=transferHistoryChanged)

    def _get_transfer_count(self) -> int:
        return len(self._transfers)

    transferCount = Property(int, _get_transfer_count, notify=transferProgressChanged)

    @Slot(result=str)
    def localHome(self) -> str:
        """Writable starting folder for the local pane.

        Prefers the user profile; falls back to a temp folder when the profile
        is not writable (managed machines, locked-down accounts), because a
        pane that opens somewhere unwritable cannot receive a download.
        """
        candidate = paths.home()
        if paths.is_writable(candidate):
            return str(candidate)
        fallback = paths.transfers_dir()
        try:
            fallback.mkdir(parents=True, exist_ok=True)
        except OSError:
            return str(candidate)
        return str(fallback)

    @Slot("QVariantList", result="QVariantList")
    def localSizes(self, paths_in: list) -> list:
        """Byte sizes for a local selection, so transfers can report a total."""
        from .sftp_client import local_size
        return [local_size(str(p)) for p in paths_in]

    @Slot(str, result="QVariantMap")
    def listLocalResult(self, path: str) -> dict:
        """Like listLocal, but reports *why* a folder is empty.

        Returns ``{ok, path, entries, error, fallback}``. A folder that does
        not exist yet but whose parent is writable counts as usable: the pane
        may navigate into it, and a download creates it on demand. Only a
        folder that is genuinely unreadable triggers ``fallback``.
        """
        target = Path(os.path.expanduser(path)) if path else paths.home()
        entries, error = self._read_dir(target)
        if error is None:
            return {"ok": True, "path": str(target), "entries": entries,
                    "error": "", "fallback": ""}

        if not target.exists() and self._parent_writable(target):
            return {"ok": True, "path": str(target), "entries": [],
                    "error": "", "fallback": ""}

        fallback = self.localHome()
        if str(target) != fallback:
            fallback_entries, fallback_error = self._read_dir(Path(fallback))
            if fallback_error is None:
                return {"ok": True, "path": fallback, "entries": fallback_entries,
                        "error": error, "fallback": fallback}
        return {"ok": False, "path": str(target), "entries": [],
                "error": error, "fallback": fallback}

    @staticmethod
    def _parent_writable(target: Path) -> bool:
        """Whether ``target`` could be created, judged from its nearest ancestor."""
        parent = target.parent
        while str(parent) != str(parent.parent):
            if parent.exists():
                return paths.is_writable(parent)
            parent = parent.parent
        return False

    @staticmethod
    def _read_dir(target: Path) -> tuple[list, str | None]:
        entries = []
        try:
            for item in target.iterdir():
                try:
                    is_dir = item.is_dir()
                    size = 0 if is_dir else item.stat().st_size
                except OSError:
                    is_dir, size = False, 0
                entries.append({
                    "name": item.name,
                    "isDir": is_dir,
                    "path": str(item),
                    "size": size,
                })
        except PermissionError:
            return [], f"Cannot open {target} — permission denied."
        except FileNotFoundError:
            return [], f"{target} does not exist."
        except OSError as exc:
            return [], f"Cannot open {target} — {exc.strerror or exc}."
        entries.sort(key=lambda e: (not e["isDir"], e["name"].lower()))
        return entries, None

    @Slot(str, result=str)
    def parentPath(self, path: str) -> str:
        if not path:
            return self.localHome()
        parent = Path(path).parent
        return str(parent) if str(parent) != path else path

    @Slot(str, result="QVariantMap")
    def duplicateHost(self, alias: str) -> dict:
        try:
            new_alias = self._store.duplicate_host(alias)
        except (ValueError, OSError) as exc:
            return {"ok": False, "error": str(exc)}
        self._refresh_hosts()
        return {"ok": True, "alias": new_alias}

    @Slot(str, str, result="QVariantMap")
    def saveRawBlock(self, alias: str, text: str) -> dict:
        try:
            self._store.replace_raw_block(alias, text)
        except (ValueError, OSError) as exc:
            return {"ok": False, "error": str(exc)}
        self._refresh_hosts()
        return {"ok": True}

    @Slot(str, result="QVariantMap")
    def revealInExplorer(self, alias: str) -> dict:
        entry = self._store.host(alias)
        if entry is None:
            return {"ok": False, "error": "Host not found"}
        return self._reveal(entry.source)

    @Slot(result="QVariantMap")
    def revealConfig(self) -> dict:
        """Open the file manager with the main config file selected.

        Settings names the config path next to an "Open folder" button; this is
        the slot that button calls.
        """
        return self._reveal(str(self._store.main_path))

    @staticmethod
    def _reveal(path: str) -> dict:
        try:
            import subprocess
            subprocess.Popen(["explorer", "/select,", path])
            return {"ok": True}
        except Exception as exc:  # noqa: BLE001 - shown in the UI
            return {"ok": False, "error": str(exc)}

    @Slot(result=str)
    def configPath(self) -> str:
        return str(self._store.main_path)

    @Slot(result="QVariantList")
    def availableFonts(self) -> list:
        from PySide6.QtGui import QFontDatabase
        families = QFontDatabase.families()
        mono = [f for f in families
                if any(k in f.lower() for k in
                       ("mono", "consolas", "courier", "cascadia", "jetbrains", "fira", "hack"))]
        preferred = ["Cascadia Mono", "Cascadia Code", "JetBrains Mono", "Consolas"]
        ordered = [f for f in preferred if f in families]
        for name in sorted(mono, key=str.lower):
            if name not in ordered:
                ordered.append(name)
        return ordered or ["Consolas"]

    @Slot(result="QVariantList")
    def fallbackFonts(self) -> list:
        """Families to offer as the fallback for missing glyphs.

        This list is deliberately *not* restricted to monospace faces: the
        common choice for CJK is a proportional face such as Microsoft YaHei,
        and only the cell width matters for the grid — a fallback glyph is
        centred in its cell box rather than advancing the cursor.

        Only families that actually contain a CJK glyph are listed, so the
        menu cannot offer a font that would not help.
        """
        return _cjk_families()

    @classmethod
    def _default_fallback(cls) -> str:
        """The configured default, or the best CJK family that is installed.

        The default names a Windows family. On a machine without it the
        setting would point at nothing, so fall back to whatever the picker
        puts first; an empty result means "no fallback", which is still better
        than a family Qt silently resolves to a Latin-only face.
        """
        from PySide6.QtGui import QFont, QRawFont

        wanted = DEFAULT_SETTINGS["fontFallback"]
        if QRawFont.fromFont(QFont(wanted)).supportsCharacter("中"):
            return wanted
        offered = _cjk_families()
        return offered[0] if offered else ""

    # ------------------------------------------------------------------- tabs

    def _get_tabs(self) -> list:
        return [
            {
                "index": i,
                "host": tab.host,
                "title": tab.title,
                "state": tab.state,
                "sessionId": tab.id,
                "exitStatus": tab.exit_status if tab.exit_status is not None else -1,
            }
            for i, tab in enumerate(self._tabs)
        ]

    tabs = Property("QVariantList", _get_tabs, notify=tabsChanged)

    def _get_active_index(self) -> int:
        return self._active

    activeIndex = Property(int, _get_active_index, notify=activeTabChanged)

    def _get_has_tabs(self) -> bool:
        return bool(self._tabs)

    hasTabs = Property(bool, _get_has_tabs, notify=tabsChanged)

    @Slot(str, result=int)
    def openHost(self, alias: str) -> int:
        entry = self._store.host(alias)
        if entry is None:
            self.toast.emit(f"Host '{alias}' was not found in ~/.ssh/config")
            return -1

        pty = PtySession()
        model = TerminalModel(Session._next_id)
        self._images.register(model)
        model.setFont(self._settings["fontFamily"], int(self._settings["fontSize"]),
                      str(self._settings.get("fontFallback") or ""))
        model.setCopyOnSelect(self._settings.get("copyOnSelect", True) is not False)
        self._apply_theme_to(model)

        tab = Session(alias, pty, model)
        self._tabs.append(tab)
        index = len(self._tabs) - 1

        model.attachPty(pty)
        model.titleChanged.connect(lambda t=tab: self._on_title(t))
        model.sessionExited.connect(lambda status, t=tab: self._on_exit(t, status))
        pty.failure.connect(lambda message, t=tab: self._on_failure(t, message))
        pty.started.connect(lambda pid, t=tab: self._on_started(t, pid))

        self._active = index
        self.tabsChanged.emit()
        self.activeTabChanged.emit()

        self._settings["lastSession"] = alias
        self._save_state()

        self._open_log(tab)
        self._register_forwards(tab)
        QTimer.singleShot(0, lambda t=tab: self._start(t))
        return index

    # ------------------------------------------------------------------- log

    def _open_log(self, tab: Session) -> None:
        """Append this session's output to a file when logging is enabled.

        The file is opened per session so a log is a session's own record; the
        folder is the app's log directory, next to the state file.
        """
        if not self._settings.get("sessionLog"):
            return
        folder = paths.log_dir()
        try:
            folder.mkdir(parents=True, exist_ok=True)
            stamp = time.strftime("%Y%m%d-%H%M%S")
            path = folder / f"{_safe_name(tab.host)}-{stamp}.log"
            handle = open(path, "a", encoding="utf-8", errors="replace")
        except OSError as exc:
            self.toast.emit(f"Could not start the session log: {exc}")
            return
        tab.log_path = str(path)
        tab.log_file = handle
        try:
            handle.write(f"# LItsshP session {tab.host} started "
                         f"{time.strftime('%Y-%m-%d %H:%M:%S')}\n")
        except OSError:
            pass
        tab.model.attachLog(handle)

    def _close_log(self, tab: Session) -> None:
        if tab.log_file is None:
            return
        try:
            tab.model.detachLog()
        except Exception:
            pass
        try:
            tab.log_file.write(
                f"# session ended {time.strftime('%Y-%m-%d %H:%M:%S')} "
                f"(exit {tab.exit_status})\n")
            tab.log_file.close()
        except OSError:
            pass
        tab.log_file = None

    @Slot(result=str)
    def logsPath(self) -> str:
        return str(paths.log_dir())

    @Slot(result="QVariantMap")
    def revealLogs(self) -> dict:
        folder = paths.log_dir()
        try:
            folder.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            return {"ok": False, "error": str(exc)}
        return self._reveal(str(folder))

    # ------------------------------------------------------------------- keys

    @Slot(result="QVariantList")
    def sshKeys(self) -> list:
        from . import keys
        return keys.list_keys()

    @Slot(str, result=str)
    def keyPathFor(self, name: str) -> str:
        """Where ``generateKey`` will write a key with this file name."""
        from . import keys
        return keys.suggested_path(name)

    @Slot(str, str, str, str, int, result="QVariantMap")
    def generateKey(self, path: str, comment: str, passphrase: str,
                    keyType: str = "ed25519", bits: int = 0) -> dict:
        from . import keys
        result = keys.generate_key(path, comment, passphrase, keyType, bits)
        if result.get("ok"):
            self.toast.emit(f"Created {Path(result['path']).name}")
        return result

    @Slot(str, str, result="QVariantMap")
    def readKey(self, path: str, which: str = "public") -> dict:
        """The key's text, for copying into a server or a service."""
        from . import keys
        target = Path(os.path.expanduser(path))
        if which == "public":
            text = keys.read_public(target)
        else:
            try:
                text = target.read_text(encoding="utf-8", errors="replace")
            except OSError as exc:
                return {"ok": False, "error": str(exc)}
        if not text:
            return {"ok": False, "error": "The key could not be read."}
        return {"ok": True, "text": text}

    @Slot(str, result="QVariantMap")
    def deleteKey(self, path: str) -> dict:
        from . import keys
        result = keys.delete_key(path)
        if result.get("ok"):
            self.toast.emit("Key deleted")
        return result

    @Slot(result="QVariantList")
    def knownHosts(self) -> list:
        from . import keys
        return keys.known_hosts_entries()

    @Slot(str, int)
    def scanHost(self, host: str, port: int = 22) -> None:
        """Start a host-key scan; the result arrives on ``hostScanFinished``.

        ``ssh-keyscan`` waits up to eight seconds per key type, which is far
        too long to hold the GUI thread, so the call returns immediately and
        the sheet renders from the signal.
        """
        target = str(host or "").strip()
        if not target:
            self.hostScanFinished.emit({"ok": False, "error": "Enter a host name"})
            return
        self._scan_seq += 1
        sequence = self._scan_seq
        from . import keys

        def work() -> None:
            result = keys.scan_host(target, int(port) or 22)
            # Emitted from the worker thread: Qt queues it to the GUI thread
            # for an auto connection, which is the same pattern the SFTP
            # client uses. A QTimer.singleShot here would never fire, because
            # this thread has no event loop.
            if sequence == self._scan_seq:
                self.hostScanFinished.emit(result)

        threading.Thread(target=work, daemon=True).start()

    @Slot("QVariantList", result="QVariantMap")
    def trustHost(self, lines: list) -> dict:
        from . import keys
        result = keys.trust_host([str(line) for line in lines])
        if result.get("ok"):
            self.toast.emit(f"Added {result.get('added', 0)} host key(s)")
        return result

    @Slot(str, int, result="QVariantMap")
    def forgetHost(self, host: str, line: int = 0) -> dict:
        """Forget a known-host entry by name, or one hashed row by its line.

        A hashed entry has no readable host name, so the sheet passes the line
        number it listed; a named row is removed by name so every key stored
        for that host goes at once.
        """
        from . import keys
        result = keys.remove_known_hosts(host, line=line or None)
        if result.get("ok"):
            label = host if host and not host.startswith("|1|") else "host key"
            self.toast.emit(f"Forgot {label}")
        return result

    @Slot(str, result="QVariantMap")
    def pushKey(self, alias: str, publicKey: str) -> dict:
        """Install a public key on a host by opening a session and typing it.

        A batch SFTP write cannot append to ``authorized_keys`` reliably (the
        folder may not exist, permissions matter, and the first login still
        needs a password), so this uses the session the user already trusts
        and leaves the prompt visible.
        """
        line = keys_line(public_key)
        if not line:
            return {"ok": False, "error": "No public key to install."}
        if self._store.host(alias) is None:
            return {"ok": False, "error": f"Host '{alias}' was not found."}
        command = (
            'mkdir -p ~/.ssh && chmod 700 ~/.ssh && '
            f'grep -qxF {shell_single(line)} ~/.ssh/authorized_keys 2>/dev/null || '
            f'echo {shell_single(line)} >> ~/.ssh/authorized_keys; '
            'chmod 600 ~/.ssh/authorized_keys; echo "LItsshP: key installed"'
        )
        self._queue_in_session(alias, command)
        return {"ok": True, "command": command}

    def _queue_in_session(self, alias: str, command: str) -> None:
        """Run a command in a tab for ``alias``, opening one if needed.

        A freshly spawned tssh has not logged in yet, so the command waits for
        the session's ``started`` callback rather than being typed into the
        login prompt.
        """
        for tab in self._tabs:
            if tab.host == alias and tab.state == "connected":
                tab.model.runCommand(command)
                return
        index = self.openHost(alias)
        if index < 0:
            return
        tab = self._tabs[index]
        tab.pending_commands.append(command)
        if tab.state == "connected":
            tab.model.runCommand(tab.pending_commands.pop(0))

    def _register_forwards(self, tab: Session) -> None:
        """Note that this session provides its host's forwarding rules.

        The session's own tssh already applies them, so no ``-N`` process is
        spawned. Registering the pairing is what lets the tunnel panel offer
        "keep running" and what ``stop_session`` releases later.
        """
        rules = self._host_rules(tab.host)
        if rules:
            self._tunnels.start(tab.host, rules, persist=False,
                                session_id=tab.id)

    @Slot(int, result="QVariant")
    def terminalModel(self, index: int) -> object:
        """The QML-side model object for a session's terminal."""
        if 0 <= index < len(self._tabs):
            return self._tabs[index].model
        return None

    def _get_active_model(self) -> object:
        """Terminal model of the selected tab, or None.

        Exposed as a notifying property so QML bindings (the command composer)
        re-resolve when tabs open, close or the selection moves. A plain Slot
        would not be re-evaluated, since slots carry no change notification.
        """
        if 0 <= self._active < len(self._tabs):
            return self._tabs[self._active].model
        return None

    activeModel = Property("QVariant", _get_active_model,
                           notify=activeTabChanged)

    def _start(self, tab: Session) -> None:
        if tab not in self._tabs or tab.pty.running:
            return
        cols = max(20, tab.model.columns)
        rows = max(4, tab.model.rows)
        argv = ["tssh"]
        # When the config lives somewhere other than ~/.ssh/config (a test
        # override), tell tssh about it too — otherwise the alias we parsed
        # would be unknown to the process we spawn.
        if os.environ.get("LITSSHP_CONFIG"):
            argv += ["-F", str(paths.ssh_config())]
        # Keep-alive. Only added when the host's config does not already set
        # it: `-o` would override the user's own value, and a host that
        # deliberately sets 0 must stay that way.
        keepalive = int(self._settings.get("keepalive", 0) or 0)
        if keepalive > 0 and not self._store.option(tab.host, "ServerAliveInterval"):
            argv += ["-o", f"ServerAliveInterval={keepalive}"]
        # If a persistent tunnel of ours already holds this host's ports, the
        # session must not try to bind them as well. tssh applies the config's
        # forwarding directives unless told to clear them, and a second bind
        # only produces a warning while the process keeps running.
        if self._tunnels.owns_process(tab.host):
            argv += ["-o", "ClearAllForwardings=yes"]
        argv.append(tab.host)
        if not tab.pty.start(argv, cols=cols, rows=rows):
            tab.state = "failed"
            self.tabsChanged.emit()

    def _apply_theme_to(self, model: TerminalModel) -> None:
        scheme = self._terminal_scheme()
        model.applyTheme(scheme["fg"], scheme["bg"], scheme["cursor"],
                         scheme["selection"], scheme["ansi"])

    @Slot()
    def refreshTerminalThemes(self) -> None:
        for tab in self._tabs:
            self._apply_theme_to(tab.model)

    def _terminal_scheme(self) -> dict:
        from .terminal_theme import build_palette
        return build_palette(self._settings)

    @Slot(int)
    def setActiveIndex(self, index: int) -> None:
        if index == self._active or not (0 <= index < len(self._tabs)):
            return
        self._active = index
        # A split that would duplicate the active session has no purpose.
        if self._split == index:
            self._split = -1
            self.layoutChanged.emit()
        self.activeTabChanged.emit()

    # ------------------------------------------------------------------ split

    def _get_split_index(self) -> int:
        return self._split

    splitIndex = Property(int, _get_split_index, notify=layoutChanged)

    def _get_split_active(self) -> bool:
        return 0 <= self._split < len(self._tabs) and self._split != self._active

    splitActive = Property(bool, _get_split_active, notify=layoutChanged)

    @Slot(int, result=int)
    def splitWith(self, index: int) -> int:
        """Show ``index`` beside the active session.

        Returns the index of the pane that leads the split (the active one), or
        -1 when the request makes no sense: a split needs two different
        sessions, and this deliberately does not open a second one.
        """
        if not (0 <= index < len(self._tabs)) or index == self._active:
            return -1
        self._split = index
        self.layoutChanged.emit()
        return self._active

    @Slot()
    def closeSplit(self) -> None:
        if self._split < 0:
            return
        self._split = -1
        self.layoutChanged.emit()

    @Slot(int)
    def swapSplit(self, which: int) -> None:
        """Make the split's other pane active, keeping both on screen."""
        if not self._get_split_active():
            return
        self._active, self._split = self._split, self._active
        self.layoutChanged.emit()
        self.activeTabChanged.emit()

    @Slot(str, result=int)
    def splitHost(self, alias: str) -> int:
        """Open ``alias`` in a new tab and split it beside the current one."""
        index = self.openHost(alias)
        if index < 0:
            return -1
        # openHost activates the new tab; the previous one becomes the split.
        if len(self._tabs) >= 2:
            self._split = max(0, len(self._tabs) - 2)
            self.layoutChanged.emit()
        return index

    @Slot(str)
    def broadcast(self, text: str) -> None:
        """Type into every pane in the split (and the active tab)."""
        if not text:
            return
        indexes = {self._active}
        if self._get_split_active():
            indexes.add(self._split)
        for index in sorted(indexes):
            if 0 <= index < len(self._tabs):
                self._tabs[index].model.runCommand(text)

    @Slot(int)
    def closeTab(self, index: int) -> None:
        if not (0 <= index < len(self._tabs)):
            return
        tab = self._tabs.pop(index)
        self._cancel_reconnect(tab)
        tab.model.detachPty()
        self._images.unregister(tab.model)
        self._close_log(tab)
        tab.pty.stop()
        tab.pty.deleteLater()
        tab.model.deleteLater()
        # Forwarding belongs to the connection: release what this session was
        # providing, keeping only rules the user marked persistent.
        self._tunnels.stop_session(tab.id)
        # Closing a pane must not leave the split pointing at a stale index.
        if index == self._split:
            self._split = -1
            self.layoutChanged.emit()
        elif self._split > index:
            self._split -= 1
        if self._active >= len(self._tabs):
            self._active = len(self._tabs) - 1
        if self._active < 0 and self._tabs:
            self._active = 0
        self.tabsChanged.emit()
        self.activeTabChanged.emit()

    @Slot()
    def reconnectActive(self) -> None:
        if not (0 <= self._active < len(self._tabs)):
            return
        self._reconnect(self._tabs[self._active])

    def _reconnect(self, tab: Session) -> None:
        if tab.state in ("connected", "connecting"):
            return
        tab.state = "connecting"
        tab.exit_status = None
        tab.suppress_reconnect = False
        tab.pty.stop()
        tab.model.detachPty()
        tab.pty = PtySession()
        tab.pty.failure.connect(lambda message, t=tab: self._on_failure(t, message))
        tab.pty.started.connect(lambda pid, t=tab: self._on_started(t, pid))
        tab.pty.exited.connect(lambda status, t=tab: self._on_exit(t, status))
        tab.model.attachPty(tab.pty)
        self.tabsChanged.emit()
        # A reconnect is a new connection: the forwards come back with it,
        # unless the user kept them alive independently in the meantime.
        self._register_forwards(tab)
        self._start(tab)

    @Slot(int)
    def reconnectTab(self, index: int) -> None:
        if not (0 <= index < len(self._tabs)):
            return
        self._active = index
        self.activeTabChanged.emit()
        self.reconnectActive()

    @Slot(int)
    def duplicateTab(self, index: int) -> None:
        if 0 <= index < len(self._tabs):
            self.openHost(self._tabs[index].host)

    @Slot(int)
    def closeOtherTabs(self, index: int) -> None:
        if not (0 <= index < len(self._tabs)):
            return
        keep = self._tabs[index]
        for tab in list(self._tabs):
            if tab is not keep:
                self.closeTab(self._tabs.index(tab))
        self._active = self._tabs.index(keep) if keep in self._tabs else 0
        self.tabsChanged.emit()
        self.activeTabChanged.emit()

    def _on_title(self, tab: Session) -> None:
        title = tab.model.title.strip()
        if title and title != tab.title:
            tab.title = title
            self.tabsChanged.emit()

    def _on_started(self, tab: Session, pid: int) -> None:
        if tab.state == "connecting":
            tab.state = "connected"
            tab.reconnect_attempts = 0
            self.tabsChanged.emit()
            self._send_startup(tab)

    def _send_startup(self, tab: Session) -> None:
        """Type the host's startup command once the shell has had a moment.

        It is sent as ordinary typing, not as a remote command: that keeps the
        shell's own init files and job control intact, which is what makes a
        command like ``cd /srv/app`` or ``tmux attach`` behave as if typed.
        """
        if tab.pending_commands:
            queue = list(tab.pending_commands)
            tab.pending_commands.clear()
            for index, command in enumerate(queue):
                QTimer.singleShot(700 + index * 250,
                                  lambda t=tab, c=command: t.model.runCommand(c))
        entry = self._store.host(tab.host)
        command = entry.startup_command if entry else ""
        if not command or tab.startup_sent:
            return
        tab.startup_sent = True
        QTimer.singleShot(900, lambda t=tab, c=command: self._run_startup(t, c))

    def _run_startup(self, tab: Session, command: str) -> None:
        if tab not in self._tabs or tab.state != "connected":
            return
        tab.model.runCommand(command, clear_first=False)

    def _on_exit(self, tab: Session, status: int) -> None:
        tab.state = "closed"
        tab.exit_status = status
        self.tabsChanged.emit()
        self._close_log(tab)
        # The process is gone, so the ports it held are free: a persistent
        # rule is taken over here, a normal one ends with the connection.
        self._tunnels.stop_session(tab.id)
        self._schedule_reconnect(tab)

    def _on_failure(self, tab: Session, message: str) -> None:
        tab.state = "failed"
        self.tabsChanged.emit()
        # `_register_forwards` ran before the spawn was attempted; with no
        # process there is nothing providing the rules, so release them.
        self._tunnels.stop_session(tab.id)
        self._close_log(tab)
        self.toast.emit(message)

    # ------------------------------------------------------------- reconnect

    # tssh's own exit codes for a connection that ended by itself. A shell the
    # user exited normally is 0, and a deliberate close never reaches here.
    _DROP_CODES = {205, 255}   # keep-alive timeout, OpenSSH transport error

    def _schedule_reconnect(self, tab: Session) -> None:
        """Restart a session that dropped, with a capped exponential backoff.

        Only a *drop* is retried. A session the user closed, a deliberate
        reconnect, or a shell that exited normally (`exit`) must stay closed —
        reopening those would fight the user.
        """
        if tab.suppress_reconnect or tab not in self._tabs:
            return
        if not self._settings.get("autoReconnect", True):
            return
        if tab.exit_status not in self._DROP_CODES:
            return
        if tab.reconnect_attempts >= 5:
            self.toast.emit(f"{tab.host}: giving up after 5 reconnect attempts")
            return
        delay = min(30, 2 ** tab.reconnect_attempts)
        tab.reconnect_attempts += 1
        timer = QTimer(self)
        timer.setSingleShot(True)
        timer.timeout.connect(lambda t=tab, tm=timer: self._auto_reconnect(t, tm))
        tab.reconnect_timer = timer
        self.toast.emit(f"{tab.host}: connection dropped, retrying in {delay}s")
        timer.start(delay * 1000)

    def _auto_reconnect(self, tab: Session, timer: QTimer) -> None:
        timer.deleteLater()
        tab.reconnect_timer = None
        if tab not in self._tabs or tab.state not in ("closed", "failed"):
            return
        self._reconnect(tab)

    def _cancel_reconnect(self, tab: Session) -> None:
        if tab.reconnect_timer is not None:
            tab.reconnect_timer.stop()
            tab.reconnect_timer.deleteLater()
            tab.reconnect_timer = None
        tab.suppress_reconnect = True

    # ------------------------------------------------------------------ misc

    @Slot()
    def shutdown(self) -> None:
        # Save while the tabs still exist: the layout is what a restore reads,
        # and this is the last moment it is complete.
        self._save_state()
        for tab in self._tabs:
            tab.model.detachPty()
            tab.pty.stop()
        self._tabs.clear()
        # Persistent tunnels are a session-lifetime promise, not a daemon:
        # nothing should keep listening after the window closes.
        self._tunnels.stop_all()


def _route(alias: str, direction: str) -> str:
    """Human-readable path for a transfer: ``A → B`` / ``B → this PC``.

    Uploads read as the remote host pulling from this machine, downloads as
    the host sending to it, so the arrow always points at the destination.
    """
    if direction == "Download":
        return f"{alias} → this PC"
    return f"this PC → {alias}"


def _ago(started: float) -> str:
    delta = max(0.0, time.time() - started)
    if delta < 60:
        return "just now"
    if delta < 3600:
        return f"{int(delta // 60)} min ago"
    if delta < 86400:
        return f"{int(delta // 3600)} h ago"
    return f"{int(delta // 86400)} d ago"


def _join_groups(value) -> str:
    if isinstance(value, (list, tuple)):
        items = [str(v) for v in value]
    else:
        items = str(value or "").replace(",", " ").split()
    seen: list[str] = []
    for item in items:
        item = item.strip()
        if item and item not in seen:
            seen.append(item)
    return " ".join(seen)


def keys_line(public_key: str) -> str:
    """Normalise a public key to ``type blob [comment]`` for authorized_keys."""
    from .keys import authorized_key_line
    return authorized_key_line(public_key)


def _safe_name(alias: str) -> str:
    """A file-name form of a host alias.

    Aliases may contain characters Windows rejects in a name, and a session log
    is named after one, so everything outside a conservative set is replaced.
    """
    cleaned = "".join(ch if (ch.isalnum() or ch in "-_.") else "_" for ch in alias)
    return cleaned.strip("._") or "session"


def shell_single(value: str) -> str:
    """Quote a string for a POSIX shell (single quotes, safe inner quotes)."""
    return "'" + value.replace("'", "'\\''") + "'"


def _cjk_families() -> list:
    """Installed families that contain a CJK glyph, preferred ones first.

    Deliberately not restricted to monospace faces: the usual choice for CJK
    is a proportional face such as Microsoft YaHei, and the grid is defined by
    the primary font — a fallback glyph is centred in its cell box rather than
    advancing the cursor. Families whose name suggests CJK coverage are tested
    before the whole list, because the test loads a font face.
    """
    from PySide6.QtGui import QFont, QFontDatabase, QRawFont

    families = QFontDatabase.families()
    broad = ("yahei", "simsun", "simhei", "song", "ming", "kai", "fang",
             "dengxian", "noto sans", "noto serif", "source han", "sarasa",
             "wenkai", "misans", "harmony", "gothic", "arial unicode")
    candidates = [f for f in families if any(k in f.lower() for k in broad)]
    usable = [name for name in candidates
              if QRawFont.fromFont(QFont(name)).supportsCharacter("中")]
    preferred = ["Microsoft YaHei", "Microsoft YaHei UI", "DengXian",
                 "SimSun", "Noto Sans SC", "LXGW WenKai Mono"]
    ordered = [f for f in preferred if f in usable]
    for name in sorted(usable, key=str.lower):
        if name not in ordered:
            ordered.append(name)
    return ordered
