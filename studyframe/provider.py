"""Explicit fixed-host answer or quota request. No app retries or paid fallback."""

import base64
import json

from PySide6.QtCore import QObject, QTimer, QUrl, Signal
from PySide6.QtNetwork import QNetworkAccessManager, QNetworkReply, QNetworkRequest

ENDPOINT = "https://api.openai.com/v1/responses"
MODEL = "gpt-4.1-mini"
MAX_RESPONSE = 1024 * 1024
MAX_QUOTA_RESPONSE = 32768
PROVIDERS = {
    'openai': {'label':'OpenAI (paid)', 'endpoint':ENDPOINT, 'model':MODEL},
    'openrouter_free': {'label':'OpenRouter (free models)',
                        'endpoint':'https://openrouter.ai/api/v1/responses', 'model':'openrouter/free'},
}
FREE_POLICY = {'max_price':{'prompt':0,'completion':0,'request':0,'image':0},
               'allow_fallbacks':True, 'data_collection':'deny'}


def provider_config(identifier):
    if not isinstance(identifier,str) or identifier not in PROVIDERS:
        raise ValueError('Choose a supported AI provider.')
    return PROVIDERS[identifier]


def payload(text, attachment=None, provider="openai"):
    config = provider_config(provider)
    content = [{"type": "input_text", "text": text}]
    if attachment is not None:
        encoded = base64.b64encode(attachment.data).decode("ascii")
        content.append({"type": "input_image", "detail": "auto",
                        "image_url": f"data:image/{attachment.format};base64,{encoded}"})
    body = {"model": config['model'], "input": [{"role": "user", "content": content}],
            "store": False, "max_output_tokens": 1500}
    if provider == 'openrouter_free':body['provider'] = FREE_POLICY
    return json.dumps(body).encode('utf-8')


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


def quota_from_response(data):
    """Render only documented counters; never echo account labels or raw JSON."""
    try:
        quota=json.loads(data)['data']['free_model_daily_requests']
        values=[quota[name] for name in ('used','limit','remaining')]
        if any(type(v) is not int or not 0<=v<=10**9 for v in values):raise ValueError()
        used,limit,remaining=values
        if remaining>limit:raise ValueError()
    except (ValueError,TypeError,KeyError):
        raise ValueError('Daily free usage was not reported in a recognized format. No remaining quota was inferred.') from None
    return (f'OpenRouter reports {remaining} of {limit} free-model requests remaining in the current UTC day ({used} used). '
            'This tier counter does not include per-minute or individual-provider limits.')


def retry_after_hint(reply):
    value=bytes(reply.rawHeader(b'Retry-After'))
    if value.isdigit() and len(value)<=5 and 0<int(value)<=86400:
        return f' Provider asks to wait at least {int(value)} seconds before a manual retry.'
    return ''


