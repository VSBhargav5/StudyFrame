"""Explicit offline portable-runtime verification. No audio/screen/model API call."""
import argparse
import json
import sys
import tempfile
from pathlib import Path


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--model', type=Path)
    args = parser.parse_args(argv)
    if args.output.exists():
        return 2
    from PySide6.QtCore import QObject, Signal, QTimer, QEventLoop
    from PySide6.QtWidgets import QApplication
    from PySide6.QtNetwork import QSslSocket
    from studyframe import __version__
    from studyframe.app import StudyWindow
    from studyframe.preferences import Preferences
    from studyframe.speech import SpeechSession
    app = QApplication([])
    app.setQuitOnLastWindowClosed(False)
    checks = []
    result = {'ok':False, 'version':__version__, 'frozen':bool(getattr(sys,'frozen',False)),
              'checks':checks, 'recorded_audio':False, 'network_request':False}

    class OfflineProvider(QObject):
        succeeded = Signal(str)
        failed = Signal(str)
        quota_received = Signal(str)
        model_used = 'offline-synthetic-fixture'
        mode = 'answer'
        def cancel(self): pass
        def check_quota(self, key):
            self.mode='quota'
            QTimer.singleShot(0,self,lambda:self.quota_received.emit('Synthetic quota: 48 of 50 remaining.'))
        def send(self, body, key, provider):
            self.mode='answer'
            data = json.loads(body)
            content = data['input'][0]['content']
            assert len(content) == 1 and content[0]['type'] == 'input_text'
            QTimer.singleShot(0, self, lambda:self.succeeded.emit('Synthetic answer: 0, 1, 2.'))
    window = None
    try:
        assert QSslSocket.supportsSsl()
        checks.append('packaged-tls-backend-available')
        with tempfile.TemporaryDirectory(prefix='studyframe-selftest-') as folder:
            store = Preferences(Path(folder)/'setup.json')
            window = StudyWindow(OfflineProvider(), preferences=store, start_collapsed=True)
            window.setWindowTitle('StudyFrame — synthetic offline self-test')
            window.show(); app.processEvents()
            assert window.width() <= 440 and window.height() <= 105
            checks.append('native-capsule-startup')
            if app.platformName() == 'windows' and sys.getwindowsversion().build >= 22000:
                # Freeze missing bindings/tables must fail the build, not silently
                # ship the fallback. Remote/OS policy can still affect appearance.
                assert window.native_backdrop is not None
                assert window.centralWidget().native_material
                checks.append('native-compositor-bindings-and-host-target')
            window.key.setText('synthetic-selftest-key')
            window.speech_text.setPlainText('Why does range(3) stop before three?')
            window.ask_transcript(); app.processEvents()
            assert window.answer.toPlainText() == 'Synthetic answer: 0, 1, 2.'
            checks.append('text-only-answer-journey')
            window.settings_toggle.setChecked(True);app.processEvents()
            window.quota_button.click();app.processEvents()
            assert '48 of 50' in window.feedback.text()
            assert window.answer.toPlainText()=='Synthetic answer: 0, 1, 2.'
            checks.append('quota-button-without-model-inference')
            window.save_setup()
            saved = store.path.read_text(encoding='utf-8')
            assert 'selftest-key' not in saved and 'range(3)' not in saved
            window.clear_session()
            assert not window.key.text() and not window.speech_text.toPlainText()
            checks.append('non-secret-setup-and-clear')
            window.preferences = None
            window.close(); window.deleteLater(); window = None

            session = SpeechSession(app); loop = QEventLoop(); observed = {}
            session.transcript.connect(lambda text:(observed.update(text=text),loop.quit()))
            session.failed.connect(lambda text:(observed.update(error=text),loop.quit()))
            timer = QTimer(); timer.setSingleShot(True); timer.timeout.connect(loop.quit)
            if args.model is not None:
                session.start('loopback',str(args.model),check_only=True)
            else:
                # Directly verify the real frozen dispatch/pipes using a missing model.
                from PySide6.QtCore import QProcess
                process = QProcess(app)
                program = sys.executable
                dispatch = ['--speech-worker'] if getattr(sys,'frozen',False) else ['-m','studyframe.speech_worker']
                process.setProgram(program)
                process.setArguments(dispatch+['--source','loopback','--model',str(Path(folder)/'missing-model'),'--check-only'])
                process.finished.connect(loop.quit); process.start()
            timer.start(20000); loop.exec(); timer.stop()
            if args.model is not None:
                session.cancel()
                assert observed.get('text') == 'Local speech backend ready.'
                checks.append('frozen-worker-pipes-and-local-model')
                # Exercise the real warm handshake and metadata list without
                # opening a microphone/playback stream or sending Listen.
                warm_observed = []
                session.level.connect(lambda value: warm_observed.append('audio'))
                session.transcript.connect(lambda text: warm_observed.append('transcript'))
                session.changed.connect(lambda active: loop.quit() if session.prepared else None)
                session.prepare('microphone', str(args.model))
                timer.start(20000); loop.exec(); timer.stop()
                assert session.prepared and not warm_observed
                session.cancel()
                checks.append('warm-recognizer-ready-without-audio')
            else:
                raw = bytes(process.readAllStandardOutput())
                process.kill(); process.waitForFinished(1000); process.deleteLater()
                assert json.loads(raw)['type'] == 'error'
                checks.append('worker-dispatch-and-pipes')
            result['ok'] = True
    except Exception as exc:
        result['failure_type'] = type(exc).__name__
    finally:
        if window is not None: window.close()
    args.output.parent.mkdir(parents=True,exist_ok=True)
    with args.output.open('x',encoding='utf-8') as target:
        json.dump(result,target,indent=2)
    return 0 if result['ok'] else 1
