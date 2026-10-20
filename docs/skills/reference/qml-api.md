# Reference: QML API surface

Everything the QML tree may call on `App` — the `AppController` registered as
the `App` context property in `app/main.py`. If a name is not here, QML must
not use it.

## Properties (all notifying)

QML bindings only re-evaluate if the property carries `notify=`. Slots never
do; binding to a slot is a bug (it caches the first result forever).

| Property | Type | Notifies on | Content |
| --- | --- | --- | --- |
| `hosts` | `QVariantList` | `hostsChanged` | one map per concrete `Host`, effective values resolved; includes `hasPassword`, `passwordSource`, `startupCommand`, `source` |
| `groups` | `QVariantList` | `groupsChanged` | sorted union of all `#!! GroupLabels` |
| `tabs` | `QVariantList` | `tabsChanged` | `{index, host, title, state, sessionId, exitStatus}` |
| `activeIndex` | `int` | `activeTabChanged` | selected tab, `-1` when none |
| `activeModel` | `QVariant` | `activeTabChanged` | `TerminalModel` of the selected tab, or `null` |
| `hasTabs` | `bool` | `tabsChanged` | whether any tab is open |
| `settings` | `QVariantMap` | `settingsChanged` | UI preferences; see `DEFAULT_SETTINGS` |
| `transfers` | `QVariantList` | `transferProgressChanged` | in-flight: `{id, alias, label, route, fraction, detail}` |
| `transferActive` | `bool` | `transferProgressChanged` | any transfer running |
| `transferCount` | `int` | `transferProgressChanged` | number running (badge) |
| `transferHistory` | `QVariantList` | `transferHistoryChanged` | last 40 finished: adds `{status, ago}` |
| `tunnels` | `QVariantList` | `tunnelsChanged` | one entry per host with rules: `{key, alias, state, persist, sessionIds, error, command, startedAt, rules}` |
| `tunnelCount` | `int` | `tunnelsChanged` | number of forwarding entries (badge) |
| `tunnelActive` | `bool` | `tunnelsChanged` | whether any entry is currently forwarding |
| `snippets` | `QVariantList` | `settingsChanged` | `{name, command}` entries from the settings |
| `splitIndex` | `int` | `layoutChanged` | the tab shown beside the active one, `-1` when not split |
| `splitActive` | `bool` | `layoutChanged` | a split is showing and it is a different tab |
| `canRestore` | `bool` | `tabsChanged` | a saved layout exists from the previous run |

`activeModel` exists precisely because `terminalModel(index)` is a slot. The
composer must bind to `App.activeModel`; a binding to the slot resolves once,
during the window when the repeater has not created delegates yet, and stays
`null`.

## Host and config calls

| Call | Returns | Notes |
| --- | --- | --- |
| `host(alias)` | map | one entry from `hosts`; `{}` when absent |
| `hostPassword(alias)` | string | decoded `encPassword` / plain `Password`, for prefilling |
| `hostRawBlock(alias)` | string | exact text of the host's block |
| `saveHost(fields)` | `{ok, alias}` or `{ok:false, error}` | create when `originalAlias` is empty, else update; renames the tab. `fields.forwards` is `[{kind, spec}]` and replaces the host's own rules. `fields.password` is written in the form named by `password_source`; `fields.startup_command` becomes `#!! StartupCommand` |
| `hostForwards(alias)` | `{own, inherited, disabled}` | `own` is editable; `inherited` entries carry a `source` label and must not be written back |
| `forwardPreview(kind, spec)` | `{valid, bind, port, target_host, target_port, error, label}` | inline validation; an invalid spec is still saveable, only the warning is advisory |
| `duplicateHost(alias)` | `{ok, alias}` | copies options into a new block in the main file |
| `deleteHost(alias)` | `{ok}` | removes the block; confirm in QML first |
| `saveRawBlock(alias, text)` | `{ok}` | block must start with `Host`/`Match` |
| `refreshHosts()` | — | re-reads the config from disk |
| `configPath()` | string | path shown in the status bar and Settings |
| `revealInExplorer(alias)` | `{ok}` | opens Explorer with the host's config file selected |
| `revealConfig()` | `{ok}` | same, for the main config file (Settings → Open folder) |

## Session calls

