"""Reader/writer for OpenSSH + tssh configuration in ``~/.ssh/config``.

The file is treated as a list of *blocks* (one per ``Host``/``Match`` stanza)
whose original lines are preserved verbatim. Editing a host rewrites only the
keyword lines it owns, so comments, ordering, tssh extensions and options this
app does not model all survive a round trip.

Value resolution follows OpenSSH: the first obtained value wins, and ``Host *``
style wildcards apply to every host they match, in file order. tssh's extended
options are the ``#!! key value`` lines OpenSSH ignores as comments.
"""

from __future__ import annotations

import fnmatch
import glob
import re
from dataclasses import dataclass, field
from pathlib import Path

from . import paths, secret

EXT_PREFIX = "#!!"
WILDCARD_CHARS = set("*?[")

# A config line: indentation, optional "#!! " extension marker, keyword, value.
_LINE_RE = re.compile(r"^(\s*)(#!!\s+)?([A-Za-z][A-Za-z0-9]*)(?:\s+|\s*=\s*)(.*)$")
_COMMENT_RE = re.compile(r"^\s*(#|$)")


@dataclass
class OptionLine:
    keyword: str
    value: str
    extended: bool
    raw: str

    @property
    def ext_key(self) -> str:
        return self.keyword if self.extended else ""


@dataclass
class Block:
    kind: str                      # "host", "match" or "global"
    start: int                     # index into ConfigFile.lines
    lines: list[str] = field(default_factory=list)
    patterns: list[tuple[str, bool]] = field(default_factory=list)  # (pattern, negated)

    @property
    def aliases(self) -> list[str]:
        return [p for p, negated in self.patterns if not negated]

    def options(self) -> list[OptionLine]:
        out: list[OptionLine] = []
        body = self.lines if self.kind == "global" else self.lines[1:]
        for raw in body:
            if _COMMENT_RE.match(raw) and not raw.lstrip().startswith(EXT_PREFIX):
                continue
            m = _LINE_RE.match(raw.rstrip("\r\n"))
            if not m:
                continue
            out.append(OptionLine(
                keyword=m.group(3),
                value=m.group(4).strip(),
                extended=bool(m.group(2)),
                raw=raw.rstrip("\r\n"),
            ))
        return out

    def get(self, key: str, extended: bool = False) -> str | None:
        low = key.lower()
        for opt in self.options():
            if opt.keyword.lower() != low:
                continue
            if opt.extended != extended:
                continue
            return opt.value
        return None

    def values(self, key: str) -> list[str]:
        """Every value for a directive that may appear more than once.

        ``LocalForward``/``RemoteForward``/``DynamicForward`` accumulate rather
        than override, so the first-value-wins rule of :meth:`get` does not
        describe them.
        """
        low = key.lower()
        return [opt.value for opt in self.options()
                if opt.keyword.lower() == low and not opt.extended]

    def has_keyword(self, key: str) -> bool:
        low = key.lower()
        return any(opt.keyword.lower() == low for opt in self.options())


@dataclass
class HostEntry:
    alias: str
    hostname: str
    port: str
    user: str
    identity_file: str
    proxy_command: str
    proxy_jump: str
    group_labels: list[str]
    hidden: bool
    has_password: bool
    raw: str
    source: str
    password_source: str = ""       # encrypted | plain | command | ""
    startup_command: str = ""       # #!! StartupCommand, LItsshP's own extension


