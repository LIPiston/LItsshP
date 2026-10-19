"""Gate: password form, search, logging, keys and layout persistence.

These are the guarantees the newer features rest on, each checked against a
throwaway config/state directory:

* a plain ``#!! Password`` stays plain and an encrypted one stays encrypted;
* clearing the field leaves a ``PasswordCommand`` untouched;
* ``#!! StartupCommand`` round-trips through update and add;
* search finds every occurrence in scrollback and the live screen and wraps;
* the session log keeps printable text and drops escape sequences;
* key fingerprints match ``ssh-keygen -lf`` and known_hosts rows can be
  removed by name and by line;
* the saved layout survives a restart and skips hosts that no longer exist.

No check touches the real ``~/.ssh``: the config is redirected and every
``keys`` call receives an explicit temp folder or path.

Run with the project virtualenv:

    .venv/Scripts/python docs/skills/reference/session_features_gate.py
"""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SCRATCH = Path(tempfile.mkdtemp(prefix="litsshp-session-gate-"))
CONFIG = SCRATCH / ".ssh" / "config"
STATE = SCRATCH / "state.json"
LOGS = SCRATCH / "logs"

# The pixel checks need a real font database. Qt's offscreen plugin on Windows
# loads no families at all, so every glyph becomes a tofu box drawn over the
# very cell the probes read; the native plugin has the system fonts. No window
# is shown either way - only a QGuiApplication and a rasterised QImage exist.
os.environ.setdefault("QT_QPA_PLATFORM",
                      "windows" if os.name == "nt" else "offscreen")
os.environ.setdefault("QT_QUICK_BACKEND", "software")
os.environ["LITSSHP_CONFIG"] = str(CONFIG)
os.environ["LITSSHP_STATE"] = str(STATE)
os.environ["LITSSHP_LOGS"] = str(LOGS)

sys.path.insert(0, str(ROOT))

from PySide6.QtGui import QColor, QGuiApplication  # noqa: E402

from app.config import ConfigStore  # noqa: E402
from app.terminal_model import TerminalModel  # noqa: E402

failures: list[str] = []


def check(name: str, condition: bool, detail: str = "") -> None:
    print(("PASS " if condition else "FAIL ") + name + (f"  [{detail}]" if detail else ""))
    if not condition:
        failures.append(name)


ORIGINAL = (
    "Host plain\r\n"
    "    HostName 10.0.0.1\r\n"
    "    #!! Password hunter2\r\n"
    "Host encoded\r\n"
    "    HostName 10.0.0.2\r\n"
    "    #!! encPassword 756b17766f45bdc44c37f811db9990b0880318d5f00f6531b15e068ef1fde2666550\r\n"
    "Host cmd\r\n"
    "    HostName 10.0.0.3\r\n"
    "    #!! PasswordCommand echo secret\r\n"
)
BASE = dict(port="22", user="", identity_file="", proxy_jump="",
            proxy_command="", group_labels="")


def block(text: str, alias: str) -> str:
    """One ``Host`` block's text, so a check never reads another host's lines."""
    collected: list[str] = []
    inside = False
    for line in text.splitlines():
        if line.lower().startswith("host "):
            if inside:
                break
            inside = alias in line.split()[1:]
            if not inside:
                continue
        if inside:
            collected.append(line)
    return "\n".join(collected)


