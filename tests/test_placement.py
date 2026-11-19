import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from types import SimpleNamespace
from unittest.mock import patch
import unittest
from PySide6.QtCore import QRect
from PySide6.QtWidgets import QApplication
from studyframe.app import StudyWindow


class PlacementTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): cls.app=QApplication.instance() or QApplication([])

    def test_expanding_near_work_area_edge_keeps_controls_visible_and_answer_intact(self):
        w=StudyWindow(start_collapsed=True)
        self.addCleanup(w.deleteLater); self.addCleanup(w.close)
        w.show(); self.app.processEvents()
        screen=SimpleNamespace(availableGeometry=lambda:QRect(-1280,0,1280,700))
        with patch.object(w,'screen',return_value=screen):
            w.move(-370,600)
            w.answer.setPlainText('Preserved answer')
            w.collapse_button.setChecked(False)
            self.assertTrue(screen.availableGeometry().contains(w.geometry()))
            self.assertEqual(w.answer.toPlainText(),'Preserved answer')
            w.resize(900,850); w.fit_to_screen()
            self.assertTrue(screen.availableGeometry().contains(w.geometry()))

    def test_removed_capture_display_disarms_pending_snapshot_without_grabbing_pixels(self):
        w=StudyWindow();self.addCleanup(w.deleteLater);self.addCleanup(w.close)
        w.show(); self.app.processEvents()
        old=object()
        w.begin_capture(old)
        with patch('studyframe.app.QApplication.screens',return_value=[]), \
             patch('studyframe.app.capture_screen') as capture:
            w.display_changed()
            w.complete_capture()
            capture.assert_not_called()
        self.assertIsNone(w.pending_screen)
        self.assertFalse(w.capture_timer.isActive())
        self.assertIn('disconnected',w.status.text())
