"""Terminal colours derived from the active Pebrel theme.

Keeping the terminal inside the app's palette is what makes the whole window
read as one surface instead of a themed shell wrapped around a black box: the
grid background is the theme's *content* surface, which is exactly the colour
the terminal card floats on.

ANSI colours are fixed per theme (a terminal needs distinguishable reds and
greens); background, foreground, cursor and selection follow the palette.
Selection stays a translucent accent overlay, never a solid fill — see
invariant 13.
"""

from __future__ import annotations

from . import theme as pebrel
from .style import StyleManager

_CLASSIC = {
    "bg": "#0b0b0f",
    "fg": "#d7dae0",
    "cursor": "#d7dae0",
    "selection": "#735a5f6e",
    "ansi": [
        "#1b1b22", "#e06c75", "#98c379", "#e5c07b", "#61afef",
        "#c678dd", "#56b6c2", "#dcdfe4",
        "#5c6370", "#ff7b86", "#a7e08c", "#f0cf8e", "#7cc4ff",
        "#d79ae8", "#6fd3dd", "#ffffff",
    ],
}


def build_palette(settings: dict) -> dict:
    if settings.get("terminalTheme") == "classic":
        return dict(_CLASSIC, ansi=list(_CLASSIC["ansi"]))

    manager = StyleManager.instance()
    if manager is None:
        result = pebrel.terminal(pebrel.resolve(pebrel.DEFAULT_FAMILY, True))
    else:
        palette_name = str(manager.property("paletteName") or "")
        dark = bool(manager.property("isDarkTheme"))
        family = str(settings.get("themeFamily") or "")
        palette = (
            pebrel.PALETTES[palette_name]
            if palette_name in pebrel.PALETTES
            else pebrel.resolve(family, dark)
        )
        accent = str(manager.property("seedColor") or "")
        result = pebrel.terminal(palette, accent)

    return {
        "bg": result["bg"],
        "fg": result["fg"],
        "cursor": result["cursor"],
        "selection": result["selection"],
        "ansi": list(result["ansi"]),
    }