def password_checks(store: ConfigStore) -> None:
    CONFIG.write_text(ORIGINAL, encoding="utf-8")
    store.reload()

    plain = next(h for h in store.hosts() if h.alias == "plain")
    command = next(h for h in store.hosts() if h.alias == "cmd")
    check("plain password is read", store.password("plain") == "hunter2")
    check("plain source is reported", plain.password_source == "plain")
    check("PasswordCommand counts as stored", command.has_password)

    store.update_host("plain", dict(BASE, alias="plain", hostname="10.0.0.1",
                                    password="hunter3", password_source="plain"))
    text = block(CONFIG.read_text(encoding="utf-8"), "plain")
    check("plain stays plain", "#!! Password hunter3" in text
          and "encPassword" not in text)
    check("plain value is read back", store.password("plain") == "hunter3")

    store.update_host("plain", dict(BASE, alias="plain", hostname="10.0.0.1",
                                    password="hunter3", password_source="encrypted"))
    text = block(CONFIG.read_text(encoding="utf-8"), "plain")
    check("plain converts to encrypted", "#!! encPassword" in text
          and "#!! Password " not in text)
    check("encrypted value is read back", store.password("plain") == "hunter3")

    store.update_host("encoded", dict(BASE, alias="encoded", hostname="10.0.0.2",
                                      password="", password_source="encrypted"))
    text = block(CONFIG.read_text(encoding="utf-8"), "encoded")
    check("clearing removes both forms",
          "encPassword" not in text and "encQuestionAnswer1" not in text)

    store.update_host("cmd", dict(BASE, alias="cmd", hostname="10.0.0.3",
                                  password="", password_source="command"))
    check("clearing keeps PasswordCommand",
          "#!! PasswordCommand echo secret" in CONFIG.read_text(encoding="utf-8"))

    # StartupCommand is the host editor's own field; it must round-trip and be
    # removable, otherwise the field is decorative.
    store.update_host("plain", dict(BASE, alias="plain", hostname="10.0.0.1",
                                    startup_command="cd /srv/app && tmux attach"))
    text = block(CONFIG.read_text(encoding="utf-8"), "plain")
    check("startup command is written",
          "#!! StartupCommand cd /srv/app && tmux attach" in text)
    check("startup command is read back",
          next(h for h in store.hosts() if h.alias == "plain").startup_command
          == "cd /srv/app && tmux attach")
    store.update_host("plain", dict(BASE, alias="plain", hostname="10.0.0.1",
                                    startup_command=""))
    check("clearing removes the startup command",
          "StartupCommand" not in block(CONFIG.read_text(encoding="utf-8"), "plain"))

    # A new host goes through add_host/_fields_to_options instead of the
    # update path, so it needs its own check.
    store.add_host(dict(BASE, alias="fresh", hostname="10.0.0.4",
                        startup_command="uptime"))
    check("new host keeps its startup command",
          "#!! StartupCommand uptime" in block(CONFIG.read_text(encoding="utf-8"), "fresh"))


def key_checks() -> None:
    """Fingerprints and known_hosts removal, all inside the scratch folder."""
    import shutil
    import subprocess

    from app import keys

    ssh_home = SCRATCH / ".ssh"
    ssh_home.mkdir(parents=True, exist_ok=True)
    key_path = ssh_home / "gate_ed25519"
    if key_path.exists():
        key_path.unlink()
    if Path(str(key_path) + ".pub").exists():
        Path(str(key_path) + ".pub").unlink()

    result = keys.generate_key(str(key_path), "gate", "", "ed25519")
    check("a key can be generated", result.get("ok") is True, str(result.get("error", "")))
    if not result.get("ok"):
        return
    # On Windows os.chmod only toggles the read-only bit (ssh-keygen sets the
    # ACL itself), so the mode check is only meaningful on POSIX.
    if os.name != "nt":
        check("the private half is not world-readable",
              (key_path.stat().st_mode & 0o077) == 0,
              oct(key_path.stat().st_mode & 0o777))
    else:
        check("the private half exists and is writable",
              key_path.is_file() and os.access(key_path, os.W_OK))
    check("a second generation is refused",
          keys.generate_key(str(key_path), "", "", "ed25519").get("ok") is False)

    listed = {item["name"]: item for item in keys.list_keys(ssh_home)}
    entry = listed.get("gate_ed25519", {})
    check("the key is listed", bool(entry), ", ".join(sorted(listed)))
    check("the listed fingerprint is SHA256", entry.get("fingerprint", "").startswith("SHA256:"))

    # Compare against the tool that OpenSSH users check with. If it is not
    # installed the local computation is still asserted above, but say so.
    tool = shutil.which("ssh-keygen")
    if tool:
        out = subprocess.run([tool, "-lf", str(key_path) + ".pub"],
                             capture_output=True, text=True, timeout=20).stdout
        expected = out.split()[1] if len(out.split()) > 1 else ""
        check("the fingerprint matches ssh-keygen -lf",
              expected == entry.get("fingerprint"),
              f"{expected} vs {entry.get('fingerprint')}")
    else:
        print("SKIP ssh-keygen is not installed; fingerprint compared locally only")

    public = keys.read_public(key_path)
    check("the public half is readable", public.startswith("ssh-ed25519 "))

    known = ssh_home / "known_hosts"
    good = "example.com ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIN7YQ0m6G7K1pQ0GkZ0m0m0m0m0m0m0m0m0m0m0m0m0"
    other = "other.example ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAII7YQ0m6G7K1pQ0GkZ0m0m0m0m0m0m0m0m0m0m0m0m0"
    known.write_text(good + "\n" + other + "\n", encoding="utf-8")
    rows = keys.known_hosts_entries(known)
    check("known_hosts rows are listed", len(rows) == 2, str(len(rows)))
    check("a row reports its key type", rows[0].get("type") == "ED25519", rows[0].get("type"))

    removed = keys.remove_known_hosts("example.com", path=known)
    check("a named entry can be removed", removed.get("ok") is True, str(removed))
    remaining = known.read_text(encoding="utf-8")
    check("only the named entry is gone",
          "example.com" not in remaining.split()[0] and "other.example" in remaining)
    check("a backup is kept", known.with_name(known.name + ".old").exists())

    # A hashed row has no readable name; removal by line is the only path.
    known.write_text(good + "\n" + other + "\n", encoding="utf-8")
    rows = keys.known_hosts_entries(known)
    removed = keys.remove_known_hosts("", path=known, line=rows[0]["line"])
    check("a hashed-style entry can be removed by line",
          removed.get("ok") is True, str(removed))
    remaining = known.read_text(encoding="utf-8")
    check("removing by line leaves the other row",
          "other.example" in remaining and good not in remaining)

    deleted = keys.delete_key(str(key_path))
    check("a key pair can be deleted", deleted.get("ok") is True, str(deleted))
    check("both halves are gone",
          not key_path.exists() and not Path(str(key_path) + ".pub").exists())


