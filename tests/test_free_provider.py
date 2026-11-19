import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
import copy
import json
import unittest
from unittest.mock import Mock
from PySide6.QtWidgets import QApplication
from studyframe.provider import StudyProvider,payload,provider_config,FREE_POLICY
from studyframe.app import StudyWindow
from test_provider import Reply,response


class FreeProviderTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.app=QApplication.instance() or QApplication([])

    def setUp(self):
        self.reply=Reply(response());self.manager=Mock();self.manager.post.return_value=self.reply
        self.provider=StudyProvider(manager=self.manager);self.addCleanup(self.provider.cancel)

    def test_fixed_free_route_and_zero_cost_policy_no_tools_or_paid_models(self):
        body=payload('Explain the screen',provider='openrouter_free');record=json.loads(body)
        self.assertEqual(record['model'],'openrouter/free');self.assertEqual(record['provider'],FREE_POLICY)
        self.assertEqual(record['provider']['data_collection'],'deny');self.assertTrue(record['provider']['allow_fallbacks'])
        self.assertTrue(all(v==0 for v in record['provider']['max_price'].values()))
        self.provider.send(body,'synthetic-key','openrouter_free')
        request,submitted=self.manager.post.call_args.args
        self.assertEqual(request.url().toString(),'https://openrouter.ai/api/v1/responses')
        self.assertEqual(submitted,body);self.assertNotIn('tools',record)

    def test_unsupported_destinations_and_paid_fallback_body_fail_before_network(self):
        for value in ('https://bad.invalid','openrouter','',None,{},False):
            with self.subTest(provider=value),self.assertRaises(ValueError):self.provider.send(b'{}','key',value)
        original=json.loads(payload('q',provider='openrouter_free'))
        changes=[{'model':'paid/model'},{'models':['paid/model']},{'store':True},{'max_output_tokens':9999},{'provider':{}},{'tools':[]}]
        for changeset in changes:
            changed=copy.deepcopy(original);changed.update(changeset)
            with self.subTest(change=changeset),self.assertRaises(ValueError):self.provider.send(json.dumps(changed).encode(),'key','openrouter_free')
        self.manager.post.assert_not_called()

    def test_free_backup_providers_cannot_weaken_price_or_data_policy(self):
        for field in ('prompt','completion','request','image','data_collection'):
            record=json.loads(payload('q',provider='openrouter_free'))
            if field=='data_collection':record['provider'][field]='allow'
            else:record['provider']['max_price'][field]=0.01
            with self.assertRaises(ValueError):
                self.provider.send(json.dumps(record).encode(),'synthetic-key','openrouter_free')
        self.manager.post.assert_not_called()

    def test_provider_switch_clears_key_preview_consent_and_previous_exchange(self):
        window=StudyWindow(self.provider);self.addCleanup(window.close)
        self.assertEqual(window.provider_choice.currentData(),'openrouter_free')
        window.question.setPlainText('What does this do?');window.prepare();window.key.setText('free-key');window.consent.setChecked(True)
        window.last_exchange=('old question','old answer');window.followup_context=window.last_exchange
        window.provider_choice.setCurrentIndex(1)
        self.assertEqual(window.key.text(),'');self.assertEqual(window.preview.toPlainText(),'')
        self.assertFalse(window.consent.isChecked());self.assertIsNone(window.last_exchange);self.assertIsNone(window.followup_context)
        self.manager.post.assert_not_called();self.assertIn('paid',window.disclosure.text())

    def test_answer_reports_sanitized_model_and_free_errors_do_not_retry_or_fallback(self):
        data=json.loads(response());data['model']='synthetic/vision-model';self.reply.data=json.dumps(data).encode()
        self.provider.send(payload('q',provider='openrouter_free'),'key','openrouter_free');self.reply.finished.emit()
        self.assertEqual(self.provider.model_used,'synthetic/vision-model')
        for code in (402,404,429,503):
            self.reply=Reply(b'sensitive provider error',code);self.manager.post.return_value=self.reply
            errors=[];self.provider.failed.connect(errors.append)
            self.provider.send(payload('q',provider='openrouter_free'),'key','openrouter_free');self.reply.finished.emit()
            self.assertEqual(len(errors),1);self.assertNotIn('sensitive',errors[0])
        self.assertEqual(self.manager.post.call_count,5)

    def test_free_window_send_has_reviewed_body_and_fixed_destination(self):
        window=StudyWindow(self.provider);self.addCleanup(window.close)
        window.question.setPlainText('Why range(3)?');window.prepare();window.key.setText('synthetic-key')
        window.send_request();self.manager.post.assert_not_called()
        window.consent.setChecked(True);window.send_request()
        self.assertFalse(window.provider_choice.isEnabled());self.assertFalse(window.capture_button.isEnabled())
        self.assertEqual(json.loads(self.manager.post.call_args.args[1])['model'],'openrouter/free')
        self.reply.finished.emit();self.assertTrue(window.answer.toPlainText());self.assertFalse(window.consent.isChecked())
