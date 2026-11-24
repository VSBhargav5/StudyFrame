"""Explicit bounded local image-text extraction in a disposable process."""
import hashlib
import json
import sys
from pathlib import Path
from PySide6.QtCore import QObject,QProcess,QTimer,Signal
from studyframe.images import MAX_FILE_BYTES

MAX_OCR_TEXT=20000
MAX_OCR_OUTPUT=128*1024


class OcrSession(QObject):
    succeeded=Signal(str)
    failed=Signal(str)

    def __init__(self,parent=None):
        super().__init__(parent)
        self.process=None
        self.buffer=bytearray()
        self.source_hash=''
        self.deadline=QTimer(self)
        self.deadline.setSingleShot(True)
        self.deadline.timeout.connect(self.timeout)

    @property
    def active(self):return self.process is not None

    def start(self,image):
        if self.active:raise ValueError('Local text extraction is already running.')
        if not 0<len(image.data)<=MAX_FILE_BYTES:raise ValueError('Choose a bounded PNG/JPEG image first.')
        self.source_hash=hashlib.sha256(image.data).hexdigest()
        self.buffer.clear()
        process=QProcess(self);self.process=process
        executable=Path(sys.executable)
        if executable.name.lower()=='pythonw.exe':executable=executable.with_name('python.exe')
        process.setProgram(str(executable))
        process.setArguments(['--ocr-worker'] if getattr(sys,'frozen',False) else ['-m','studyframe.ocr_worker'])
        def write_input():
            if process is self.process:
                process.write(image.data);process.closeWriteChannel()
        process.started.connect(write_input)
        process.readyReadStandardOutput.connect(lambda:self.read(process))
        process.readyReadStandardError.connect(lambda:process.readAllStandardError())
        process.finished.connect(lambda code,status:self.finished(process,code))
        process.errorOccurred.connect(lambda error:self.abort('Local OCR worker could not run. No image was sent.') if process is self.process else None)
        self.deadline.start(30000)
        process.start()

    def read(self,process):
        if process is not self.process:return
        self.buffer.extend(bytes(process.readAllStandardOutput()))
        if len(self.buffer)>MAX_OCR_OUTPUT:self.abort('Local OCR output exceeded its limit. Nothing sent.')

    def finished(self,process,code):
        if process is not self.process:return
        self.read(process)
        if process is not self.process:return
        data=bytes(self.buffer);self.process=None;self.deadline.stop();self.buffer.clear();process.deleteLater()
        try:
            result=json.loads(data)
            text=result['text']
            if code or result.get('sha256')!=self.source_hash or not isinstance(text,str) or not 0<len(text.strip())<=MAX_OCR_TEXT:
                raise ValueError()
            text.encode('utf-8')
        except (ValueError,KeyError,TypeError,UnicodeError):
            self.failed.emit('Local OCR found no usable text or could not finish. Crop more tightly or use the image route. Nothing sent.')
        else:self.succeeded.emit(text)

    def cancel(self):
        process,self.process=self.process,None
        self.deadline.stop();self.buffer.clear()
        if process is not None:
            process.kill();process.waitForFinished(1000);process.deleteLater()

    def abort(self,message):self.cancel();self.failed.emit(message)

    def timeout(self):self.abort('Local OCR stopped after30seconds. No image or text was sent.')
