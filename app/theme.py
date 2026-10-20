"""Pebrel-style theme catalog and token resolution.

Themes are **user-editable YAML files** in the application's data directory
(``paths.state_dir()/themes``), not in ``~/.ssh``. On first launch the built-in
catalog is written there once; after that the files on disk are the truth, so a
user can retune a palette or add a variant without touching the source. Files
that are missing are re-seeded, files that exist are never overwritten.

Two families ship:

* ``catppuccin`` — Mocha (dark) and Latte (light).
* ``mono`` — a greyscale pair for people who want the chrome to disappear.

Each file describes one *member* (one appearance). A family is the pair of
members sharing a ``family`` id, which is what lets "follow system" switch
appearance without changing the user's chosen family.

Three consumers share this module so they cannot drift apart:

* ``style.py`` turns a palette into the Material-role map QML already reads
  through ``Theme.color``.
* ``terminal_theme.py`` builds the terminal palette from the same palette, so
  the shell and the grid are one surface.
* ``Theme.skin`` in QML exposes the Pebrel-only tokens (ink ladder, accent
  wash, hairline alpha, radii, row heights).

Colour parsing and token building are pure functions with no Qt imports, so a
palette can be exercised without a display.

YAML schema
-----------
::

    id: catppuccin-mocha          # unique; stored in state.json
    label: Catppuccin Mocha       # shown in the picker
    family: catppuccin            # groups the dark/light pair
    family_label: Catppuccin      # optional; defaults to a title-cased family
    appearance: dark              # dark | light

    colors:
      shell: "#181825"            # window chrome
      surface: "#1e1e2e"          # content plane and terminal grid
      foreground: "#cdd6f4"       # primary ink
      muted: "#a6adc8"            # secondary ink and icons
      accent: "#b4befe"           # selection and primary actions
      selected: "#313244"         # selected-row base colour
      line: "#45475a"             # divider base colour
      selected_alpha: 1.0         # optional, default 1.0
      line_alpha: 1.0             # optional, default 1.0
      red: "#f38ba8"              # semantic inks; never follow the accent
      green: "#a6e3a1"
      yellow: "#f9e2af"
      blue: "#89b4fa"
      purple: "#cba6f7"
      cyan: "#94e2d5"
      frame: "#6c7086"            # outline / border colour

    terminal:
      ansi: ["#45475a", ...]      # exactly 16 entries, normal then bright

A file that fails to parse is skipped with a message in ``load_errors()``; the
rest of the catalog still loads, and the app falls back to the built-in palette
for that id.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from . import paths

RGB = tuple[int, int, int]


# ---------------------------------------------------------------------------
# Palette model
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Palette:
    """One theme member's audited colours.

    ``shell`` is the window chrome base (sidebar, top bar) and ``surface`` is
    the content/terminal card that sits on it. ``selected`` and ``line`` carry
    alpha, exactly as the YAML declares them.
    """

    name: str
    label: str
    family: str
    family_label: str
    shell: str
    surface: str
    foreground: str
    muted: str
    accent: str
    selected: tuple[str, float]
    line: tuple[str, float]
    red: str
    green: str
    yellow: str
    blue: str
    purple: str
    cyan: str
    frame: str
    is_light: bool
    ansi: tuple[str, ...]


# ---------------------------------------------------------------------------
# Built-in catalog (seeded to disk on first run)
# ---------------------------------------------------------------------------

_BUILTIN: dict[str, str] = {
    "catppuccin-mocha.yaml": """\
# Catppuccin Mocha — the dark member of the Catppuccin family.
# Edit any value, then Settings → Appearance → Reload themes.
id: catppuccin-mocha
label: Catppuccin Mocha
family: catppuccin
family_label: Catppuccin
appearance: dark

