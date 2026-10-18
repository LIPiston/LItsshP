"""Gate: the ~/.ssh/config writer preserves everything it does not edit.

Checks the guarantees the parser is built around, on a throwaway file:

* a UTF-8 BOM and CRLF line endings survive save();
* an unrelated Host block stays byte-identical after another host is edited;
* the edited host gets the new value;
* tssh's encPassword round-trips through the same module tssh uses.

Run with the project virtualenv:

    .venv/Scripts/python docs/skills/reference/config_roundtrip_gate.py
"""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

SCRATCH = Path(tempfile.mkdtemp(prefix="litsshp-config-gate-"))
CONFIG = SCRATCH / ".ssh" / "config"
os.environ["LITSSHP_CONFIG"] = str(CONFIG)
os.environ["LITSSHP_STATE"] = str(SCRATCH / "state.json")

from app.config import ConfigStore  # noqa: E402
from app.secret import decode_secret, encode_secret  # noqa: E402

ORIGINAL = (
    b"\xef\xbb\xbf"
    b"# managed by hand\r\n"
    b"Host alpha\r\n"
    b"    HostName 10.0.0.1\r\n"
    b"    User ops\r\n"
    b"\r\n"
    b"Host beta\r\n"
    b"    HostName 10.0.0.2\r\n"
    b"    # keep this comment\r\n"
)

failures: list[str] = []


def check(name: str, condition: bool, detail: str = "") -> None:
    print(("PASS " if condition else "FAIL ") + name + (f"  [{detail}]" if detail else ""))
    if not condition:
        failures.append(name)


def beta_tail(blob: bytes) -> bytes:
    return blob.split(b"Host beta", 1)[1]


def main() -> int:
    CONFIG.parent.mkdir(parents=True, exist_ok=True)
    CONFIG.write_bytes(ORIGINAL)
    before = CONFIG.read_bytes()

    store = ConfigStore()
    check("hosts parsed", [h.alias for h in store.hosts()] == ["alpha", "beta"],
          str([h.alias for h in store.hosts()]))

    store.update_host("alpha", {
        "alias": "alpha",
        "hostname": "10.0.0.9",
        "port": "22",
        "user": "ops",
        "identity_file": "",
        "proxy_jump": "",
        "proxy_command": "",
        "group_labels": "lab",
    })
    after = CONFIG.read_bytes()

    check("BOM preserved", after.startswith(b"\xef\xbb\xbf"))
    check("CRLF preserved",
          after.count(b"\r\n") > 0 and b"\n" not in after.replace(b"\r\n", b""))
    check("unrelated block byte-identical", beta_tail(after) == beta_tail(before))
    check("edited value written", b"HostName 10.0.0.9" in after)
    check("tssh extension written", b"#!! GroupLabels lab" in after)

    decoded = decode_secret(encode_secret("s3cret"))
    check("encPassword round-trips", decoded == "s3cret")
    # BOM/newline flags live on ConfigFile (per file), not on ConfigStore,
    # which only owns the list of files.
    check("BOM survives a second load", ConfigStore().files[0].bom)

    print()
    if failures:
        print(f"FAIL config round-trip gate ({len(failures)} failing checks)")
        return 1
    print("PASS config round-trip gate")
    return 0


if __name__ == "__main__":
    sys.exit(main())
