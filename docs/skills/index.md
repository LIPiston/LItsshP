# Skills

Task playbooks for working **on this repository** — for agents and for anyone
making their first change. `reference/` holds the fact sheets they rest on.

New here? Start with the [quick start](quickstart.md).

| Skill | Use when |
|---|---|
| [Quick start](quickstart.md) | first time in the repo: setup, orientation, a safe first change |
| [Fixing defects](fixing-defects.md) | something broke, a test/gate fails, or the UI misbehaves |
| [Terminal rendering](terminal-rendering.md) | touching the screen model, input translation, colours, fonts, scrollback |
| [File transfers](file-transfers.md) | touching the SFTP window, progress reporting or the transfer list |
| [Config and secrets](config-and-secrets.md) | touching `~/.ssh/config` parsing/writing or stored passwords |
| [Testing and verification](testing.md) | running the gates, or adding a new check |
| [Updating documentation](updating-docs.md) | changing the README, these pages, or the reference sheets |

The rules that apply to every task:

- The config file is shared with the tssh CLI. Never invent a second store.
- No Qt object off the GUI thread; no UI behaviour that depends on a QML
  animation or QML `Timer` finishing.
- Verify with the gates in [reference/verification](../skills/reference/verification.md),
  and say plainly what you ran when you report back.

Ground rule: every playbook describes the repo as it is. When reality and a
playbook disagree, fix the playbook in the same change — never work around the
repo to satisfy the doc.
