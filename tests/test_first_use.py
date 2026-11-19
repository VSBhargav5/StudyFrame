import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
import unittest
from unittest.mock import patch
from PySide6.QtWidgets import QApplication
from studyframe.app import StudyWindow


class FirstUseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.window = StudyWindow(start_collapsed=True)
        self.addCleanup(self.window.deleteLater); self.addCleanup(self.window.close)
        self.window.show(); self.app.processEvents()

    def test_setup_is_first_and_explicit_key_action_never_captures_or_sends(self):
        w = self.window
        with patch('studyframe.app.capture_screen') as capture, patch.object(w.provider.manager, 'post') as post:
            self.assertEqual(w.capture_button.text(), 'Connect model')
            w.capture_button.click(); self.app.processEvents()
            self.assertTrue(w.settings_pane.isVisible())
            self.assertIs(w.content.layout().itemAt(0).widget(), w.settings_pane)
            self.assertFalse(w.connection_done.isEnabled())
            w.key.setText('synthetic-key')
            self.assertIn('Key entered', w.provider_badge.text())
            w.connection_done.click()
            self.assertTrue(w.settings_pane.isHidden())
            self.assertIn('No test request', w.status.text())
            self.assertIsNone(w.pending_screen)
            capture.assert_not_called(); post.assert_not_called()

    def test_invalid_keys_provider_switch_and_clear_reset_readiness_without_losing_question(self):
        w = self.window
        w.question.setPlainText('Explain range(3)')
        for key in ('', 'with space', 'bad\nkey', 'nonascii-é'):
            w.key.setText(key)
            self.assertFalse(w.connection_done.isEnabled())
            self.assertEqual(w.capture_button.text(), 'Connect model')
        w.key.setText('synthetic-key')
        w.provider_choice.setCurrentIndex(w.provider_choice.findData('openai'))
        self.assertFalse(w.key.text())
        self.assertIn('paid', w.provider_badge.text())
        self.assertEqual(w.question.toPlainText(), 'Explain range(3)')
        w.key.setText('synthetic-key'); w.clear_session()
        self.assertEqual(w.capture_button.text(), 'Connect model')
