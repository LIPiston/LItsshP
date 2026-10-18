# Reference: Environment

LItsshP reads a handful of environment variables, all of which exist so a
scratch configuration can be used without touching the real one.

| Variable | Effect | Default |
| --- | --- | --- |
| `LITSSHP_CONFIG` | path to the OpenSSH/tssh config file | `~/.ssh/config` |
| `LITSSHP_STATE` | path to the UI state file (JSON) | `%APPDATA%\LItsshP\state.json` |
| `LITSSHP_TSSH` | path to the `tssh` executable | found on `PATH`, then WinGet links, `~/.local/bin`, `C:\Program Files\tssh` |
| `LITSSHP_SFTP` | path to the `sftp` executable | found on `PATH`, then `%SystemRoot%\System32\OpenSSH\sftp.exe` |

When `LITSSHP_CONFIG` is set, both the session spawner and the SFTP client also
pass `-F <that file>` to the binaries, so the child processes read the same
configuration the GUI parsed.

## Files and locations

| Path | Owner | Content |
| --- | --- | --- |
| `~/.ssh/config` (+ `Include`s) | tssh / OpenSSH | hosts, credentials, all real configuration |
| `%APPDATA%\LItsshP\state.json` | LItsshP | window geometry and UI preferences only |
| `%TEMP%\LItsshP` | LItsshP | fallback folder for downloads when the chosen destination is unwritable |

`paths.home()` deliberately prefers `USERPROFILE` over `HOME` on Windows,
because a Git Bash session exports `HOME=/c/Users/...`, which is not a valid
Windows path for the spawned processes.

## Required binaries

| Binary | Used for | Failure mode when missing |
| --- | --- | --- |
| Python 3.10+ | the app itself | — |
| `tssh` | every session | tab enters `failed`, toast names `winget install trzsz.tssh` |
| `ssh` | spawned by tssh | tssh reports the error in the terminal |
| `sftp` | transfer window | `sftp was not found. Install the OpenSSH client.` |

`PtySession` resolves `tssh` through `paths.find_tssh()`, so the executable
path is recorded on the session object for diagnostics.

## Python dependencies

From `requirements.txt`: `PySide6>=6.7`, `pyte>=0.8.1`,
`pywinpty>=2.0` (Windows only), `cryptography>=42`, `materialyoucolor>=2.0`.

`materialyoucolor` is what replaces the C++ `StyleManager` in the vendored
component library. There is no compiler step: `third_party/md3` is pure QML
and the two singletons it expects are registered from `app/style.py`.

## Verified toolchain

The combination the app is developed and verified against:

- Windows 11 (build 26300), Python 3.12.13, PySide6 6.12.0
- tssh installed through WinGet (`winget install trzsz.tssh`)
- OpenSSH `ssh`/`sftp` from `C:\Windows\System32\OpenSSH`

Older PySide6 releases are allowed by the requirement but have not been
verified; the rendering workarounds in
[Terminal rendering](../terminal-rendering.md) depend on Qt 6 behaviour that
may differ.
