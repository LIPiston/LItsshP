"""Headless gate: load the whole QML tree and fail on binding errors.

Catches the class of defect that never shows up in `python -m compileall`:
a typo in a property name, a call into the controller that does not exist, or
a binding that is evaluated before its model is ready.

Run with the project virtualenv:

    .venv/Scripts/python docs/skills/reference/qml_load_gate.py

Exit code 0 means the tree loaded and emitted no TypeError/ReferenceError.
The gate points LITSSHP_CONFIG and LITSSHP_STATE at a throwaway directory, so
it never reads or writes the real ~/.ssh/config.
"""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SCRATCH = Path(tempfile.mkdtemp(prefix="litsshp-qml-gate-"))

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_QUICK_BACKEND", "software")
os.environ["LITSSHP_CONFIG"] = str(SCRATCH / ".ssh" / "config")
os.environ["LITSSHP_STATE"] = str(SCRATCH / "state.json")

sys.path.insert(0, str(ROOT))

from PySide6.QtCore import QUrl, QTimer  # noqa: E402
from PySide6.QtGui import QGuiApplication  # noqa: E402
from PySide6.QtQml import QQmlApplicationEngine, qmlRegisterSingletonType  # noqa: E402

from app.controller import AppController  # noqa: E402
from app.style import ColorHelper, StyleManager  # noqa: E402


def main() -> int:
    app = QGuiApplication(sys.argv)
    qmlRegisterSingletonType(StyleManager, "md3.Core", 1, 0, "StyleManager",
                             lambda _engine: StyleManager())
    qmlRegisterSingletonType(ColorHelper, "md3.Core", 1, 0, "ColorHelper",
                             lambda _engine: ColorHelper())

    controller = AppController()
    engine = QQmlApplicationEngine()
    engine.addImageProvider("terminal", controller.imageProvider())
    # Parenting the controller to the engine keeps it alive while the QML tree
    # evaluates its bindings during teardown; without this the bindings read a
    # deleted controller and log TypeErrors after a clean run.
    controller.setParent(engine)
    engine.addImportPath(str(ROOT / "third_party"))
    engine.rootContext().setContextProperty("App", controller)

    warnings: list[str] = []
    engine.warnings.connect(
        lambda messages: [warnings.append(w.toString()) for w in messages])

    engine.load(QUrl.fromLocalFile(str(ROOT / "app" / "qml" / "Main.qml")))
    QTimer.singleShot(700, app.quit)
    app.exec()

    errors = [w for w in warnings
              if "TypeError" in w or "ReferenceError" in w or "not defined" in w]
    roots = len(engine.rootObjects())

    print(f"root objects: {roots}")
    print(f"warnings: {len(warnings)}, binding errors: {len(errors)}")
    for line in errors[:12]:
        print(f"  {line}")

    if roots != 1 or errors:
        print("FAIL qml load gate")
        return 1
    print("PASS qml load gate")
    return 0


if __name__ == "__main__":
    sys.exit(main())
