# Hear a question, review the transcript, get a text answer

In v0.9, open **Voice**, choose **Computer audio** or **Microphone**, and click
**Prepare audio**. This loads the recognizer and lists devices without opening a
recording stream. When Ready, optionally choose a named device, then **Listen**.
Start speaking only when **Listening now** appears. Preparation and Starting audio
are deliberately separate from recording: the earlier app loaded the model after
the click, which could lose speech spoken during startup.

**Stop** ends early; otherwise recording ends after 30 seconds. The loaded model
stays ready between clips for up to 90 seconds of inactivity, so repeated questions
do not reload it. Discard/Clear/Close or source/model changes release it. Preparing
never auto-starts recording, and no key is needed for any local transcription.

Review and correct the editable transcript, then **Ask text only**. That button
authorizes one request containing the transcript and chosen learning style. It
does not send raw audio, screenshots, notes or an earlier conversation. The text
answer appears in the existing answer panel. A missing model key opens connection
settings without transmission. Transcription itself needs no API key or account.

Computer audio captures all playback on the chosen output, not one tab. Pick
Windows default or a named device from the list populated by Prepare audio. Named
devices resolve by exact ID and source type; a missing device fails rather than
falling back to another microphone/output. Selection stays session-only; provider,
source, model folder and pinning remain the only saved preferences. No mixed source.

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
the ZIP or its parent. Model folder, audio source, provider and pinning are remembered in local setup preferences. An installed copy launched
elsewhere may need you to choose the folder. Use Save setup in connection settings or close normally to save them. Keys, questions, transcripts and approval are never saved; capture exclusion starts on again. The selected model determines language.

The current local checkout already has the optional dependencies and that small
English model installed for development verification. Model weights are not committed to Git or included in CI artifacts; the local
portable development package includes the explicitly selected small English model. Windows ARM and unusual devices are unverified.

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
avoid SoundCard's documented single-channel issue. Model preparation/startup is
bounded by a 45-second parent deadline; the ready worker expires after 90 idle seconds; stopping allows three seconds to finalize,
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


The voice panel now shows the selected source's live signal level while recording.
A flat meter plus an empty transcript reports no input signal and suggests checking
the selected output, playback and mute/volume settings. Detected audio without a
transcript instead suggests checking speech/model language. Level values are bounded
0–100 and stay local; no raw waveform is saved or sent. This follows the observed
muted-output hardware test rather than assuming all empty recognition is one error.


## Indian-English option

The local v0.11 portable includes both small US-English0.15 and Indian-English0.4
models. In Voice choose Try Indian English, Prepare audio, wait Ready, then Listen
and speak after Listening now. Changing a model does not start recording. A saved
model folder is respected until you explicitly select a preset; Save setup retains
that folder. Packages without weights explain a missing preset and keep the current
folder; install an extracted trusted model yourself.

[Official Vosk list](https://alphacephei.com/vosk/models) lists the36MB Indian
model under Apache2.0 and a49.05% word-error rate on NPTEL Pure. That benchmark is
not your voice and does not promise accurate coding vocabulary or mixed languages.
We have verified loading/readiness, not improved personal transcription. Review/edit
all transcripts. No audio is sent to a provider for speech recognition.

Local model archive SHA25620663dcac4d5cb783a579c54d98339344a688e4ec6e1b4a4b059fd1235454cc7;
56,700,192 extracted bytes. Download from the official HTTPS source, safe prefix/
size/no-link extraction. This hash records bytes, not an independent authenticity
signature. No recording was made to test it in this iteration.
