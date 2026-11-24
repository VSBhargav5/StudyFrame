import json
import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from PySide6.QtCore import Qt,QPoint
from PySide6.QtGui import QImage,QColor,QPainter,QPalette
from PySide6.QtWidgets import QApplication
from studyframe.app import StudyWindow
from studyframe.glass import GlassPanel
from studyframe.preferences import Preferences
from test_readability import luminance


class ClearGlassTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.app=QApplication.instance() or QApplication([])

    def test_clear_canvas_and_presets_preserve_question_and_session_key(self):
        w=StudyWindow();self.addCleanup(w.close);self.addCleanup(w.deleteLater)
        self.assertEqual(w.centralWidget().tint,25)
        w.key.setText('synthetic-key');w.question.setPlainText('Synthetic question')
        w.glass_preset.setCurrentIndex(w.glass_preset.findData(0));w.choose_glass_preset()
        self.assertEqual(w.centralWidget().tint,0)
        w.glass_tint.setValue(78);self.assertEqual(w.glass_preset.currentData(),78)
        self.assertEqual(w.key.text(),'synthetic-key');self.assertEqual(w.question.toPlainText(),'Synthetic question')

    def test_zero_tint_is_transparent_at_center_with_round_corners(self):
        panel=GlassPanel();self.addCleanup(panel.deleteLater);panel.resize(500,300)
        panel.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        panel.set_tint(0);clear=panel.grab().toImage()
        self.assertEqual(clear.pixelColor(250,150).alpha(),0)
        self.assertEqual(clear.pixelColor(0,0).alpha(),0)
        panel.set_tint(78);dark=panel.grab().toImage()
        self.assertGreater(dark.pixelColor(250,150).alpha(),190)
        for value in (True,-1,91,25.5):
            with self.assertRaises(ValueError):panel.set_tint(value)

    def test_v1_migration_keeps_old_choices_and_rejects_invalid_v2_tint(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'setup.json'
            old=dict(version=1,provider='openai',source='microphone',model='chosen',pin=False)
            path.write_text(json.dumps(old));original=path.read_bytes()
            data=Preferences(path).load();self.assertEqual(data['glass_tint'],25)
            self.assertEqual(data['provider'],'openai');self.assertEqual(path.read_bytes(),original)
            for value in (True,-1,91,2.5):
                path.write_text(json.dumps({**data,'glass_tint':value}))
                self.assertFalse(Preferences(path).load())

    def test_default_clear_controls_have_contrast_on_owned_white_background(self):
        with patch('studyframe.app.create_backdrop',return_value=None):
            w=StudyWindow();w.show();self.app.processEvents()
        self.addCleanup(w.close);self.addCleanup(w.deleteLater)
        panel=w.centralWidget();canvas=QImage(panel.size(),QImage.Format.Format_ARGB32);canvas.fill(QColor('white'))
        painter=QPainter(canvas);panel.render(painter,QPoint());painter.end()
        target=w.question.viewport().mapTo(panel,QPoint(30,50))
        background=canvas.pixelColor(target)
        foreground=w.question.palette().color(QPalette.ColorRole.PlaceholderText)
        a,b=sorted((luminance(background),luminance(foreground)))
        self.assertGreaterEqual((b+0.05)/(a+0.05),4.5)
