# Documentation

This directory holds two kinds of material:

- **[skills/](skills/index.md)** — task playbooks for working *on* LItsshP:
  setting up, diagnosing the platform quirks, changing the terminal, the
  transfer window or the config writer, and verifying the result.
- **[skills/reference/](skills/reference/index.md)** — fact sheets the
  playbooks stand on: architecture, invariants, verification gates, the
  QML/controller API surface and the environment overrides.

The user-facing description of the app stays in the top-level README — it is
the only page a person who just wants to use LItsshP needs to read. The
Chinese version is [`README.md`](../README.md) (the default) and the English one
is [`README_en.md`](../README_en.md); each links to the other at the top.

## Where to start

| You want to | Read |
| --- | --- |
| run the app for the first time | [Quick start](skills/quickstart.md) |
| understand how the pieces fit | [Architecture](skills/reference/architecture.md) |
| know what must never break | [Invariants](skills/reference/invariants.md) |
| run the checks before handing off | [Verification gates](skills/reference/verification.md) |
| fix something that is broken | [Fixing defects](skills/fixing-defects.md) |
| touch the terminal renderer | [Terminal rendering](skills/terminal-rendering.md) |
| touch uploads/downloads | [File transfers](skills/file-transfers.md) |
| touch `~/.ssh/config` handling | [Config and secrets](skills/config-and-secrets.md) |
| touch keys, known hosts or the key sheet | [Config and secrets](skills/config-and-secrets.md), then [Invariants](skills/reference/invariants.md) §11–12 |
| change README or these pages | [Updating documentation](skills/updating-docs.md) |

Ground rule: these pages describe the repository as it is. When a page and
the code disagree, the code wins and the page is fixed in the same change.