class StudyProvider(QObject):
    succeeded = Signal(str)
    failed = Signal(str)
    quota_received = Signal(str)

    def __init__(self, parent=None, manager=None):
        super().__init__(parent)
        self.manager = manager or QNetworkAccessManager(self)
        self.reply = None
        self.model_used = ""
        self.provider_id = 'openai'
        self.mode = 'answer'
        self.buffer = bytearray()
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self.timeout)

    def send(self, body, key, provider="openai"):
        config = provider_config(provider)
        if self.reply is not None:
            raise ValueError("A request is already running.")
        if not key or not key.isascii() or any(c.isspace() or ord(c) < 32 or ord(c) == 127 for c in key):
            raise ValueError("Enter a valid API key in the session key field.")
        if provider == 'openrouter_free':
            try:record = json.loads(body)
            except (ValueError,TypeError):raise ValueError('Prepare the free-model request again.') from None
            if (not isinstance(record,dict) or set(record) != {'model','input','store','max_output_tokens','provider'}
                    or record.get('model') != 'openrouter/free' or record.get('provider') != FREE_POLICY
                    or record.get('store') is not False or type(record.get('max_output_tokens')) is not int
                    or record['max_output_tokens'] != 1500):
                raise ValueError('The free route requires its fixed model and zero-price policy.')
        self.model_used = ''
        self.mode = 'answer'
        self.provider_id = provider
        request = QNetworkRequest(QUrl(config['endpoint']))
        request.setAttribute(QNetworkRequest.Attribute.RedirectPolicyAttribute,
                             QNetworkRequest.RedirectPolicy.ManualRedirectPolicy)
        request.setRawHeader(b"Content-Type", b"application/json")
        request.setRawHeader(b"Authorization", b"Bearer " + key.encode("ascii"))
        self.watch(self.manager.post(request, body),60000)

    def check_quota(self, key):
        if self.reply is not None:raise ValueError('A request is already running.')
        if not key or not key.isascii() or any(c.isspace() or ord(c)<32 or ord(c)==127 for c in key):
            raise ValueError('Enter a valid session key before checking free usage.')
        self.mode='quota';self.provider_id='openrouter_free'
        request=QNetworkRequest(QUrl('https://openrouter.ai/api/v1/key'))
        request.setAttribute(QNetworkRequest.Attribute.RedirectPolicyAttribute,QNetworkRequest.RedirectPolicy.ManualRedirectPolicy)
        request.setRawHeader(b'Authorization',b'Bearer '+key.encode('ascii'))
        self.watch(self.manager.get(request),15000)

    def watch(self, reply, deadline):
        self.buffer.clear()
        self.reply = reply
        reply.setReadBufferSize((MAX_QUOTA_RESPONSE if self.mode=='quota' else MAX_RESPONSE) + 1)
        reply.readyRead.connect(lambda: self.read(reply))
        reply.finished.connect(lambda: self.finish(reply))
        self.timer.start(deadline)

    def read(self, reply):
        if reply is not self.reply:
            return
        limit=MAX_QUOTA_RESPONSE if self.mode=='quota' else MAX_RESPONSE
        self.buffer.extend(bytes(reply.read(limit + 1 - len(self.buffer))))
        if len(self.buffer) > limit:
            self.cancel()
            self.failed.emit('The usage response exceeded the 32 KiB limit.' if self.mode=='quota' else "The response exceeded the 1 MiB limit.")

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
        hint=retry_after_hint(reply) if status in (429,503) else ''
        reply.deleteLater()
        messages = {400: "The provider rejected the request format or parameters.",
                    402: "Account or key credit access restricted. No paid fallback was attempted.",
                    401: "API key rejected. Check the key and project permissions.",
                    403: "This project cannot use the selected model.",
                    404: ("No compatible free endpoint matched the model, image support or privacy/price filters. No paid fallback was attempted."
                          if self.provider_id=='openrouter_free' else "Selected model or endpoint unavailable."),
                    429: "Rate limit reached. Check free usage in model settings. Per-minute/provider limits can apply even with daily quota left. Nothing was retried.",
                    502: "The upstream provider failed. Try again later.",
                    503: "The provider is unavailable. Try again later.",
                    504: "The upstream provider timed out. Nothing was retried."}
        if self.mode=='quota' and status==404:
            messages[404]='Usage metadata endpoint unavailable. No model request was made.'
        if status != 200 or error != QNetworkReply.NetworkError.NoError:
            if status is not None:
                self.failed.emit(f'HTTP {status}: '+messages.get(status,"Request failed. Check provider access; nothing was retried.")+hint)
            else:
                network = {QNetworkReply.NetworkError.SslHandshakeFailedError:"Secure connection failed. Check system time and TLS/certificate configuration.",
                           QNetworkReply.NetworkError.HostNotFoundError:"Provider host could not be found. Check your network/DNS.",
                           QNetworkReply.NetworkError.ConnectionRefusedError:"Connection refused. Check network or proxy settings."}
                self.failed.emit(network.get(error,"No HTTP response received. Check your network; nothing was retried."))
            return
        if self.mode=='quota':
            try: summary=quota_from_response(data)
            except ValueError as exc:self.failed.emit(str(exc))
            else:self.quota_received.emit(summary)
            return
        try:
            answer = answer_from_response(data)
        except ValueError as exc:
            self.failed.emit(str(exc))
        else:
            model = json.loads(data).get('model','')
            self.model_used = model if isinstance(model,str) and len(model) <= 200 and all(32 <= ord(c) < 127 for c in model) else ''
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
        self.failed.emit('Usage check timed out after 15 seconds. No model request was made.' if self.mode=='quota' else
                         "Stopped waiting after 60 seconds. The provider may still process and bill the request.")
