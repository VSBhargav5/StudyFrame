import base64
import json
import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from types import SimpleNamespace
from unittest.mock import Mock,patch
import unittest

from PySide6.QtCore import Qt,QRect
from PySide6.QtGui import QImage,QPixmap
from PySide6.QtWidgets import QApplication
from studyframe.app import StudyWindow
from studyframe.capture import capture_screen
from test_provider import Reply,response
from studyframe.provider import StudyProvider


class OverlayTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.app=QApplication.instance() or QApplication([])

    def setUp(self):
        self.reply=Reply(response('The screen shows a bounded loop.'))
        self.manager=Mock();self.manager.post.return_value=self.reply
        self.provider=StudyProvider(manager=self.manager)
        self.window=StudyWindow(self.provider);self.window.show();self.app.processEvents()
        self.addCleanup(self.window.deleteLater);self.addCleanup(self.window.close)
        image=QImage(64,32,QImage.Format.Format_RGB32);image.fill(Qt.GlobalColor.cyan)
        self.screen=SimpleNamespace(name=lambda:'Synthetic',geometry=lambda:QRect(0,0,64,32),devicePixelRatio=lambda:1,
                                    grabWindow=Mock(return_value=QPixmap.fromImage(image)))
        self.window.screen_choice.clear();self.window.screen_choice.addItem('Synthetic display',self.screen)

    def click(self):
        with patch('studyframe.app.QApplication.screens',return_value=[self.screen]):self.window.capture_button.click()

    def test_glass_surface_and_minimal_default_keep_controls_visible(self):
        self.assertTrue(self.window.testAttribute(Qt.WidgetAttribute.WA_TranslucentBackground))
        self.assertTrue(self.window.windowFlags() & Qt.WindowType.FramelessWindowHint)
        self.assertTrue(self.window.windowFlags() & Qt.WindowType.WindowStaysOnTopHint)
        self.assertTrue(self.window.settings_pane.isHidden());self.assertTrue(self.window.review_pane.isHidden())
        self.assertLessEqual(self.window.width(),660)
        surface=self.window.centralWidget().grab().toImage()
        self.assertEqual(surface.pixelColor(0,0).alpha(),0)
        self.assertGreater(surface.pixelColor(12,100).alpha(),0)
        self.assertLess(surface.pixelColor(12,100).alpha(),255)
        self.assertTrue(self.window.capture_button.isVisible());self.assertTrue(self.window.answer.isVisible())

    def test_small_overlay_keeps_primary_window_controls_inside_the_surface(self):
        self.window.resize(470,580);self.app.processEvents()
        for button in (self.window.capture_button,self.window.settings_toggle,self.window.collapse_button,self.window.close_button):
            corner=button.mapTo(self.window,button.rect().bottomRight())
            self.assertLess(corner.x(),self.window.width());self.assertLess(corner.y(),self.window.height())
        self.assertEqual(self.window.scroll.horizontalScrollBar().maximum(),0)
        self.window.review_toggle.setChecked(True);self.app.processEvents();self.app.processEvents()
        self.assertEqual(self.window.scroll.horizontalScrollBar().maximum(),0)

    def test_missing_key_opens_settings_without_capture_or_send(self):
        self.click()
        self.assertFalse(self.window.settings_pane.isHidden());self.assertIsNone(self.window.pending_screen)
        self.screen.grabWindow.assert_not_called();self.manager.post.assert_not_called()

    def test_settings_key_scrolls_into_view_and_collapse_is_reversible(self):
        self.window.settings_toggle.setChecked(True);self.app.processEvents()
        position=self.window.key.mapTo(self.window.scroll.viewport(),self.window.key.rect().topLeft())
        self.assertGreaterEqual(position.y(),0)
        self.assertLess(position.y()+self.window.key.height(),self.window.scroll.viewport().height()+1)
        self.window.settings_toggle.setChecked(False);self.app.processEvents()
        self.assertTrue(self.window.settings_pane.isHidden())

    def test_drag_bar_fallback_moves_only_the_visible_overlay(self):
        from PySide6.QtCore import QPointF,QPoint
        start=self.window.pos();press=Mock();press.button.return_value=Qt.MouseButton.LeftButton
        press.globalPosition.return_value=QPointF(start+QPoint(40,20))
        move=Mock();move.buttons.return_value=Qt.MouseButton.LeftButton
        move.globalPosition.return_value=QPointF(start+QPoint(70,45))
        with patch.object(self.window,'windowHandle',return_value=None):
            self.window.drag_bar.mousePressEvent(press);self.window.drag_bar.mouseMoveEvent(move)
        self.assertEqual(self.window.pos(),start+QPoint(30,25));self.manager.post.assert_not_called()

    def test_single_click_captures_then_sends_fresh_pixels_and_shows_answer(self):
        self.window.key.setText('synthetic-key');self.window.question.setPlainText('Explain this loop')
        old=capture_screen(self.screen);self.window.attachment=old
        self.click();self.assertTrue(self.window.busy);self.assertFalse(self.window.isVisible())
        self.manager.post.assert_not_called()
        self.window.complete_capture()
        self.assertEqual(self.manager.post.call_count,1);self.assertTrue(self.window.busy)
        self.assertTrue(self.window.isVisible());self.assertFalse(self.window.capture_button.isEnabled())
        record=json.loads(self.manager.post.call_args.args[1]);image=record['input'][0]['content'][1]
        self.assertEqual(base64.b64decode(image['image_url'].split(',')[1]),self.window.attachment.data)
        self.assertIsNot(self.window.attachment,old)
        self.assertIn('Explain this loop',record['input'][0]['content'][0]['text'])
        self.assertFalse(self.window.consent.isChecked(),'One-click authorization does not pretend the unseen pixels were reviewed')
        self.reply.finished.emit()
        self.assertEqual(self.window.answer.toPlainText(),'The screen shows a bounded loop.')
        self.assertFalse(self.window.busy);self.assertFalse(self.window.review_pane.isVisible())
        self.assertTrue(self.window.copy_answer_button.isEnabled())

    def test_generic_question_allows_one_click_without_worksheet_fields(self):
        self.window.key.setText('synthetic-key');self.click();self.window.complete_capture()
        self.assertIn('Explain what is on this screen.',json.loads(self.manager.post.call_args.args[1])['input'][0]['content'][0]['text'])
        self.assertEqual(self.manager.post.call_count,1)

    def test_failed_capture_never_sends_an_old_image_or_request(self):
        from studyframe.images import ImageError
        self.window.attachment=capture_screen(self.screen);self.window.question.setPlainText('Old question');self.window.prepare()
        self.window.key.setText('synthetic-key');self.window.consent.setChecked(True)
        old=self.window.attachment;self.click()
        with patch('studyframe.app.capture_screen',side_effect=ImageError('Blocked synthetic capture')):self.window.complete_capture()
        self.manager.post.assert_not_called();self.assertIs(self.window.attachment,old)
        self.assertFalse(self.window.busy);self.assertTrue(self.window.isVisible())
        self.assertIn('nothing sent',self.window.status.text())

    def test_cancel_clear_close_disarm_direct_send_before_timer_completion(self):
        for action in ('cancel_request','clear_session','close'):
            with self.subTest(action=action):
                self.window.show();self.window.key.setText('synthetic-key');self.click()
                getattr(self.window,action)();self.window.complete_capture()
                self.assertIsNone(self.window.direct_request);self.assertIsNone(self.window.pending_screen)
                self.manager.post.assert_not_called()

    def test_connection_or_question_change_during_capture_cancels_the_bound_action(self):
        changes=[lambda:self.window.key.setText('different-key'),lambda:self.window.provider_choice.setCurrentIndex(1),
                 lambda:self.window.question.setPlainText('A newer question')]
        for change in changes:
            self.window.provider_choice.setCurrentIndex(0);self.window.key.setText('synthetic-key');self.click()
            change();self.window.complete_capture();self.manager.post.assert_not_called()
            self.assertIsNone(self.window.direct_request)

    def test_removed_display_requires_new_explicit_click_after_refresh(self):
        self.window.key.setText('synthetic-key')
        with patch('studyframe.app.QApplication.screens',return_value=[]):self.window.capture_and_ask()
        self.assertIsNone(self.window.pending_screen);self.manager.post.assert_not_called()
        self.assertIn('unavailable',self.window.status.text())

    def test_no_duplicate_send_and_collapse_preserves_an_inflight_answer(self):
        self.window.key.setText('synthetic-key');self.click();self.window.complete_capture();self.window.capture_and_ask()
        self.assertEqual(self.manager.post.call_count,1)
        self.window.collapse_button.setChecked(True);self.app.processEvents()
        self.assertLess(self.window.height(),160);self.assertTrue(self.window.scroll.isHidden())
        self.assertTrue(self.window.close_button.isVisible());self.assertFalse(self.window.capture_button.isEnabled())
        self.reply.finished.emit();self.window.collapse_button.setChecked(False);self.app.processEvents()
        self.assertEqual(self.window.answer.toPlainText(),'The screen shows a bounded loop.')
        self.assertFalse(self.window.scroll.isHidden());self.assertTrue(self.window.capture_button.isEnabled())

    def test_followup_is_explicit_and_new_capture_keeps_only_the_last_exchange(self):
        self.window.key.setText('synthetic-key');self.click();self.window.complete_capture();self.reply.finished.emit()
        self.window.start_followup();self.click();self.assertIsNone(self.window.pending_screen)
        self.window.question.setPlainText('What changes with range(4)?')
        self.reply=Reply(response('Now it includes3.'));self.manager.post.return_value=self.reply
        self.click();self.window.complete_capture()
        text=json.loads(self.manager.post.call_args.args[1])['input'][0]['content'][0]['text']
        self.assertIn('Previous AI answer:',text);self.assertIn('The screen shows a bounded loop.',text)
        self.assertEqual(self.manager.post.call_count,2)
