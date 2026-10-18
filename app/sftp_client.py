"""SFTP-backed file browser used by the transfer window.

tssh's own transfer path (``--upload-file`` / trzsz ``tsz``) requires trzsz to be
installed on the *remote* host. A file manager that only works after installing
extra binaries on the server is not much use, so the transfer window speaks
plain SFTP through the OpenSSH client instead: it honours the same
``~/.ssh/config`` entry, including ProxyJump, IdentityFile and agent settings.

Two execution paths are used:

* metadata (``pwd``, ``ls``, ``rm``, ``mkdir``, ``rename``) runs in batch mode
  (``sftp -b -``), which produces clean, predictable output;
* file transfers run inside a ConPTY, because sftp only draws its progress
  meter when it owns a terminal. The meter lines are scraped for percentages so
  the UI can show real progress.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import threading
from pathlib import Path

from PySide6.QtCore import QObject, Signal, Slot

from winpty import PTY
from winpty.enums import Backend

from . import paths

_ANSI_RE = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]|\x1b[()][A-Za-z0-9]")
# "name   42%    1.2MB   3.4MB/s   00:03 ETA"
_PROGRESS_RE = re.compile(
    r"^(?P<name>.+?)\s+(?P<pct>\d{1,3})%\s+(?P<amount>[\d.]+)\s*(?P<unit>[KMG]?)B?(?=\s)")
_FAILURE_HINTS = ("failure", "no such file", "not found", "permission denied",
                  "couldn't", "could not", "broken pipe", "connection closed",
                  "connection reset", "not a directory")
_UNITS = {"": 1, "K": 1024, "M": 1024 ** 2, "G": 1024 ** 3}


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


def local_size(path: str) -> int:
    """Total bytes of a local file or directory tree; -1 when unknown."""
    try:
        p = Path(path)
        if p.is_file():
            return p.stat().st_size
        if p.is_dir():
            total = 0
            for root, _dirs, files in os.walk(p):
                for name in files:
                    try:
                        total += (Path(root) / name).stat().st_size
                    except OSError:
                        pass
            return total
    except OSError:
        pass
    return -1


def _human(size: float) -> str:
    for unit, factor in (("GB", 1024 ** 3), ("MB", 1024 ** 2), ("KB", 1024)):
        if size >= factor:
            return f"{size / factor:.1f} {unit}"
    return f"{int(size)} B"


class SftpClient(QObject):
    """Runs sftp operations off the GUI thread."""

    listingReady = Signal(str, "QVariantList")   # path, entries
    operationDone = Signal(str, bool, str)       # description, ok, message
    failed = Signal(str)
    progressChanged = Signal(str, float, str)    # label, fraction (-1 unknown), detail

    def __init__(self, alias: str, parent: QObject | None = None):
        super().__init__(parent)
        self.alias = alias
        self.home = ""
        self._busy = False
        self._cancelled = False
        self._lock = threading.Lock()

    # ------------------------------------------------------------------ helpers

    @Slot()
    def cancel(self) -> None:
        """Stop an in-flight transfer; used when the window closes."""
        self._cancelled = True
        pty = getattr(self, "_transfer_pty", None)
        if pty is not None:
            try:
                pty.write("\x03")
            except Exception:
                pass

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
        """Open the remote pane at ``~``, falling back when it is unusable.

        ``pwd`` is the authoritative answer for "~", but a locked-down account
        can have a home it may not list. Rather than showing an empty pane,
        try the usual candidates and open the first one that actually reads.
        """
        code, out = self._run(["pwd"])
        home = ""
        for line in out.splitlines():
            if "Remote working directory:" in line:
                home = line.split("Remote working directory:", 1)[1].strip()
        if not home:
            home = "~"

        tried = []
        for candidate in (home, "~", "/", "/tmp"):
            if candidate in tried:
                continue
            tried.append(candidate)
            entries = self._try_list(candidate)
            if entries is not None:
                self.home = candidate
                self.listingReady.emit(candidate, entries)
                if candidate != home:
                    self.failed.emit(
                        f"Could not open {home}; showing {candidate} instead.")
                return

        self.home = home
        self.failed.emit(
            f"Could not list the remote home directory ({home}). "
            "The account may lack permission to read it.")

    @Slot(str)
    def listDir(self, path: str) -> None:
        threading.Thread(target=self._list, args=(path, False), daemon=True).start()

    def _try_list(self, path: str) -> list[dict] | None:
        """Parsed entries for ``path``, or None when sftp refused to list it."""
        code, out = self._run(["ls -la " + _quote_remote(path)])
        lowered = out.lower()
        if code != 0 or any(hint in lowered for hint in _FAILURE_HINTS):
            return None
        return self._parse_ls(out)

    def _list(self, path: str, initial: bool) -> None:
        entries = self._try_list(path)
        if entries is None:
            if initial:
                entries = []
            else:
                self.failed.emit(
                    f"Cannot open {path} — permission denied or not a directory.")
                return
        self.listingReady.emit(path, entries)

    @Slot(list, str, "QVariantList")
    def upload(self, local_paths: list, remote_dir: str, sizes: list) -> None:
        threading.Thread(target=self._upload,
                         args=(list(local_paths), remote_dir, list(sizes)),
                         daemon=True).start()

    def _upload(self, local_paths: list[str], remote_dir: str, sizes: list) -> None:
        # -R makes directories transfer recursively and is a no-op for plain
        # files, so selection can mix both without extra stat round-trips.
        lines = ["put -R " + _quote_local(p) + " " + _quote_remote(remote_dir)
                 for p in local_paths]
        self._transfer("Upload", lines, _total(sizes))

    @Slot(list, str, "QVariantList")
    def download(self, remote_paths: list, local_dir: str, sizes: list) -> None:
        threading.Thread(target=self._download,
                         args=(list(remote_paths), local_dir, list(sizes)),
                         daemon=True).start()

    def _download(self, remote_paths: list[str], local_dir: str, sizes: list) -> None:
        # `get ... <dir>` writes into <dir> and refuses to create it, so make
        # sure the destination exists before handing the batch to sftp. If it
        # cannot be created or written to (permissions, read-only share), fall
        # back to the app's temp folder rather than failing the transfer.
        destination = Path(local_dir)
        try:
            destination.mkdir(parents=True, exist_ok=True)
            writable = paths.is_writable(destination)
        except OSError:
            writable = False
        if not writable:
            fallback = paths.transfers_dir()
            try:
                fallback.mkdir(parents=True, exist_ok=True)
            except OSError as exc:
                self.operationDone.emit("Download", False,
                                        f"{local_dir} is not writable: {exc}")
                return
            if not paths.is_writable(fallback):
                self.operationDone.emit(
                    "Download", False,
                    f"{local_dir} is not writable and no fallback folder "
                    "could be created.")
                return
            destination = fallback

        lines = ["get -R " + _quote_remote(p) + " " + _quote_local(str(destination))
                 for p in remote_paths]
        self._transfer("Download", lines, _total(sizes))

    # --------------------------------------------------------------- transfers

    def _transfer(self, label: str, lines: list[str], total: int) -> None:
        binary = find_sftp()
        if not binary:
            self.operationDone.emit(label, False, "sftp was not found.")
            return

        self._cancelled = False
        argv = [binary]
        if os.environ.get("LITSSHP_CONFIG"):
            argv += ["-F", str(paths.ssh_config())]
        argv.append(self.alias)

        env = dict(os.environ)
        env_str = "\0".join(f"{k}={v}" for k, v in env.items()) + "\0"
        try:
            pty = PTY(50, 200, backend=Backend.ConPTY)
            spawned = pty.spawn(argv[0], " " + subprocess.list2cmdline(argv[1:]),
                                cwd=None, env=env_str)
        except Exception as exc:  # noqa: BLE001 - surfaced in the UI
            self.operationDone.emit(label, False, str(exc))
            return
        if not spawned:
            self.operationDone.emit(label, False, "Could not start sftp.")
            return

        self._transfer_pty = pty
        state = _MeterState(label, total, self.progressChanged)
        stop = threading.Event()

        def read_loop() -> None:
            while not stop.is_set() and not self._cancelled:
                try:
                    chunk = pty.read(True)
                except Exception:
                    break
                if not chunk:
                    break
                state.feed(chunk)

        reader = threading.Thread(target=read_loop, daemon=True)
        reader.start()

        # ConPTY buffers typed input, so the whole script can be queued before
        # the server prompt appears.
        script = "\r".join(lines) + "\rbye\r"
        try:
            pty.write(script)
        except Exception as exc:  # noqa: BLE001
            stop.set()
            self.operationDone.emit(label, False, str(exc))
            return

        deadline = 900.0
        waited = 0.0
        while waited < deadline and not self._cancelled:
            try:
                if not pty.isalive():
                    break
            except Exception:
                break
            threading.Event().wait(0.05)
            waited += 0.05

        stop.set()
        if self._cancelled:
            try:
                pty.cancel_io()
            except Exception:
                pass
            self.operationDone.emit(label, False, "Cancelled")
            return

        status = 0
        try:
            status = pty.get_exitstatus() or 0
        except Exception:
            status = 0
        ok = status == 0 and not state.failed
        if ok:
            self.progressChanged.emit(label, 1.0, state.summary())
        self.operationDone.emit(label, ok, state.message(ok))

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


def _total(sizes: list) -> int:
    """Combined size of the selection, or -1 if any part is unknown."""
    total = 0
    for value in sizes:
        try:
            size = int(value)
        except (TypeError, ValueError):
            size = -1
        if size < 0:
            return -1
        total += size
    return total


class _MeterState:
    """Scrapes sftp's progress meter out of a terminal byte stream."""

    def __init__(self, label: str, total: int, signal):
        self.label = label
        self.total = total
        self._signal = signal
        self._buf = ""
        self._log: list[str] = []
        self._done = 0
        self._counted = False
        self._last_pct = 0
        self._last_name = ""
        self._files = 0
        self.failed = False
        self._failure = ""

    def feed(self, chunk: str) -> None:
        self._buf += chunk
        parts = re.split(r"[\r\n]", self._buf)
        self._buf = parts.pop()
        for raw in parts:
            self._line(raw)

    def _line(self, raw: str) -> None:
        line = _ANSI_RE.sub("", raw).strip()
        if not line:
            return
        self._log.append(line)
        if len(self._log) > 200:
            del self._log[:100]

        lowered = line.lower()
        if lowered.startswith(("uploading ", "downloading ")):
            self._files += 1
            self._counted = False
            self._last_pct = 0
            return
        if any(hint in lowered for hint in _FAILURE_HINTS) and "sftp>" not in lowered:
            self.failed = True
            self._failure = line

        match = _PROGRESS_RE.match(line)
        if not match:
            return

        pct = max(0, min(100, int(match.group("pct"))))
        amount = float(match.group("amount")) * _UNITS.get(match.group("unit"), 1)
        self._last_pct = pct
        self._last_name = match.group("name").strip()

        if self.total > 0:
            fraction = (self._done + amount) / self.total
            detail = f"{_human(min(self._done + amount, self.total))} / {_human(self.total)}"
        else:
            fraction = pct / 100.0
            detail = self._last_name

        if pct >= 100 and not self._counted:
            self._done += amount
            self._counted = True
            if self.total > 0:
                fraction = self._done / self.total
                detail = f"{_human(min(self._done, self.total))} / {_human(self.total)}"

        self._signal.emit(self.label, max(0.0, min(1.0, fraction)), detail)

    def summary(self) -> str:
        if self._files:
            return f"{self._files} item{'s' if self._files != 1 else ''}"
        return "done"

    def message(self, ok: bool) -> str:
        if ok:
            return "\n".join(self._log[-3:])
        if self._failure:
            return self._failure
        return "\n".join(self._log[-6:]) or "The transfer did not finish."