colors:
  shell: "#181825"      # window chrome: sidebar, tab strip, status bar
  surface: "#1e1e2e"    # content plane and terminal grid
  foreground: "#cdd6f4" # primary ink
  muted: "#a6adc8"      # secondary ink and icons
  accent: "#b4befe"     # selection and primary actions
  selected: "#313244"   # selected-row base colour
  line: "#45475a"       # divider base colour
  red: "#f38ba8"
  green: "#a6e3a1"
  yellow: "#f9e2af"
  blue: "#89b4fa"
  purple: "#cba6f7"
  cyan: "#94e2d5"
  frame: "#6c7086"      # outline / border colour

terminal:
  ansi:
    - "#45475a"
    - "#f38ba8"
    - "#a6e3a1"
    - "#f9e2af"
    - "#89b4fa"
    - "#f5c2e7"
    - "#94e2d5"
    - "#bac2de"
    - "#585b70"
    - "#f38ba8"
    - "#a6e3a1"
    - "#f9e2af"
    - "#89b4fa"
    - "#f5c2e7"
    - "#94e2d5"
    - "#a6adc8"
""",
    "catppuccin-latte.yaml": """\
# Catppuccin Latte — the light member of the Catppuccin family.
id: catppuccin-latte
label: Catppuccin Latte
family: catppuccin
family_label: Catppuccin
appearance: light

colors:
  shell: "#e6e9ef"
  surface: "#eff1f5"
  foreground: "#4c4f69"
  muted: "#5c5f77"
  accent: "#7287fd"
  selected: "#ccd0da"
  line: "#bcc0cc"
  red: "#d20f39"
  green: "#40a02b"
  yellow: "#df8e1d"
  blue: "#1e66f5"
  purple: "#8839ef"
  cyan: "#179299"
  frame: "#9ca0b0"

terminal:
  ansi:
    - "#5c5f77"
    - "#d20f39"
    - "#40a02b"
    - "#df8e1d"
    - "#1e66f5"
    - "#ea76cb"
    - "#179299"
    - "#acb0be"
    - "#6c6f85"
    - "#d20f39"
    - "#40a02b"
    - "#df8e1d"
    - "#1e66f5"
    - "#ea76cb"
    - "#179299"
    - "#bcc0cc"
""",
    "mono-dark.yaml": """\
# Mono Dark — greyscale chrome and a grey ANSI ramp.
# With no hue to work with, the semantic inks and the accent are separated by
# brightness instead: a status dot or a warning still reads as "louder" or
# "quieter" even though everything is grey.
id: mono-dark
label: Mono Dark
family: mono
family_label: Mono
appearance: dark

colors:
  shell: "#121212"
  surface: "#1a1a1a"
  foreground: "#ececec"
  muted: "#9b9b9b"
  accent: "#c4c4c4"      # selection + primary actions
  selected: "#2a2a2a"
  line: "#333333"
  red: "#ffffff"         # danger: the brightest step is the loudest
  green: "#7e7e7e"       # ok: quiet
  yellow: "#9a9a9a"      # warn: one step above ok
  blue: "#8c8c8c"        # info
  purple: "#a8a8a8"
  cyan: "#b0b0b0"
  frame: "#5c5c5c"

terminal:
  ansi:
    - "#3d3d3d"
    - "#b5b5b5"
    - "#9a9a9a"
    - "#d0d0d0"
    - "#868686"
    - "#c0c0c0"
    - "#a8a8a8"
    - "#dcdcdc"
    - "#6b6b6b"
    - "#d8d8d8"
    - "#bfbfbf"
    - "#f0f0f0"
    - "#a0a0a0"
    - "#e0e0e0"
    - "#c8c8c8"
    - "#ffffff"
""",
    "mono-light.yaml": """\
# Mono Light — greyscale chrome on a near-white plane.
# Same rule as Mono Dark with the ladder inverted: darker is louder.
id: mono-light
label: Mono Light
family: mono
family_label: Mono
appearance: light

