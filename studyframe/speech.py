"""Explicit local speech sessions in a disposable, cancellable worker process."""
import importlib.util
import json
import sys
from pathlib import Path

from PySide6.QtCore import QObject, QProcess, QTimer, Signal

MAX_TRANSCRIPT = 4000
MAX_OUTPUT = 64 * 1024


def validate_speech_setup(source, model):
    if sys.platform != 'win32' or source not in ('microphone', 'loopback'):
        raise ValueError('Choose microphone or computer audio on Windows.')
    if any(importlib.util.find_spec(name) is None for name in ('soundcard', 'vosk', 'numpy')):
        raise ValueError('Install the optional speech dependencies first. See docs/speech.md.')
    path = Path(model)
    if not path.is_dir() or not (path / 'am/final.mdl').is_file() or not (path / 'conf/model.conf').is_file():
        raise ValueError('Choose an extracted, trusted Vosk model folder. See docs/speech.md.')
    return str(path.resolve())


class SpeechSession(QObject):
    changed = Signal(bool)
    status = Signal(str)
    transcript = Signal(str)
    failed = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.process = None
        self.buffer = bytearray()
        self.total = 0
        self.result = None
        self.problem = None
        self.deadline = QTimer(self)
        self.deadline.setSingleShot(True)
        self.deadline.timeout.connect(self.timeout)

    @property
    def active(self):
        return self.process is not None

    def start(self, source, model):
        if self.active:
            return
        try:
            model = validate_speech_setup(source, model)
        except (ValueError, OSError) as exc:
            self.failed.emit(str(exc))
            return
        process = QProcess(self)
        self.process = process
        self.buffer.clear(); self.total = 0; self.result = None; self.problem = None
        executable = Path(sys.executable)
        # pythonw can have no standard streams; the worker needs private pipes.
        if executable.name.lower() == 'pythonw.exe':
            executable = executable.with_name('python.exe')
        process.setProgram(str(executable))
        process.setArguments(['-m', 'studyframe.speech_worker', '--source', source, '--model', model])
        process.readyReadStandardOutput.connect(lambda: self.read_output(process))
        process.readyReadStandardError.connect(lambda: process.readAllStandardError())
        process.finished.connect(lambda code, state: self.finished(process, code))
        process.errorOccurred.connect(lambda error: self.process_error(process))
        self.changed.emit(True)
        self.status.emit('Loading local recognizer. Recording stops after 30 seconds; Stop finishes early.')
        self.deadline.start(45000)  # Includes bounded model/backend startup.
        process.start()

    def stop(self):
        if self.process is not None:
            self.process.write(b'stop\n')
            self.status.emit('Stopping and finalizing locally…')
            self.deadline.start(3000)

    def cancel(self):
        process, self.process = self.process, None
        self.deadline.stop()
        self.buffer.clear(); self.result = None; self.problem = None
        if process is not None:
            process.setParent(None)
            process.kill()
            process.finished.connect(process.deleteLater)
            if process.state() == QProcess.ProcessState.NotRunning:
                process.deleteLater()
            self.changed.emit(False)

    def abort(self, message):
        self.cancel()
        self.failed.emit(message)

    def timeout(self):
        self.abort('Local speech timed out and was stopped. No transcript was sent.')

    def process_error(self, process):
        if process is self.process:
            self.abort('The local speech worker could not run. Check the optional installation; no audio was sent.')

    def read_output(self, process):
        if process is not self.process:
            return
        chunk = bytes(process.readAllStandardOutput())
        self.total += len(chunk)
        if self.total > MAX_OUTPUT:
            self.abort('Local speech output exceeded its limit. Nothing was sent.')
            return
        self.buffer.extend(chunk)
        while b'\n' in self.buffer:
            line, _, tail = self.buffer.partition(b'\n')
            self.buffer = bytearray(tail)
            try:
                event = json.loads(line)
                kind = event['type']
                text = event.get('text', '')
                if not isinstance(text, str) or len(text) > MAX_TRANSCRIPT:
                    raise ValueError()
                if kind == 'started':
                    self.status.emit('Recording locally · ' + text + ' · Stop when the question ends.')
                elif kind == 'transcript' and self.result is None:
                    self.result = text
                elif kind == 'error':
                    # Never relay worker diagnostics, device IDs or local paths.
                    self.problem = 'Audio/recognizer unavailable. Check device permissions, selected source and model.'
                else:
                    raise ValueError()
            except (ValueError, KeyError, TypeError, UnicodeError):
                self.abort('The local speech worker returned invalid output. Nothing was sent.')
                return

    def finished(self, process, code):
        if process is not self.process:
            return
        self.read_output(process)
        if process is not self.process:
            return
        text, problem = self.result, self.problem
        if self.buffer:
            problem = 'The local speech response was incomplete. Nothing was sent.'
        self.process = None
        self.deadline.stop(); self.buffer.clear(); self.result = None; self.problem = None
        process.setParent(None)
        process.deleteLater(); self.changed.emit(False)
        if code != 0 or problem or text is None:
            self.failed.emit(problem or 'Local speech stopped unexpectedly. Nothing was sent.')
        elif not text.strip():
            self.failed.emit('No speech recognized. Check the selected source and try again.')
        else:
            self.transcript.emit(text)
