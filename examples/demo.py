"""A synthetic study session; optional reproducible window rendering."""

import argparse
import os
import sys
from pathlib import Path
import tempfile


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot", type=Path, help="Render the synthetic app to a new PNG and exit")
    views = parser.add_mutually_exclusive_group()
    views.add_argument("--crop", action="store_true", help="Apply a code-only crop to the synthetic image")
    views.add_argument("--crop-editor", action="store_true", help="Open the crop editor with the synthetic image")
    args = parser.parse_args()
    if args.snapshot:
        os.environ.setdefault("QT_QPA_PLATFORM", "windows" if sys.platform == "win32" else "offscreen")

    from PySide6.QtCore import Qt, QRect
    from PySide6.QtGui import QColor, QFont, QFontDatabase, QImage, QPainter
    from PySide6.QtWidgets import QApplication, QDialog
    from studyframe.app import StudyWindow
    from studyframe.crop import CropDialog

    app = QApplication([])
    if not QFontDatabase.families():
        raise RuntimeError("No fonts available. On Windows use QT_QPA_PLATFORM=windows; on Linux install system fonts.")
    image = QImage(720, 320, QImage.Format.Format_RGB32)
    image.fill(QColor("#152b40"))
    painter = QPainter(image)
    painter.setPen(QColor("#d5e8f5"))
    painter.setFont(QFont("Consolas", 22))
    painter.drawText(30, 60, "# Synthetic learning example")
    painter.drawText(30, 130, "for i in range(3):")
    painter.drawText(30, 185, "    print(i)")
    painter.setPen(QColor("#81d3b0"))
    painter.drawText(30, 265, "# Predict before asking")
    painter.end()

    with tempfile.TemporaryDirectory(prefix="studyframe-demo-") as directory:
        source = Path(directory) / "synthetic-code.png"
        if not image.save(str(source)):
            raise RuntimeError("Could not create synthetic example")
        window = StudyWindow()
        window.question.setPlainText("Why does range(3) stop before 3?")
        window.context.setPlainText("for i in range(3):\n    print(i)")
        window.select_image(source)
        window.show()
        app.processEvents()
        window.render_image()
        if args.crop:
            window.apply_crop(QRect(20, 100, 650, 110))
        window.prepare()
        target = window
        if args.crop_editor:
            dialog = CropDialog(window.attachment.image, window)
            if args.snapshot:
                dialog.from_canvas(QRect(20, 100, 650, 110))
                dialog.show()
                app.processEvents()
                target = dialog
            elif dialog.exec() == QDialog.DialogCode.Accepted:
                window.apply_crop(dialog.selected_rect())
                window.prepare()
        if args.snapshot:
            args.snapshot.parent.mkdir(parents=True, exist_ok=True)
            # Reserve the destination without overwriting an existing artifact.
            with args.snapshot.open("xb") as destination:
                from PySide6.QtCore import QBuffer, QByteArray, QIODevice
                encoded = QByteArray()
                buffer = QBuffer(encoded)
                buffer.open(QIODevice.OpenModeFlag.WriteOnly)
                if not target.grab().save(buffer, "PNG"):
                    raise RuntimeError("Could not render synthetic window")
                destination.write(bytes(encoded))
            window.close()
            return 0
        return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