| Call | Notes |
| --- | --- |
| `openHost(alias)` → int | spawns `tssh <alias>` and returns the new tab index |
| `terminalModel(index)` | model of a tab; prefer `activeModel` in bindings |
| `setActiveIndex(index)` | select a tab |
| `closeTab(index)` | stops the process and unregisters the image |
| `closeOtherTabs(index)` | keeps one tab |
| `reconnectActive()` / `reconnectTab(index)` | restarts a closed/failed session |
| `duplicateTab(index)` | opens the same host in a new tab |
| `refreshTerminalThemes()` | re-applies the palette after a theme change |
| `availableFonts()` | monospace families, preferred ones first |
| `fallbackFonts()` | families that actually contain CJK, preferred ones first; anything else would make a useless fallback entry |

## Split, snippets, logs and restore

| Call | Notes |
| --- | --- |
| `splitWith(index)` → int | show `index` beside the active tab; returns the leading pane, `-1` when the request is invalid (same tab, out of range) |
| `splitHost(alias)` → int | open the host in a new tab and split it; returns the new tab index |
| `closeSplit()` | back to one pane, keeping both tabs |
| `swapSplit(which)` | exchange the active and the split pane |
| `broadcast(text)` | type `text` into the active pane and the split pane (deduplicated when they are the same) |
| `saveSnippet(fields)` | `{name, command, originalName?}` → `{ok, name}`; keyed by `originalName` when renaming |
| `deleteSnippet(name)` | `{ok}` or `{ok:false, error}` |
| `runSnippet(name, command)` | types the snippet into the active tab; the second argument lets the palette pass the command directly |
| `logsPath()` / `revealLogs()` | the session-log folder and a button to open it |
| `restoreLayout()` | reopens the saved tabs → `{ok, opened}`; unknown aliases are skipped |

`splitIndex` and `splitActive` are the only split state QML needs: the
workspace lays out the active tab and `splitIndex` side by side while
`splitActive` is true. `broadcast` is called by `CommandComposer` when its
`broadcast` property is set.

## Key and known-host calls

| Call | Returns | Notes |
| --- | --- | --- |
| `sshKeys()` | list | `{name, path, publicPath, private, type, bits, fingerprint, comment, publicKey}`; a key outside `~/.ssh` that a host's `IdentityFile` names is also listed, with `referencedBy` set to that alias |
| `keyPathFor(name)` | string | where `generateKey` would write that file name |
| `generateKey(path, comment, passphrase, keyType, bits)` | `{ok, path, publicPath, publicKey}` or `{ok:false, error}` | runs `ssh-keygen`; refuses an existing file instead of prompting |
| `readKey(path, which)` | `{ok, text}` | `which` is `public` or `private` |
| `deleteKey(path)` | `{ok, removed}` | removes the private key and its `.pub`; `removed` lists the files |
| `knownHosts()` | list | `{line, hosts, hashed, displayHost, type, fingerprint, raw}`; a hashed row shows `(hashed)` as its display name and its key type still parses |
| `scanHost(host, port)` | — | starts `ssh-keyscan` in a worker thread; the result arrives on `hostScanFinished` |
| `trustHost(lines)` | `{ok, added}` | appends deduplicated `raw` lines to `known_hosts` |
| `forgetHost(host, line)` | `{ok, removed, message}` | `ssh-keygen -R` by name, so hashed rows for that host go too; with a non-zero `line` the listed row is deleted in place instead, which is the only way to remove a hashed entry whose name cannot be reversed |
| `pushKey(alias, publicKey)` | `{ok, command}` | types an idempotent install line into the host's session, opening one if needed |

Key management talks to the real `~/.ssh`; there is no override for it (see
invariant 12).

## Transfer calls

| Call | Notes |
| --- | --- |
| `createSftpClient(alias)` | returns an `SftpClient` owned by QML; connect its signals, then call `start()` |
| `localHome()` | writable starting folder for the local pane |
| `localSizes(list)` | byte sizes (directories walk the tree; `-1` when unknown) |
| `listLocalResult(path)` | `{ok, path, entries, error, fallback}` — explains an empty pane |
| `parentPath(path)` | parent folder for the "up" button |

`SftpClient` itself: signals `listingReady(path, entries)`,
`operationDone(what, ok, message)`, `failed(message)`,
`progressChanged(label, fraction, detail)`; slots `start()`, `listDir(path)`,
`upload(paths, remoteDir, sizes)`, `download(paths, localDir, sizes)`,
`remove(paths)`, `mkdir(path)`, `rename(old, new)`, `cancel()`.

