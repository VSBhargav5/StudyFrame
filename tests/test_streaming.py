"""Bounded real provider lifecycle with synthetic SSE chunks, never live keys."""
import json
import unittest
from unittest.mock import Mock
from PySide6.QtWidgets import QApplication
from studyframe.provider import StudyProvider,payload,MAX_RESPONSE
from studyframe.requests import prepare_request
from studyframe.app import StudyWindow
from test_provider import Reply,response


def event(kind,**fields):
    return b'data: '+json.dumps({'type':kind,**fields},ensure_ascii=False).encode()+b'\r\n\r\n'


class StreamingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.app=QApplication.instance() or QApplication([])

    def setUp(self):
        self.reply=Reply();self.reply.headers[b'Content-Type']=b'text/event-stream; charset=utf-8'
        self.manager=Mock();self.manager.post.return_value=self.reply
        self.provider=StudyProvider(manager=self.manager);self.addCleanup(self.provider.cancel)
        self.answers=[];self.errors=[];self.parts=[]
        self.provider.succeeded.connect(self.answers.append)
        self.provider.failed.connect(self.errors.append)
        self.provider.partial.connect(self.parts.append)

    def start(self):self.provider.send(payload('q',provider='openrouter_free'),'synthetic-key','openrouter_free')

    def feed(self,data):
        self.reply.data+=data;self.reply.readyRead.emit()

    def test_split_utf8_comments_multiline_and_authoritative_completion(self):
        self.start()
        data=b': keepalive\r\n\r\n'+event('response.output_text.delta',delta='5 λ')
        for byte in data:self.feed(bytes([byte]))
        self.assertEqual(self.parts,['5 λ']);self.assertEqual(self.answers,[])
        self.feed(b'data: {"type":"response.completed",\r\ndata: "response":'+response('5 λ')+b'}\r\n\r\n')
        self.feed(b'data: [DONE]\n\n');self.reply.finished.emit()
        self.assertEqual(self.answers,['5 λ']);self.assertFalse(self.errors)

    def test_failure_incomplete_and_malformed_never_echo_provider_bodies(self):
        for kind in ('error','response.failed','response.incomplete'):
            self.start();self.feed(event(kind,message='private account body'))
            self.assertNotIn('private',self.errors[-1]);self.assertTrue(self.reply.aborted)
            self.reply.aborted=False
        self.start();self.feed(b'data: {private}\n\n')
        self.assertIn('unreadable',self.errors[-1]);self.assertFalse(self.answers)

    def test_eof_without_completed_is_not_success_even_after_text(self):
        self.start();self.feed(event('response.output_text.delta',delta='Partial'))
        self.reply.finished.emit()
        self.assertFalse(self.answers);self.assertIn('before completion',self.errors[0])

    def test_cancel_ignores_late_stream_and_total_wire_limit_includes_comments(self):
        self.start();self.provider.cancel()
        self.feed(event('response.output_text.delta',delta='late'))
        self.assertFalse(self.parts)
        self.reply.data=b'';self.start();self.feed(b':'+b'x'*MAX_RESPONSE)
        self.assertTrue(self.reply.aborted);self.assertIn('1 MiB',self.errors[-1])

    def test_ui_shows_text_before_finished_and_does_not_reuse_partial_as_followup(self):
        w=StudyWindow(self.provider);self.addCleanup(w.close);self.addCleanup(w.deleteLater)
        w.key.setText('synthetic-key');w.last_exchange=('old','old answer')
        w.send_prepared(payload('q',provider='openrouter_free'),'q')
        self.feed(event('response.output_text.delta',delta='5'))
        self.assertTrue(w.busy);self.assertEqual(w.answer.toPlainText(),'5')
        self.assertFalse(w.copy_answer_button.isEnabled());self.assertIsNone(w.last_exchange)
        self.assertIn('Receiving answer',w.feedback.text())
        self.reply.finished.emit()
        self.assertFalse(w.busy);self.assertIn('Partial answer',w.feedback.text())
        self.assertFalse(w.followup_button.isEnabled());self.assertFalse(w.wait_timer.isActive())

    def test_quick_prompt_and_key_ready_clear_stale_errors_without_network(self):
        text=prepare_request('One sentence please',mode='quick')
        self.assertIn('takes priority',text);self.assertIn('one to three',text)
        w=StudyWindow(self.provider);self.addCleanup(w.close);self.addCleanup(w.deleteLater)
        self.assertEqual(w.mode.currentData(),'quick')
        w.show_feedback('Old timeout',failed=True);w.key.setText('synthetic-key');w.finish_connection()
        self.assertFalse(w.request_failed);self.assertIn('No test request',w.feedback.text())
        self.manager.post.assert_not_called()
