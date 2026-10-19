# Skill: Config and Secrets

`app/config.py` is the most delicate module in the project: it edits a file the
user also edits by hand and the tssh CLI reads. Read this before changing it.

## The model

The file is kept as a list of lines (`ConfigFile.lines`), split with
`keepends=True`. Parsing only builds an index over those lines:

- `Block` — one `Host`/`Match` stanza, plus a synthetic `global` block for
  anything before the first stanza. Comments before the first `Host` are
  dropped in that synthetic block so they never look editable.
- `OptionLine` — keyword/value/indentation of one line, with an `extended`
  flag for tssh's `#!! key value` lines.
- `patterns` — the tokens after `Host`, with `!` negations recorded.

Nothing is normalised. Values are only trimmed when *read* into `HostEntry`;
the line itself is untouched until an edit rewrites it.

## Value resolution (OpenSSH semantics)

| Rule | Implementation |
| --- | --- |
| first obtained value wins | `_first_value` walks files in Include order, then blocks in file order |
| `Host *` and wildcards apply | `_block_matches` with `fnmatch.fnmatchcase` on lower-cased names |
| `!pattern` excludes | negatives checked before positives |
| `Include` is followed recursively | `_load_file`, depth-capped at 8, cycle-safe via resolved paths |
| only concrete aliases are listed | `_concrete_hosts` skips tokens containing `*?[` |
| `Match` blocks are not listed | `kind == "match"` is skipped when resolving |
| tssh options are `#!!` lines | `_first_ext` matches only `extended=True` |

`#!! HideHost yes|true|1` removes a host from the list (it is still reachable
through `hosts(include_hidden=True)`). `#!! GroupLabels a b` adds groups.

## Writing rules

Every writer follows the same shape: mutate the target block's lines, patch
`ConfigFile.lines` at the block's offset, adjust the `start` offsets of later
blocks, then `save()` the whole file as bytes.

- `set_option(block, key, value, extended)` — replace in place (keeping the
  original indentation), delete when `value is None`, or append with 4-space
  indentation.
- `add_block(header, options)` — append at EOF, separated by a blank line.
- `remove_block(block)` — removes the block and the blank lines directly after
  it; keeps the separator before it so neighbours stay visually separated;
  drops that separator if the block was last.
- `rename_alias(block, old, new)` — rewrites the `Host` header tokens only.
- `replace_raw_block(alias, text)` — replaces the line range wholesale; the
  text must start with `Host` or `Match`.

`save()` re-emits the BOM if the file had one and never changes the newline
style: `load()` records `\r\n` vs `\n`, and a file with no trailing newline
gets exactly one.

`_target(alias)` picks the block to edit when an alias appears more than once:
the first block that actually has a `HostName`, otherwise the first occurrence.
This mirrors "the block users think of as the definition".

## Reading passwords

`_stored_password` prefers `#!! encPassword`, decoding it through
`secret.decode_secret`; it falls back to a plain `#!! Password`, which tssh
also accepts. `hostPassword` exposes the decoded value so the editor can
prefill it, and the editor compares it before writing (an unchanged field does
not generate a new nonce).

`_password_source` reports *how* it was stored (`encrypted`, `plain`,
`command`, `answer`, or empty), because that is what decides how a save writes
it back. `has_password` is true for a `PasswordCommand` as well, since such a
host needs no typed secret.

## Writing passwords

`update_host` writes both `#!! encPassword` and `#!! encQuestionAnswer1` with
the same encoded value — that is what tssh does, so its question-answer flow
keeps working.

Which form is written depends on `fields["password_source"]`, which the editor
received as `HostEntry.password_source`:

| Source | Saving a value | Clearing the field |
| --- | --- | --- |
| `encrypted` (or empty) | `encPassword` + `encQuestionAnswer1`; the plain line is removed | both removed |
| `plain` | `#!! Password` kept plain; `encPassword`/`encQuestionAnswer1` removed | plain line removed |
| `command` | not written — there is no value to round-trip | `PasswordCommand` left untouched |
| `answer` | treated as encrypted | both removed |

Leaving `PasswordCommand` alone when the field is cleared is deliberate: the
editor never showed that command, so emptying a field it could not fill must
not delete a working login.

`#!! StartupCommand <text>` is LItsshP's own option. tssh ignores it; the app
types the text into the session once the shell reports ready. It is stored in
the host's block, so it survives renames and is shared with the CLI's view of
the file (though only LItsshP acts on it).

`secret.py` is a byte-compatible port: AES-256-GCM, 12-byte random nonce,
`hex(nonce || ciphertext || tag)`, constant key
`THE_UNSAFE_KEY_FOR_ENCODING_ONLY`. It is obfuscation, not encryption, and the
README says so; do not describe it as secure anywhere.

## Rules for changes

1. **Never rewrite a line you were not asked to change.** Comments, ordering,
   blank lines, CRLF and BOM are user data.
2. **Never re-serialise the whole file.** There is no "save the parsed model"
   path, and adding one would break invariant 2.
3. **Editing must be idempotent.** Saving twice with the same fields must
   produce the same bytes the second time.
4. **Validate aliases** through `_validate_alias`: no spaces, no wildcard
   characters, no leading `!`.
5. **Reload after every write.** Writers call `self.reload()`; the controller
   then calls `_refresh_hosts()`. Skipping this leaves stale `start` offsets.
6. **Check case sensitivity.** Keywords compare case-insensitively
   (`.lower()`), aliases match case-insensitively for wildcards but are stored
   as written.

## Verification

```bash
.venv/Scripts/python docs/skills/reference/config_roundtrip_gate.py
.venv/Scripts/python docs/skills/reference/session_features_gate.py
```

The first covers BOM, CRLF, untouched-neighbour, edited-value, extension and
`encPassword` round-tripping. The second covers the password *form*: plain
stays plain, encrypted stays encrypted, and clearing leaves `PasswordCommand`
alone. Any new guarantee should get a line there rather than being verified by
eye.

For a manual check, always copy the config first:

```bash
cp ~/.ssh/config /tmp/cfg.bak
LITSSHP_CONFIG=/tmp/cfg.bak .venv/Scripts/python -m app.main
```

and afterwards confirm `diff` shows only the intended block changed, and that
the file still resolves the host — `tssh` has no `-G`, so ask the OpenSSH
client it delegates to: `ssh -F /tmp/cfg.bak -G <alias>`.
