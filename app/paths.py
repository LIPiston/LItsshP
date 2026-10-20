"""Filesystem locations used by LItsshP.

Sessions live in the same place tssh reads them from: ``~/.ssh/config``.
The app's own state (window geometry, UI preferences) is kept separately so
nothing but hosts ever touches the tssh configuration.
"""

from __future__ import annotations

import os
import shutil
import tempfile
from pathlib import Path


def home() -> Path:
    """The user's home directory, independent of the launching shell.

    ``os.path.expanduser`` prefers ``HOME``, which is wrong when the app is
    started from a POSIX-style shell (Git Bash sets ``HOME=/c/Users/...``).
    On Windows the profile directory is the authoritative answer, so use it
    and fall back to ``expanduser`` elsewhere.
    """
    if os.name == "nt":
        profile = os.environ.get("USERPROFILE")
        if profile:
            path = Path(profile)
            if path.is_dir():
                return path
    expanded = Path(os.path.expanduser("~"))
    return expanded if expanded.is_dir() else Path.home()


def transfers_dir() -> Path:
    """A guaranteed-writable folder for files the transfer window touches.

    Used when the home directory or a chosen destination is not writable, so
    a permissions problem degrades to a working folder instead of an empty
    pane or a failed transfer.
    """
    return Path(tempfile.gettempdir()) / "LItsshP"


def is_writable(path: Path) -> bool:
    """Whether ``path`` exists and can be created into / written to."""
    try:
        probe = path / ".litsshp-write-test"
        with open(probe, "wb"):
            pass
        probe.unlink()
        return True
    except OSError:
        return False


def ssh_dir() -> Path:
    return home() / ".ssh"


def ssh_config() -> Path:
    """The main OpenSSH/tssh config file.

    ``LITSSHP_CONFIG`` overrides the location, which is useful for testing
    against a scratch config without touching the real one.
    """
    override = os.environ.get("LITSSHP_CONFIG")
    if override:
        return Path(os.path.expanduser(override))
    return ssh_dir() / "config"


def state_dir() -> Path:
    override = os.environ.get("LITSSHP_STATE")
    if override:
        return Path(os.path.expanduser(override)).parent
    base = os.environ.get("APPDATA") or os.environ.get("XDG_CONFIG_HOME")
    if base:
        return Path(base) / "LItsshP"
    return home() / ".litsshp"


def state_file() -> Path:
    override = os.environ.get("LITSSHP_STATE")
    if override:
        return Path(os.path.expanduser(override))
    return state_dir() / "state.json"


def log_dir() -> Path:
    """Where session logs are written when logging is enabled."""
    override = os.environ.get("LITSSHP_LOGS")
    if override:
        return Path(os.path.expanduser(override))
    return state_dir() / "logs"


def themes_dir() -> Path:
    """User-editable theme catalog.

    Deliberately under the application data directory and never under
    ``~/.ssh``: themes are UI preferences, and the SSH directory is reserved
    for files the ssh tools themselves read.
    """
    return state_dir() / "themes"


def find_tssh() -> str | None:
    """Locate the tssh executable, preferring a user-local install."""
    override = os.environ.get("LITSSHP_TSSH")
    if override and Path(override).exists():
        return override

    found = shutil.which("tssh")
    if found:
        return found

    candidates = [
        Path(os.environ.get("LOCALAPPDATA", "")) / "Microsoft/WinGet/Links/tssh.exe",
        home() / "AppData/Local/Microsoft/WinGet/Links/tssh.exe",
        home() / ".local/bin/tssh.exe",
        Path("C:/Program Files/tssh/tssh.exe"),
    ]
    for candidate in candidates:
        if candidate.exists():
            return str(candidate)
    return None


def shell_quote(value: str) -> str:
    """Quote a value for the ConPTY command line (Windows rules)."""
    if not value:
        return '""'
    if not any(ch in value for ch in ' \t"'):
        return value
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'
