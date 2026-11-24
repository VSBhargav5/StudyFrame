"""Windows-only visual/affinity check using an opaque, synthetic owned backdrop.

No personal desktop pixels, credentials or model/network calls. Capture only the
backdrop rectangle, entirely inside an opaque app-owned window. New output dir
required. Read report.json alongside the PNGs: API success alone is not visual QA.
"""
import argparse
import json
import sys
from pathlib import Path

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import QApplication, QWidget
from studyframe.app import StudyWindow


class Backdrop(QWidget):
    background = 'stripes'

    def paintEvent(self, event):
        painter = QPainter(self)
        if self.background != 'stripes':
            painter.fillRect(self.rect(), QColor('#ffffff' if self.background == 'light' else '#080c13'))
            return
        painter.fillRect(self.rect(), QColor('#2462e1'))
        painter.fillRect(self.width() // 2, 0, self.width(), self.height(), QColor('#f3d237'))
        for y in range(0, self.height(), 32):
            painter.fillRect(0, y, self.width(), 5, QColor('#ed5680'))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--background', choices=('stripes', 'light', 'dark'), default='stripes')
    parser.add_argument('--tint',type=int,choices=range(91),default=25)
    args = parser.parse_args()
    if sys.platform != 'win32': parser.error('This check requires native Windows Qt.')
    app = QApplication([])
    if app.platformName() != 'windows': parser.error('Set QT_QPA_PLATFORM=windows.')
    available = app.primaryScreen().availableGeometry()
    if available.width() < 750 or available.height() < 740:
        parser.error('Requires at least 750 × 740 logical pixels for a bounded synthetic check.')
    args.output.mkdir(parents=True, exist_ok=False)
    backdrop = Backdrop()
    backdrop.background = args.background
    backdrop.setWindowFlags(Qt.WindowType.Window | Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint)
    backdrop.resize(min(1100, available.width()), min(850, available.height()))
    backdrop.move(available.center() - backdrop.rect().center())
    backdrop.show()
    window = StudyWindow(start_collapsed=True)
    window.glass_tint.setValue(args.tint)
    window.move(backdrop.geometry().center() - window.rect().center())
    window.question.setPlainText('Why does range(3) stop before 3?')
    window.answer.setPlainText('Synthetic answer — no model called.\n\nrange(3) produces 0, 1, 2. The stop is exclusive.\n\nTry list(range(3)) to verify this prediction.')
    window.show(); window.raise_(); window.activateWindow()
    observations = []
    captures = {}

    def save(name):
        region = window.frameGeometry()
        # The window must remain entirely inside our opaque backdrop.
        if not backdrop.geometry().contains(region):
            raise RuntimeError('Synthetic overlay escaped the owned backdrop; refusing capture.')
        for x in range(7):
            for y in range(5):
                point = region.topLeft()
                point.setX(region.left() + x * (region.width()-1)//6)
                point.setY(region.top() + y * (region.height()-1)//4)
                if app.topLevelAt(point) not in (window, backdrop):
                    raise RuntimeError('Another window occludes the synthetic fixture; refusing capture.')
        image = backdrop.screen().grabWindow(0, region.x(), region.y(), region.width(), region.height())
        if image.isNull() or not image.save(str(args.output / (name + '.png'))):
            raise RuntimeError('Synthetic capture failed.')
        if name in ('glass-visible', 'glass-excluded', 'glass-baseline'):
            captures[name] = image.toImage()
        observations.append({'step': name, 'requested_exclusion': window.exclude_capture.isChecked(),
                             'status': window.privacy_badge.text(), 'detail': window.effects_info.text()})

    def visible():
        window.exclude_capture.setChecked(False)
        QTimer.singleShot(700, lambda: (save('glass-visible'), hidden()))

    def baseline():
        save('glass-baseline')
        window.show(); window.raise_()
        QTimer.singleShot(700, visible)

    def hidden():
        window.exclude_capture.setChecked(True)
        QTimer.singleShot(700, lambda: (save('glass-excluded'), restored()))

    def restored():
        window.exclude_capture.setChecked(False)
        QTimer.singleShot(700, finish)

    def finish():
        save('glass-restored')
        window.collapse_button.setChecked(False)
        window.move(backdrop.geometry().center() - window.rect().center())
        QTimer.singleShot(700, expanded)

    def expanded():
        save('glass-answer')
        window.open_voice()
        window.speech_text.setPlainText('Synthetic transcript: why does range three stop before three?')
        QTimer.singleShot(700, voice)

    def voice():
        save('glass-voice')
        shown, hidden = captures['glass-visible'], captures['glass-excluded']
        points = [(x if left else shown.width()-1-x, y if top else shown.height()-1-y)
                  for x in range(3) for y in range(3) for left in (True, False) for top in (True, False)]
        unchanged = sum(shown.pixelColor(x,y) == hidden.pixelColor(x,y) for x,y in points)
        report = {'windows_build': sys.getwindowsversion().build, 'background': args.background,'tint':args.tint, 'observations': observations,
                  'outside_corner_pixels_unchanged': unchanged, 'outside_corner_pixels_checked': len(points),
                  'excluded_matches_hidden_fixture': hidden == captures['glass-baseline']}
        (args.output / 'report.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
        print(json.dumps(report))
        window.close(); backdrop.close(); app.quit()

    window.hide()
    backdrop.raise_(); backdrop.activateWindow()
    QTimer.singleShot(700, baseline)
    QTimer.singleShot(10000, app.quit)
    app.exec()
    return 0 if (args.output / 'report.json').exists() else 1


if __name__ == '__main__': raise SystemExit(main())