colors:
  shell: "#f2f2f2"
  surface: "#fafafa"
  foreground: "#1a1a1a"
  muted: "#6a6a6a"
  accent: "#4a4a4a"      # selection + primary actions
  selected: "#e4e4e4"
  line: "#d6d6d6"
  red: "#111111"         # danger: darkest step
  green: "#8a8a8a"       # ok: quiet
  yellow: "#6e6e6e"      # warn: one step above ok
  blue: "#5c5c5c"        # info
  purple: "#666666"
  cyan: "#626262"
  frame: "#a0a0a0"

terminal:
  ansi:
    - "#3a3a3a"
    - "#545454"
    - "#767676"
    - "#4a4a4a"
    - "#8a8a8a"
    - "#5e5e5e"
    - "#6a6a6a"
    - "#2e2e2e"
    - "#8a8a8a"
    - "#3c3c3c"
    - "#5a5a5a"
    - "#2a2a2a"
    - "#767676"
    - "#484848"
    - "#606060"
    - "#222222"
""",
}

DEFAULT_FAMILY = "catppuccin"

_COLOUR_KEYS = (
    "shell", "surface", "foreground", "muted", "accent", "selected", "line",
    "red", "green", "yellow", "blue", "purple", "cyan", "frame",
)
_REQUIRED = ("id", "family", "appearance")


# ---------------------------------------------------------------------------
# Loading
# ---------------------------------------------------------------------------


def theme_dir() -> Path:
    """Where theme YAML lives: the app's data directory, never ``~/.ssh``."""
    return paths.themes_dir()


def load_errors() -> list[str]:
    """Problems found while loading; empty when every file parsed."""
    return list(_ERRORS)


def _seed() -> None:
    """Write the built-in YAML once; never touch a file that already exists."""
    target = theme_dir()
    try:
        target.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        _ERRORS.append(f"cannot create {target}: {exc}")
        return
    for name, text in _BUILTIN.items():
        path = target / name
        if path.exists():
            continue
        try:
            path.write_text(text, encoding="utf-8")
        except OSError as exc:
            _ERRORS.append(f"cannot write {path.name}: {exc}")


def _is_colour(value: object) -> bool:
    if not isinstance(value, str):
        return False
    text = value.strip().lstrip("#")
    if len(text) not in (6, 8):
        return False
    try:
        int(text, 16)
    except ValueError:
        return False
    return True


def _colour(colors: dict, key: str, source: str) -> str:
    value = colors.get(key)
    if not _is_colour(value):
        raise ValueError(f"{source}: colors.{key} is not a hex colour")
    text = str(value).strip()
    return text if text.startswith("#") else "#" + text


def _alpha(colors: dict, key: str) -> float:
    value = colors.get(key, 1.0)
    try:
        number = float(value)
    except (TypeError, ValueError):
        return 1.0
    return max(0.0, min(1.0, number))