def render_checks() -> None:
    """Selection and search paint as overlays, not as reverse video."""
    model = TerminalModel(9003)
    model.setViewport(600, 240, 1.0)
    model.feed("hello world\r\n")
    model.applyTheme("#ffffff", "#000000", "#00ff00", "#80ff0000",
                     ["#000000"] * 16)
    cell_h = int(model._cell_h)
    # A cell past the end of "hello world" but inside the selected row, so the
    # probe sees a background fill rather than glyph pixels.
    probe_x = int(4 + model._cell_w * 20)
    probe_y = 2 + cell_h // 2

    def pixel(image) -> str:
        return QColor(image.pixel(probe_x, probe_y)).name(QColor.HexArgb)

    model._render()
    plain = pixel(model.image())
    model.selectAll()
    model._render()
    selected = pixel(model.image())
    check("selection changes the cell background", selected != plain,
          f"{plain} → {selected}")
    # #80ff0000 over black is roughly #ff800000: the themed alpha colour, not
    # a reversal of the cell's own colours.
    check("selection uses the themed overlay colour",
          selected.lower().endswith("800000"), selected)

    model.clearSelection()
    model.setSearch("world")
    model._render()
    # Probe a column inside "world" (columns 6-10), past the glyph pixels.
    search_x = int(4 + model._cell_w * 8)
    marked = QColor(model.image().pixel(search_x, probe_y)).name(QColor.HexArgb)
    check("search marks the matching cells", marked != plain, f"{plain} → {marked}")
    model.clearSearch()

    model.detachLog()


def search_checks() -> None:
    model = TerminalModel(9001)
    model.feed("alpha beta gamma\r\nsecond alpha line\r\nno match here\r\n")
    model.setSearch("alpha")
    check("search finds every hit", model.searchCount == 2, str(model.searchCount))
    check("search selects the newest hit", model.searchCurrent == 2)

    model.nextMatch(1)
    check("next wraps to the first", model.searchCurrent == 1)
    model.nextMatch(-1)
    check("previous wraps back", model.searchCurrent == 2)

    model.setSearch("ALPHA")
    check("search is case-insensitive by default", model.searchCount == 2)
    model.setSearch("ALPHA", True)
    check("case-sensitive search finds none", model.searchCount == 0)

    model.clearSearch()
    check("clearing the search removes hits",
          model.searchQuery == "" and model.searchCount == 0)


def log_checks() -> None:
    LOGS.mkdir(parents=True, exist_ok=True)
    path = LOGS / "unit.log"
    with open(path, "w", encoding="utf-8") as handle:
        model = TerminalModel(9002)
        model.attachLog(handle)
        model.feed("\x1b[31mred\x1b[0m text\r\n")
        model.feed("progress 10%\rprogress 90%\r\ndone\r\n")
        # The live file must be current while the session is still running,
        # not only after detach: the timer is what makes that true.
        model.flushLog()
        live = path.read_text(encoding="utf-8")
        check("the log is written while the session is alive", "done" in live, repr(live[:40]))
        model.detachLog()
    text = path.read_text(encoding="utf-8")
    check("log drops escape sequences", "\x1b" not in text, repr(text[:40]))
    check("log keeps the printable text", "red text" in text and "done" in text)
    check("log keeps the last carriage-return revision",
          "progress 90%" in text and "progress 10%" not in text)


