"""Explicit fixed public-metadata HTTPS check. No key, model call or study content."""
import argparse
import json
from pathlib import Path


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',required=True,type=Path)
    args=parser.parse_args(argv)
    if args.output.exists():return 2
    from PySide6.QtCore import QCoreApplication,QEventLoop,QTimer,QUrl
    from PySide6.QtNetwork import QNetworkAccessManager,QNetworkRequest,QSslSocket
    app=QCoreApplication([])
    result={'ok':False,'tls_available':QSslSocket.supportsSsl(),
            'tls_backend':QSslSocket.activeBackend(),'http_status':None,
            'sent_key':False,'sent_study_content':False,'model_request':False}
    if result['tls_available']:
        manager=QNetworkAccessManager()
        request=QNetworkRequest(QUrl('https://openrouter.ai/api/v1/models'))
        request.setAttribute(QNetworkRequest.Attribute.RedirectPolicyAttribute,
                             QNetworkRequest.RedirectPolicy.ManualRedirectPolicy)
        reply=manager.get(request)
        reply.setReadBufferSize(1024)
        loop=QEventLoop();timer=QTimer();timer.setSingleShot(True)
        def headers():
            status=reply.attribute(QNetworkRequest.Attribute.HttpStatusCodeAttribute)
            if status is not None:
                result['http_status']=status
                result['ok']=status==200
                loop.quit()
        reply.metaDataChanged.connect(headers)
        reply.finished.connect(loop.quit);timer.timeout.connect(loop.quit)
        timer.start(15000);loop.exec();timer.stop()
        headers()
        if result['http_status'] is None:
            result['network_error']=reply.error().name if reply.isFinished() else 'TimedOut'
        reply.abort();reply.deleteLater()
    args.output.parent.mkdir(parents=True,exist_ok=True)
    with args.output.open('x',encoding='utf-8') as target:json.dump(result,target,indent=2)
    return 0 if result['ok'] else 1