def _parse(data: object, source: str) -> Palette:
    if not isinstance(data, dict):
        raise ValueError(f"{source}: expected a mapping at the top level")
    for key in _REQUIRED:
        if not data.get(key):
            raise ValueError(f"{source}: missing '{key}'")

    colors = data.get("colors")
    if not isinstance(colors, dict):
        raise ValueError(f"{source}: missing 'colors' mapping")

    appearance = str(data.get("appearance", "")).strip().lower()
    if appearance not in ("dark", "light"):
        raise ValueError(f"{source}: appearance must be 'dark' or 'light'")

    terminal = data.get("terminal") or {}
    ansi = terminal.get("ansi") if isinstance(terminal, dict) else None
    if not isinstance(ansi, list) or len(ansi) != 16:
        raise ValueError(f"{source}: terminal.ansi must list exactly 16 colours")
    for entry in ansi:
        if not _is_colour(entry):
            raise ValueError(f"{source}: terminal.ansi contains a bad colour")

    family = str(data["family"]).strip()
    name = str(data["id"]).strip()
    # Default to a readable name rather than the raw id: a family added by hand
    # often omits family_label, and "nordic-blue" is a poor button caption.
    family_label = str(data.get("family_label") or family.replace("-", " ").title()).strip()

    return Palette(
        name=name,
        label=str(data.get("label") or name),
        family=family,
        family_label=family_label,
        shell=_colour(colors, "shell", source),
        surface=_colour(colors, "surface", source),
        foreground=_colour(colors, "foreground", source),
        muted=_colour(colors, "muted", source),
        accent=_colour(colors, "accent", source),
        selected=(_colour(colors, "selected", source), _alpha(colors, "selected_alpha")),
        line=(_colour(colors, "line", source), _alpha(colors, "line_alpha")),
        red=_colour(colors, "red", source),
        green=_colour(colors, "green", source),
        yellow=_colour(colors, "yellow", source),
        blue=_colour(colors, "blue", source),
        purple=_colour(colors, "purple", source),
        cyan=_colour(colors, "cyan", source),
        frame=_colour(colors, "frame", source),
        is_light=appearance == "light",
        ansi=tuple(str(entry).strip() for entry in ansi),
    )


def _group(palettes: dict[str, Palette]) -> list[dict[str, str]]:
    """Pair members into families, in file order.

    A family with only one member uses that member for both appearances, so a
    hand-written single-variant theme still works with "follow system".
    """
    order: list[str] = []
    members: dict[str, dict[str, str]] = {}
    for palette in palettes.values():
        if palette.family not in members:
            members[palette.family] = {}
            order.append(palette.family)
        key = "light" if palette.is_light else "dark"
        members[palette.family].setdefault(key, palette.name)

    out: list[dict[str, str]] = []
    for family in order:
        pair = members[family]
        only = pair.get("dark") or pair.get("light") or ""
        out.append({
            "id": family,
            "label": palettes[only].family_label,
            "dark": pair.get("dark", only),
            "light": pair.get("light", only),
        })
    return out


def _builtin_palettes() -> dict[str, Palette]:
    """The seeded catalog, parsed straight from the strings above."""
    import yaml

    out: dict[str, Palette] = {}
    for index, text in enumerate(_BUILTIN.values()):
        palette = _parse(yaml.safe_load(text), f"built-in #{index + 1}")
        out[palette.name] = palette
    return out


def load() -> tuple[dict[str, Palette], list[dict[str, str]], list[str]]:
    """Read the theme directory, falling back to the built-ins for bad files."""
    errors: list[str] = []
    palettes = _builtin_palettes()

    try:
        import yaml
    except ImportError as exc:  # pragma: no cover - declared in requirements
        errors.append(f"PyYAML is unavailable ({exc}); using the built-in themes")
        return palettes, _group(palettes), errors

    _seed()
    for path in sorted(theme_dir().glob("*")):
        if path.suffix.lower() not in (".yaml", ".yml") or not path.is_file():
            continue
        try:
            palette = _parse(yaml.safe_load(path.read_text(encoding="utf-8")),
                             path.name)
        except Exception as exc:
            # A YAML syntax error is raised before _parse can add the file
            # name, so prefix only when the message does not already carry it.
            message = str(exc)
            if path.name not in message:
                message = f"{path.name}: {message}"
            errors.append(message)
            continue
        palettes[palette.name] = palette

    return palettes, _group(palettes), errors


PALETTES, FAMILIES, _ERRORS = load()


def reload() -> None:
    """Re-read the theme directory, keeping the module-level maps in place.

    ``style.py`` and ``terminal_theme.py`` hold references to ``PALETTES`` and
    ``FAMILIES``; mutating them instead of rebinding means a reload is visible
    everywhere without re-importing.
    """
    palettes, families, errors = load()
    PALETTES.clear()
    PALETTES.update(palettes)
    FAMILIES[:] = families
    _ERRORS[:] = errors


