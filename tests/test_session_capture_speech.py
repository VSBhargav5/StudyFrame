import unittest
import hashlib
import json
from types import SimpleNamespace
from unittest.mock import Mock,patch
from PySide6.QtCore import Qt,QRect
from PySide6.QtGui import QImage,QPixmap
from PySide6.QtWidgets import QApplication
from studyframe.app import StudyWindow
from studyframe.images import LoadedImage,resize_image
from studyframe.provider import StudyProvider
from test_provider import Reply,response


class SessionCaptureSpeechTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.app=QApplication.instance() or QApplication([])

    def window(self):
        manager=Mock();manager.post.side_effect=lambda *a:Reply(response('5'))
        w=StudyWindow(StudyProvider(manager=manager));w.key.setText('synthetic-free-key')
        self.addCleanup(w.close);self.addCleanup(w.deleteLater)
        return w,manager

    def test_two_capture_voice_roundtrips_keep_key_and_use_current_session(self):
        w,manager=self.window()
        image=QImage(40,20,QImage.Format.Format_RGB32);image.fill(Qt.GlobalColor.blue)
        screen=SimpleNamespace(geometry=lambda:QRect(0,0,40,20),devicePixelRatio=lambda:1,
                              grabWindow=lambda _:QPixmap.fromImage(image))
        w.screen_choice.clear();w.screen_choice.addItem('Synthetic',screen)
        for _ in range(2):
            with patch('studyframe.app.QApplication.screens',return_value=[screen]):
                w.capture_and_ask();w.complete_capture()
            w.provider.reply.finished.emit()
            w.open_voice();w.speech_text.setPlainText('What is two plus three?');w.ask_transcript()
            w.provider.reply.finished.emit()
            self.assertEqual(w.key.text(),'synthetic-free-key')
        self.assertEqual(manager.post.call_count,4)
        for call in manager.post.call_args_list:
            self.assertEqual(bytes(call.args[0].rawHeader('Authorization')),b'Bearer synthetic-free-key')

    def test_provider_keys_are_isolated_restored_in_memory_and_end_session_forgets_all(self):
        w,manager=self.window()
        w.provider_choice.setCurrentIndex(1);self.assertFalse(w.key.text())
        w.key.setText('synthetic-paid-key');w.provider_choice.setCurrentIndex(0)
        self.assertEqual(w.key.text(),'synthetic-free-key')
        w.clear_answer();self.assertEqual(w.key.text(),'synthetic-free-key')
        w.clear_session();self.assertFalse(w.session_keys);self.assertFalse(w.key.text())
        w.provider_choice.setCurrentIndex(1);self.assertFalse(w.key.text())
        w.provider_choice.setCurrentIndex(0);self.assertFalse(w.key.text())
        manager.post.assert_not_called()

    def test_balanced_resize_bounds_pixels_preserves_original_and_never_upscales(self):
        image=QImage(2560,1440,QImage.Format.Format_RGB32);image.fill(Qt.GlobalColor.blue)
        source=LoadedImage(b'original',image,'original-hash',2560,1440,'png')
        small=resize_image(source,1280)
        self.assertEqual((small.width,small.height),(1280,720))
        self.assertEqual(small.sha256,hashlib.sha256(small.data).hexdigest())
        self.assertEqual(source.data,b'original');self.assertEqual(source.image.width(),2560)
        self.assertIs(resize_image(small,1280),small)
        with self.assertRaises(ValueError):resize_image(source,True)

    def test_balanced_capture_preview_keeps_full_resolution_restore_available(self):
        w,manager=self.window()
        image=QImage(2560,1440,QImage.Format.Format_RGB32);image.fill(Qt.GlobalColor.blue)
        screen=SimpleNamespace(geometry=lambda:QRect(0,0,2560,1440),devicePixelRatio=lambda:1,
                              grabWindow=lambda _:QPixmap.fromImage(image))
        w.begin_capture(screen);w.complete_capture()
        self.assertEqual(w.attachment.width,1280)
        self.assertEqual(w.original_attachment.width,2560)
        self.assertTrue(w.restore_button.isEnabled())
        self.assertEqual(w.attachment.sha256,hashlib.sha256(w.attachment.data).hexdigest())
        manager.post.assert_not_called()

    def test_model_preset_selects_only_installed_folder_without_recording(self):
        w,manager=self.window()
        original=w.speech_model.text();w.speech_variant.setCurrentIndex(1)
        with patch('studyframe.app.Path.is_file',return_value=False):w.choose_speech_variant()
        self.assertEqual(w.speech_model.text(),original)
        with patch('studyframe.app.Path.is_file',return_value=True):w.choose_speech_variant()
        self.assertTrue(w.speech_model.text().endswith('vosk-model-small-en-in-0.4'))
        self.assertFalse(w.speech.active);manager.post.assert_not_called()
