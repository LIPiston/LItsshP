"""Terminal colours derived from the Material scheme.

Keeping the terminal inside the app's palette is what makes the whole window
read as one flat surface instead of a themed shell wrapped around a black box.
The ANSI colours are fixed hues (terminals need distinguishable reds/greens),
while the background, foreground, cursor and selection follow the theme.
"""

from __future__ import annotations

from .style import StyleManager

_ANSI_DARK = [
    "#1b1b22", "#e06c75", "#98c379", "#e5c07b", "#61afef",
    "#c678dd", "#56b6c2", "#dcdfe4",
    "#5c6370", "#ff7b86", "#a7e08c", "#f0cf8e", "#7cc4ff",
    "#d79ae8", "#6fd3dd", "#ffffff",
]

_ANSI_LIGHT = [
    "#3c3f4a", "#c1424c", "#3f8f4f", "#a57415", "#2b6cb0",
    "#9a4bb5", "#1a8a99", "#6b6f7b",
    "#8a8f9c", "#d4565f", "#4ca35c", "#b8860b", "#3d82cc",
    "#ad64c8", "#2ba3b3", "#1b1b22",
]

_CLASSIC = {
    "bg": "#0b0b0f",
    "fg": "#d7dae0",
    "cursor": "#d7dae0",
}


def _qcolor(color: str, alpha: float) -> str:
    """Return a themed colour in the ``#AARRGGBB`` form QColor parses.

    The terminal model builds QColors from these strings, not QML colours, and
    ``QColor("rgba(...)")`` is invalid — which silently discarded the themed
    selection colour and fell back to a hard-coded one.
    """
    value = color.lstrip("#")
    if len(value) == 8:
        return "#" + value.upper()
    if len(value) != 6:
        return color
    a = max(0, min(255, int(round(alpha * 255))))
    return f"#{a:02X}{value.upper()}"


def build_palette(settings: dict) -> dict:
    manager = StyleManager.instance()
    scheme = {}
    if manager is not None:
        try:
            scheme = dict(manager.property("currentScheme")) or {}
        except Exception:
            scheme = {}

    dark = bool(manager.property("isDarkTheme")) if manager is not None else True
    classic = settings.get("terminalTheme") == "classic"

    surface_lowest = scheme.get("surfaceContainerLowest", "#0f0d12")
    surface = scheme.get("surface", "#0f0d12")
    on_surface = scheme.get("onSurfaceColor", "#e6e1e7")
    primary = scheme.get("primary", "#cdc0ec")

    if classic:
        return {
            "bg": _CLASSIC["bg"],
            "fg": _CLASSIC["fg"],
            "cursor": _CLASSIC["cursor"],
            "selection": _qcolor("#5a5f6e", 0.45),
            "ansi": list(_ANSI_DARK),
        }

    return {
        "bg": surface_lowest if dark else surface,
        "fg": on_surface,
        "cursor": primary,
        "selection": _qcolor(primary, 0.32),
        "ansi": list(_ANSI_DARK if dark else _ANSI_LIGHT),
    }
