# Reference: QML API surface

Everything the QML tree may call on `App` — the `AppController` registered as
the `App` context property in `app/main.py`. If a name is not here, QML must
not use it.

## Properties (all notifying)

QML bindings only re-evaluate if the property carries `notify=`. Slots never
do; binding to a slot is a bug (it caches the first result forever).

| Property | Type | Notifies on | Content |
| --- | --- | --- | --- |
| `hosts` | `QVariantList` | `hostsChanged` | one map per concrete `Host`, effective values resolved |
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
| `saveHost(fields)` | `{ok, alias}` or `{ok:false, error}` | create when `originalAlias` is empty, else update; renames the tab |
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

## Signals QML listens to

| Signal | Used by |
| --- | --- |
| `hostsChanged` | sidebar rebuild, palette |
| `settingsChanged` | theme re-application, all setting bindings |
| `terminalColorsChanged` | forces `applyTheme()` in `Main.qml` |
| `toast(message)` | Snackbar |
| `tabsChanged` / `activeTabChanged` | tab strip, panes, composer |

## Settings keys

`fontFamily`, `fontSize`, `theme` (`dark`/`light`/`system`), `seedColor`,
`sidebarWidth`, `sidebarVisible`, `confirmClose`, `copyOnSelect`,
`composerVisible`, `terminalTheme` (`match`/`classic`), `lastSession`, plus a
private `_geometry` map. Set them through `setSetting(key, value)`; the
controller persists the map and fires `settingsChanged`.

## TerminalModel surface used by QML

Properties: `source`, `title`, `columns`, `rows`, `altScreen`,
`mouseReporting`, `historySize`, `scrollbackOffset`, `hasSelection`, `idle`.

Slots: `handleKey`, `mousePress`, `mouseMove`, `mouseRelease`,
`mouseDoubleClick`, `wheel`, `setViewport`, `setFont`, `applyTheme`,
`scrollLines`, `scrollToBottom`, `copySelection`, `copySelectionIfAny`,
`pasteClipboard`, `selectAll`, `clearSelection`, `selectedText`,
`hasClipboardText`, `sendText`, `runCommand`, `setCopyOnSelect`.
