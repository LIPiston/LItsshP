"""Python ports of the two C++ singletons the vendored md3 QML library expects.

The upstream library registers ``StyleManager`` and ``ColorHelper`` from C++
linked against Google's material-color-utilities. Building C++ here would need
a compiler toolchain, so the same Material 3 tonal-spot algorithm is provided
through the pure-Python ``materialyoucolor`` package instead.
"""

from __future__ import annotations


from PySide6.QtCore import QObject, Property, Signal, Slot
from PySide6.QtGui import QColor, QGuiApplication

from materialyoucolor.dynamiccolor.material_dynamic_colors import MaterialDynamicColors
from materialyoucolor.hct import Hct
from materialyoucolor.scheme.scheme_tonal_spot import SchemeTonalSpot


def _hex(argb: int) -> str:
    """ARGB int -> #AARRGGBB, matching QColor::name(HexArgb) in the original."""
    return "#%08x" % (argb & 0xFFFFFFFF)


class StyleManager(QObject):
    _instance: "StyleManager | None" = None

    @classmethod
    def instance(cls) -> "StyleManager | None":
        return cls._instance

    isDarkThemeChanged = Signal()
    seedColorChanged = Signal()
    currentSchemeChanged = Signal()
    lightSchemeChanged = Signal()
    darkSchemeChanged = Signal()

    def __init__(self, parent: QObject | None = None):
        super().__init__(parent)
        StyleManager._instance = self
        self._is_dark = False
        self._seed = QColor("#6750a4")
        self._light: dict[str, str] = {}
        self._dark: dict[str, str] = {}
        self._current: dict[str, str] = {}

        hints = QGuiApplication.styleHints()
        if hints is not None:
            self._is_dark = hints.colorScheme() == Qt_ColorScheme_Dark
            hints.colorSchemeChanged.connect(self._on_system_scheme)

        self._colors = MaterialDynamicColors("2025")
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

    def _get_seed(self) -> QColor:
        return self._seed

    def _set_seed(self, value: QColor) -> None:
        if value == self._seed:
            return
        self._seed = value
        self.seedColorChanged.emit()
        self._update_scheme()

    seedColor = Property(QColor, _get_seed, _set_seed, notify=seedColorChanged)

    def _get_current(self) -> dict:
        return self._current

    currentScheme = Property("QVariantMap", _get_current, notify=currentSchemeChanged)

    def _get_light(self) -> dict:
        return self._light

    lightScheme = Property("QVariantMap", _get_light, notify=lightSchemeChanged)

    def _get_dark(self) -> dict:
        return self._dark

    darkScheme = Property("QVariantMap", _get_dark, notify=darkSchemeChanged)

    def _get_hue(self) -> float:
        return Hct.from_int(self._seed.rgba()).hue

    hctHue = Property(float, _get_hue, notify=seedColorChanged)

    def _get_chroma(self) -> float:
        return Hct.from_int(self._seed.rgba()).chroma

    hctChroma = Property(float, _get_chroma, notify=seedColorChanged)

    def _get_tone(self) -> float:
        return Hct.from_int(self._seed.rgba()).tone

    hctTone = Property(float, _get_tone, notify=seedColorChanged)

    # --------------------------------------------------------------- slots

    @Slot(float, float, float)
    def setSeedColorHct(self, hue: float, chroma: float, tone: float) -> None:
        argb = Hct(hue, chroma, tone).to_int()
        self._set_seed(QColor.fromRgba(argb))

    # ------------------------------------------------------------ internals

    def _on_system_scheme(self, scheme) -> None:
        self._set_is_dark(scheme == Qt_ColorScheme_Dark)

    def _update_scheme(self) -> None:
        argb = self._seed.rgba()
        self._light = self._generate(argb, False)
        self._dark = self._generate(argb, True)
        self._current = self._dark if self._is_dark else self._light
        self.lightSchemeChanged.emit()
        self.darkSchemeChanged.emit()
        self.currentSchemeChanged.emit()

    def _generate(self, argb: int, is_dark: bool) -> dict[str, str]:
        scheme = SchemeTonalSpot(Hct.from_int(argb), is_dark, 0.0)
        roles = {
            "primary": "primary",
            "onPrimaryColor": "onPrimary",
            "primaryContainer": "primaryContainer",
            "onPrimaryContainerColor": "onPrimaryContainer",
            "secondary": "secondary",
            "onSecondaryColor": "onSecondary",
            "secondaryContainer": "secondaryContainer",
            "onSecondaryContainerColor": "onSecondaryContainer",
            "tertiary": "tertiary",
            "onTertiaryColor": "onTertiary",
            "tertiaryContainer": "tertiaryContainer",
            "onTertiaryContainerColor": "onTertiaryContainer",
            "error": "error",
            "onErrorColor": "onError",
            "errorContainer": "errorContainer",
            "onErrorContainerColor": "onErrorContainer",
            "background": "background",
            "onBackgroundColor": "onBackground",
            "surface": "surface",
            "onSurfaceColor": "onSurface",
            "surfaceVariant": "surfaceVariant",
            "onSurfaceVariantColor": "onSurfaceVariant",
            "outline": "outline",
            "outlineVariant": "outlineVariant",
            "shadow": "shadow",
            "scrim": "scrim",
            "inverseSurface": "inverseSurface",
            "inverseOnSurface": "inverseOnSurface",
            "inversePrimary": "inversePrimary",
            "surfaceDim": "surfaceDim",
            "surfaceBright": "surfaceBright",
            "surfaceContainerLowest": "surfaceContainerLowest",
            "surfaceContainerLow": "surfaceContainerLow",
            "surfaceContainer": "surfaceContainer",
            "surfaceContainerHigh": "surfaceContainerHigh",
            "surfaceContainerHighest": "surfaceContainerHighest",
        }
        out: dict[str, str] = {}
        for alias, role in roles.items():
            dyn = getattr(self._colors, role, None)
            out[alias] = _hex(dyn.get_argb(scheme)) if dyn is not None else "#ffffffff"
        return out


class ColorHelper(QObject):
    @Slot(QColor, result=float)
    def hue(self, color: QColor) -> float:
        return Hct.from_int(color.rgba()).hue

    @Slot(QColor, result=float)
    def chroma(self, color: QColor) -> float:
        return Hct.from_int(color.rgba()).chroma

    @Slot(QColor, result=float)
    def tone(self, color: QColor) -> float:
        return Hct.from_int(color.rgba()).tone

    @Slot(QColor, result=str)
    def ahex(self, color: QColor) -> str:
        return "#%08x" % color.rgba()

    @Slot(QColor, result=str)
    def hex(self, color: QColor) -> str:
        return color.name()

    @Slot(float, float, float, result=QColor)
    def hct2QColor(self, hue: float, chroma: float, tone: float) -> QColor:
        return QColor.fromRgba(Hct(hue, chroma, tone).to_int())


def _qt_color_scheme_dark():
    from PySide6.QtCore import Qt
    return Qt.ColorScheme.Dark


Qt_ColorScheme_Dark = _qt_color_scheme_dark()
