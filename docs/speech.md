# Hear a question, review the transcript, get a text answer

In v0.6, **Voice** opens local speech controls. Choose **Computer audio** (default
playback output) or **Microphone** (default input), then **Listen**. **Stop** ends
early; otherwise recording ends after 30 seconds. The capsule also offers Stop
audio while listening. Discard/Clear/Close kill the worker and discard its result.
There is no startup recording, simultaneous mixed source or automatic restart.

Review and correct the editable transcript, then **Ask text only**. That button
authorizes one request containing the transcript and chosen learning style. It
does not send raw audio, screenshots, notes or an earlier conversation. The text
answer appears in the existing answer panel. A missing model key opens connection
settings without transmission. Transcription itself needs no API key or account.

Computer audio captures all playback on the selected default output, not just a
particular video or browser tab. The microphone captures its input. Devices are
resolved once per session with no silent fallback between microphone and playback;
changing the Windows default during a session does not switch the active source.
Hardware permission/driver failures are reported rather than replaced by fake text.

## One-time Windows x64 setup

From the checkout:

```powershell
.venv/Scripts/python.exe -m pip install -r requirements-speech.txt
```

Alternatively, install from this checkout with `pip install ".[speech]"`.
The optional dependencies are SoundCard 0.4.6, Vosk 0.3.45 and NumPy 2.2.6.
Screen-only use still requires just the original Qt dependencies. No package or
model is downloaded automatically by the app.

Download and extract a trusted model from the [official Vosk model list](https://alphacephei.com/vosk/models).
The small US-English `vosk-model-small-en-us-0.15` is listed as 40 MB, Apache 2.0;
Indian-English/Hindi and other models are separate choices with their own licenses
and accuracy. Put the extracted folder in `models/` in the checkout, or choose its
folder with **Model folder…**. Select the folder containing `am/` and `conf/`, not
the ZIP or its parent. Model choice is session-local. An installed copy launched
elsewhere may need you to choose the folder. The selected model determines language.

The current local checkout already has the optional dependencies and that small
English model installed for development verification. They are not bundled into
Git, a standalone installer or CI. Windows ARM and unusual devices are unverified.

## Privacy and limits

Recognition runs locally in a disposable process. Audio samples are processed as
bounded chunks in memory and are not written as WAV/history, uploaded or logged.
This is not secure memory erasure; OS/third-party device facilities are outside the
app's control. Only your later **Ask text only** action sends text to the model.
Normal provider cost/privacy/cancellation limits still apply to that text request.
Capture exclusion applies to the main overlay, not a guarantee for every OS dialog
or recording tool, and it does not control audio captured by other applications.

SoundCard reads Windows WASAPI channels, then the worker downmixes to 16-kHz
little-endian signed PCM16 for Vosk. Mono devices use a duplicate channel map to
avoid SoundCard's documented single-channel issue. Hardware/model loading is
bounded by a 45-second parent deadline; stopping allows three seconds to finalize,
then kills a stalled worker. Cancellation ignores late results. Output is capped
at 64 KiB and transcripts at 4,000 characters; unsupported data fails closed.

## Evidence and runnable verification

```powershell
$env:QT_QPA_PLATFORM='windows'
.venv/Scripts/python.exe -m unittest discover -s tests -v
.venv/Scripts/python.exe -m examples.native_glass --output out/voice-check-new
```

Offline tests cover source isolation, PCM channel/sign handling, stop/timeout,
invalid/oversized/stale worker output, the real invalid-model process without
opening audio, and edited-transcript text-only sending with old images present.
The process check caught and fixed a Qt deferred-deletion ownership crash.

Local inference was also exercised using the upstream Vosk API example `test.wav`
(SHA256 `dcfea5712c43a43ba7ae8083afb39d36993e5a69c46e88b68aaa72b65cb615bb`),
through the same conversion/recognition path, without opening hardware or making
network calls during inference. It recognized the opening “one zero zero zero
one”; later digits contained recognition errors. This is evidence the local path
runs, not a study-quality or accuracy benchmark. The model/sample were downloaded
explicitly for this check. Real microphone, loopback devices, multilingual quality
and live answer-provider behavior remain unverified. No personal audio was recorded.

For a focused 60–90 minute practice, use a synthetic question about `range(3)`.
Predict the transcript, choose one source, record a short permitted sample, stop,
and correct it. Before Ask text only, explain why the old screenshot and notes
will not accompany it. Compare the answer against `list(range(3))`. No practice
or usefulness is marked complete until the user performs it. The tradeoff is an
offline, keyless recognizer with a local model and imperfect recognition quality.

Primary references:

- [Vosk local recognition example](https://github.com/alphacep/vosk-api/blob/master/python/example/test_microphone.py)
- [Vosk model contracts and licenses](https://alphacephei.com/vosk/models)
- [SoundCard WASAPI and known issues](https://soundcard.readthedocs.io/en/latest/)
- [SoundCard release](https://pypi.org/project/SoundCard/0.4.6/)
- [Vosk release](https://pypi.org/project/vosk/0.3.45/)


## Hardware follow-up on 18 November

An explicitly authorized public-sample playback test found a real startup deadlock:
the blocking stdin listener thread prevented NumPy native DLL initialization in
the worker. The worker now polls the parent Windows pipe with PeekNamedPipe and
reads only when bytes are available. A no-recorder subprocess regression imports
the native backend and then receives Stop; the earlier thread-based path stalled.
Fixed stage messages distinguish backend/model/device startup from recording.

After the user unmuted the output, the same approved sample played and was
recognized through the default playback loopback: the expected opening digits
were present. Captured audio was not saved or sent to a cloud provider. This
establishes that one device/path, not all playback devices or microphone quality.
The muted run correctly returned no speech. Microphone and live AI remain gates.
[Windows pipe contract](https://learn.microsoft.com/en-us/windows/win32/api/namedpipeapi/nf-namedpipeapi-peeknamedpipe).
