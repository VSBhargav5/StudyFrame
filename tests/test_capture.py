import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
import base64
import hashlib
import json
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from PySide6.QtCore import QRect,Qt
from PySide6.QtGui import QImage,QPixmap
from PySide6.QtWidgets import QApplication
from studyframe.capture import capture_screen
from studyframe.images import ImageError,MAX_PIXELS
from studyframe.app import StudyWindow
from studyframe.provider import payload


class CaptureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.app=QApplication.instance() or QApplication([])

    def screen(self,ratio=1):
        image=QImage(80,40,QImage.Format.Format_ARGB32);image.fill(Qt.GlobalColor.blue)
        image.setText('private','not part of capture output');image.setDevicePixelRatio(ratio)
        return SimpleNamespace(name=lambda:'Synthetic display',geometry=lambda:QRect(0,0,int(80/ratio),int(40/ratio)),
                    devicePixelRatio=lambda:ratio,grabWindow=Mock(return_value=QPixmap.fromImage(image)))

    def window(self):
        window=StudyWindow();window.show();self.app.processEvents()
        self.addCleanup(window.deleteLater);self.addCleanup(window.close)
        return window

    def choose(self,window,screen):
        with patch('studyframe.app.QApplication.screens',return_value=[screen]),patch('studyframe.app.QInputDialog.getItem',side_effect=lambda *args:(args[3][0],True)):
            window.choose_screen()

    def test_exact_local_png_uses_physical_pixels_not_dpi_scaled_dimensions(self):
        for ratio in (1,2):
            screen=self.screen(ratio);result=capture_screen(screen)
            screen.grabWindow.assert_called_once_with(0)
            self.assertEqual((result.width,result.height),(80,40));self.assertEqual(result.format,'png')
            self.assertEqual(result.sha256,hashlib.sha256(result.data).hexdigest())
            self.assertEqual(result.image.textKeys(),[]);self.assertEqual(result.image.devicePixelRatio(),1)
            decoded=QImage.fromData(result.data)
            self.assertEqual(decoded.pixelColor(79,39),result.image.pixelColor(79,39))
            self.assertEqual(decoded.textKeys(),[])

    def test_preflight_refuses_excessive_or_invalid_scale_before_capture(self):
        for geometry,ratio in ((QRect(0,0,8000,4000),1),(QRect(0,0,4000,2000),2),(QRect(),1),(QRect(0,0,10,10),float('nan'))):
            screen=self.screen();screen.geometry=lambda:geometry;screen.devicePixelRatio=lambda:ratio
            with self.assertRaises(ImageError):capture_screen(screen)
            screen.grabWindow.assert_not_called()

    def test_postflight_and_png_size_limits_preserve_fail_closed_behavior(self):
        screen=self.screen();screen.geometry=lambda:QRect(0,0,40,20)
        with patch('studyframe.capture.MAX_PIXELS',1000),self.assertRaisesRegex(ImageError,'pixel limit'):
            capture_screen(screen)
        with patch('studyframe.capture.MAX_FILE_BYTES',1),self.assertRaisesRegex(ImageError,'8MiB'):
            capture_screen(self.screen())

    def test_no_monitor_does_not_open_a_picker_or_capture(self):
        window=self.window()
        with patch('studyframe.app.QApplication.screens',return_value=[]),patch('studyframe.app.QInputDialog.getItem') as picker:
            window.choose_screen();picker.assert_not_called()
        self.assertIsNone(window.pending_screen);self.assertFalse(window.capture_timer.isActive())
        self.assertIn('No display',window.status.text())

    def test_removed_or_blocked_display_fails_without_a_fake_image(self):
        screen=self.screen();screen.grabWindow.side_effect=RuntimeError('deleted')
        with self.assertRaisesRegex(ImageError,'no longer available'):capture_screen(screen)
        screen=self.screen();screen.grabWindow.return_value=QPixmap()
        with self.assertRaisesRegex(ImageError,'blocked'):capture_screen(screen)

    def test_selection_and_cancel_do_not_capture_or_send_and_keep_previous_preview(self):
        window=self.window();screen=self.screen();window.question.setPlainText('Explain this');window.prepare();before=window.preview.toPlainText()
        with patch('studyframe.app.QApplication.screens',return_value=[screen]),patch('studyframe.app.QInputDialog.getItem',return_value=('',False)),patch.object(window.provider.manager,'post') as post:
            window.choose_screen();post.assert_not_called()
        screen.grabWindow.assert_not_called();self.assertEqual(window.preview.toPlainText(),before)
        self.assertIsNone(window.pending_screen)

    def test_capture_replaces_only_after_success_and_never_sends_automatically(self):
        window=self.window();screen=self.screen()
        window.question.setPlainText('Explain the loop');window.prepare();window.key.setText('synthetic-key');window.consent.setChecked(True)
        with patch.object(window.provider.manager,'post') as post:
            self.choose(window,screen)
            self.assertFalse(window.isVisible());self.assertTrue(window.capture_timer.isActive())
            screen.grabWindow.assert_not_called()
            window.complete_capture();post.assert_not_called()
        self.assertTrue(window.isVisible());self.assertIsNotNone(window.attachment);self.assertFalse(window.busy)
        self.assertFalse(window.consent.isChecked());self.assertFalse(window.preview.toPlainText())
        self.assertIs(window.attachment,window.original_attachment)
        window.prepare();body=json.loads(payload(window.preview.toPlainText(),window.attachment,'openrouter_free'))
        self.assertEqual(body['input'][0]['content'][1]['image_url'].split(',')[1],base64.b64encode(window.attachment.data).decode())
        window.apply_crop(QRect(0,0,20,10));self.assertEqual(window.attachment.width,20)
        window.restore_image();self.assertEqual(window.attachment.width,80)

    def test_failed_capture_preserves_prior_snapshot_and_request(self):
        window=self.window();window.attachment=capture_screen(self.screen());window.original_attachment=window.attachment
        window.question.setPlainText('Explain this');window.prepare();old=window.attachment;text=window.preview.toPlainText()
        self.choose(window,self.screen())
        with patch('studyframe.app.capture_screen',side_effect=ImageError('Synthetic blocked capture')):window.complete_capture()
        self.assertIs(window.attachment,old);self.assertEqual(window.preview.toPlainText(),text)
        self.assertTrue(window.isVisible());self.assertFalse(window.busy)

    def test_cancel_clear_and_close_disarm_delayed_capture(self):
        for action in ('cancel_request','clear_session','close'):
            window=self.window();screen=self.screen();self.choose(window,screen)
            getattr(window,action)();window.complete_capture();self.app.processEvents()
            screen.grabWindow.assert_not_called();self.assertFalse(window.capture_timer.isActive())
            self.assertIsNone(window.pending_screen);self.assertIsNone(window.attachment)

    def test_pin_uses_visible_window_flag_and_does_not_capture_or_send(self):
        window=self.window()
        with patch('studyframe.app.capture_screen') as capture,patch.object(window.provider.manager,'post') as post:
            window.pin.setChecked(True);self.app.processEvents()
            self.assertTrue(window.windowFlags() & Qt.WindowType.WindowStaysOnTopHint)
            window.pin.setChecked(False);self.assertFalse(window.windowFlags() & Qt.WindowType.WindowStaysOnTopHint)
            capture.assert_not_called();post.assert_not_called()
