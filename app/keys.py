"""SSH key and known_hosts management.

Everything here shells out to the OpenSSH tools (``ssh-keygen``,
``ssh-keyscan``) rather than reimplementing their formats. Fingerprints are
computed locally because that is a stable, documented hash — it lets a list of
keys be shown without spawning a process per row.

Pushing a public key is deliberately *not* an SFTP or batch operation: adding a
line to ``authorized_keys`` needs a shell, and the first login may still ask
for a password. The controller opens an ordinary session tab and types the
command, so the prompt appears in a real terminal instead of a hidden process.
"""

from __future__ import annotations

import base64
import hashlib
import os
import re
import shutil
import subprocess
from pathlib import Path

from . import paths

_PRIVATE_HEADER = "-----BEGIN OPENSSH PRIVATE KEY-----"
_KEY_TYPES = {
    "ssh-ed25519": "ED25519",
    "ssh-rsa": "RSA",
    "ssh-dss": "DSA",
    "ecdsa-sha2-nistp256": "ECDSA",
    "ecdsa-sha2-nistp384": "ECDSA",
    "ecdsa-sha2-nistp521": "ECDSA",
    "sk-ssh-ed25519@openssh.com": "ED25519-SK",
    "sk-ecdsa-sha2-nistp256@openssh.com": "ECDSA-SK",
}
# Files in ~/.ssh that are not keys, even though they have no extension.
_NOT_KEYS = {"config", "known_hosts", "known_hosts.old", "authorized_keys",
             "authorized_keys2", "environment"}
_MAX_SCAN_BYTES = 64 * 1024


def _tool(name: str) -> str | None:
    found = shutil.which(name)
    if found:
        return found
    candidates = [
        Path(os.environ.get("SystemRoot", r"C:\Windows")) / "System32/OpenSSH" / f"{name}.exe",
        Path("C:/Windows/System32/OpenSSH") / f"{name}.exe",
    ]
    for candidate in candidates:
        if candidate.exists():
            return str(candidate)
    return None


