"""Filesystem locations used by LItsshP.

Sessions live in the same place tssh reads them from: ``~/.ssh/config``.
The app's own state (window geometry, UI preferences) is kept separately so
nothing but hosts ever touches the tssh configuration.
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path


def home() -> Path:
    return Path(os.path.expanduser("~"))


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
