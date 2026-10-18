"""Gate: forwarding rules survive a round trip and stay scoped to one block.

Checks the guarantees the forwarding editor relies on, on a throwaway file:

* an accumulating directive (multiple ``LocalForward`` lines) is read as a
  list, not collapsed to the first value;
* editing replaces lines positionally, so comments between them survive;
* removing a rule deletes only that directive line;
* an unrelated Host block stays byte-identical;
* BOM and CRLF survive;
* rules inherited from ``Host *`` are reported separately and are not
  rewritten;
* ``ClearAllForwardings yes`` is reported as disabling the host's rules;
* the forwarding spec parser accepts IPv4, IPv6, dynamic and bind forms and
  rejects malformed ones.

Run with the project virtualenv:

    .venv/Scripts/python docs/skills/reference/forward_roundtrip_gate.py
"""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

SCRATCH = Path(tempfile.mkdtemp(prefix="litsshp-forward-gate-"))
CONFIG = SCRATCH / ".ssh" / "config"
os.environ["LITSSHP_CONFIG"] = str(CONFIG)
os.environ["LITSSHP_STATE"] = str(SCRATCH / "state.json")

from app.config import ConfigStore  # noqa: E402
from app.tunnel import format_forward_label, parse_forward_spec  # noqa: E402

ORIGINAL = (
    b"\xef\xbb\xbf"
    b"# forwarding test\r\n"
    b"Host alpha\r\n"
    b"    HostName 10.0.0.1\r\n"
    b"    LocalForward 8080 localhost:80\r\n"
    b"    # keep this comment\r\n"
    b"    LocalForward 8443 localhost:443\r\n"
    b"    DynamicForward 1080\r\n"
    b"    RemoteForward 9090 localhost:3000\r\n"
    b"\r\n"
    b"Host beta\r\n"
    b"    HostName 10.0.0.2\r\n"
    b"\r\n"
    b"Host *\r\n"
    b"    LocalForward 5000 localhost:5000\r\n"
)

failures: list[str] = []


def check(name: str, condition: bool, detail: str = "") -> None:
    print(("PASS " if condition else "FAIL ") + name + (f"  [{detail}]" if detail else ""))
    if not condition:
        failures.append(name)


def alpha_block(blob: bytes) -> bytes:
    return blob.split(b"Host alpha", 1)[1].split(b"Host beta", 1)[0]


def beta_tail(blob: bytes) -> bytes:
    return blob.split(b"Host beta", 1)[-1]


