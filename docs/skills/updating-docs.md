# Skill: Updating Documentation

Three kinds of pages exist, and they answer to different rules.

| Page | Audience | Rule |
| --- | --- | --- |
| `README.md` | someone deciding whether to use LItsshP | describe behaviour, not internals; no "how we fixed it" history |
| `docs/skills/*.md` | someone changing the code | describe the repo as it is; procedures must be runnable |
| `docs/skills/reference/*.md` | both of the above | facts only, derived from the code |

## When to update what

| Change | Update |
| --- | --- |
| a shortcut, menu item, or visible control | both READMEs (Keyboard / Interface sections) |
| a new setting | both READMEs' Settings paragraph **and** `reference/qml-api.md` (settings keys) |
| a new controller member used by QML | `reference/qml-api.md` |
| a new invariant or a changed one | `reference/invariants.md` |
| a new or changed check | `reference/verification.md` and `skills/testing.md` |
| a new `LITSSHP_*` variable or default path | both READMEs' Configuration list **and** `reference/environment.md` |
| a new module or a changed data flow | both READMEs' Architecture block **and** `reference/architecture.md` |
| a workaround for a platform defect | `skills/fixing-defects.md` (and the code comment that explains it) |

If a change touches behaviour a playbook describes, the playbook is part of
the change. A page that tells the next person to do something that no longer
works is worse than no page.

## README conventions

- Two files, one content: `README.md` is the Chinese default and
  `README_en.md` is the English one. Each opens with a one-line language
  switch (`**简体中文** · [English](README_en.md)`), and the two are kept in
  step — a change to one is a change to both, same headings, same order.
- The UI itself is English-only, so translated pages keep visible labels
  (`Reload`, `Keep running`, `Upload ↑`) verbatim and gloss them in the local
  language. Translating a button caption the user cannot find on screen is
  worse than leaving it in English.
- It opens with what the app is and the one decision that explains everything:
  each session is a real `tssh` process and hosts live in `~/.ssh/config`.
- The ASCII diagram at the top is a sketch, not a spec; keep it roughly in
  sync with the layout (sidebar header / host count / tab strip / composer /
  status bar) but do not chase pixel changes.
- Tables are used only for short enumerable facts (shortcuts, host actions,
  environment variables).
- Paragraphs explain *why* a design choice was made (plain SFTP instead of
  trzsz, `Ctrl+Shift+C` instead of `Ctrl+C`) in one or two sentences. Do not
  turn it into a design document — that is what `docs/` is for.
- Security-relevant text must stay blunt: `encPassword` is obfuscation with a
  key that ships in tssh's source.

## Style

- Plain language, present tense, no marketing adjectives.
- Say `this PC → host`, not "upload", when describing the route; keep
  "upload"/"download" only where the button label actually says it.
- Use `~/.ssh/config` verbatim, and `%TEMP%\LItsshP` for the fallback folder.
- Code identifiers in backticks; commands in fenced blocks with the shell
  shown when it matters (`bash` for the Git Bash environment, `bat` for
  `run.bat`).
- One sentence per idea. If a paragraph needs a second read, split it.

## Keeping the reference honest

The reference sheets are supposed to be checkable. Two habits keep them that
way:

1. **Prefer a command to a claim.** A page saying "the writer preserves the
   BOM" is weaker than naming the gate that proves it.
2. **Delete rather than soften.** If something is no longer true, remove the
   sentence. Do not leave "currently" or "mostly" hedges in place.

When you touch a reference sheet, run the gates afterwards if the sheet
describes them — a changed command line that was never executed is exactly the
kind of doc drift this page exists to prevent.

## Cross-links

- `docs/README.md` is the hub; every skill page is one click from it.
- Skills link to reference sheets as `reference/<page>.md`; reference sheets
  link back as `../<skill>.md`.
- The top-level READMEs link here once, under a short "Documentation" /
  "文档" line, so a user who wants to modify the app can find it without
  reading the repo tree.
