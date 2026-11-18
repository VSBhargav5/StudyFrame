# StudyFrame

A personal Windows screen assistant, built in original Python source.

**v0.8.0: rounded native frost, screen-and-voice companion.** StudyFrame opens
as a small desktop capsule. **+** expands the question/answer panel; **Voice**
opens microphone/computer-playback controls. Listen, Stop, review/edit the local
transcript, then **Ask text only** for a text answer. No raw audio or old screenshot
is sent by that action. [Speech setup and workflow](docs/speech.md).

On Windows 11, the capsule uses a real compositor host-backdrop brush clipped to
its rounded shape, behind the existing Qt controls. No rectangular Acrylic halo
or background screenshot is used to simulate blur. Unsupported/disabled hosts
retain the rounded translucent fallback. Both owned layers receive capture
exclusion with read-back; the companion stays hidden if its setting is unconfirmed.
The guarded Windows synthetic fixture verifies untouched corners and exclusion
against the hidden-window baseline. Other recorders can differ.
[Capsule evidence and limits](docs/native-capsule.md).

**Capture & ask** still explicitly sends one fresh selected-display screenshot
plus your question. Preview/crop remains available for local inspection before a
reviewed send. No continuous watching, startup recording or background uploads.
OpenRouter free routing is the default; paid OpenAI stays separately labelled.
Transcription is offline and keyless, using optional Vosk/SoundCard dependencies
and a trusted local model. A model-provider key is needed only for AI answers.

An authorized real default-playback loopback test recognized the public sample’s opening digits after unmuting. Offline regressions also verify the recognition path;
recognition made errors on later sample digits. Microphone quality, other playback devices, live AI quality and personal usefulness remain unverified. No personal audio was
recorded or live model call made. RoleWeave remains paused.

## Open the Windows portable app

Unzip the complete portable folder and open **StudyFrame.exe**. Keep `_internal`
next to it. Python is not needed for that build. The local development package
includes the small English speech model; builds without it let you choose a local
model folder. Setup choices persist locally; API keys and study content do not.
See [Windows release and acceptance checklist](docs/windows-release.md).

## Run from source on Windows

Python 3.11 or newer is required. From this repository in PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m studyframe
```

After setup, double-click **Launch-StudyFrame.cmd** in this folder. It opens the
current project source using its own environment, including when launched from
another directory. Close older StudyFrame windows before reopening this build.
If you previously installed the desktop entry point, refresh that copy after
updates with `.\.venv\Scripts\python.exe -m pip install --no-deps .`.

No Node.js, Electron, local server, or database is required. An API key is needed
only for live AI requests. Dependencies
are the pinned PySide6 Essentials and Shiboken wheels. Optional package install:
`python -m pip install .` exposes the `studyframe` desktop entry point.

## What works

- **Capture & ask:** the selected display is visible in the selector. Click, or
  use Ctrl+Enter while the app is focused, to capture and send one fresh still.
  A failed capture never sends an older image. No key opens settings without
  capturing. The app briefly hides for capture and restores for the answer.
- **Preview / crop:** Capture for preview only uses a display picker and sends
  nothing. Load, crop, prepare and explicitly approve/send when you want inspection
  first. Source listing takes metadata only; timestamps identify captured stills.
- **Keep on top:** a pinnable window. Capture exclusion is a separate Windows setting
  with explicit status; pin/unpin reapplies it to the current window handle.
- **Provider choice:** free OpenRouter route or paid OpenAI. Switching clears the
  key, prepared request, approval and follow-up context. Keys stay session-only.

- One glass-style window keeps the question, Capture & ask and answer together.
  Drag the title, resize at the lower-right grip, collapse to a bar, or open the
  settings/preview drawers. Copy answer, Follow up, Cancel and Clear stay explicit.
- Ask a follow-up carries only the last question and AI answer into the next
  prepared text. Type a new question, review the complete combined request and
  consent again. The current notes/image are sent again; older turns are omitted.
  Start a new question or change the notes/image to drop that previous exchange.

- Choose one saved PNG/JPEG; inspect, replace, or remove its local preview.
- **Crop / focus area:** drag a rectangle or use Left/Top/Width/Height pixel
  controls. Use selected area replaces the attachment with a fresh PNG containing
  those oriented pixels. Restore original uses the original byte snapshot;
  the source file is never changed. Crop/restore require preparing and reviewing
  again and reset follow-up context. Cancelling a crop preserves the prior state.
- Image loading checks content, reads one bounded byte snapshot, handles JPEG
  orientation, and rejects unreadable or oversized images.
- Prepare a text request in hint, explain, or debug mode. Pasted code retains its
  indentation. Copy sends **text only** to the clipboard; the image is not attached.
- Editing inputs or changing/removing the image invalidates the prepared request.
  Cancelling selection or failing to load a replacement retains the prior state.
- Clear session drops the app's references to the text/image; the original file
  and system clipboard are unchanged. This is not secure memory erasure.

No background uploads, persistent history or code execution. Capture & ask sends
one fresh frame only when you deliberately invoke it; preview-only captures do not.
There is no continuous capture, audio capture, local OCR, telemetry, or model SDK.
The file picker and OS clipboard are operating-system facilities; OS/cloud
clipboard history is outside StudyFrame's control.

Limits: 8 MiB per selected file, 8192 pixels per dimension, 16 million pixels,
4,000 question characters and 20,000 context characters (Python Unicode code
points, checked before question trimming). Qt has a 64 MiB image allocation cap;
this is not a whole-process memory limit. Only the first still preview is used;
Qt-reported animations are rejected, but there is no independent APNG parser.
Large supported images decode synchronously; UI responsiveness is not benchmarked.

## Verify and learn

For AI help, open the connection drawer (ellipsis), choose a provider and enter
your session key. Select the display and click **Capture & ask**; this is the
explicit authorization to send that fresh screenshot and question. For review
first, use **Preview**, prepare the request, approve its text/image and
**Send reviewed capture**. Never put credentials in chat or Git.

- Default: `https://openrouter.ai/api/v1/responses`, model `openrouter/free`.
  The server chooses an eligible free model, including image capability for images.
  Requests set zero price caps, disable provider fallbacks and request providers
  disallowing data collection. An unavailable eligible route fails; the app never
  switches to paid OpenAI. This policy is not a zero-retention guarantee or a live
  compatibility/availability claim. Selected model metadata is shown if returned.
