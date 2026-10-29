import base64
import json
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
import unittest
from types import SimpleNamespace
from unittest.mock import Mock

from PySide6.QtCore import QObject, Signal
from PySide6.QtNetwork import QNetworkReply, QNetworkRequest
from PySide6.QtWidgets import QApplication

from studyframe.provider import StudyProvider, payload, answer_from_response, MAX_RESPONSE, ENDPOINT
from studyframe.app import StudyWindow


def response(text="Try range(3): the stop is excluded."):
    return json.dumps({"status": "completed", "output": [{"type": "message", "role": "assistant",
                       "content": [{"type": "output_text", "text": text}]}]}).encode()


class Reply(QObject):
    readyRead = Signal()
    finished = Signal()

    def __init__(self, data=b"", status=200):
        super().__init__()
        self.data, self.status, self.aborted = data, status, False

    def read(self, size):
        result, self.data = self.data[:size], self.data[size:]
        return result

    def setReadBufferSize(self, size):
        self.limit = size

    def attribute(self, attribute):
        return self.status

    def error(self):
        return QNetworkReply.NetworkError.NoError

    def abort(self):
        self.aborted = True
        self.finished.emit()


class ProviderTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.reply = Reply(response())
        self.manager = Mock()
        self.manager.post.return_value = self.reply
        self.provider = StudyProvider(manager=self.manager)
        self.errors, self.answers = [], []
        self.provider.failed.connect(self.errors.append)
        self.provider.succeeded.connect(self.answers.append)
        self.addCleanup(self.provider.cancel)

    def test_payload_uses_exact_snapshot_not_a_path(self):
        image = SimpleNamespace(data=b"snapshot", format="png")
        body = json.loads(payload("  code\n", image))
        content = body["input"][0]["content"]
        self.assertEqual(content[0]["text"], "  code\n")
        self.assertEqual(base64.b64decode(content[1]["image_url"].split(",")[1]), b"snapshot")
        self.assertFalse(body["store"])
        self.assertEqual(body["max_output_tokens"], 1500)
        self.assertNotIn("tools", body)

    def test_text_only_has_no_image(self):
        self.assertEqual(len(json.loads(payload("question"))["input"][0]["content"]), 1)

    def test_send_is_explicit_fixed_destination_no_redirects(self):
        self.manager.post.assert_not_called()
        self.provider.send(b"{}", "synthetic-key")
        request, body = self.manager.post.call_args.args
        self.assertEqual(request.url().toString(), ENDPOINT)
        self.assertEqual(request.attribute(QNetworkRequest.Attribute.RedirectPolicyAttribute),
                         QNetworkRequest.RedirectPolicy.ManualRedirectPolicy)
        self.assertEqual(bytes(request.rawHeader("Authorization")), b"Bearer synthetic-key")
        self.reply.finished.emit()
        self.assertEqual(self.answers, ["Try range(3): the stop is excluded."])
        self.assertFalse(self.provider.timer.isActive())

    def test_invalid_keys_never_send(self):
        for key in ("", "a\nb", "a b", "λ", "a\x00b", "a\x7fb"):
            with self.assertRaises(ValueError):
                self.provider.send(b"{}", key)
        self.manager.post.assert_not_called()

    def test_duplicate_send_rejected(self):
        self.provider.send(b"{}", "key")
        with self.assertRaises(ValueError):
            self.provider.send(b"{}", "key")
        self.assertEqual(self.manager.post.call_count, 1)

    def test_cancel_ignores_late_completion(self):
        self.provider.send(b"{}", "key")
        self.provider.cancel()
        self.reply.finished.emit()
        self.assertTrue(self.reply.aborted)
        self.assertEqual(self.answers + self.errors, [])

    def test_old_reply_cannot_complete_new_request(self):
        self.provider.send(b"{}", "key")
        old = self.reply
        self.provider.cancel()
        new = Reply(response("new"))
        self.manager.post.return_value = new
        self.provider.send(b"{}", "key")
        old.finished.emit()
        new.finished.emit()
        self.assertEqual(self.answers, ["new"])

    def test_timeout_aborts_without_retry(self):
        self.provider.send(b"{}", "key")
        self.provider.timeout()
        self.assertTrue(self.reply.aborted)
        self.assertIn("60 seconds", self.errors[0])
        self.assertEqual(self.manager.post.call_count, 1)

    def test_oversized_response_aborts(self):
        self.reply.data = b"x" * (MAX_RESPONSE + 1)
        self.provider.send(b"{}", "key")
        self.reply.readyRead.emit()
        self.assertTrue(self.reply.aborted)
        self.assertEqual(self.answers, [])
        self.assertIn("1 MiB", self.errors[0])

    def test_error_body_never_echoes_secrets_or_retries(self):
        for status in (301, 400, 401, 403, 429, 500):
            self.reply = Reply(b"private screenshot and key", status)
            self.manager.post.return_value = self.reply
            self.provider.send(b"{}", "key")
            self.reply.finished.emit()
            self.assertNotIn("private", self.errors[-1])
        self.assertEqual(self.answers, [])

    def test_malformed_incomplete_empty_and_refused_responses(self):
        for data in (b"bad", b"[]", b"null", b"{}", b'{"status":"incomplete"}',
                     b'{"status":"completed","output":null}',
                     b'{"status":"completed","output":[{"type":"message","role":"assistant","content":[{"type":"refusal"}]}]}'):
            with self.subTest(data=data), self.assertRaises(ValueError):
                answer_from_response(data)

    def test_window_consent_send_answer_and_invalidation(self):
        window = StudyWindow(self.provider)
        self.addCleanup(window.close)
        window.question.setPlainText("Why?")
        window.prepare()
        window.key.setText("synthetic-key")
        self.assertFalse(window.send_button.isEnabled())
        window.consent.setChecked(True)
        window.send_request()
        self.assertFalse(window.question.isEnabled())
        self.reply.finished.emit()
        self.assertTrue(window.question.isEnabled())
        self.assertTrue(window.answer.toPlainText())
        self.assertFalse(window.consent.isChecked())
        window.question.insertPlainText("new")
        self.assertEqual(window.answer.toPlainText(), "")

    def test_window_failure_preserves_inputs_and_requires_new_consent(self):
        window = StudyWindow(self.provider)
        self.addCleanup(window.close)
        window.question.setPlainText("Why?")
        window.prepare()
        window.key.setText("key")
        window.consent.setChecked(True)
        self.reply.status = 429
        window.send_request()
        self.reply.finished.emit()
        self.assertEqual(window.question.toPlainText(), "Why?")
        self.assertTrue(window.preview.toPlainText())
        self.assertFalse(window.send_button.isEnabled())

    def test_clear_cancels_and_clears_key_without_late_answer(self):
        window = StudyWindow(self.provider)
        self.addCleanup(window.close)
        window.question.setPlainText("Why?")
        window.prepare()
        window.key.setText("key")
        window.consent.setChecked(True)
        window.send_request()
        window.clear_session()
        self.reply.finished.emit()
        self.assertEqual(window.key.text(), "")
        self.assertEqual(window.answer.toPlainText(), "")
        self.assertTrue(self.reply.aborted)
