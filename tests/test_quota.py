import json
import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from unittest.mock import Mock
import unittest
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from studyframe.app import StudyWindow
from studyframe.provider import StudyProvider,quota_from_response
from test_provider import Reply


class QuotaTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.app=QApplication.instance() or QApplication([])

    def data(self,used=2,limit=50,remaining=48):
        return json.dumps({'data':{'label':'DO NOT ECHO PRIVATE LABEL','limit':5,
            'free_model_daily_requests':{'used':used,'limit':limit,'remaining':remaining}}}).encode()

    def test_counters_are_not_inferred_from_spending_cap_and_bad_values_fail_closed(self):
        text=quota_from_response(self.data())
        self.assertIn('48 of 50',text);self.assertIn('per-minute',text);self.assertNotIn('PRIVATE',text)
        for data in (b'{}',b'bad',self.data(True),self.data(-1),self.data(2,50,51)):
            with self.assertRaises(ValueError):quota_from_response(data)

    def test_explicit_quota_get_sends_no_model_request_and_preserves_previous_answer(self):
        manager=Mock();reply=Reply(self.data());manager.get.return_value=reply
        provider=StudyProvider(manager=manager);w=StudyWindow(provider)
        self.addCleanup(w.deleteLater);self.addCleanup(w.close)
        w.show();self.app.processEvents()
        w.key.setText('synthetic-key');w.answer.setPlainText('Previous answer')
        w.settings_toggle.setChecked(True);self.app.processEvents()
        w.scroll.ensureWidgetVisible(w.quota_button);self.app.processEvents()
        self.assertTrue(w.quota_button.isEnabled())
        manager.get.assert_not_called()
        QTest.mouseClick(w.quota_button,Qt.MouseButton.LeftButton)
        self.assertTrue(w.busy)
        request=manager.get.call_args.args[0]
        self.assertEqual(request.url().toString(),'https://openrouter.ai/api/v1/key')
        self.assertEqual(bytes(request.rawHeader('Authorization')),b'Bearer synthetic-key')
        manager.post.assert_not_called()
        reply.finished.emit()
        self.assertFalse(w.busy);self.assertIn('48 of 50',w.feedback.text())
        self.assertEqual(w.answer.toPlainText(),'Previous answer')
        w.provider_choice.setCurrentIndex(w.provider_choice.findData('openai'))
        w.key.setText('synthetic-other-key');self.assertFalse(w.quota_button.isEnabled())

    def test_retry_delay_is_bounded_and_private_error_body_is_not_echoed(self):
        for header,expected in [(b'60','60 seconds'),(b'private header','nothing'),(b'999999999','nothing')]:
            manager=Mock();reply=Reply(b'private provider body',429);reply.headers[b'Retry-After']=header
            manager.post.return_value=reply;provider=StudyProvider(manager=manager);errors=[]
            provider.failed.connect(errors.append)
            provider.send(b'{}','synthetic-key');reply.finished.emit()
            self.assertNotIn('private',errors[0]);self.assertIn(expected.lower(),errors[0].lower())
            self.assertEqual(manager.post.call_count,1)
