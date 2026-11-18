"""Local-only audio → Vosk text. Run only through an explicit SpeechSession.

No network API, model download, audio file, credentials or model-answer request.
The parent can kill this process if a hardware driver/model call stalls.
"""
import argparse
import json
import os
import sys
import time
from pathlib import Path

RATE = 16000
CHUNK = 1600
MAX_SECONDS = 30
MAX_TEXT = 4000


class PipeStop:
    """Poll the parent's Windows pipe without a blocking CRT reader thread.

    Blocking os.read on another thread can deadlock native DLL initialization.
    PeekNamedPipe prevents entering that read until bytes are already available.
    """
    def __init__(self):
        import ctypes
        import msvcrt
        self.ctypes = ctypes
        self.fd = sys.stdin.fileno()
        self.handle = msvcrt.get_osfhandle(self.fd)
        self.kernel = ctypes.WinDLL('kernel32', use_last_error=True, winmode=0x800)
        self.kernel.PeekNamedPipe.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_uint32,
                                              ctypes.c_void_p, ctypes.POINTER(ctypes.c_uint32), ctypes.c_void_p]
        self.kernel.PeekNamedPipe.restype = ctypes.c_int32
        self.stopped = False

    def is_set(self):
        if self.stopped:
            return True
        available = self.ctypes.c_uint32()
        if not self.kernel.PeekNamedPipe(self.handle, None, 0, None, self.ctypes.byref(available), None):
            self.stopped = True  # Closed/invalid parent pipe fails closed.
        elif available.value:
            os.read(self.fd, min(available.value, 16))
            self.stopped = True
        return self.stopped


def pcm16(block):
    import numpy as np
    block = np.asarray(block, dtype=np.float32)
    if block.ndim != 2 or not 0 < block.shape[0] <= CHUNK or not 0 < block.shape[1] <= 32:
        raise ValueError('Unexpected audio dimensions')
    if not np.isfinite(block).all():
        raise ValueError('Invalid audio samples')
    # Record all channels first: WASAPI single-channel recording has known issues.
    mono = block.mean(axis=1, dtype=np.float64)
    return (np.clip(mono, -1, 1) * 32767).astype('<i2').tobytes()


def choose_device(sc, source):
    if source == 'microphone':
        device = sc.default_microphone()
        if device is None or device.isloopback:
            raise ValueError('No microphone')
        return device
    if source == 'loopback':
        speaker = sc.default_speaker()
        if speaker is None:
            raise ValueError('No playback device')
        device = sc.get_microphone(id=speaker.id, include_loopback=True)
        if device is None or not device.isloopback or device.id != speaker.id:
            raise ValueError('No exact playback loopback')
        return device
    raise ValueError('Unknown source')


def recognize(device, recognizer, stop, emit, *, clock=time.monotonic):
    pieces = []
    def collect(data):
        text = json.loads(data).get('text', '')
        if not isinstance(text, str):
            raise ValueError('Invalid transcript')
        pieces.append(text)
        if len(' '.join(pieces)) > MAX_TEXT:
            raise ValueError('Transcript too long')
    if stop.is_set():
        return ''
    channels = int(device.channels)
    if not 0 < channels <= 32:
        raise ValueError('Unsupported channel count')
    # Duplicate mapping on a mono device avoids requesting a single WASAPI channel.
    mapping = [0, 0] if channels == 1 else None
    deadline = clock() + MAX_SECONDS
    frames = 0
    with device.recorder(samplerate=RATE, channels=mapping, blocksize=6400) as recorder:
        emit('started', 'Microphone' if not device.isloopback else 'Computer playback audio')
        while not stop.is_set() and clock() < deadline and frames < RATE * MAX_SECONDS:
            block = recorder.record(numframes=CHUNK)
            encoded = pcm16(block)
            import numpy as np
            samples = np.frombuffer(encoded, dtype='<i2').astype(np.int32)
            emit('level', str(min(100, round(int(np.abs(samples).max()) * 100 / 32767))))
            frames += len(encoded) // 2
            if recognizer.AcceptWaveform(encoded):
                collect(recognizer.Result())
    collect(recognizer.FinalResult())
    return ' '.join(piece for piece in pieces if piece).strip()


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument('--source', choices=['microphone', 'loopback'], required=True)
    parser.add_argument('--model', required=True)
    parser.add_argument('--check-only', action='store_true', help='Check local imports/model without opening any audio device')
    args = parser.parse_args(argv)
    def emit(kind, text):
        print(json.dumps({'type': kind, 'text': text}), flush=True)
    try:
        if sys.platform != 'win32' or not Path(args.model).is_dir():
            raise ValueError('Unsupported setup')
        stop = PipeStop()
        emit('status', 'Preparing local Windows audio backend…')
        import soundcard as sc
        from vosk import Model, KaldiRecognizer, SetLogLevel
        SetLogLevel(-1)
        emit('status', 'Loading the local speech model…')
        model = Model(model_path=args.model)  # Explicit local path; never Model(lang=...).
        recognizer = KaldiRecognizer(model, RATE)
        if args.check_only:
            recognizer.AcceptWaveform(b'\0' * 3200)
            emit('transcript', 'Local speech backend ready.')
            return 0
        if stop.is_set():
            emit('transcript', '')
            return 0
        emit('status', 'Resolving the selected Windows audio device…')
        device = choose_device(sc, args.source)
        emit('status', 'Opening the selected audio stream…')
        text = recognize(device, recognizer, stop, emit)
        emit('transcript', text)
        return 0
    except Exception:
        emit('error', 'Local audio or recognizer unavailable.')
        return 2


if __name__ == '__main__': raise SystemExit(main())