class ConfigFile:
    def __init__(self, path: Path):
        self.path = path
        self.bom = False
        self.newline = "\r\n"
        self.lines: list[str] = []
        self.blocks: list[Block] = []
        self.load()

    # ---------------------------------------------------------------- loading

    def load(self) -> None:
        try:
            data = self.path.read_bytes()
        except OSError:
            self.lines = []
            self.blocks = []
            return

        text = data.decode("utf-8", errors="surrogateescape")
        if text.startswith("\ufeff"):
            self.bom = True
            text = text[1:]
        if "\r\n" in text:
            self.newline = "\r\n"
        elif "\n" in text:
            self.newline = "\n"

        self.lines = text.splitlines(keepends=True)
        if self.lines and not self.lines[-1].endswith(("\n", "\r")):
            self.lines[-1] += self.newline
        self._parse()

    def _parse(self) -> None:
        self.blocks = []
        current: Block | None = None
        for idx, raw in enumerate(self.lines):
            m = _LINE_RE.match(raw.rstrip("\r\n"))
            is_match = (
                m is not None
                and not m.group(2)
                and m.group(3).lower() in ("host", "match")
            )
            if is_match:
                current = Block(
                    kind=m.group(3).lower(),
                    start=idx,
                    lines=[raw],
                )
                if current.kind == "host":
                    current.patterns = [
                        (tok, tok.startswith("!"))
                        for tok in m.group(4).split()
                    ]
                self.blocks.append(current)
            elif current is None:
                current = Block(kind="global", start=idx, lines=[raw])
                self.blocks.append(current)
            else:
                current.lines.append(raw)

        # A leading global block only matters if it carries real options (an
        # Include, a CanonicalizeHostname, ...). Comment-only preambles are
        # dropped so they never look like an editable host.
        self.blocks = [
            b for b in self.blocks
            if b.kind != "global" or any(not _COMMENT_RE.match(l) for l in b.lines)
        ]

    def save(self) -> None:
        text = "".join(self.lines)
        if self.bom:
            text = "\ufeff" + text
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_bytes(text.encode("utf-8", errors="surrogateescape"))

    # ------------------------------------------------------------ block edits

    def _line_index(self, block: Block, offset: int) -> int:
        return block.start + offset

    def _adjust_starts(self, after: int, delta: int) -> None:
        for b in self.blocks:
            if b.start > after:
                b.start += delta

    def add_block(self, header: str, options: list[tuple[str, str]]) -> Block:
        if self.lines and self.lines[-1].strip():
            self.lines.append(self.newline)
        start = len(self.lines)
        new_lines = [header + self.newline]
        for key, value in options:
            new_lines.append(f"    {key} {value}{self.newline}")
        self.lines.extend(new_lines)

        block = Block(kind="host", start=start, lines=new_lines)
        block.patterns = [(tok, tok.startswith("!")) for tok in header[5:].split()]
        self.blocks.append(block)
        return block

    def remove_block(self, block: Block) -> None:
        if block not in self.blocks:
            return
        start = block.start
        end = start + len(block.lines)
        # Blank lines directly after a block belong to it, so they go with it.
        while end < len(self.lines) and not self.lines[end].strip():
            end += 1
        # The separator *before* the block belongs to the previous block; keep
        # it so the neighbours stay visually separated. If the deleted block
        # was last, that separator would dangle at EOF, so drop it.
        if end >= len(self.lines) and start > 0 and not self.lines[start - 1].strip():
            start -= 1
        removed = end - start
        del self.lines[start:end]
        self.blocks.remove(block)
        self._adjust_starts(start - 1, -removed)

    def set_option(self, block: Block, key: str, value: str | None,
                   extended: bool = False) -> None:
        """Set or remove a keyword inside ``block``, preserving indentation."""
        low = key.lower()
        for offset, raw in enumerate(block.lines):
            if offset == 0:
                continue
            m = _LINE_RE.match(raw.rstrip("\r\n"))
            if not m or m.group(3).lower() != low or bool(m.group(2)) != extended:
                continue
            if value is None:
                idx = block.start + offset
                del block.lines[offset]
                del self.lines[idx]
                self._adjust_starts(idx - 1, -1)
                return
            indent = m.group(1) or "    "
            prefix = f"{EXT_PREFIX} " if extended else ""
            line = f"{indent}{prefix}{key} {value}{self.newline}"
            block.lines[offset] = line
            self.lines[block.start + offset] = line
            return

        if value is None:
            return

        insert_at = block.start + len(block.lines)
        prefix = f"{EXT_PREFIX} " if extended else ""
        line = f"    {prefix}{key} {value}{self.newline}"
        block.lines.append(line)
        self.lines.insert(insert_at, line)
        self._adjust_starts(insert_at - 1, 1)

    def set_options(self, block: Block, key: str, values: list[str]) -> None:
        """Replace every occurrence of an accumulating directive in ``block``.

        Used for ``LocalForward``/``RemoteForward``/``DynamicForward``, which
        OpenSSH appends rather than overrides. Existing directive lines are
        rewritten in place (keeping their indentation), surplus ones are
        removed, and anything between them — comments, blank lines — stays
        where it is. New lines are appended after the last existing directive,
        or at the end of the block when it has none.
        """
        low = key.lower()
        matches: list[int] = []
        for offset, raw in enumerate(block.lines):
            if offset == 0:
                continue
            m = _LINE_RE.match(raw.rstrip("\r\n"))
            if m and m.group(3).lower() == low and not m.group(2):
                matches.append(offset)

        if not matches:
            for value in values:
                self.set_option(block, key, value)
            return

        old_len = len(block.lines)
        new_lines = list(block.lines)
        rewritten: list[int] = []
        # Walk backwards so earlier offsets stay valid as surplus lines go.
        for position, offset in enumerate(matches):
            if position < len(values):
                m = _LINE_RE.match(new_lines[offset].rstrip("\r\n"))
                indent = m.group(1) if m else "    "
                new_lines[offset] = f"{indent}{key} {values[position]}{self.newline}"
                rewritten.append(offset)
            else:
                del new_lines[offset]

        extra = values[len(matches):]
        if extra:
            insert_at = (rewritten[-1] + 1) if rewritten else len(new_lines)
            for position, value in enumerate(extra):
                new_lines.insert(insert_at + position,
                                 f"    {key} {value}{self.newline}")

        block.lines = new_lines
        self.lines[block.start:block.start + old_len] = new_lines
        self._adjust_starts(block.start, len(new_lines) - old_len)

    def rename_alias(self, block: Block, old: str, new: str) -> None:
        if old == new or not block.lines:
            return
        header = block.lines[0]
        m = _LINE_RE.match(header.rstrip("\r\n"))
        if not m:
            return
        tokens = m.group(4).split()
        replaced = []
        for tok in tokens:
            negated = tok.startswith("!")
            bare = tok[1:] if negated else tok
            if bare.lower() == old.lower():
                bare = new
            replaced.append(("!" if negated else "") + bare)
        trailing = "\r\n" if header.endswith("\r\n") else "\n"
        line = f"{m.group(1)}{m.group(3)} {' '.join(replaced)}{trailing}"
        block.lines[0] = line
        self.lines[block.start] = line
        block.patterns = [(t, t.startswith("!")) for t in replaced]


