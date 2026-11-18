import json
import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
import threading
import tempfile
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, MagicMock, patch

from PySide6.QtCore import QObject, Signal, QEventLoop, QTimer, QProcess
from PySide6.QtWidgets import QApplication
from studyframe.speech import SpeechSession, validate_speech_setup
from studyframe.speech_worker import pcm16, choose_device, recognize
from studyframe.app import StudyWindow
from studyframe.provider import StudyProvider
from test_provider import Reply, response

try:
    import numpy as np
except ImportError:
    np = None


class WorkerContractTests(unittest.TestCase):
    @unittest.skipIf(np is None, 'Optional speech dependencies not installed')
    def test_downmix_clipping_pcm_endianness_and_invalid_samples(self):
        block = np.array([[1, -1], [2, 2], [-2, -2], [0.5, 0.5]], dtype=np.float32)
        self.assertEqual(np.frombuffer(pcm16(block), dtype='<i2').tolist(), [0, 32767, -32767, 16383])
        for invalid in (np.ones(2), np.ones((1601, 2)), np.ones((2, 33)), np.array([[float('nan')]])):
            with self.assertRaises(ValueError): pcm16(invalid)

    def test_exact_loopback_and_microphone_source_never_silently_fallback(self):
        mic = SimpleNamespace(id='mic', isloopback=False)
        loop = SimpleNamespace(id='speaker', isloopback=True)
        sc = Mock(); sc.default_microphone.return_value = mic
        sc.default_speaker.return_value = SimpleNamespace(id='speaker')
        sc.get_microphone.return_value = loop
        self.assertIs(choose_device(sc, 'microphone'), mic)
        self.assertIs(choose_device(sc, 'loopback'), loop)
        sc.get_microphone.assert_called_once_with(id='speaker', include_loopback=True)
        for wrong in (None, mic, SimpleNamespace(id='other', isloopback=True)):
            sc.get_microphone.return_value = wrong
            with self.assertRaises(ValueError): choose_device(sc, 'loopback')

    @unittest.skipIf(np is None, 'Optional speech dependencies not installed')
    def test_stop_closes_device_collects_final_text_and_mono_channel_map(self):
        stop = threading.Event(); device = MagicMock(); device.channels = 1; device.isloopback = False
        recorder = device.recorder.return_value.__enter__.return_value
        # Mock magic context methods explicitly: no actual device or audio API.
        def record(**kwargs):
            stop.set()
            return np.zeros((1600, 2), dtype=np.float32)
        recorder.record.side_effect = record
        recognizer = Mock(); recognizer.AcceptWaveform.return_value = True
        recognizer.Result.return_value = '{"text":"why does"}'
        recognizer.FinalResult.return_value = '{"text":"range stop"}'
        emit = Mock()
        self.assertEqual(recognize(device, recognizer, stop, emit), 'why does range stop')
        emit.assert_any_call('level', '0')
        device.recorder.assert_called_once_with(samplerate=16000, channels=[0, 0], blocksize=6400)
        device.recorder.return_value.__exit__.assert_called_once()
        stop.set(); device.recorder.reset_mock()
        self.assertEqual(recognize(device, recognizer, stop, emit), '')
        device.recorder.assert_not_called()

    def test_missing_optional_setup_is_actionable_and_does_not_import_audio_backend(self):
        with patch('studyframe.speech.sys.platform', 'win32'), \
             patch('studyframe.speech.importlib.util.find_spec', return_value=None):
            with self.assertRaisesRegex(ValueError, 'optional speech dependencies'):
                validate_speech_setup('loopback', 'unused')


class Process(QObject):
    readyReadStandardOutput = Signal()
    readyReadStandardError = Signal()
    finished = Signal(int, int)
    errorOccurred = Signal(int)
    ProcessState = SimpleNamespace(NotRunning=0)
    def __init__(self, parent=None):
        super().__init__(parent)
        self.output = b''
        self.setProgram = Mock(); self.setArguments = Mock(); self.start = Mock()
        self.write = Mock(); self.kill = Mock()
    def state(self): return 0
    def readAllStandardOutput(self):
        data, self.output = self.output, b''
        return data
    def readAllStandardError(self): return b''
    def event_line(self, kind, text):
        self.output += json.dumps({'type': kind, 'text': text}).encode() + b'\n'
        self.readyReadStandardOutput.emit()


class RealWorkerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): cls.app = QApplication.instance() or QApplication([])

    @unittest.skipUnless(sys.platform == 'win32' and np is not None, 'Windows speech backend')
    def test_nonblocking_stop_pipe_does_not_deadlock_native_imports(self):
        process = QProcess(self.app); loop = QEventLoop(); output = bytearray()
        code = ('import time; from studyframe.speech_worker import PipeStop; stop=PipeStop(); '
                'import numpy,soundcard; print("imports-ready",flush=True); '
                '\nwhile not stop.is_set(): time.sleep(0.01)\nprint("stopped",flush=True)')
        def read():
            output.extend(bytes(process.readAllStandardOutput()))
            if b'imports-ready' in output: process.write(b'stop\n')
        process.readyReadStandardOutput.connect(read)
        process.finished.connect(loop.quit)
        process.setProgram(sys.executable); process.setArguments(['-u', '-c', code]); process.start()
        timer = QTimer(); timer.setSingleShot(True); timer.timeout.connect(loop.quit); timer.start(8000)
        loop.exec(); timer.stop(); read()
        process.kill(); process.waitForFinished(1000); process.deleteLater()
        self.assertIn(b'imports-ready', output)
        self.assertIn(b'stopped', output)

    def test_actual_worker_invalid_model_exits_without_opening_audio(self):
        session = SpeechSession()
        loop = QEventLoop(); errors = []
        session.failed.connect(lambda text: (errors.append(text), loop.quit()))
        self.addCleanup(session.cancel)
        with tempfile.TemporaryDirectory() as directory, \
             patch('studyframe.speech.validate_speech_setup', return_value=directory + '/nonexistent-model'):
            session.start('loopback', directory)
            timer = QTimer(); timer.setSingleShot(True); timer.timeout.connect(loop.quit); timer.start(5000)
            loop.exec(); timer.stop()
        self.assertTrue(errors)
        self.assertFalse(session.active)
        self.assertNotIn('nonexistent-model', errors[0])


class SessionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): cls.app = QApplication.instance() or QApplication([])
    def setUp(self):
        self.session = SpeechSession()
        self.addCleanup(self.session.cancel)
        self.text = Mock(); self.error = Mock()
        self.session.transcript.connect(self.text); self.session.failed.connect(self.error)
        self.factory = patch('studyframe.speech.QProcess', Process)
        self.factory.start(); self.addCleanup(self.factory.stop)
        setup = patch('studyframe.speech.validate_speech_setup', return_value='trusted-model')
        setup.start(); self.addCleanup(setup.stop)
    def start(self):
        self.session.start('loopback', 'model')
        return self.session.process
    def test_stop_finishes_transcript_without_network_and_duplicate_start_is_ignored(self):
        with patch('studyframe.speech.sys.executable', '/runtime/pythonw.exe'):
            process = self.start()
        self.assertTrue(process.setProgram.call_args.args[0].endswith('python.exe'))
        self.session.start('microphone', 'other')
        self.assertIs(self.session.process, process)
        process.setArguments.assert_called_once_with(['-m', 'studyframe.speech_worker', '--source', 'loopback', '--model', 'trusted-model'])
        self.session.stop(); process.write.assert_called_once_with(b'stop\n')
        process.event_line('started', 'Computer playback audio')
        process.event_line('status', 'Finalizing locally')
        process.event_line('transcript', 'What is a generator?')
        process.finished.emit(0, 0)
        self.text.assert_called_once_with('What is a generator?')
        self.assertFalse(self.session.active); self.error.assert_not_called()
    def test_cancel_kills_and_late_reply_cannot_complete_another_session(self):
        old = self.start(); self.session.cancel(); old.kill.assert_called_once()
        new = self.start()
        old.event_line('transcript', 'stale text'); old.finished.emit(0, 0)
        self.assertIs(self.session.process, new); self.text.assert_not_called()
        self.session.timeout(); self.assertFalse(self.session.active)
        new.kill.assert_called_once(); self.error.assert_called_once()
    def test_invalid_oversized_empty_and_failed_worker_never_yield_transcript(self):
        for output, code in ((b'not-json\n', 0), (b'x'*65537, 0),
                             (b'{"type":"transcript","text":""}\n', 0),
                             (b'{"type":"transcript","text":"partial"}', 0),
                             (b'{"type":"error","text":"private/device/path"}\n', 2)):
            with self.subTest(output=output[:20]):
                process = self.start(); process.output = output
                process.readyReadStandardOutput.emit(); process.finished.emit(code, 0)
                self.text.assert_not_called(); self.assertFalse(self.session.active)
                self.assertNotIn('private/device/path', str(self.error.call_args))

    def test_signal_level_distinguishes_silence_from_unrecognized_audio(self):
        for level, message in ((0, 'No input signal'), (60, 'Audio was detected')):
            process = self.start()
            process.event_line('level', str(level))
            process.event_line('transcript', '')
            process.finished.emit(0,0)
            self.assertIn(message, self.error.call_args.args[0])
        process = self.start(); process.event_line('level', '101')
        self.assertFalse(self.session.active)


