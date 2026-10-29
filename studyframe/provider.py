"""One explicit, asynchronous OpenAI request. No retries or history."""

import base64
import json

from PySide6.QtCore import QObject, QTimer, QUrl, Signal
from PySide6.QtNetwork import QNetworkAccessManager, QNetworkReply, QNetworkRequest

ENDPOINT = "https://api.openai.com/v1/responses"
MODEL = "gpt-4.1-mini"
MAX_RESPONSE = 1024 * 1024


def payload(text, attachment=None):
    content = [{"type": "input_text", "text": text}]
    if attachment is not None:
        encoded = base64.b64encode(attachment.data).decode("ascii")
        content.append({"type": "input_image", "detail": "auto",
                        "image_url": f"data:image/{attachment.format};base64,{encoded}"})
    return json.dumps({"model": MODEL, "input": [{"role": "user", "content": content}],
                       "store": False, "max_output_tokens": 1500}).encode("utf-8")


def answer_from_response(data):
    try:
        result = json.loads(data)
        if result.get("status") != "completed":
            raise ValueError("The provider did not complete the answer. Try a shorter question.")
        parts = []
        for item in result.get("output", []):
            if item.get("type") == "message" and item.get("role") == "assistant":
                for part in item.get("content", []):
                    if part.get("type") == "refusal":
                        raise ValueError("The provider declined this request. Rephrase your study question.")
                    if part.get("type") == "output_text" and isinstance(part.get("text"), str):
                        parts.append(part["text"])
        text = "\n\n".join(parts).strip()
        if not text:
            raise ValueError("The provider returned no study text.")
        return text
    except (json.JSONDecodeError, UnicodeError, AttributeError, TypeError):
        raise ValueError("The provider returned an unreadable response.") from None


class StudyProvider(QObject):
    succeeded = Signal(str)
    failed = Signal(str)

    def __init__(self, parent=None, manager=None):
        super().__init__(parent)
        self.manager = manager or QNetworkAccessManager(self)
        self.reply = None
        self.buffer = bytearray()
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self.timeout)

    def send(self, body, key):
        if self.reply is not None:
            raise ValueError("A request is already running.")
        if not key or not key.isascii() or any(c.isspace() or ord(c) < 32 or ord(c) == 127 for c in key):
            raise ValueError("Enter a valid API key in the session key field.")
        request = QNetworkRequest(QUrl(ENDPOINT))
        request.setAttribute(QNetworkRequest.Attribute.RedirectPolicyAttribute,
                             QNetworkRequest.RedirectPolicy.ManualRedirectPolicy)
        request.setRawHeader(b"Content-Type", b"application/json")
        request.setRawHeader(b"Authorization", b"Bearer " + key.encode("ascii"))
        self.buffer.clear()
        reply = self.manager.post(request, body)
        self.reply = reply
        reply.setReadBufferSize(MAX_RESPONSE + 1)
        reply.readyRead.connect(lambda: self.read(reply))
        reply.finished.connect(lambda: self.finish(reply))
        self.timer.start(60000)

    def read(self, reply):
        if reply is not self.reply:
            return
        self.buffer.extend(bytes(reply.read(MAX_RESPONSE + 1 - len(self.buffer))))
        if len(self.buffer) > MAX_RESPONSE:
            self.cancel()
            self.failed.emit("The response exceeded the 1 MiB limit.")

    def finish(self, reply):
        if reply is not self.reply:
            return
        self.read(reply)
        if reply is not self.reply:
            return
        self.reply = None
        self.timer.stop()
        status = reply.attribute(QNetworkRequest.Attribute.HttpStatusCodeAttribute)
        error = reply.error()
        data = bytes(self.buffer)
        self.buffer.clear()
        reply.deleteLater()
        messages = {401: "API key rejected. Check the key and project permissions.",
                    403: "This project cannot use the selected model.",
                    429: "Rate or billing limit reached. Check your API account before retrying."}
        if status != 200 or error != QNetworkReply.NetworkError.NoError:
            self.failed.emit(messages.get(status, "Request failed. Check your connection and API access; nothing was retried."))
            return
        try:
            answer = answer_from_response(data)
        except ValueError as exc:
            self.failed.emit(str(exc))
        else:
            self.succeeded.emit(answer)

    def cancel(self):
        reply, self.reply = self.reply, None
        self.timer.stop()
        self.buffer.clear()
        if reply is not None:
            reply.abort()
            reply.deleteLater()

    def timeout(self):
        self.cancel()
        self.failed.emit("Stopped waiting after 60 seconds. The provider may still process and bill the request.")