# ---------------------------------------------------------------------------
# Family lookup
# ---------------------------------------------------------------------------


def family_ids() -> list[str]:
    return [family["id"] for family in FAMILIES]


def normalize_family(value: str | None) -> str:
    """Map a stored string onto a loaded family id.

    Accepts a family id (``catppuccin``) or a member id (``catppuccin-mocha``).
    Retired families from older state files fall back to the default family,
    because their palettes no longer ship.
    """
    wanted = (value or "").strip().lower()
    if not wanted:
        return DEFAULT_FAMILY
    for family in FAMILIES:
        if wanted == family["id"] or wanted in (family["dark"], family["light"]):
            return family["id"]
    return FAMILIES[0]["id"] if FAMILIES else DEFAULT_FAMILY


def family_label(family_id: str) -> str:
    for family in FAMILIES:
        if family["id"] == family_id:
            return family["label"]
    return FAMILIES[0]["label"] if FAMILIES else family_id


def resolve(family: str | None, dark: bool) -> Palette:
    """Pick the family member for the requested appearance."""
    family_id = normalize_family(family)
    for entry in FAMILIES:
        if entry["id"] == family_id:
            name = entry["dark"] if dark else entry["light"]
            if name in PALETTES:
                return PALETTES[name]
    # A catalog that lost its default still has to return something.
    return next(iter(PALETTES.values()))


# ---------------------------------------------------------------------------
# Colour helpers
# ---------------------------------------------------------------------------


def _channels(value: str) -> RGB:
    text = value.lstrip("#")
    if len(text) == 8:  # #AARRGGBB
        text = text[2:]
    if len(text) != 6:
        raise ValueError(f"not a colour: {value!r}")
    return (int(text[0:2], 16), int(text[2:4], 16), int(text[4:6], 16))


def _hex(rgb: RGB) -> str:
    return "#%02x%02x%02x" % rgb


def rgba(value: str, alpha: float) -> str:
    """``#AARRGGBB`` — QML and QColor both parse alpha-first hex."""
    r, g, b = _channels(value)
    a = max(0, min(255, int(round(alpha * 255))))
    return "#%02X%02X%02X%02X" % (a, r, g, b)


def blend(base: str, over: str, alpha: float) -> str:
    """Composite ``over`` at ``alpha`` on top of an opaque ``base``."""
    br, bg, bb = _channels(base)
    orr, og, ob = _channels(over)
    return _hex((
        int(round(br + (orr - br) * alpha)),
        int(round(bg + (og - bg) * alpha)),
        int(round(bb + (ob - bb) * alpha)),
    ))


def lift(value: str, amount: float = 14.0) -> str:
    """Pebrel's proportional lift: scale channels by the same factor.

    Adding a constant washes out the cool tint; multiplying keeps the channel
    ratios and therefore the theme's temperature.
    """
    rgb = _channels(value)
    average = max(1.0, sum(rgb) / 3.0)
    factor = (average + amount) / average
    return _hex(tuple(min(255, int(round(c * factor))) for c in rgb))  # type: ignore[arg-type]


def darken(value: str, factor: float) -> str:
    return _hex(tuple(max(0, int(round(c * factor))) for c in _channels(value)))  # type: ignore[arg-type]


def luminance(value: str) -> float:
    def channel(raw: float) -> float:
        c = raw / 255.0
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4

    r, g, b = _channels(value)
    return 0.2126 * channel(r) + 0.7152 * channel(g) + 0.0722 * channel(b)


def contrast(first: str, second: str) -> float:
    a, b = luminance(first), luminance(second)
    high, low = max(a, b), min(a, b)
    return (high + 0.05) / (low + 0.05)