Every one of those is decorated with `@Slot`; removing a decorator makes the
call throw "Property … is not a function" in QML rather than failing at
import.

## Forwarding calls

| Call | Notes |
| --- | --- |
| `tunnelCommand(alias)` | the equivalent command line, shown in the panel |
| `startTunnels(alias, persist)` | enable a host's rules; while a session is open it is that session that provides them |
| `stopTunnels(alias)` | release the forwarding for a host |
| `setTunnelPersist(alias, persist)` | the "keep running" opt-in; takes effect when the session ends |

States in `tunnels`: `session` (an open tab provides the rules, no process of
ours), `pending`/`starting`/`running` (our own `tssh -N`), `failed`, `stopped`.
A non-persistent entry is removed when its last session closes; a persistent one
moves to `pending` and spawns `tssh -N` once the port is free.

## Signals QML listens to

| Signal | Used by |
| --- | --- |
| `hostsChanged` | sidebar rebuild, palette |
| `settingsChanged` | theme re-application, all setting bindings |
| `terminalColorsChanged` | forces `applyTheme()` in `Main.qml` |
| `tunnelsChanged` | tunnel panel, `tunnelCount` badge |
| `layoutChanged` | split geometry, split toolbar, tab menu state |
| `hostScanFinished(result)` | key sheet: `{ok, host, port, entries}` with `{hosts, type, fingerprint, raw}` per entry, or `{ok:false, error}` |
| `toast(message)` | Snackbar |
| `tabsChanged` / `activeTabChanged` | tab strip, panes, composer, `canRestore` |

## Settings keys

`fontFamily`, `fontSize`, `fontFallback`, `theme` (`dark`/`light`/`system`),
`themeFamily` (`catppuccin`/`mono`, default `catppuccin`; the set is whatever
the YAML catalog in the app data directory defines, so a hand-added family is
accepted as-is and an unknown one normalizes back to `catppuccin`),
`seedColor` (optional `#rrggbb` accent override; empty means
"use the family's own accent"), `sidebarWidth`, `sidebarVisible`,
`confirmClose`, `copyOnSelect`,
`composerVisible`, `terminalTheme` (`match`/`classic`), `lastSession`,
`sessionLog` (bool, default false), `autoReconnect` (bool, default true),
`keepalive` (int seconds, default 30; `0` disables), `broadcastInput` (bool),
`snippets` (list of `{name, command}`), plus a private `_geometry` map. Set
them through `setSetting(key, value)`; the controller persists the map and
fires `settingsChanged`.

The saved `layout` (`{tabs, active, split}`) is written alongside the settings
but is not a setting: it only describes which tabs were open, and
`restoreLayout()` is the only reader. A state file without it simply has
nothing to restore.

## TerminalModel surface used by QML

Properties: `source`, `title`, `columns`, `rows`, `altScreen`,
`mouseReporting`, `historySize`, `scrollbackOffset`, `hasSelection`, `idle`,
`searchQuery`, `searchCount`, `searchCurrent`.

Slots: `handleKey`, `mousePress`, `mouseMove`, `mouseRelease`,
`mouseDoubleClick`, `wheel`, `setViewport`, `setFont(family, size, fallback)`,
`applyTheme`,
`scrollLines`, `scrollToBottom`, `copySelection`, `copySelectionIfAny`,
`pasteClipboard`, `selectAll`, `clearSelection`, `selectedText`,
`hasClipboardText`, `sendText`, `runCommand`, `setCopyOnSelect`,
`setSearch(query, caseSensitive)`, `clearSearch()`, `nextMatch(delta)`,
`attachLog(handle)`, `detachLog()`, `flushLog()`.

`attachLog` takes an open text handle owned by Python (the controller opens and
closes it); QML never touches it. `searchCurrent` is 1-based and `0` when there
are no hits; `nextMatch` wraps in both directions.

`setFont`'s third argument is the fallback family for characters the primary
font has no glyph for (the CJK case); an empty string means "do not
substitute", leaving Qt's own system fallback in charge. The cell size always
comes from the primary family, so changing the fallback never reflows the
grid. `fontFallback` defaults to `Microsoft YaHei`; `fallbackFonts()` returns
the families worth offering. If the default family is not installed, the
controller resolves it to the first offered family on startup (or to `""`,
which means no substitution) instead of leaving the setting aimed at a face Qt
would resolve to something Latin-only.
