# Reference

Fact sheets about this repository: how the code is organized, which
guarantees are non-negotiable, and which commands prove a change works. The
[skills](../index.md) are the playbooks; these are the facts they stand
on.

| Sheet | Content |
| --- | --- |
| [Architecture](architecture.md) | module map, the PTY → pyte → image-provider pipeline, QML layer |
| [Invariants](invariants.md) | the guarantees that must survive every change, and where they are enforced |
| [Verification gates](verification.md) | the checks that exist today, exactly as they run |
| [QML API surface](qml-api.md) | everything the QML tree may call on `App`, and the signal each property notifies on |
| [Environment](environment.md) | `LITSSHP_*` overrides, state file, and which binaries are needed |

Every sheet is derived from the code. When a sheet and the code disagree, the
code wins and the sheet gets fixed in the same change.