def ensure_contrast(text: str, background: str, minimum: float = 4.5) -> str:
    """Darken (light theme) or lighten (dark theme) until readable.

    The audited palettes already pass, but a hand-edited YAML or an accent
    override must not produce unreadable text. If moving away from the plane
    saturates (white on a mid-luminance accent, say) the other direction is
    tried before falling back to pure black or white.
    """
    if contrast(text, background) >= minimum:
        return text
    dark_plane = luminance(background) < 0.45
    for lighten in ((True, False) if dark_plane else (False, True)):
        candidate = text
        for _ in range(24):
            candidate = lift(candidate, 12.0) if lighten else darken(candidate, 0.9)
            if contrast(candidate, background) >= minimum:
                return candidate
    return "#ffffff" if dark_plane else "#000000"


# A near-black neutral for glyphs on a mid-luminance accent, where neither
# white nor the plane colour reaches 4.5:1. Catppuccin Latte's #7287fd is the
# case that needs it (white manages only 3.2:1).
DEEP_INK = "#11111b"


def accent_ink(accent: str, surface: str, is_light: bool) -> str:
    """Readable glyph colour for text sitting on a filled accent.

    Dark themes reuse the plane colour, which is what Pebrel does and keeps
    the accent feeling like part of the palette. Light themes use white,
    because their accents are dark. When neither reaches 4.5:1 (a saturated
    mid-luminance accent) the deep neutral wins over a washed-out grey.
    """
    preferred = "#ffffff" if is_light else surface
    if contrast(preferred, accent) >= 4.5:
        return preferred
    alternative = DEEP_INK if preferred == "#ffffff" else "#ffffff"
    if contrast(alternative, accent) >= 4.5:
        return alternative
    return ensure_contrast(preferred, accent)


# ---------------------------------------------------------------------------
# Skin (chrome tokens)
# ---------------------------------------------------------------------------

RADIUS_CHIP = 4
RADIUS_CONTROL = 6
RADIUS_ICON_TILE = 7
RADIUS_OVERLAY = 8
RADIUS_LAUNCHER = 14
RADIUS_CARD = 0

CONTROL_HEIGHT = 32
ROW_HEIGHT = 44
DENSE_ROW = 38
HAIRLINE = 1
# Built-in presets ship the *flush* card geometry: radius 0, no gutter, and a
# 1px divider between the sidebar and the content area
# (``ThemeName::card_geometry``). The rounded floating card is the
# user-configurable variant, not the default look.
GUTTER = 0
CARD_DIVIDER = 1


def _planes(palette: Palette) -> tuple[str, str]:
    """Return ``(shell, surface)`` with a visible step between the two planes.

    A palette may declare ``shell == surface``, which renders the whole window
    as one flat tone and erases the structure Pebrel's chrome is built on:
    sidebar and content are separate planes meeting at a hairline. The terminal
    surface must stay exactly as the theme declares it (the grid colour), so the
    *shell* moves instead — a slight darkening on dark themes, which is also
    what the reference screenshots show.
    """
    shell, surface = palette.shell, palette.surface
    if shell.lower() == surface.lower():
        shell = darken(shell, 0.93) if not palette.is_light else darken(shell, 0.97)
    return shell, surface