- Paid alternative: `https://api.openai.com/v1/responses`, `gpt-4.1-mini`.
  Deliberately select it and enter its separate key. API charges apply.

A display capture is a fresh pixel-only PNG. A loaded original file includes its
original metadata until cropped. A crop sends a fresh PNG of selected pixels.
A follow-up includes only the displayed previous question and answer, alongside
the current image/notes. Manual capture/replace/crop changes reset that old exchange. A deliberately chosen
Follow up can carry the last exchange with a new one-click capture.
The app does not save the key; Clear session removes it, without secure-erasure
or clipboard-history guarantees. [Free API options and official key links](docs/free-vision-options.md).

The request is asynchronous, limited to 1,500 output tokens, with a 60-second
local deadline and 1 MiB response cap. No automatic retries or redirects occur.
Cancel/close stops the local request; it cannot guarantee provider cancellation
or prevent charges. Failures retain your question. Changes discard the old
answer and require a new review. Answers are plain text and never executed.
`store=false` is sent, but does not promise zero provider retention.

See [AI workflow and first principles](docs/ai-workflow.md) for the provider
contract, limits, and a 60–90 minute exercise.

Follow-ups include one exchange from memory. The current request preview and
answer remain visible until invalidated or cleared. Previous questions are limited to
4,000 characters and answers to 12,000; oversized answers can still be read and
copied, but cannot start a follow-up. They are never silently truncated. This is
bounded context, not complete conversation memory. Clear session drops retained
exchanges and the key; it does not guarantee secure memory erasure.

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe -m examples.demo --snapshot out/demo.png
.\.venv\Scripts\python.exe -m examples.demo --crop-editor
.\.venv\Scripts\python.exe -m examples.demo --crop --snapshot out/cropped-demo.png
```

The crop demo uses a synthetic code image. It performs no screen capture or model
call. See [screenshot-focus exercise](docs/screenshot-focus.md).

The tests exercise pure request rules, synthetic PNG/JPEG files, actual Qt widgets,
and state transitions. The picker and clipboard are stubbed in automated widget
tests so they never access your clipboard or personal files. The demo renders
synthetic code with the real window; it sends nothing to a model. Run it without
`--snapshot` to explore the synthetic session interactively.

See [first principles](docs/first-principles.md) for one 60–90 minute exercise,
and the [MVP plan](docs/mvp.md) for the next gate. An offscreen test is not proof
of foreground usability, physical clipboard integration, installer readiness,
model quality, or useful learning outcomes.

## Origin and stack

StudyFrame is a new repository with original Python source and independent Git
history. The general screen-assistance idea was inspired by
[Cue](https://github.com/Blueturboguy07/cue). An earlier
[CueDesk fork experiment](https://github.com/VSBhargav5/CueDesk) remains separate;
its code, assets, tests, and Git history were not imported into this repository.
This is a fresh implementation, not a translated or renamed fork.

Python keeps request logic close to the author's data/AI projects. PySide6 Qt
Widgets supplies a desktop window and native file picker without a second app
runtime. Its tradeoff is a sizeable dependency and eventual Windows packaging
work. Only Essentials is installed; no web engine is needed. References:
[Qt setup](https://doc.qt.io/qtforpython-6/gettingstarted.html),
[Qt package details](https://doc.qt.io/qtforpython-6/package_details.html),
[image reader](https://doc.qt.io/qtforpython-6/PySide6/QtGui/QImageReader.html).

StudyFrame source uses the [MIT license](LICENSE). Third-party dependencies keep
their own licenses; see [PySide6 licensing](https://pypi.org/project/PySide6/).
No bundled executable or commercial distribution is provided at this stage.
