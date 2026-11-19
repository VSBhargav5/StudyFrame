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
    level = Signal(int)
    devices = Signal(list)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.process = None
        self.buffer = bytearray()
        self.total = 0
        self.result = None
        self.problem = None
        self.peak = 0
        self.phase = 'idle'
        self.warm = False
        self.deadline = QTimer(self)
        self.deadline.setSingleShot(True)
        self.deadline.timeout.connect(self.timeout)

    @property
    def active(self):
        return self.process is not None and self.phase != 'ready'

    @property
    def prepared(self):
        return self.process is not None and self.phase == 'ready'

    def prepare(self, source, model):
        self.cancel()
        self.start(source, model, warm=True)

    def listen(self, device_id=None):
        if not self.prepared:
            return
        if device_id is not None and (not isinstance(device_id,str) or not 0<len(device_id)<=512 or any(ord(c)<32 for c in device_id)):
            self.failed.emit('Choose a valid audio device.')
            return
        self.result = self.problem = None
        self.peak = self.total = 0
        self.phase = 'starting'
        self.changed.emit(True)
        self.status.emit('Starting audio. Wait for Listening now before speaking.')
        self.deadline.start(45000)
        self.process.write((json.dumps({'listen':device_id}).encode()+b'\n') if device_id is not None else b'listen\n')

    def start(self, source, model, *, check_only=False, warm=False):
        if self.process is not None:
            return
        try:
            model = validate_speech_setup(source, model)
        except (ValueError, OSError) as exc:
            self.failed.emit(str(exc))
            return
        process = QProcess(self)
        self.process = process
        self.phase = 'preparing'
        self.warm = warm
        self.buffer.clear(); self.total = 0; self.result = None; self.problem = None
        self.peak = 0
        executable = Path(sys.executable)
        # pythonw can have no standard streams; the worker needs private pipes.
        if executable.name.lower() == 'pythonw.exe':
            executable = executable.with_name('python.exe')
        process.setProgram(str(executable))
        dispatch = ['--speech-worker'] if getattr(sys, 'frozen', False) else ['-m', 'studyframe.speech_worker']
        process.setArguments(dispatch + ['--source', source, '--model', model] +
                             (['--check-only'] if check_only else ['--warm'] if warm else []))
        process.readyReadStandardOutput.connect(lambda: self.read_output(process))
        process.readyReadStandardError.connect(lambda: process.readAllStandardError())
        process.finished.connect(lambda code, state: self.finished(process, code))
        process.errorOccurred.connect(lambda error: self.process_error(process))
        self.changed.emit(True)
        self.status.emit('Preparing local recognizer; not recording. Wait for Ready before Listen.' if warm else
                         'Loading local recognizer. Wait for Listening now before speaking.')
        self.deadline.start(45000)  # Includes bounded model/backend startup.
        process.start()

    def stop(self):
        if self.process is not None:
            if self.phase == 'preparing' and self.warm:
                self.cancel()
                self.status.emit('Audio preparation cancelled. No recording started.')
                return
            if self.phase == 'ready':
                return
            self.phase = 'stopping'
            self.process.write(b'stop\n')
            self.status.emit('Stopping and finalizing locally…')
            self.deadline.start(3000)

    def cancel(self):
        process, self.process = self.process, None
        self.deadline.stop()
        self.buffer.clear(); self.result = None; self.problem = None
        self.phase = 'idle'
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
        if self.prepared:
            self.cancel()
            self.status.emit('Audio setup released after inactivity. Prepare again when ready.')
            return
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
                if not isinstance(text, str) or len(text) > (32768 if kind=='devices' else MAX_TRANSCRIPT):
                    raise ValueError()
                if kind == 'devices' and self.warm and self.phase == 'preparing':
                    options=json.loads(text)
                    if not isinstance(options,list) or len(options)>64:
                        raise ValueError()
                    for item in options:
                        if (not isinstance(item,dict) or set(item)!={'id','name'} or
                            not isinstance(item['id'],str) or not 0<len(item['id'])<=512 or
                            not isinstance(item['name'],str) or not 0<len(item['name'])<=128 or
                            any(ord(c)<32 for c in item['id']+item['name'])):
                            raise ValueError()
                    if len({x['id'] for x in options})!=len(options): raise ValueError()
                    self.devices.emit(options)
                elif kind == 'level':
                    if not text.isascii() or not text.isdigit() or len(text) > 3 or int(text) > 100:
                        raise ValueError()
                    self.peak = max(self.peak, int(text))
                    self.level.emit(int(text))
                elif kind == 'status':
                    self.status.emit(text)
                elif kind == 'started':
                    self.phase = 'listening'
                    self.changed.emit(True)
                    self.status.emit('Listening now · ' + text + ' · Speak, then Stop when the question ends.')
                elif kind == 'ready' and self.warm:
                    if self.phase not in ('preparing', 'starting', 'listening', 'stopping'):
                        raise ValueError()
                    result, peak = self.result, self.peak
                    self.result = None
                    self.phase = 'ready'
                    self.deadline.start(90000)
                    self.changed.emit(False)
                    self.status.emit(text)
                    if result is not None:
                        self.deliver(result, peak)
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
        text, problem, was_ready = self.result, self.problem, self.prepared
        if self.buffer:
            problem = 'The local speech response was incomplete. Nothing was sent.'
        self.process = None
        self.phase = 'idle'
        self.deadline.stop(); self.buffer.clear(); self.result = None; self.problem = None
        process.setParent(None)
        process.deleteLater(); self.changed.emit(False)
        if was_ready and code == 0 and not problem:
            self.status.emit('Audio setup released. Prepare again when ready.')
        elif code != 0 or problem or text is None:
            self.failed.emit(problem or 'Local speech stopped unexpectedly. Nothing was sent.')
        else:
            self.deliver(text, self.peak)

    def deliver(self, text, peak):
        if not text.strip():
            self.failed.emit('No input signal detected. Check the selected device, playback and mute/volume settings.'
                             if peak == 0 else 'Audio was detected but no speech recognized. Check the model/language and try again.')
        else:
            self.transcript.emit(text)
