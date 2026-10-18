"""QML-facing controller: host list, tabs, settings and terminal sessions."""

from __future__ import annotations

import json
import os
import time
from pathlib import Path

from PySide6.QtCore import Property, QObject, QTimer, Signal, Slot

from . import paths
from .config import ConfigStore, all_groups
from .pty_session import PtySession
from .sftp_client import SftpClient
from .terminal_model import TerminalImageProvider, TerminalModel

DEFAULT_SETTINGS = {
    "fontFamily": "Cascadia Mono",
    "fontSize": 14,
    "theme": "dark",          # dark | light | system
    "seedColor": "#6750a4",
    "sidebarWidth": 268,
    "sidebarVisible": True,
    "confirmClose": True,
    "copyOnSelect": True,
    "composerVisible": True,   # command composer strip under the terminal
    "terminalTheme": "match",  # match | classic
    "lastSession": "",
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
        self._load_state()
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

    def _save_state(self) -> None:
        data = dict(self._settings)
        try:
            self._state_path().parent.mkdir(parents=True, exist_ok=True)
            self._state_path().write_text(
                json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        except OSError:
            pass

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
        if key in ("fontFamily", "fontSize"):
            for tab in self._tabs:
                tab.model.setFont(self._settings["fontFamily"],
                                  int(self._settings["fontSize"]))
        if key == "copyOnSelect":
            for tab in self._tabs:
                tab.model.setCopyOnSelect(value is not False)
        if key in ("theme", "seedColor", "terminalTheme"):
            self.terminalColorsChanged.emit()
            self.refreshTerminalThemes()

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
        model.setFont(self._settings["fontFamily"], int(self._settings["fontSize"]))
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

        QTimer.singleShot(0, lambda t=tab: self._start(t))
        return index

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
        self.activeTabChanged.emit()

    @Slot(int)
    def closeTab(self, index: int) -> None:
        if not (0 <= index < len(self._tabs)):
            return
        tab = self._tabs.pop(index)
        tab.model.detachPty()
        self._images.unregister(tab.model)
        tab.pty.stop()
        tab.pty.deleteLater()
        tab.model.deleteLater()
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
        tab.pty.stop()
        tab.model.detachPty()
        tab.pty = PtySession()
        tab.pty.failure.connect(lambda message, t=tab: self._on_failure(t, message))
        tab.pty.started.connect(lambda pid, t=tab: self._on_started(t, pid))
        tab.pty.exited.connect(lambda status, t=tab: self._on_exit(t, status))
        tab.model.attachPty(tab.pty)
        self.tabsChanged.emit()
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
            self.tabsChanged.emit()

    def _on_exit(self, tab: Session, status: int) -> None:
        tab.state = "closed"
        tab.exit_status = status
        self.tabsChanged.emit()

    def _on_failure(self, tab: Session, message: str) -> None:
        tab.state = "failed"
        self.tabsChanged.emit()
        self.toast.emit(message)

    # ------------------------------------------------------------------ misc

    @Slot()
    def shutdown(self) -> None:
        for tab in self._tabs:
            tab.model.detachPty()
            tab.pty.stop()
        self._tabs.clear()
        self._save_state()


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