def skin(palette: Palette, accent_override: str = "") -> dict:
    """Pebrel's chrome skin for one palette.

    Ink ladder: ``ink > inkDim > inkFaint``. ``accentSoft`` is the single
    selected-state wash; ``hairline`` is the translucent separator. Semantic
    colours (danger/ok/warn) never follow the accent.
    """
    accent = accent_override or palette.accent
    shell, surface = _planes(palette)
    ink = ensure_contrast(palette.foreground, surface)
    # Ink ladder: ink > inkDim > inkFaint. Deriving all three from the same
    # `muted` would collapse the ladder on a monochrome palette, where the
    # palette's own greys are already close together, so the faint step is a
    # blend toward the plane and then held at 3:1.
    ink_dim = ensure_contrast(palette.muted, surface)
    ink_faint = ensure_contrast(blend(surface, palette.muted, 0.72), surface, 3.0)
    if ink_faint.lower() == ink_dim.lower():
        ink_faint = blend(surface, ink_dim, 0.82)
        ink_faint = ensure_contrast(ink_faint, surface, 3.0)
    on_accent = accent_ink(accent, surface, palette.is_light)

    # Floating panels sit one step in front of the shell. Dark themes lift,
    # light themes use the neutral card wash instead of a second white.
    if palette.is_light:
        panel = "#ffffff"
        card = rgba("#64748b", 11 / 255)  # slate-500 @ 4.5%
        hover = rgba("#64748b", 33 / 255)
        hover_strong = rgba("#64748b", 52 / 255)
        wash = rgba("#64748b", 20 / 255)
        veil = rgba("#0f172a", 56 / 255)
    else:
        panel = lift(surface)
        card = rgba("#ffffff", 11 / 255)
        hover = rgba("#cbd5e1", 35 / 255)
        hover_strong = rgba("#cbd5e1", 53 / 255)
        wash = rgba("#cbd5e1", 15 / 255)
        veil = rgba("#020617", 92 / 255)

    selected = rgba(accent, 0.15 if palette.is_light else 0.18)
    hairline = rgba(palette.muted, 36 / 255)

    return {
        "name": palette.name,
        "label": palette.label,
        "family": palette.family,
        "isLight": palette.is_light,
        # surfaces
        "shell": shell,
        "surface": surface,
        "panel": panel,
        "card": card,
        "veil": veil,
        "surfaceWash": wash,
        "hover": hover,
        "hoverStrong": hover_strong,
        "hairline": hairline,
        # ink
        "ink": ink,
        "inkDim": ink_dim,
        "inkFaint": ink_faint,
        "inkStrong": ink,
        "inkOnAccent": on_accent,
        "icon": ensure_contrast(palette.muted, surface, 3.0),
        "iconHover": ink,
        # brand + selection
        "accent": accent,
        "accentSoft": selected,
        "accentContrast": on_accent,
        # semantic
        "danger": palette.red,
        "ok": palette.green,
        "warn": palette.yellow,
        "info": palette.blue,
        "frame": palette.frame,
        # geometry ladder
        "radiusChip": RADIUS_CHIP,
        "radiusControl": RADIUS_CONTROL,
        "radiusIconTile": RADIUS_ICON_TILE,
        "radiusOverlay": RADIUS_OVERLAY,
        "radiusLauncher": RADIUS_LAUNCHER,
        "radiusCard": RADIUS_CARD,
        "cardDivider": CARD_DIVIDER,
        "controlHeight": CONTROL_HEIGHT,
        "rowHeight": ROW_HEIGHT,
        "denseRow": DENSE_ROW,
        "hairlineWidth": HAIRLINE,
        "gutter": GUTTER,
    }


# ---------------------------------------------------------------------------
# Material role map (what ``Theme.color`` reads)
# ---------------------------------------------------------------------------


