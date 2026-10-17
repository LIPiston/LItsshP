"""SFTP-backed file browser used by the transfer window.

tssh's own transfer path (``--upload-file`` / trzsz ``tsz``) requires trzsz to be
installed on the *remote* host. A file manager that only works after installing
extra binaries on the server is not much use, so the transfer window speaks
plain SFTP through the OpenSSH client instead: it honours the same
``~/.ssh/config`` entry, including ProxyJump, IdentityFile and agent settings.

The protocol is driven with OpenSSH's batch mode (``sftp -b -``), one command
per line, so no third-party SSH library is needed.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import threading
from pathlib import Path

from PySide6.QtCore import QObject, Signal, Slot

from . import paths


def _quote_remote(value: str) -> str:
    """Quote a remote path for the sftp batch parser."""
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


def _quote_local(value: str) -> str:
    # sftp's batch parser consumes backslashes inside quotes, so a Windows path
    # must reach it with forward slashes or "C:\Users" loses every separator.
    # sftp accepts either form, so normalising is safe.
    normalized = value.replace("\\", "/")
    return '"' + normalized.replace('"', '\\"') + '"'


def find_sftp() -> str | None:
    override = os.environ.get("LITSSHP_SFTP")
    if override and Path(override).exists():
        return override

    found = shutil.which("sftp")
    if found:
        return found

    candidates = [
        Path(os.environ.get("SystemRoot", r"C:\Windows")) / "System32/OpenSSH/sftp.exe",
        Path("C:/Windows/System32/OpenSSH/sftp.exe"),
        Path("C:/Program Files/OpenSSH/sftp.exe"),
    ]
    for candidate in candidates:
        if candidate.exists():
            return str(candidate)
    return None


class SftpClient(QObject):
    """Runs sftp batch commands off the GUI thread."""

    listingReady = Signal(str, "QVariantList")   # path, entries
    operationDone = Signal(str, bool, str)       # description, ok, message
    failed = Signal(str)

    def __init__(self, alias: str, parent: QObject | None = None):
        super().__init__(parent)
        self.alias = alias
        self.home = ""
        self._busy = False

    # ------------------------------------------------------------------ helpers

    def _command(self) -> list[str] | None:
        binary = find_sftp()
        if not binary:
            self.failed.emit("sftp was not found. Install the OpenSSH client.")
            return None
        argv = [binary]
        if os.environ.get("LITSSHP_CONFIG"):
            argv += ["-F", str(paths.ssh_config())]
        argv += ["-b", "-", self.alias]
        return argv

    def _run(self, lines: list[str], timeout: float = 60.0) -> tuple[int, str]:
        argv = self._command()
        if argv is None:
            return 1, ""
        script = "\n".join(lines) + "\nbye\n"
        try:
            proc = subprocess.run(
                argv,
                input=script,
                capture_output=True,
                text=True,
                timeout=timeout,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
        except subprocess.TimeoutExpired:
            return 1, "Timed out talking to the server."
        except OSError as exc:
            return 1, str(exc)
        output = (proc.stdout or "") + (proc.stderr or "")
        return proc.returncode, output

    @staticmethod
    def _parse_ls(output: str) -> list[dict]:
        """Turn ``ls -l`` output into entries.

        sftp's long format is close enough to POSIX ls -l: permissions, links,
        owner, group, size, month, day, time-or-year, name.
        """
        entries: list[dict] = []
        for raw in output.splitlines():
            line = raw.strip()
            if not line or line.startswith("sftp>"):
                continue
            if line.startswith("Remote working directory:"):
                continue
            parts = line.split(maxsplit=8)
            if len(parts) < 9 or len(parts[0]) < 10:
                continue
            perms = parts[0]
            if perms[0] not in "-dlbcps":
                continue
            name = parts[8]
            if name in (".", ".."):
                continue
            is_dir = perms[0] == "d"
            is_link = perms[0] == "l"
            if is_link and " -> " in name:
                name = name.split(" -> ", 1)[0]
            try:
                size = int(parts[4])
            except ValueError:
                size = 0
            entries.append({
                "name": name,
                "isDir": is_dir,
                "isLink": is_link,
                "size": size,
                "mode": perms,
                "modified": " ".join(parts[5:8]),
            })
        entries.sort(key=lambda e: (not e["isDir"], e["name"].lower()))
        return entries

    # ------------------------------------------------------------------ actions

    @Slot()
    def start(self) -> None:
        """Resolve the remote home directory, then list it."""
        threading.Thread(target=self._initial, daemon=True).start()

    def _initial(self) -> None:
        code, out = self._run(["pwd"])
        home = ""
        for line in out.splitlines():
            if "Remote working directory:" in line:
                home = line.split("Remote working directory:", 1)[1].strip()
        if not home:
            home = "/"
        self.home = home
        self._list(home, initial=True)

    @Slot(str)
    def listDir(self, path: str) -> None:
        threading.Thread(target=self._list, args=(path, False), daemon=True).start()

    def _list(self, path: str, initial: bool) -> None:
        code, out = self._run(["ls -la " + _quote_remote(path)])
        if code != 0 and not initial:
            self.failed.emit(out.strip() or "Could not list the directory.")
            return
        self.listingReady.emit(path, self._parse_ls(out))

    @Slot(list, str)
    def upload(self, local_paths: list, remote_dir: str) -> None:
        threading.Thread(target=self._upload, args=(list(local_paths), remote_dir),
                         daemon=True).start()

    def _upload(self, local_paths: list[str], remote_dir: str) -> None:
        # -R makes directories transfer recursively and is a no-op for plain
        # files, so selection can mix both without extra stat round-trips.
        lines = ["put -R " + _quote_local(p) + " " + _quote_remote(remote_dir)
                 for p in local_paths]
        code, out = self._run(lines, timeout=600.0)
        lowered = out.lower()
        ok = code == 0 and "not found" not in lowered and "no such file" not in lowered
        self.operationDone.emit("Upload", ok, out.strip())

    @Slot(list, str)
    def download(self, remote_paths: list, local_dir: str) -> None:
        threading.Thread(target=self._download, args=(list(remote_paths), local_dir),
                         daemon=True).start()

    def _download(self, remote_paths: list[str], local_dir: str) -> None:
        # `get ... <dir>` writes into <dir> and refuses to create it, so make
        # sure the destination exists before handing the batch to sftp.
        try:
            Path(local_dir).mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            self.operationDone.emit("Download", False, str(exc))
            return
        lines = ["get -R " + _quote_remote(p) + " " + _quote_local(local_dir)
                 for p in remote_paths]
        code, out = self._run(lines, timeout=600.0)
        lowered = out.lower()
        ok = code == 0 and "not found" not in lowered and "no such file" not in lowered
        self.operationDone.emit("Download", ok, out.strip())

    @Slot(list)
    def remove(self, remote_paths: list) -> None:
        threading.Thread(target=self._remove, args=(list(remote_paths),),
                         daemon=True).start()

    def _remove(self, remote_paths: list[str]) -> None:
        lines = ["rm " + _quote_remote(p) for p in remote_paths]
        code, out = self._run(lines)
        self.operationDone.emit("Delete", code == 0, out.strip())

    @Slot(str)
    def mkdir(self, remote_path: str) -> None:
        threading.Thread(target=self._mkdir, args=(remote_path,), daemon=True).start()

    def _mkdir(self, remote_path: str) -> None:
        code, out = self._run(["mkdir " + _quote_remote(remote_path)])
        self.operationDone.emit("Create folder", code == 0, out.strip())

    @Slot(str, str)
    def rename(self, old_path: str, new_path: str) -> None:
        threading.Thread(target=self._rename, args=(old_path, new_path),
                         daemon=True).start()

    def _rename(self, old_path: str, new_path: str) -> None:
        code, out = self._run(
            ["rename " + _quote_remote(old_path) + " " + _quote_remote(new_path)])
        self.operationDone.emit("Rename", code == 0, out.strip())
