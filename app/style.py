"""Python port of the ``StyleManager`` / ``ColorHelper`` singletons md3 expects.

The vendored md3 QML library asks for a ``currentScheme`` map of Material role
names. Instead of generating that map from a seed colour (Material You), this
port renders it from a **Pebrel reviewed palette** (see ``app/theme.py``): the
roles keep their Material names, so every page keeps working, but the values
now match the Pebrel design system rather than a tonal-spot derivation of a
purple seed.

Keeping the role names is deliberate. Rewriting every ``Theme.color.x`` call
site would be a large diff with no visual benefit; the palette is the thing
that carries the look, and it lives in one place.
"""

from __future__ import annotations

from PySide6.QtCore import QObject, Property, Signal, Slot
from PySide6.QtGui import QColor, QGuiApplication

from . import theme as pebrel


class StyleManager(QObject):
    _instance: "StyleManager | None" = None

    @classmethod
    def instance(cls) -> "StyleManager | None":
        return cls._instance

    isDarkThemeChanged = Signal()
    seedColorChanged = Signal()
    themeFamilyChanged = Signal()
    currentSchemeChanged = Signal()
    lightSchemeChanged = Signal()
    darkSchemeChanged = Signal()
    skinChanged = Signal()

    def __init__(self, parent: QObject | None = None):
        super().__init__(parent)
        StyleManager._instance = self
        self._is_dark = False
        self._family = pebrel.DEFAULT_FAMILY
        # The accent override is the "seed" from the Material era. It stays a
        # settable property so old state files and the settings page keep
        # working; empty means "use the theme's own accent".
        self._seed = ""
        self._light: dict[str, str] = {}
        self._dark: dict[str, str] = {}
        self._current: dict[str, str] = {}
        self._skin: dict = {}

        hints = QGuiApplication.styleHints()
        if hints is not None:
            self._is_dark = hints.colorScheme() == Qt_ColorScheme_Dark
            hints.colorSchemeChanged.connect(self._on_system_scheme)

        self._update_scheme()

    # ------------------------------------------------------------- properties

    def _get_is_dark(self) -> bool:
        return self._is_dark

    def _set_is_dark(self, value: bool) -> None:
        if value == self._is_dark:
            return
        self._is_dark = value
        self.isDarkThemeChanged.emit()
        self._update_scheme()

    isDarkTheme = Property(bool, _get_is_dark, _set_is_dark, notify=isDarkThemeChanged)

    def _get_family(self) -> str:
        return self._family

    def _set_family(self, value: str) -> None:
        family = pebrel.normalize_family(str(value or ""))
        if family == self._family:
            return
        self._family = family
        self.themeFamilyChanged.emit()
        self._update_scheme()

    themeFamily = Property(str, _get_family, _set_family, notify=themeFamilyChanged)

    def _get_seed(self) -> str:
        return self._seed

    def _set_seed(self, value) -> None:
        # QColor, "#rrggbb" and "" all arrive here.
        if isinstance(value, QColor):
            text = value.name() if value.isValid() else ""
        else:
            text = str(value or "").strip()
        if text and not text.startswith("#"):
            text = "#" + text
        if len(text) not in (0, 7, 9):
            return
        if text == self._seed:
            return
        self._seed = text
        self.seedColorChanged.emit()
        self._update_scheme()

    seedColor = Property(str, _get_seed, _set_seed, notify=seedColorChanged)

    def _get_current(self) -> dict:
        return self._current

    currentScheme = Property("QVariantMap", _get_current, notify=currentSchemeChanged)

    def _get_light(self) -> dict:
        return self._light

    lightScheme = Property("QVariantMap", _get_light, notify=lightSchemeChanged)

    def _get_dark(self) -> dict:
        return self._dark

    darkScheme = Property("QVariantMap", _get_dark, notify=darkSchemeChanged)

    def _get_skin(self) -> dict:
        return self._skin

    skin = Property("QVariantMap", _get_skin, notify=skinChanged)

    # Convenience accessors so QML can read the resolved palette directly.
    def _get_palette_name(self) -> str:
        return str(self._skin.get("name", "")) if self._skin else ""

    paletteName = Property(str, _get_palette_name, notify=skinChanged)

    def _get_families(self) -> list:
        """Picker data: each family's own planes and accent, for the swatch.

        The preview is drawn from the same palettes the app resolves, so a
        swatch cannot show a colour the theme will not actually use.
        """
        out = []
        for family in pebrel.FAMILIES:
            palette = pebrel.resolve(family["id"], self._is_dark)
            skin = pebrel.skin(palette)
            out.append({
                "id": family["id"],
                "label": family["label"],
                "shell": skin["shell"],
                "surface": skin["surface"],
                "accent": skin["accent"],
            })
        return out

    families = Property("QVariantList", _get_families, notify=skinChanged)

    def _get_theme_dir(self) -> str:
        return str(pebrel.theme_dir())

    themeDir = Property(str, _get_theme_dir, constant=True)

    def _get_theme_errors(self) -> list:
        return pebrel.load_errors()

    themeErrors = Property("QVariantList", _get_theme_errors, notify=skinChanged)

    # --------------------------------------------------------------- slots

    @Slot(float, float, float)
    def setSeedColorHct(self, hue: float, chroma: float, tone: float) -> None:
        """Kept for API compatibility; converts HCT to a hex accent."""
        from materialyoucolor.hct import Hct

        argb = Hct(hue, chroma, tone).to_int()
        self._set_seed(QColor.fromRgba(argb))

    @Slot(str, result="QVariantMap")
    def skinFor(self, family: str) -> dict:
        """Preview a family without applying it (used by the theme picker)."""
        palette = pebrel.resolve(family, self._is_dark)
        return pebrel.skin(palette)

    @Slot(result=str)
    def reloadThemes(self) -> str:
        """Re-read the theme directory after the user edited a YAML file.

        Returns "" on success, otherwise the first problem found so the
        settings page can show it instead of silently keeping the old theme.
        """
        pebrel.reload()
        family = pebrel.normalize_family(self._family)
        if family != self._family:
            self._family = family
            self.themeFamilyChanged.emit()
        self._update_scheme()
        errors = pebrel.load_errors()
        return errors[0] if errors else ""

    @Slot(result=bool)
    def isLight(self) -> bool:
        return not self._is_dark

    # ------------------------------------------------------------ internals

    def _on_system_scheme(self, scheme) -> None:
        self._set_is_dark(scheme == Qt_ColorScheme_Dark)

    def _accent_override(self) -> str:
        return self._seed if self._seed else ""

    def _update_scheme(self) -> None:
        accent = self._accent_override()
        light_palette = pebrel.resolve(self._family, False)
        dark_palette = pebrel.resolve(self._family, True)
        self._light = pebrel.scheme(light_palette, accent)
        self._dark = pebrel.scheme(dark_palette, accent)
        self._current = self._dark if self._is_dark else self._light
        active = dark_palette if self._is_dark else light_palette
        self._skin = pebrel.skin(active, accent)
        self.lightSchemeChanged.emit()
        self.darkSchemeChanged.emit()
        self.currentSchemeChanged.emit()
        self.skinChanged.emit()


class ColorHelper(QObject):
    @Slot(QColor, result=float)
    def hue(self, color: QColor) -> float:
        from materialyoucolor.hct import Hct

        return Hct.from_int(color.rgba()).hue

    @Slot(QColor, result=float)
    def chroma(self, color: QColor) -> float:
        from materialyoucolor.hct import Hct

        return Hct.from_int(color.rgba()).chroma

    @Slot(QColor, result=float)
    def tone(self, color: QColor) -> float:
        from materialyoucolor.hct import Hct

        return Hct.from_int(color.rgba()).tone

    @Slot(QColor, result=str)
    def ahex(self, color: QColor) -> str:
        return "#%08x" % color.rgba()

    @Slot(QColor, result=str)
    def hex(self, color: QColor) -> str:
        return color.name()

    @Slot(float, float, float, result=QColor)
    def hct2QColor(self, hue: float, chroma: float, tone: float) -> QColor:
        from materialyoucolor.hct import Hct

        return QColor.fromRgba(Hct(hue, chroma, tone).to_int())


def _qt_color_scheme_dark():
    from PySide6.QtCore import Qt
    return Qt.ColorScheme.Dark


Qt_ColorScheme_Dark = _qt_color_scheme_dark()