def scheme(palette: Palette, accent_override: str = "") -> dict:
    """Map a Pebrel palette onto the Material role names the QML uses.

    Keeping the role names means every existing page restyles without being
    rewritten; only the values change.
    """
    accent = accent_override or palette.accent
    dark = not palette.is_light
    shell, surface = _planes(palette)
    ink = ensure_contrast(palette.foreground, surface)
    ink_dim = ensure_contrast(palette.muted, surface)
    on_accent = accent_ink(accent, surface, palette.is_light)

    if dark:
        container_lowest = lift(surface, 6)
        container_low = shell
        container = lift(surface, 14)
        container_high = lift(surface, 22)
        container_highest = lift(surface, 30)
    else:
        container_lowest = "#ffffff"
        container_low = shell
        container = blend(surface, "#64748b", 0.045)
        container_high = blend(surface, "#64748b", 0.075)
        container_highest = blend(surface, "#64748b", 0.11)

    primary_container = blend(surface, accent, 0.20 if dark else 0.12)
    on_primary_container = ensure_contrast(accent, primary_container, 4.5)
    secondary_container = blend(surface, palette.muted, 0.14 if dark else 0.10)

    return {
        "primary": accent,
        "onPrimaryColor": on_accent,
        "primaryContainer": primary_container,
        "onPrimaryContainerColor": on_primary_container,
        "secondary": ensure_contrast(palette.muted, surface, 3.0),
        "onSecondaryColor": on_accent,
        "secondaryContainer": secondary_container,
        "onSecondaryContainerColor": ink,
        "tertiary": palette.cyan,
        "onTertiaryColor": on_accent,
        "tertiaryContainer": blend(surface, palette.cyan, 0.16),
        "onTertiaryContainerColor": ensure_contrast(palette.cyan, surface),
        "error": palette.red,
        "onErrorColor": accent_ink(palette.red, surface, palette.is_light),
        "errorContainer": blend(surface, palette.red, 0.16),
        "onErrorContainerColor": ensure_contrast(palette.red, surface),
        "background": shell,
        "onBackgroundColor": ink,
        "surface": surface,
        "onSurfaceColor": ink,
        "surfaceVariant": container_high,
        "onSurfaceVariantColor": ink_dim,
        # Outline is the quiet border; outlineVariant is the hairline wash.
        "outline": ensure_contrast(palette.frame, surface, 3.0),
        "outlineVariant": rgba(palette.muted, 36 / 255),
        "shadow": "#000000",
        "scrim": "#000000",
        "inverseSurface": ink,
        "inverseOnSurface": surface,
        "inversePrimary": accent,
        "surfaceDim": shell,
        "surfaceBright": lift(surface, 8) if dark else "#ffffff",
        "surfaceContainerLowest": container_lowest,
        "surfaceContainerLow": container_low,
        "surfaceContainer": container,
        "surfaceContainerHigh": container_high,
        "surfaceContainerHighest": container_highest,
    }


def accent_presets(palette: Palette) -> list[str]:
    """Swatches offered as accent overrides — the palette's own semantic inks."""
    return [palette.accent, palette.cyan, palette.blue, palette.purple,
            palette.green, palette.yellow, palette.red]


# ---------------------------------------------------------------------------
# Terminal colours
# ---------------------------------------------------------------------------

# Used only if a palette somehow lost its ANSI table.
_LIGHT_ANSI_FALLBACK = [
    "#26384a", "#a34248", "#28745e", "#88621f", "#306592", "#77569b", "#247782",
    "#526375", "#667788", "#b13d48", "#247052", "#826013", "#295e9b", "#80529a",
    "#19717d", "#34485c",
]
_DARK_ANSI_FALLBACK = [
    "#263b49", "#e49a9d", "#9bc5a6", "#e0c38b", "#91bcdf", "#c5addd", "#91cecf",
    "#dfeaf1", "#90a5b5", "#f0b2b3", "#b1dcc0", "#eed4a5", "#b0d1ed", "#d9c4ed",
    "#b0e1dc", "#f2f7fa",
]


def terminal(palette: Palette, accent_override: str = "") -> dict:
    """The terminal palette for one theme.

    The grid background is the content surface, not the shell: in Pebrel the
    terminal is a card sitting on the chrome, so it must not be the chrome
    colour. Selection is a translucent accent overlay (invariant 13), not a
    solid fill, so the glyph keeps its own colour.
    """
    accent = accent_override or palette.accent
    ansi = palette.ansi if len(palette.ansi) == 16 else (
        _LIGHT_ANSI_FALLBACK if palette.is_light else _DARK_ANSI_FALLBACK)
    alpha = 0.15 if palette.is_light else 0.22
    return {
        "bg": palette.surface,
        "fg": ensure_contrast(palette.foreground, palette.surface),
        "cursor": accent,
        "selection": rgba(accent, alpha),
        "ansi": list(ansi),
        "isLight": palette.is_light,
    }