def wide_cell_checks() -> None:
    """A full-width character owns two columns; the next cell is a stub."""
    from app.terminal_model import TerminalModel as Model
    from app.terminal_model import _cell_span, _row_text

    model = Model(9004)
    model.setViewport(600, 240, 1.0)
    model.setFont("Cascadia Mono", 16, "")
    model.applyTheme("#ffffff", "#000000", "#00ff00", "#80ff0000",
                     ["#000000"] * 16)
    model._cursor_on = False
    model.feed("AB中文CD\r\n")

    row = model._screen.history_view(0)[0]
    check("a wide glyph reports two columns", _cell_span(row[2]) == 2)
    check("the cell after a wide glyph is a stub", _cell_span(row[3]) == 0)

    text, columns, spans = _row_text(row)
    check("row text skips the stub cells", text.startswith("AB中文CD"), repr(text[:8]))
    check("characters map to their real columns",
          columns[:6] == [0, 1, 2, 4, 6, 7], str(columns[:6]))
    check("wide characters map to two-column spans",
          spans[:6] == [1, 1, 2, 2, 1, 1], str(spans[:6]))

    model._render()
    image = model.image()
    cell_w, cell_h = model._cell_w, int(model._cell_h)

    def ink(col: int) -> bool:
        x0 = int(4 + col * cell_w)
        x1 = int(4 + (col + 1) * cell_w)
        return any((image.pixel(x, y) & 0xFFFFFF) != 0
                   for y in range(cell_h) for x in range(x0, x1))

    check("glyphs stay on the column grid", all(ink(col) for col in range(8)),
          str([c for c in range(10) if ink(c)]))
    check("nothing is painted past the last character", not ink(8))

    model.selectAll()
    check("selection text rebuilds the wide characters",
          model.selectedText().startswith("AB中文CD"), repr(model.selectedText()[:8]))
    model.clearSelection()

    model.setSearch("文C")
    check("search maps a match after a wide glyph to its column",
          model.searchCount == 1 and model._search_hits[0] == (0, 4, 3),
          str(model._search_hits))
    model.setSearch("中文")
    check("a search hit spanning two wide glyphs covers four columns",
          model._search_hits[0] == (0, 2, 4), str(model._search_hits))
    model.clearSearch()
    model.detachLog()


class _StubRaw:
    """A raw font that covers everything but CJK, for a font-independent test."""

    def supportsCharacter(self, ch: str) -> bool:
        return not ("\u4e00" <= ch <= "\u9fff")


def fallback_checks() -> None:
    """The configured fallback, and only it, supplies glyphs the primary lacks.

    ``QFont.setFamilies`` looks like the right tool but is a *resolution*
    order: Qt still picks the system CJK font for a missing glyph. The model
    therefore tests coverage per character. This gate replaces the raw font
    with a stub so the decision is checked on any machine, whatever fonts are
    installed.
    """
    from app.terminal_model import TerminalModel as Model

    model = Model(9005)
    model.setViewport(600, 240, 1.0)
    model.setFont("Cascadia Mono", 16, "Microsoft YaHei")
    model.applyTheme("#ffffff", "#000000", "#00ff00", "#80ff0000",
                     ["#000000"] * 16)
    model._cursor_on = False

    check("the fallback family is kept", model._fallback == "Microsoft YaHei",
          model._fallback)
    check("a fallback equal to the primary is ignored",
          (model.setFont("Cascadia Mono", 16, "Cascadia Mono")
           or model._fallback) == "")
    model.setFont("Cascadia Mono", 16, "Microsoft YaHei")

    model._raw_primary = _StubRaw()
    model._glyph_cache = {}
    check("a covered glyph does not need the fallback",
          model._needs_fallback("ABC") is False)
    check("a glyph the primary lacks needs the fallback",
          model._needs_fallback("中") is True)
    check("the coverage answer is cached", "中" in model._glyph_cache)

    style = model._screen.history_view(0)[0][0]
    check("a covered glyph uses the primary font",
          model._font_for(style, "A") is model._font)
    check("a missing glyph uses the fallback font",
          model._font_for(style, "中") is model._fallback_font)
    check("bold and italic keep their own fallback faces",
          model._fallback_bold.family() == "Microsoft YaHei"
          and model._fallback_italic.family() == "Microsoft YaHei"
          and model._fallback_bold_italic.family() == "Microsoft YaHei")

    # Without a fallback nothing is substituted and the decision is always
    # false, so the renderer never reaches for a second font.
    model.setFont("Cascadia Mono", 16, "")
    model._raw_primary = _StubRaw()
    check("with no fallback configured nothing is substituted",
          model._needs_fallback("中") is False)

    # A row that mixes scripts must be split into runs at the fallback
    # boundary, or the whole run would be drawn in one font.
    model.setFont("Cascadia Mono", 16, "Microsoft YaHei")
    model._raw_primary = _StubRaw()
    model._glyph_cache = {}
    model.feed("AB中文CD\r\n")
    model._scrollback = 0
    calls: list[str] = []
    original = model._font_for

    def spy(attr, text: str = ""):
        if text:
            calls.append(text)
        return original(attr, text)

    model._font_for = spy
    model._render()
    model._font_for = original
    check("only the missing glyphs get a per-glyph font",
          [c for c in calls if c.strip()] == ["中", "文"],
          str([c for c in calls if c.strip()]))
    model.detachLog()


