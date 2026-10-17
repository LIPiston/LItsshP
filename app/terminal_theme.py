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


def _rgba(color: str, alpha: float) -> str:
    """Turn #AARRGGBB / #RRGGBB into a QML rgba() string."""
    value = color.lstrip("#")
    if len(value) == 8:
        a = int(value[0:2], 16) / 255.0
        r, g, b = value[2:4], value[4:6], value[6:8]
    else:
        a = alpha
        r, g, b = value[0:2], value[2:4], value[4:6]
    return f"rgba({int(r, 16)},{int(g, 16)},{int(b, 16)},{a:.3f})"


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
            "selection": "rgba(90,95,110,0.45)",
            "ansi": list(_ANSI_DARK),
        }

    return {
        "bg": surface_lowest if dark else surface,
        "fg": on_surface,
        "cursor": primary,
        "selection": _rgba(primary, 0.32),
        "ansi": list(_ANSI_DARK if dark else _ANSI_LIGHT),
    }