class FakeSpeech(QObject):
    changed = Signal(bool)
    status = Signal(str)
    transcript = Signal(str)
    failed = Signal(str)
    level = Signal(int)
    active = False
    def start(self, source, model): self.active = True; self.source = source; self.changed.emit(True)
    def stop(self): self.active = False; self.changed.emit(False)
    def cancel(self): self.stop()


class VoiceUITests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): cls.app = QApplication.instance() or QApplication([])
    def setUp(self):
        self.speech = FakeSpeech()
        self.reply = Reply(response('A generator yields values lazily.'))
        self.manager = Mock(); self.manager.post.return_value = self.reply
        self.window = StudyWindow(StudyProvider(manager=self.manager), speech=self.speech, start_collapsed=True)
        self.window.show(); self.app.processEvents()
        self.addCleanup(self.window.deleteLater); self.addCleanup(self.window.close)
    def test_sources_stop_and_clear_keep_recording_explicit_and_never_send(self):
        self.assertFalse(self.speech.active)
        self.window.voice_button.click(); self.assertFalse(self.speech.active)
        self.assertFalse(self.window.collapse_button.isChecked())
        for source in ('loopback', 'microphone'):
            self.window.speech_source.setCurrentIndex(self.window.speech_source.findData(source))
            self.window.speech_record.click(); self.assertEqual(self.speech.source, source)
            self.speech.level.emit(55); self.assertEqual(self.window.speech_level.value(), 55)
            self.assertFalse(self.window.capture_button.isEnabled())
            self.assertFalse(self.window.speech_source.isEnabled())
            self.window.voice_button.click(); self.assertFalse(self.speech.active)
        self.window.speech_record.click(); self.window.clear_session()
        self.assertFalse(self.speech.active); self.assertFalse(self.window.speech_text.toPlainText())
        self.assertEqual(self.window.speech_level.value(), 0)
        self.manager.post.assert_not_called()
    def test_reviewed_transcript_sends_text_only_even_with_existing_image_notes_and_history(self):
        from PySide6.QtCore import Qt, QRect
        from PySide6.QtGui import QImage, QPixmap
        from studyframe.capture import capture_screen
        image = QImage(20, 20, QImage.Format.Format_RGB32); image.fill(Qt.GlobalColor.red)
        screen = SimpleNamespace(name=lambda:'synthetic', geometry=lambda:QRect(0,0,20,20),
                                 devicePixelRatio=lambda:1, grabWindow=lambda _:QPixmap.fromImage(image))
        self.window.attachment = capture_screen(screen)
        self.window.context.setPlainText('DO NOT SEND THESE NOTES')
        self.window.followup_context = ('old question', 'old answer')
        self.speech.transcript.emit('What is a generator?')
        self.manager.post.assert_not_called()
        self.window.ask_speech.click(); self.assertTrue(self.window.settings_toggle.isChecked())
        self.window.key.setText('synthetic-key')
        self.window.speech_text.setPlainText('Explain a Python generator')
        self.window.ask_speech.click()
        body = json.loads(self.manager.post.call_args.args[1])
        content = body['input'][0]['content']
        self.assertEqual(len(content), 1); self.assertEqual(content[0]['type'], 'input_text')
        self.assertIn('Explain a Python generator', content[0]['text'])
        self.assertNotIn('DO NOT SEND', content[0]['text']); self.assertNotIn('old answer', content[0]['text'])
        self.reply.finished.emit()
        self.assertIn('lazily', self.window.answer.toPlainText())