def setting_checks() -> None:
    from app.controller import DEFAULT_SETTINGS, AppController

    check("fontFallback has a default", "fontFallback" in DEFAULT_SETTINGS,
          str(DEFAULT_SETTINGS.get("fontFallback")))
    cjk = DEFAULT_SETTINGS.get("fontFallback") or ""
    if cjk:
        from PySide6.QtGui import QFont, QRawFont
        check("the default fallback can render Chinese",
              QRawFont.fromFont(QFont(cjk)).supportsCharacter("中"), cjk)

    controller = AppController()
    offered = controller.fallbackFonts()
    check("the fallback picker returns a list", isinstance(offered, list),
          str(type(offered).__name__))
    if offered:
        from PySide6.QtGui import QFont, QRawFont
        check("every offered fallback renders Chinese",
              all(QRawFont.fromFont(QFont(name)).supportsCharacter("中")
                  for name in offered), str(offered[:3]))
        check("the default resolves to an installed family",
              controller.settings.get("fontFallback") in offered,
              str(controller.settings.get("fontFallback")))
    controller.setSetting("fontFallback", "KaiTi")
    check("the fallback setting persists",
          controller.settings.get("fontFallback") == "KaiTi"
          and '"fontFallback": "KaiTi"' in STATE.read_text(encoding="utf-8"))
    controller.shutdown()

    # An install whose default family is absent must not keep pointing at it:
    # _default_fallback() picks the first family the picker offers instead.
    saved = dict(DEFAULT_SETTINGS)
    DEFAULT_SETTINGS["fontFallback"] = "No Such CJK Family 12345"
    try:
        fallback = AppController._default_fallback()
    finally:
        DEFAULT_SETTINGS.clear()
        DEFAULT_SETTINGS.update(saved)
    if offered:
        check("a missing default is replaced by an installed family",
              fallback in offered, repr(fallback))
    else:
        check("a missing default degrades to no fallback", fallback == "",
              repr(fallback))


def filename_checks() -> None:
    from app.controller import _safe_name

    check("an alias becomes a usable file name", _safe_name("prod/web*01") == "prod_web_01",
          _safe_name("prod/web*01"))
    check("a name of only separators still yields a file", _safe_name("***") == "session",
          _safe_name("***"))


def layout_checks() -> None:
    from app.controller import AppController

    CONFIG.write_text("Host alpha\r\n    HostName 10.0.0.1\r\n"
                      "Host beta\r\n    HostName 10.0.0.2\r\n", encoding="utf-8")
    if STATE.exists():
        STATE.unlink()

    first = AppController()
    first._saved_layout = {"tabs": ["alpha", "beta"], "active": 1, "split": 0}
    first._save_state()
    check("layout is written to state", '"layout"' in STATE.read_text(encoding="utf-8"))

    second = AppController()
    check("layout survives a restart", second.canRestore)
    second._saved_layout = {"tabs": ["missing", "alpha"], "active": 0, "split": -1}
    result = second.restoreLayout()
    check("restore skips an unknown host",
          result.get("ok") is True and result.get("opened") == 1, str(result))
    check("restore opened the known host",
          [tab.host for tab in second._tabs] == ["alpha"])
    second.shutdown()


def main() -> int:
    CONFIG.parent.mkdir(parents=True, exist_ok=True)
    app = QGuiApplication(sys.argv)          # noqa: F841 - needed for QObjects

    password_checks(ConfigStore())
    key_checks()
    search_checks()
    render_checks()
    wide_cell_checks()
    fallback_checks()
    log_checks()
    filename_checks()
    layout_checks()
    setting_checks()

    print()
    if failures:
        print(f"FAIL session features gate ({len(failures)} failing checks)")
        return 1
    print("PASS session features gate")
    return 0


if __name__ == "__main__":
    sys.exit(main())