def _run(argv: list[str], timeout: float = 20.0) -> tuple[int, str]:
    try:
        proc = subprocess.run(
            argv,
            capture_output=True,
            text=True,
            timeout=timeout,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return 1, str(exc)
    return proc.returncode, (proc.stdout or "") + (proc.stderr or "")


# --------------------------------------------------------------- fingerprints


def _blob_fingerprint(blob_b64: str) -> str:
    """OpenSSH's ``SHA256:...`` fingerprint of a base64 key blob."""
    try:
        raw = base64.b64decode(blob_b64)
    except (ValueError, TypeError):
        return ""
    digest = base64.b64encode(hashlib.sha256(raw).digest()).decode("ascii")
    return "SHA256:" + digest.rstrip("=")


def _blob_type(blob_b64: str) -> str:
    """Key type as stored inside the blob (not the comment)."""
    try:
        raw = base64.b64decode(blob_b64)
    except (ValueError, TypeError):
        return ""
    if len(raw) < 4:
        return ""
    size = int.from_bytes(raw[:4], "big")
    return raw[4:4 + size].decode("ascii", errors="replace")


def _public_parts(line: str) -> tuple[str, str, str] | None:
    """Split ``type base64 comment`` from a public key line."""
    parts = line.strip().split(None, 2)
    if len(parts) < 2:
        return None
    return parts[0], parts[1], (parts[2] if len(parts) > 2 else "")


# ----------------------------------------------------------------------- keys


def _looks_private(path: Path) -> bool:
    try:
        if path.stat().st_size > _MAX_SCAN_BYTES:
            return False
        with open(path, "r", encoding="utf-8", errors="replace") as handle:
            first = handle.readline()
    except OSError:
        return False
    return first.strip() == _PRIVATE_HEADER


def list_keys(folder: Path | None = None) -> list[dict]:
    """Every key pair in ``~/.ssh`` (plus optional subfolders).

    A key is listed if it has a readable ``.pub`` sidecar; a private key with
    no public half is still shown, without a fingerprint, because deleting or
    copying it is exactly what a manager is for.
    """
    root = folder or paths.ssh_dir()
    seen: dict[str, dict] = {}

    candidates: list[Path] = []
    if root.is_dir():
        candidates.extend(sorted(root.iterdir()))
        keys_dir = root / "keys"
        if keys_dir.is_dir():
            candidates.extend(sorted(keys_dir.iterdir()))

    for path in candidates:
        if not path.is_file():
            continue
        if path.suffix == ".pub":
            continue
        if path.parent == root and path.name in _NOT_KEYS:
            continue
        is_private = _looks_private(path)
        pub_path = Path(str(path) + ".pub")
        if not is_private and not pub_path.exists():
            continue
        entry = {
            "name": path.name,
            "path": str(path),
            "publicPath": str(pub_path) if pub_path.exists() else "",
            "private": is_private,
            "type": "",
            "bits": 0,
            "fingerprint": "",
            "comment": "",
            "publicKey": "",
        }
        if pub_path.exists():
            try:
                line = pub_path.read_text(encoding="utf-8", errors="replace").strip()
            except OSError:
                line = ""
            parts = _public_parts(line)
            if parts:
                declared, blob, comment = parts
                kind = _blob_type(blob) or declared
                entry.update(
                    type=_KEY_TYPES.get(kind, kind.replace("ssh-", "").upper()),
                    fingerprint=_blob_fingerprint(blob),
                    comment=comment,
                    publicKey=f"{declared} {blob}",
                    bits=_key_bits(blob),
                )
        seen[entry["path"]] = entry

    # Keys referenced by IdentityFile but stored elsewhere are worth showing:
    # they are the ones a session will actually use.
    try:
        from .config import ConfigStore
        store = ConfigStore()
        for host in store.hosts(include_hidden=True):
            for raw in (host.identity_file or "").replace(",", " ").split():
                target = Path(os.path.expanduser(raw.strip()))
                if str(target) in seen or not target.exists() or not target.is_file():
                    continue
                if target.suffix == ".pub":
                    continue
                pub_path = Path(str(target) + ".pub")
                entry = {
                    "name": target.name,
                    "path": str(target),
                    "publicPath": str(pub_path) if pub_path.exists() else "",
                    "private": _looks_private(target),
                    "type": "", "bits": 0, "fingerprint": "", "comment": "",
                    "publicKey": "",
                    "referencedBy": host.alias,
                }
                if pub_path.exists():
                    try:
                        parts = _public_parts(
                            pub_path.read_text(encoding="utf-8", errors="replace"))
                    except OSError:
                        parts = None
                    if parts:
                        declared, blob, comment = parts
                        kind = _blob_type(blob) or declared
                        entry.update(
                            type=_KEY_TYPES.get(kind, kind.replace("ssh-", "").upper()),
                            fingerprint=_blob_fingerprint(blob),
                            comment=comment,
                            publicKey=f"{declared} {blob}",
                            bits=_key_bits(blob),
                        )
                seen[str(target)] = entry
    except Exception:  # noqa: BLE001 - a broken config must not hide the keys
        pass

    keys = list(seen.values())
    keys.sort(key=lambda k: (not k["private"], k["name"].lower()))
    return keys


def _key_bits(blob_b64: str) -> int:
    """Bits for RSA/DSA keys; 0 for fixed-size types where it is implied."""
    try:
        raw = base64.b64decode(blob_b64)
    except (ValueError, TypeError):
        return 0
    kind = _blob_type(blob_b64)
    offset = 4 + len(kind)
    try:
        if kind == "ssh-rsa":
            size = int.from_bytes(raw[offset:offset + 4], "big")
            offset += 4 + size          # public exponent
            if offset + 4 > len(raw):
                return 0
            size = int.from_bytes(raw[offset:offset + 4], "big")
            return int.from_bytes(raw[offset + 4:offset + 4 + size], "big").bit_length()
        if kind == "ssh-dss":
            return 1024
        if kind == "ssh-ed25519":
            return 256
        if kind.startswith("ecdsa-sha2-nistp"):
            return int(kind.rsplit("nistp", 1)[1])
    except (IndexError, ValueError):
        return 0
    return 0


def generate_key(path: str, comment: str, passphrase: str,
                 key_type: str = "ed25519", bits: int = 0) -> dict:
    """Create a new key pair without prompting.

    ``ssh-keygen`` asks before overwriting an existing file, which a hidden
    process cannot answer; refusing here is both safer and clearer.
    """
    tool = _tool("ssh-keygen")
    if not tool:
        return {"ok": False, "error": "ssh-keygen was not found."}

    target = Path(os.path.expanduser(path.strip()))
    if not str(target):
        return {"ok": False, "error": "A file name is required."}
    if target.exists() or Path(str(target) + ".pub").exists():
        return {"ok": False,
                "error": f"{target.name} already exists — choose another name."}

    try:
        target.parent.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        return {"ok": False, "error": f"Cannot create {target.parent}: {exc}"}

    argv = [tool, "-q", "-t", key_type, "-f", str(target), "-N", passphrase or ""]
    if key_type == "rsa":
        argv += ["-b", str(bits or 4096)]
    if comment:
        argv += ["-C", comment]

    code, output = _run(argv)
    if code != 0 or not target.exists():
        return {"ok": False, "error": output.strip() or "ssh-keygen failed."}

    try:
        os.chmod(target, 0o600)
    except OSError:
        pass
    return {"ok": True, "path": str(target),
            "publicPath": str(target) + ".pub",
            "publicKey": read_public(target)}


def read_public(private_path: str | Path) -> str:
    """The public half of a key, generated from the private one if missing."""
    path = Path(os.path.expanduser(str(private_path)))
    pub = Path(str(path) + ".pub")
    if pub.exists():
        try:
            return pub.read_text(encoding="utf-8", errors="replace").strip()
        except OSError:
            return ""
    tool = _tool("ssh-keygen")
    if not tool or not path.exists():
        return ""
    code, output = _run([tool, "-y", "-f", str(path)])
    if code != 0:
        return ""
    # `ssh-keygen -y` prints only the blob and type; rebuild the usual line.
    parts = output.strip().split()
    if len(parts) < 2:
        return ""
    return f"{parts[0]} {parts[1]} {os.environ.get('USERNAME', '')}@{os.environ.get('COMPUTERNAME', '')}".strip()


def delete_key(path: str) -> dict:
    """Remove a key pair (both halves) after the caller confirmed."""
    target = Path(os.path.expanduser(path))
    removed = []
    for candidate in (target, Path(str(target) + ".pub")):
        if candidate.exists():
            try:
                candidate.unlink()
                removed.append(candidate.name)
            except OSError as exc:
                return {"ok": False, "error": f"Cannot delete {candidate.name}: {exc}"}
    if not removed:
        return {"ok": False, "error": "Nothing to delete."}
    return {"ok": True, "removed": removed}


def authorized_key_line(public_key: str, comment: str = "") -> str:
    """A single ``type blob [comment]`` line, stripped of any leading options."""
    line = (public_key or "").strip()
    if not line:
        return ""
    for prefix in ("ssh-ed25519 ", "ssh-rsa ", "ecdsa-sha2-", "sk-ssh-ed25519@",
                   "sk-ecdsa-sha2-"):
        index = line.find(prefix)
        if index >= 0:
            line = line[index:]
            break
    parts = line.split(None, 2)
    if len(parts) < 2:
        return ""
    return " ".join(parts[:2]) + (f" {comment.strip()}" if comment.strip() else "")


# --------------------------------------------------------------- known_hosts


def _host_field(entry: str) -> tuple[str, bool]:
    """(host text, hashed) for a known_hosts first column."""
    if entry.startswith("|1|"):
        return entry, True
    return entry, False


def known_hosts_entries(path: Path | None = None) -> list[dict]:
    """Parse ``known_hosts`` into rows the UI can show and delete.

    Hashed entries (``HashKnownHosts yes``) cannot be reversed, so they are
    listed with their hashed field and marked; removal still works because
    ``ssh-keygen -R`` understands both forms.
    """
    target = path or (paths.ssh_dir() / "known_hosts")
    entries: list[dict] = []
    try:
        text = target.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return entries

    for number, raw in enumerate(text.splitlines(), start=1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split()
        if len(parts) < 3:
            continue
        hosts, hashed = _host_field(parts[0])
        declared, blob = parts[1], parts[2]
        kind = _blob_type(blob) or declared
        entries.append({
            "line": number,
            "hosts": hosts,
            "hashed": hashed,
            "displayHost": hosts if not hashed else "(hashed)",
            "type": _KEY_TYPES.get(kind, declared),
            "fingerprint": _blob_fingerprint(blob),
            "raw": line,
        })
    return entries


def remove_known_hosts(host: str, path: Path | None = None,
                       line: int | None = None) -> dict:
    """Forget keys stored for ``host``, or the entry on ``line``.

    ``ssh-keygen -R <host>`` matches plain *and* hashed entries — but a hashed
    row cannot be reversed to a host name, so the UI passes the row's line
    number instead and this deletes that line, keeping a ``.old`` backup the
    way the tool does.
    """
    target = path or (paths.ssh_dir() / "known_hosts")
    if not target.exists():
        return {"ok": False, "error": "There is no known_hosts file yet."}

    if line is not None:
        try:
            lines = target.read_text(encoding="utf-8", errors="replace").splitlines(keepends=True)
        except OSError as exc:
            return {"ok": False, "error": str(exc)}
        index = int(line) - 1
        if not (0 <= index < len(lines)):
            return {"ok": False, "error": "That entry is no longer in the file."}
        removed = lines[index].strip()
        try:
            target.with_name(target.name + ".old").write_text(
                "".join(lines), encoding="utf-8")
            del lines[index]
            target.write_text("".join(lines), encoding="utf-8")
        except OSError as exc:
            return {"ok": False, "error": str(exc)}
        return {"ok": True, "message": f"Removed {removed.split()[0]}",
                "removed": True}

    tool = _tool("ssh-keygen")
    if not tool:
        return {"ok": False, "error": "ssh-keygen was not found."}
    code, output = _run([tool, "-R", host, "-f", str(target)])
    # ssh-keygen exits 0 on success and prints either "updated." or
    # "not found in ..."; both mean the requested state holds.
    lowered = output.lower()
    if code != 0:
        return {"ok": False, "error": output.strip() or "ssh-keygen failed."}
    return {"ok": True, "message": output.strip(),
            "removed": "not found" not in lowered}


def scan_host(host: str, port: int = 22) -> dict:
    """Fetch a host's public keys, for the user to compare before trusting."""
    tool = _tool("ssh-keyscan")
    if not tool:
        return {"ok": False, "error": "ssh-keyscan was not found."}
    code, output = _run([tool, "-T", "8", "-p", str(port), host], timeout=15.0)
    entries = []
    for line in output.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split()
        if len(parts) < 3:
            continue
        kind = _blob_type(parts[2]) or parts[1]
        entries.append({
            "hosts": parts[0],
            "type": _KEY_TYPES.get(kind, parts[1]),
            "fingerprint": _blob_fingerprint(parts[2]),
            "raw": line,
        })
    if not entries:
        return {"ok": False,
                "error": output.strip() or f"No keys were returned for {host}."}
    return {"ok": True, "host": host, "port": port, "entries": entries}


def trust_host(lines: list[str], path: Path | None = None) -> dict:
    """Append scanned lines to known_hosts, refusing duplicates."""
    target = path or (paths.ssh_dir() / "known_hosts")
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        existing = set()
        if target.exists():
            existing = {line.strip() for line in
                        target.read_text(encoding="utf-8", errors="replace").splitlines()}
        added = 0
        with open(target, "a", encoding="utf-8") as handle:
            for line in lines:
                clean = line.strip()
                if not clean or clean in existing:
                    continue
                handle.write(clean + "\n")
                existing.add(clean)
                added += 1
    except OSError as exc:
        return {"ok": False, "error": str(exc)}
    return {"ok": True, "added": added}


def ensure_ssh_dir() -> dict:
    """Create ``~/.ssh`` with the permissions ssh expects."""
    folder = paths.ssh_dir()
    try:
        folder.mkdir(parents=True, exist_ok=True)
        os.chmod(folder, 0o700)
    except OSError as exc:
        return {"ok": False, "error": str(exc)}
    return {"ok": True, "path": str(folder)}


def suggested_path(name: str) -> str:
    """A default identity path, defaulting to ``id_ed25519``."""
    clean = re.sub(r"[^A-Za-z0-9._-]+", "-", (name or "").strip()).strip("-")
    return str(paths.ssh_dir() / (clean or "id_ed25519"))


def looks_like_passphrase_protected(path: str) -> bool:
    """Whether ``ssh-keygen -y`` needs a passphrase for this key."""
    tool = _tool("ssh-keygen")
    if not tool or not Path(os.path.expanduser(path)).exists():
        return False
    code, _ = _run([tool, "-y", "-P", "", "-f", os.path.expanduser(path)])
    return code != 0


__all__ = [
    "authorized_key_line", "delete_key", "ensure_ssh_dir", "generate_key",
    "known_hosts_entries", "list_keys", "looks_like_passphrase_protected",
    "read_public", "remove_known_hosts", "scan_host", "suggested_path",
    "trust_host",
]
