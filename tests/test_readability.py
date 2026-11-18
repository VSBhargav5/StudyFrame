"""Check the rendered material floor against actual enabled widget text colors."""
import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
import unittest
from unittest.mock import patch

from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QColor, QImage, QPainter, QPalette
from PySide6.QtWidgets import QApplication
from studyframe.app import StudyWindow
from studyframe.glass import GlassPanel


def luminance(color):
    values = [v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055)**2.4
              for v in (color.redF(), color.greenF(), color.blueF())]
    return sum(v*w for v,w in zip(values, (0.2126, 0.7152, 0.0722)))


class ReadabilityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_enabled_secondary_and_placeholder_text_survive_light_and_dark_backdrops(self):
        with patch('studyframe.app.create_backdrop', return_value=None):
            window = StudyWindow()
            window.show(); self.app.processEvents()
        self.addCleanup(window.deleteLater); self.addCleanup(window.close)
        foregrounds = [window.status.palette().color(QPalette.ColorRole.WindowText),
                       window.voice_button.palette().color(QPalette.ColorRole.ButtonText),
                       window.close_button.palette().color(QPalette.ColorRole.ButtonText),
                       window.question.palette().color(QPalette.ColorRole.PlaceholderText)]
        panel = GlassPanel()
        panel.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        panel.resize(500, 300)
        self.addCleanup(panel.deleteLater)
        for native in (False, True):
            panel.set_native_material(native)
            for background in ('white', 'black'):
                image = QImage(panel.size(), QImage.Format.Format_ARGB32)
                image.fill(QColor(background))
                painter = QPainter(image)
                try:
                    panel.render(painter, QPoint())
                finally:
                    painter.end()
                for foreground in foregrounds:
                    ratios = []
                    for x in range(30, 470, 20):
                        for y in range(30, 270, 20):
                            a,b = sorted((luminance(foreground), luminance(image.pixelColor(x,y))))
                            ratios.append((b+0.05)/(a+0.05))
                    self.assertGreaterEqual(min(ratios), 4.5,
                        f'{foreground.name()} over {background}, native={native}: {min(ratios):.2f}')
