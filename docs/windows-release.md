# Windows portable release and first use

The local v0.9 portable app includes Python, Qt, local recognition dependencies
and the trusted small US-English model. Open `StudyFrame.exe` inside its extracted
folder; keep `_internal`, `models`, notices and licenses with it. No terminal,
Node server or Python installation is required. Source users can still run
`Launch-StudyFrame.cmd`, which prefers this version's local portable build.

This is an **unsigned portable app**, not an installed/signed Windows release.
Windows/antivirus may ask you to confirm an unfamiliar executable. The supplied
manifest/ZIP hashes check bytes, not publisher authenticity or universal safety.
No Start menu/global settings/account setup is modified by the portable package.

## Use the two workflows

1. Open the capsule. Click Connect model (or the model badge), choose the AI provider and enter your own session key.
   Setup is at the top; Get your own key opens only the official provider page.
   Use this session key closes setup without making a test request.
   OpenRouter is the separately constrained free route; OpenAI is labelled paid.
   Keys are never read from files or saved. Availability/quality requires your
   own trial. No background connection or automatic paid fallback.
2. **Screen:** expand +, inspect the selected display and write a question, then
   Capture & ask. That click authorizes one fresh selected-screen send. Preview/
   crop remains available for inspection before a separately reviewed send.
3. **Voice:** Voice → choose playback or microphone → Prepare audio → Ready. Choose a
   default or named device, click Listen, then speak after Listening now. Watch the signal
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
out/portable-v0.10.0/StudyFrame/StudyFrame.exe --self-test --output out/new-runtime-check.json --model out/portable-v0.10.0/StudyFrame/models/vosk-model-small-en-us-0.15
```

Use a new report path. The self-test never reads your normal setup or key. CI builds
the same runtime without model weights and checks worker dispatch/failure behavior.
All model downloads, credential entry and actual user sends remain explicit.

Primary contracts: [PyInstaller runtime paths](https://pyinstaller.org/en/stable/runtime-information.html),
[windowed stdio behavior](https://pyinstaller.org/en/stable/common-issues-and-pitfalls.html),
[Windows rounding limitations](https://learn.microsoft.com/en-us/windows/apps/desktop/modernize/ui/apply-rounded-corners).


## Optional per-user installer

The Windows CI artifact also includes an unsigned `StudyFrame-0.10.0-windows-x64-setup.exe`.
It installs for the current user, adds a Start menu entry and an uninstaller, and
does not auto-run or request admin rights. Close StudyFrame before upgrading or
uninstalling; a running v0.9+ session blocks these operations rather than being
terminated. Older portable versions do not implement this installer guard.
The uninstaller retains app configuration outside the install folder. Model and
all dependencies inside the install folder are removed with that copy. No signing
or interrupted-upgrade recovery guarantee is established.

To compile with a separately installed trusted Inno Setup 6 compiler:

```powershell
.venv/Scripts/python.exe build_installer.py --compiler "C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
```

The compiler is not downloaded or installed automatically. Bundle hashes, version,
file set and links/reparse points are checked before compilation; existing setup
outputs are refused. `verify_installer.py` is only for a disposable Windows CI
runner, never a personal install; it tests install, active-session refusal,
reinstall, installed runtime and retained configuration after uninstall.


## When a request appears to do nothing

The answer area is revealed when a send starts or completes, with a visible status
banner for waiting, failure or success. Preview reveals the captured image. A
collapsed failed request says Request failed; expanding shows its safe error.
HTTP401 means key/project access,429 rate limits, and OpenRouter404 may mean no
compatible endpoint matches the current model/image/privacy/price restrictions.
These are not automatically resolved by buying credits; no policy, pricing or
paid fallback was relaxed. Raw provider bodies are never echoed.

For an explicit public-metadata transport check (no key/content/model request):

```powershell
out/portable-v0.10.0/StudyFrame/StudyFrame.exe --connection-check --output out/new-connection.json
```

This contacts only OpenRouter's public models endpoint and checks HTTPS response
headers, refusing redirects. It does not validate your key, quota or model quality.
The ordinary offline self-test additionally checks packaged TLS availability.


## HTTP429 and free usage

HTTP429 does not by itself distinguish daily account allowance from a per-minute
or upstream-provider limit. It does not establish that adding a payment method is
required. Stop repeated model attempts; failed attempts can consume free allowance.
In model settings, **Check free usage · no model request** explicitly sends your
session key only to OpenRouter's fixed HTTPS `GET /api/v1/key`. It sends no study
text, screenshot, audio or model inference request and has no automatic retry.
The app shows only reported daily used/limit/remaining counters, never raw account
labels, budget metadata or response bodies. It does not infer quota from a $5 key
spending cap. Unknown quota formats remain unknown. This is reported tier policy,
not a guarantee that a particular endpoint is currently available or limited.

A positive daily remainder does not remove per-minute or individual-provider caps.
If the response includes a valid numeric Retry-After of at most one day, the app
shows that waiting guidance. HTTP-date or unrecognized hints are not guessed. No
account, payment method, privacy policy or pricing cap is changed;
there is no key rotation, automatic resend or paid fallback.

Primary contracts: [OpenRouter limits and key counters](https://openrouter.ai/docs/api_reference/limits),
[Retry-After and error semantics](https://openrouter.ai/docs/api_reference/errors-and-debugging).

OpenRouter may now try another eligible provider under the same free-router,
zero-price and data-collection-deny filters. Previously allow_fallbacks=false
unnecessarily disabled even free-provider backup routing. This does not add
client retries, paid alternatives or a bypass of platform/account quota. It can
help only when another matching provider is available. Live success is unverified.


## Streaming and latency

Quick answer is the initial UI mode. The request asks for one to three sentences
and honors an explicit format/length request over Explain's suggested lesson.
Prompt instructions cannot guarantee every model follows them. The answer is
plain text; Markdown is not executed or rendered as HTML.

The Responses request now uses stream=true. Only output_text deltas are displayed;
reasoning/keepalives/provider error bodies are not. A completed response event is
required for success, copy/follow-up and the authoritative final text. EOF,
incomplete/failed events, cancellation or the hard 60-second deadline leave any
text explicitly partial. No auto retry. The existing 1 MiB total wire cap also
covers comments and events; arbitrary byte/UTF-8 chunks and multiline data are
handled. JSON-only successful replies remain supported for compatible providers.
Quota checks remain non-streaming metadata-only GET requests.

First-text and total elapsed times are session-only observations, not provider
benchmarks. Streaming removes the wait-for-whole-answer display behavior; it
cannot remove free-provider queue/first-token delays or guarantee faster service.
No paid routing, lowered privacy filters or background warmup requests are used.
The key field is used by explicit requests as entered; Use this session key just
closes setup and clears stale failure feedback, without a connection test.
A timeout/incomplete answer is not evidence that the key was absent or invalid.

Primary protocol: [OpenRouter streaming documentation](https://github.com/OpenRouterTeam/docs/blob/main/api_reference/streaming.mdx).
