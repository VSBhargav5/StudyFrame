import json
import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch
from PySide6.QtWidgets import QApplication
from studyframe.preferences import Preferences
from studyframe.app import StudyWindow


class PreferencesTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / 'setup.json'
        self.store = Preferences(self.path)

    def test_ui_round_trip_saves_only_whitelisted_setup_and_never_restores_approval(self):
        window = StudyWindow(preferences=self.store)
        self.addCleanup(window.deleteLater); self.addCleanup(window.close)
        window.provider_choice.setCurrentIndex(window.provider_choice.findData('openai'))
        window.key.setText('synthetic-secret-key')
        window.question.setPlainText('synthetic private question')
        window.speech_text.setPlainText('synthetic private transcript')
        window.speech_source.setCurrentIndex(window.speech_source.findData('microphone'))
        window.speech_model.setText('chosen-model-folder')
        window.pin.setChecked(False)
        window.exclude_capture.setChecked(False)
        window.save_setup()
        data = self.path.read_text(encoding='utf-8')
        saved = json.loads(data)
        self.assertEqual(set(saved), {'version','provider','source','model','pin'})
        self.assertNotIn('secret-key', data); self.assertNotIn('private', data)
        restored = StudyWindow(preferences=Preferences(self.path))
        self.addCleanup(restored.deleteLater); self.addCleanup(restored.close)
        self.assertEqual(restored.provider_choice.currentData(), 'openai')
        self.assertEqual(restored.speech_source.currentData(), 'microphone')
        self.assertEqual(restored.speech_model.text(), 'chosen-model-folder')
        self.assertFalse(restored.pin.isChecked())
        self.assertTrue(restored.exclude_capture.isChecked())
        self.assertFalse(restored.key.text()); self.assertFalse(restored.question.toPlainText())
        self.assertFalse(restored.speech_text.toPlainText()); self.assertFalse(restored.consent.isChecked())

    def test_missing_invalid_oversized_and_credential_bearing_files_use_defaults(self):
        self.assertEqual(self.store.load(), {})
        for data in (b'x'*16385, b'not-json', b'[]', b'{"version":true}',
                     b'{"version":1,"key":"do-not-import"}'):
            self.path.write_bytes(data)
            store = Preferences(self.path)
            self.assertEqual(store.load(), {}); self.assertTrue(store.warning)

    def test_failed_atomic_open_preserves_saved_file_and_never_uses_direct_write(self):
        self.store.save('openrouter_free','loopback','model',True)
        original = self.path.read_bytes()
        target = Mock(); target.open.return_value = False
        with patch('studyframe.preferences.QSaveFile', return_value=target):
            with self.assertRaises(OSError): self.store.save('openai','microphone','other',False)
        target.setDirectWriteFallback.assert_called_once_with(False)
        self.assertEqual(self.path.read_bytes(), original)
