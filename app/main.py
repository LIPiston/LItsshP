"""Application entry point: registers the QML types and loads the UI."""

from __future__ import annotations

import os
import sys
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = APP_DIR.parent

# Everything this app owns lives outside the tool's own directory so the QML
# module import path matches the vendored layout.
QML_IMPORT_PATH = str(PROJECT_ROOT / "third_party")

os.environ.setdefault("QT_QUICK_CONTROLS_STYLE", "Basic")


def main() -> int:
    from PySide6.QtCore import QUrl
    from PySide6.QtGui import QGuiApplication, QIcon
    from PySide6.QtQml import QQmlApplicationEngine, qmlRegisterSingletonType

    from app.controller import AppController
    from app.style import ColorHelper, StyleManager

    QGuiApplication.setApplicationName("LItsshP")
    QGuiApplication.setOrganizationName("LItsshP")
    QGuiApplication.setApplicationDisplayName("LItsshP")

    app = QGuiApplication(sys.argv)
    app.setWindowIcon(QIcon(str(APP_DIR / "assets" / "app.png")))

    qmlRegisterSingletonType(StyleManager, "md3.Core", 1, 0, "StyleManager",
                             lambda engine: StyleManager())
    qmlRegisterSingletonType(ColorHelper, "md3.Core", 1, 0, "ColorHelper",
                             lambda engine: ColorHelper())
    controller = AppController()

    engine = QQmlApplicationEngine()
    engine.addImageProvider("terminal", controller.imageProvider())
    engine.addImportPath(QML_IMPORT_PATH)
    engine.rootContext().setContextProperty("App", controller)

    qml_main = APP_DIR / "qml" / "Main.qml"
    engine.load(QUrl.fromLocalFile(str(qml_main)))
    if not engine.rootObjects():
        return 1

    window = engine.rootObjects()[0]
    _restore_geometry(controller, window)

    def on_closing():
        _save_geometry(controller, window)
        controller.shutdown()

    app.aboutToQuit.connect(on_closing)
    result = app.exec()

    # The QML tree reads the `App` context property while it is being torn
    # down, so the engine has to go before the controller does. Without this,
    # every binding fires once more against a deleted controller at exit.
    import shiboken6
    shiboken6.delete(engine)
    return result


def _restore_geometry(controller, window) -> None:
    geometry = controller.settings.get("_geometry") if controller.settings else None
    if not isinstance(geometry, dict):
        return
    width = int(geometry.get("w", 0) or 0)
    height = int(geometry.get("h", 0) or 0)
    x = geometry.get("x")
    y = geometry.get("y")
    maximized = bool(geometry.get("max"))
    if width >= 860 and height >= 520:
        window.resize(width, height)
    if isinstance(x, int) and isinstance(y, int):
        window.setPosition(x, y)
    if maximized:
        window.showMaximized()


def _save_geometry(controller, window) -> None:
    try:
        controller.setSetting("_geometry", {
            "w": window.width(),
            "h": window.height(),
            "x": window.x(),
            "y": window.y(),
            "max": window.visibility == 4,  # QWindow.WindowMaximized
        })
    except Exception:
        pass


if __name__ == "__main__":
    sys.path.insert(0, str(PROJECT_ROOT))
    sys.exit(main())