def _expand_includes(base: Path, pattern: str) -> list[Path]:
    pattern = pattern.strip().strip('"')
    if not pattern:
        return []
    expanded = str(Path(pattern).expanduser())
    if not Path(expanded).is_absolute():
        expanded = str(base.parent / expanded)
    matches = sorted(glob.glob(expanded))
    if not matches and Path(expanded).exists():
        matches = [expanded]
    return [Path(p) for p in matches if Path(p).is_file()]


def _block_label(block: Block) -> str:
    """Short description of where a rule came from, for the read-only list."""
    if block.kind == "global":
        return "top-level options"
    return " ".join(block.lines[0].split())


def _matches(pattern: str, alias: str) -> bool:
    return fnmatch.fnmatchcase(alias.lower(), pattern.lower())


def _block_matches(block: Block, alias: str) -> bool:
    positives = [p for p, neg in block.patterns if not neg]
    negatives = [p for p, neg in block.patterns if neg]
    if not positives:
        return False
    if any(_matches(p, alias) for p in negatives):
        return False
    return any(_matches(p, alias) for p in positives)


class ConfigStore:
    """All config files that make up the tssh host list."""

    def __init__(self, main_path: Path | None = None):
        self.main_path = main_path or paths.ssh_config()
        self.files: list[ConfigFile] = []
        self.reload()

    # ---------------------------------------------------------------- loading

    def reload(self) -> None:
        self.files = []
        self._load_file(self.main_path, set(), 0)

    def _load_file(self, path: Path, seen: set[Path], depth: int) -> None:
        if depth > 8:
            return
        try:
            resolved = path.resolve()
        except OSError:
            resolved = path
        if resolved in seen or not path.exists():
            return
        seen.add(resolved)

        cfg = ConfigFile(path)
        self.files.append(cfg)
        for block in list(cfg.blocks):
            for opt in block.options():
                if opt.extended or opt.keyword.lower() != "include":
                    continue
                for inc in _expand_includes(path, opt.value):
                    self._load_file(inc, seen, depth + 1)

    # ---------------------------------------------------------------- reading

    def _concrete_hosts(self) -> list[tuple[ConfigFile, Block, str]]:
        out = []
        for cfg in self.files:
            for block in cfg.blocks:
                if block.kind != "host":
                    continue
                for alias in block.aliases:
                    if not alias or any(ch in alias for ch in WILDCARD_CHARS):
                        continue
                    out.append((cfg, block, alias))
        return out

    def _first_value(self, alias: str, key: str) -> str:
        for cfg in self.files:
            for block in cfg.blocks:
                if block.kind == "match":
                    continue
                if block.kind == "host" and not _block_matches(block, alias):
                    continue
                value = block.get(key)
                if value:
                    return value
        return ""

    def _first_ext(self, alias: str, key: str) -> str:
        for cfg in self.files:
            for block in cfg.blocks:
                if block.kind != "host" or not _block_matches(block, alias):
                    continue
                value = block.get(key, extended=True)
                if value is not None:
                    return value
        return ""

    def hosts(self, include_hidden: bool = False) -> list[HostEntry]:
        entries: list[HostEntry] = []
        seen: set[str] = set()
        for cfg, block, alias in self._concrete_hosts():
            if alias in seen:
                continue
            seen.add(alias)

            groups = self._first_ext(alias, "GroupLabels")
            hidden = self._first_ext(alias, "HideHost").lower() in ("yes", "true", "1")
            if hidden and not include_hidden:
                continue

            entries.append(HostEntry(
                alias=alias,
                hostname=self._first_value(alias, "HostName") or alias,
                port=self._first_value(alias, "Port") or "22",
                user=self._first_value(alias, "User"),
                identity_file=self._first_value(alias, "IdentityFile"),
                proxy_command=self._first_value(alias, "ProxyCommand"),
                proxy_jump=self._first_value(alias, "ProxyJump"),
                group_labels=groups.split(),
                hidden=hidden,
                # A PasswordCommand hides its secret, but the host is still
                # configured to authenticate without prompting, which is what
                # the key marker in the sidebar means.
                has_password=bool(self._stored_password(alias))
                             or bool(self._first_ext(alias, "PasswordCommand")),
                raw="".join(block.lines),
                source=str(cfg.path),
                password_source=self._password_source(alias),
                startup_command=self._first_ext(alias, "StartupCommand"),
            ))
        entries.sort(key=lambda e: (e.group_labels[0].lower() if e.group_labels else "", e.alias.lower()))
        return entries

    def host(self, alias: str) -> HostEntry | None:
        for entry in self.hosts(include_hidden=True):
            if entry.alias == alias:
                return entry
        return None

    def _stored_password(self, alias: str) -> str | None:
        encoded = self._first_ext(alias, "encPassword")
        if encoded:
            decoded = secret.decode_secret(encoded)
            if decoded:
                return decoded
        plain = self._first_ext(alias, "Password")
        if plain:
            return plain
        return None

    def _password_source(self, alias: str) -> str:
        """How the password is stored, so the editor can keep the same form.

        tssh resolves ``encPassword`` → ``PasswordCommand`` → ``Password``; the
        editor must not silently convert one form into another, because a
        ``PasswordCommand`` has no plain-text value to round-trip.
        """
        if self._first_ext(alias, "encPassword"):
            return "encrypted"
        if self._first_ext(alias, "PasswordCommand"):
            return "command"
        if self._first_ext(alias, "Password"):
            return "plain"
        if self._first_ext(alias, "encQuestionAnswer1"):
            return "answer"
        return ""

    def password(self, alias: str) -> str | None:
        return self._stored_password(alias)

    def option(self, alias: str, key: str) -> str:
        """Effective value of a plain OpenSSH option for ``alias``."""
        return self._first_value(alias, key)

    # ------------------------------------------------------------- forwarding

    # Forwarding directives accumulate across every block that applies to a
    # host, so they cannot go through _first_value. The mapping to CLI flags
    # is what tssh -N is invoked with.
    FORWARD_KEYS = (("LocalForward", "L"), ("RemoteForward", "R"),
                    ("DynamicForward", "D"))

    def forward_rules(self, alias: str) -> dict:
        """Forwarding rules that apply to ``alias``.

        ``own`` holds the rules written in the host's own block and is what the
        editor may rewrite. ``inherited`` holds rules that reach the host from
        a wildcard, ``Match`` or ``Include`` block: they are shown read-only,
        because deleting them would silently change every other host matching
        the same block.
        """
        own: list[dict] = []
        inherited: list[dict] = []
        own_block: Block | None = None
        for cfg, block, name in self._concrete_hosts():
            if name == alias:
                own_block = block
                break

        for cfg in self.files:
            for block in cfg.blocks:
                if block.kind == "match":
                    continue
                if block.kind == "host" and not _block_matches(block, alias):
                    continue
                is_own = block is own_block
                for key, kind in self.FORWARD_KEYS:
                    for value in block.values(key):
                        rule = {"kind": kind, "spec": value}
                        if is_own:
                            own.append(rule)
                        else:
                            inherited.append({**rule, "source": _block_label(block)})

        return {"own": own, "inherited": inherited,
                "disabled": self._forwarding_disabled(alias)}

    def _forwarding_disabled(self, alias: str) -> bool:
        value = self._first_value(alias, "ClearAllForwardings")
        return value.strip().lower() in ("yes", "true", "1", "on")

    # ---------------------------------------------------------------- writing

    def _target(self, alias: str) -> tuple[ConfigFile, Block] | None:
        fallback = None
        for cfg, block, name in self._concrete_hosts():
            if name != alias:
                continue
            if fallback is None:
                fallback = (cfg, block)
            if block.get("HostName"):
                return (cfg, block)
        return fallback

    def add_host(self, fields: dict[str, str]) -> str:
        alias = (fields.get("alias") or "").strip()
        _validate_alias(alias)
        if self.host(alias) is not None:
            raise ValueError(f"Host '{alias}' already exists")

        main = self._main_file()
        main.add_block(f"Host {alias}", self._fields_to_options(fields, alias))
        main.save()
        self.reload()
        return alias

    def update_host(self, old_alias: str, fields: dict[str, str]) -> str:
        target = self._target(old_alias)
        if target is None:
            raise ValueError(f"Host '{old_alias}' not found in the configuration")
        cfg, block = target

        new_alias = (fields.get("alias") or old_alias).strip()
        _validate_alias(new_alias)
        if new_alias != old_alias and self.host(new_alias) is not None:
            raise ValueError(f"Host '{new_alias}' already exists")

        cfg.rename_alias(block, old_alias, new_alias)

        simple = (
            ("HostName", "hostname"),
            ("Port", "port"),
            ("User", "user"),
            ("IdentityFile", "identity_file"),
            ("ProxyJump", "proxy_jump"),
            ("ProxyCommand", "proxy_command"),
        )
        for key, field_name in simple:
            if field_name not in fields:
                continue
            value = (fields[field_name] or "").strip()
            if value:
                cfg.set_option(block, key, value)
                if key == "IdentityFile" and not block.has_keyword("IdentitiesOnly"):
                    cfg.set_option(block, "IdentitiesOnly", "yes")
            else:
                cfg.set_option(block, key, None)

        if "group_labels" in fields:
            groups = _normalise_groups(fields["group_labels"])
            cfg.set_option(block, "GroupLabels", groups or None, extended=True)

        password = fields.get("password")
        if password:
            source = str(fields.get("password_source") or
                         self._password_source(old_alias))
            self._write_password(cfg, block, password, source)
        elif password == "":
            self._write_password(cfg, block, "", self._password_source(old_alias))

        if "forwards" in fields:
            self._write_forwards(cfg, block, fields["forwards"])

        if "startup_command" in fields:
            startup = str(fields.get("startup_command") or "").strip()
            cfg.set_option(block, "StartupCommand", startup or None, extended=True)

        cfg.save()
        self.reload()
        return new_alias

    def _write_password(self, cfg: ConfigFile, block: Block, value: str,
                        source: str) -> None:
        """Write the password back in the form it was stored in.

        A plain ``#!! Password`` stays plain, an encrypted one stays encrypted.
        Converting on every save would rewrite the file for no reason, and a
        ``PasswordCommand`` has no secret to write at all — clearing the field
        must not delete a command the editor never showed.
        """
        if source == "plain" and value:
            cfg.set_option(block, "encPassword", None, extended=True)
            cfg.set_option(block, "encQuestionAnswer1", None, extended=True)
            cfg.set_option(block, "Password", value, extended=True)
            return
        if value:
            encoded = secret.encode_secret(value)
            cfg.set_option(block, "Password", None, extended=True)
            cfg.set_option(block, "encPassword", encoded, extended=True)
            cfg.set_option(block, "encQuestionAnswer1", encoded, extended=True)
            return
        # Clearing: remove both forms the editor can show, but leave a
        # PasswordCommand alone — it is part of the config the user wrote by
        # hand and this form has no field for it.
        cfg.set_option(block, "encPassword", None, extended=True)
        cfg.set_option(block, "encQuestionAnswer1", None, extended=True)
        cfg.set_option(block, "Password", None, extended=True)

    def _write_forwards(self, cfg: ConfigFile, block: Block,
                        rules: list) -> None:
        """Persist the host's own forwarding rules, leaving inherited ones alone."""
        grouped: dict[str, list[str]] = {kind: [] for _, kind in self.FORWARD_KEYS}
        for rule in rules or []:
            kind = str(rule.get("kind", "")).upper()
            spec = str(rule.get("spec", "")).strip()
            if kind in grouped and spec:
                grouped[kind].append(spec)
        for key, kind in self.FORWARD_KEYS:
            cfg.set_options(block, key, grouped[kind])

    def delete_host(self, alias: str) -> None:
        target = self._target(alias)
        if target is None:
            raise ValueError(f"Host '{alias}' not found in the configuration")
        cfg, block = target
        cfg.remove_block(block)
        cfg.save()
        self.reload()

    def duplicate_host(self, alias: str) -> str:
        target = self._target(alias)
        if target is None:
            raise ValueError(f"Host '{alias}' not found in the configuration")
        _, block = target

        options: list[tuple[str, str]] = []
        for opt in block.options():
            key = f"{EXT_PREFIX} {opt.keyword}" if opt.extended else opt.keyword
            options.append((key, opt.value))

        base = f"{alias}-copy"
        new_alias = base
        suffix = 1
        while self.host(new_alias) is not None:
            suffix += 1
            new_alias = f"{base}{suffix}"

        main = self._main_file()
        main.add_block(f"Host {new_alias}", options)
        main.save()
        self.reload()
        return new_alias

    def raw_block(self, alias: str) -> str:
        target = self._target(alias)
        return "".join(target[1].lines) if target else ""

    def replace_raw_block(self, alias: str, text: str) -> None:
        target = self._target(alias)
        if target is None:
            raise ValueError(f"Host '{alias}' not found in the configuration")
        cfg, block = target
        if not text.endswith(("\n", "\r")):
            text += cfg.newline
        new_lines = text.splitlines(keepends=True)
        if not new_lines or not new_lines[0].strip().lower().startswith(("host ", "match ")):
            raise ValueError("The block must start with a 'Host' line")
        old_len = len(block.lines)
        cfg.lines[block.start:block.start + old_len] = new_lines
        delta = len(new_lines) - old_len
        cfg.lines[block.start:block.start + len(new_lines)] = new_lines
        cfg._adjust_starts(block.start - 1, delta)
        cfg.save()
        self.reload()

    def _fields_to_options(self, fields: dict[str, str], alias: str) -> list[tuple[str, str]]:
        options: list[tuple[str, str]] = []
        hostname = (fields.get("hostname") or "").strip()
        options.append(("HostName", hostname or alias))
        port = (fields.get("port") or "").strip()
        if port:
            options.append(("Port", port))
        user = (fields.get("user") or "").strip()
        if user:
            options.append(("User", user))
        identity = (fields.get("identity_file") or "").strip()
        if identity:
            options.append(("IdentityFile", identity))
            options.append(("IdentitiesOnly", "yes"))
        jump = (fields.get("proxy_jump") or "").strip()
        if jump:
            options.append(("ProxyJump", jump))
        proxy_command = (fields.get("proxy_command") or "").strip()
        if proxy_command:
            options.append(("ProxyCommand", proxy_command))
        groups = _normalise_groups(fields.get("group_labels", ""))
        if groups:
            options.append((f"{EXT_PREFIX} GroupLabels", groups))
        startup = (fields.get("startup_command") or "").strip()
        if startup:
            options.append((f"{EXT_PREFIX} StartupCommand", startup))
        for rule in fields.get("forwards") or []:
            kind = str(rule.get("kind", "")).upper()
            spec = str(rule.get("spec", "")).strip()
            key = dict((k, key) for key, k in self.FORWARD_KEYS).get(kind)
            if key and spec:
                options.append((key, spec))
        password = fields.get("password") or ""
        if password:
            if str(fields.get("password_source") or "") == "plain":
                options.append((f"{EXT_PREFIX} Password", password))
            else:
                encoded = secret.encode_secret(password)
                options.append((f"{EXT_PREFIX} encPassword", encoded))
                options.append((f"{EXT_PREFIX} encQuestionAnswer1", encoded))
        return options

    def _main_file(self) -> ConfigFile:
        try:
            main_resolved = self.main_path.resolve()
        except OSError:
            main_resolved = self.main_path
        for cfg in self.files:
            try:
                if cfg.path.resolve() == main_resolved:
                    return cfg
            except OSError:
                continue
        self.main_path.parent.mkdir(parents=True, exist_ok=True)
        if not self.main_path.exists():
            self.main_path.write_text("", encoding="utf-8")
        self.reload()
        return self.files[0]


def _validate_alias(alias: str) -> None:
    if not alias:
        raise ValueError("Host alias is required")
    if any(ch in alias for ch in WILDCARD_CHARS) or any(ch.isspace() for ch in alias):
        raise ValueError("Host alias cannot contain spaces or wildcards")
    if alias.startswith("!"):
        raise ValueError("Host alias cannot start with '!'")


def _normalise_groups(value: str) -> str:
    seen: list[str] = []
    for token in (value or "").replace(",", " ").split():
        if token not in seen:
            seen.append(token)
    return " ".join(seen)


def all_groups(entries: list[HostEntry]) -> list[str]:
    groups: list[str] = []
    for entry in entries:
        for label in entry.group_labels:
            if label not in groups:
                groups.append(label)
    return sorted(groups, key=str.lower)
