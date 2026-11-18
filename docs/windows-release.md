# Windows portable release and first use

The local v0.7 portable app includes Python, Qt, local recognition dependencies
and the trusted small US-English model. Open `StudyFrame.exe` inside its extracted
folder; keep `_internal`, `models`, notices and licenses with it. No terminal,
Node server or Python installation is required. Source users can still run
`Launch-StudyFrame.cmd`, which prefers this version's local portable build.

This is an **unsigned portable app**, not an installed/signed Windows release.
Windows/antivirus may ask you to confirm an unfamiliar executable. The supplied
manifest/ZIP hashes check bytes, not publisher authenticity or universal safety.
No Start menu/global settings/account setup is modified by the portable package.

## Use the two workflows

1. Open the capsule. In … choose the AI provider and enter your own session key.
   OpenRouter is the separately constrained free route; OpenAI is labelled paid.
   Keys are never read from files or saved. Availability/quality requires your
   own trial. No background connection or automatic paid fallback.
2. **Screen:** expand +, inspect the selected display and write a question, then
   Capture & ask. That click authorizes one fresh selected-screen send. Preview/
   crop remains available for inspection before a separately reviewed send.
3. **Voice:** Voice → choose playback or microphone → Listen. Watch the signal
   meter; Stop ends the clip. Review/correct the transcript, then Ask text only.
   This sends no audio, screenshot, notes or prior exchange. Silence suggests
   checking the selected output and mute/volume settings. A wrong transcript with
   signal suggests checking model/language and speaking more clearly.
4. Collapse to the capsule; expand for the answer. Copy only when desired.
   Clear drops key/content and cancels work. Close cancels recording/request.

Non-secret setup (provider, source, model folder, pinning) is saved atomically to
Qt's per-user app configuration folder as `setup.json`. Save setup in … or close
normally. The app stores no key, question, answer, image, transcript or approval.
Capture exclusion starts enabled every session; remember to test your own recorder.
Unreadable/incompatible setup uses safe defaults with a visible settings message.

The included model avoids folder selection for a fresh local portable launch.
CI artifacts deliberately omit large model weights; follow [speech setup](speech.md)
to select an extracted trusted Vosk model once. Moving an externally chosen model
can require selecting its folder again. Model/pack resources are unencrypted.

## What has and has not been verified

The source has an authorized default-playback hardware test: a public Vosk sample
was played and transcribed through the real worker, with expected opening digits.
The test first exposed a Windows DLL/startup deadlock caused by a blocking stdin
thread; nonblocking pipe polling fixes it. A muted-output run returned no speech,
leading to signal-meter and silence diagnostics. Captured audio was not saved or
uploaded. This does not establish every device, microphone quality or AI quality.

The offline runtime check opens its own synthetic capsule, exercises text-only
answer/clear with a fixed fake reply, checks non-secret preferences, and launches
the actual worker through private pipes. With a supplied local model, it also
checks native recognition libraries/model with silence, **without opening audio**.
It makes no model API request and captures no desktop. The portable GUI worker
explicitly restores inherited pipe streams and never recursively starts a GUI.

v0.8 uses a Windows 11 compositor host-backdrop brush and rounded geometric clip.
The extra owned, non-activating HWND follows Qt bounds in physical pixels and
hides during capture/minimization/close. Failure falls back to rounded Qt paint.
This replaces the unsupported Acrylic clipping approach, not the Python app.
The local synthetic check proves actual frost and untouched outside corners on
build 26300; system transparency policies can change its appearance. Other
recording tools, unusual DPI/dialogs and personal acceptance still need checking.
No blanket production-ready, learning or usefulness claim.

## Reproduce the build and checks

```powershell
.venv/Scripts/python.exe -m pip install -r requirements-build.txt
.venv/Scripts/python.exe -m unittest discover -s tests -v
.venv/Scripts/python.exe build_windows.py --model models/vosk-model-small-en-us-0.15
```

The build uses a fresh stage and refuses existing versioned folder/ZIP outputs.
It bundles public dependencies/licenses and only an explicitly chosen trusted
small-English model, then runs the actual executable's self-test before publishing
the new folder/ZIP. Failed/previous stages stay intact; do not build into a running
app's folder. Stages consume disk. No recursive cleanup or private-data sweep occurs.

```powershell
out/portable-v0.8.0/StudyFrame/StudyFrame.exe --self-test --output out/new-runtime-check.json --model out/portable-v0.8.0/StudyFrame/models/vosk-model-small-en-us-0.15
```

Use a new report path. The self-test never reads your normal setup or key. CI builds
the same runtime without model weights and checks worker dispatch/failure behavior.
All model downloads, credential entry and actual user sends remain explicit.

Primary contracts: [PyInstaller runtime paths](https://pyinstaller.org/en/stable/runtime-information.html),
[windowed stdio behavior](https://pyinstaller.org/en/stable/common-issues-and-pitfalls.html),
[Windows rounding limitations](https://learn.microsoft.com/en-us/windows/apps/desktop/modernize/ui/apply-rounded-corners).