def main() -> int:
    CONFIG.parent.mkdir(parents=True, exist_ok=True)
    CONFIG.write_bytes(ORIGINAL)

    store = ConfigStore()
    rules = store.forward_rules("alpha")
    own = [(r["kind"], r["spec"]) for r in rules["own"]]
    inherited = [(r["kind"], r["spec"]) for r in rules["inherited"]]

    # Rules come back grouped by directive (Local, Remote, Dynamic) rather
    # than in file order, because that is the order the editor writes them
    # back in. Read and write agreeing is what keeps a save from reordering
    # the file behind the user's back.
    check("own rules read in full", own == [
        ("L", "8080 localhost:80"),
        ("L", "8443 localhost:443"),
        ("R", "9090 localhost:3000"),
        ("D", "1080"),
    ], str(own))
    check("inherited rule attributed to Host *",
          inherited == [("L", "5000 localhost:5000")], str(inherited))
    check("wildcard rule not duplicated into own", len(own) == 4, str(own))
    check("not disabled without ClearAllForwardings", rules["disabled"] is False)

    before = CONFIG.read_bytes()

    # Rewrite: keep one local rule, change it, drop the second, keep the rest.
    store.update_host("alpha", {
        "alias": "alpha",
        "hostname": "10.0.0.1",
        "port": "22",
        "user": "",
        "identity_file": "",
        "proxy_jump": "",
        "proxy_command": "",
        "group_labels": "",
        "forwards": [
            {"kind": "L", "spec": "8080 localhost:8080"},
            {"kind": "D", "spec": "1080"},
            {"kind": "R", "spec": "9090 localhost:3000"},
        ],
    })
    after = CONFIG.read_bytes()
    block = alpha_block(after)

    check("BOM preserved", after.startswith(b"\xef\xbb\xbf"))
    check("CRLF preserved",
          after.count(b"\r\n") > 0 and b"\n" not in after.replace(b"\r\n", b""))
    check("unrelated block byte-identical", beta_tail(after) == beta_tail(before),
          "beta or Host * changed")
    check("edited rule rewritten in place",
          b"LocalForward 8080 localhost:8080" in block)
    check("comment between directives preserved",
          b"# keep this comment" in block)
    check("removed rule is gone", b"8443" not in block)
    check("wildcard rule left untouched",
          b"LocalForward 5000 localhost:5000" in after)
    check("indentation preserved", b"    LocalForward 8080 localhost:8080" in block)

    reloaded = ConfigStore().forward_rules("alpha")
    check("re-read matches what was written",
          [(r["kind"], r["spec"]) for r in reloaded["own"]] == [
              ("L", "8080 localhost:8080"),
              ("R", "9090 localhost:3000"),
              ("D", "1080"),
          ], str(reloaded["own"]))

    # Clearing every rule removes only directive lines.
    store.update_host("alpha", {
        "alias": "alpha", "hostname": "10.0.0.1", "port": "22", "user": "",
        "identity_file": "", "proxy_jump": "", "proxy_command": "",
        "group_labels": "", "forwards": [],
    })
    cleared = CONFIG.read_bytes()
    cleared_block = alpha_block(cleared)
    check("all own directives removed",
          b"LocalForward" not in cleared_block
          and b"DynamicForward" not in cleared_block
          and b"RemoteForward" not in cleared_block, cleared_block.decode("utf-8", "replace"))
    check("comment survives clearing", b"# keep this comment" in cleared_block)
    check("inherited directive still present",
          b"LocalForward 5000 localhost:5000" in cleared)

    # ClearAllForwardings disables the host.
    store = ConfigStore()
    cfg = store.files[0]
    block_obj = [b for b in cfg.blocks
                 if b.kind == "host" and "alpha" in b.aliases][0]
    cfg.set_option(block_obj, "ClearAllForwardings", "yes")
    cfg.save()
    store.reload()
    check("ClearAllForwardings reported",
          ConfigStore().forward_rules("alpha")["disabled"] is True)

    # Spec parsing.
    parsed = parse_forward_spec("L", "8080:localhost:80")
    check("IPv4 spec parsed",
          parsed["valid"] and parsed["port"] == 8080
          and parsed["target_host"] == "localhost"
          and parsed["target_port"] == 80, str(parsed))

    parsed = parse_forward_spec("L", "[::1]:9000:[::1]:80")
    check("IPv6 spec parsed",
          parsed["valid"] and parsed["bind"] == "::1" and parsed["port"] == 9000,
          str(parsed))

    parsed = parse_forward_spec("D", "1080")
    check("dynamic spec parsed",
          parsed["valid"] and parsed["port"] == 1080 and parsed["bind"] == "127.0.0.1",
          str(parsed))

    parsed = parse_forward_spec("L", "127.0.0.1:8080:db.internal:5432")
    check("bind address kept",
          parsed["valid"] and parsed["bind"] == "127.0.0.1"
          and parsed["target_host"] == "db.internal", str(parsed))

    for bad in ("", "8080", "8080:localhost", "8080:localhost:notaport",
                "99999:localhost:80", "1:2:3:4:5"):
        parsed = parse_forward_spec("L", bad)
        check(f"rejects {bad!r}", not parsed["valid"], parsed["error"])

    check("label formats IPv4",
          format_forward_label("L", "8080:localhost:80")
          == "127.0.0.1:8080 → localhost:80",
          format_forward_label("L", "8080:localhost:80"))
    check("label formats IPv6",
          format_forward_label("L", "[::1]:9000:[::1]:80")
          == "[::1]:9000 → [::1]:80",
          format_forward_label("L", "[::1]:9000:[::1]:80"))

    print()
    if failures:
        print(f"FAIL forward round-trip gate ({len(failures)} failing checks)")
        return 1
    print("PASS forward round-trip gate")
    return 0


if __name__ == "__main__":
    sys.exit(main())
