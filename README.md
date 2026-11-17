# StudyFrame

A personal Windows screen assistant, built in original Python source.

**v0.3.0: capture, ask, refresh.** Choose a display, capture a local still, crop
what matters, and ask a vision model about the pixels you reviewed. Keep the
assistant above other windows when useful. OpenRouter's free-model route is the
default; OpenAI remains an explicitly labelled paid option. This restores the
Cue-like screen-assistance direction instead of requiring saved-image preparation.

This version uses deliberate still captures, not continuous video watching. It
does not capture on startup or send a frame automatically. Real display capture,
free-account availability and live model quality still need a user trial;85offline
tests use synthetic pixels and mocked replies. RoleWeave is paused while StudyFrame
is the active portfolio implementation. CueDesk remains a separate historical
reference, not a second app being developed in parallel.

## Run on Windows

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

- **Capture screen:** choose one connected display. StudyFrame briefly hides,
  then captures one still PNG locally. No source thumbnail capture or network call
  happens while listing displays. A timestamp identifies the capture; click again
  for new pixels. Ctrl+Shift+S is an app-focused shortcut, not a global hotkey.
- **Keep on top:** visible always-on-top window, not concealment from sharing tools.
- **Provider choice:** free OpenRouter route or paid OpenAI. Switching clears the
  key, prepared request, approval and follow-up context. Keys stay session-only.

- Question, Review & send, and Answer tabs keep each step in its own workspace.
  Preparing opens the review; a completed answer opens the answer tab. Cancel
  and Clear session stay available below the workspace. Copy answer is explicit.
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

Nothing is automatically uploaded, persisted as history, or executed.
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

For AI help: capture a screen or load an image, review the text and pixels, enter
your own selected-provider key in the masked session field, check the review box
and click **Send reviewed request**. Do not put credentials in chat or Git.

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
the current image/notes. Capture/replace/crop changes reset that old exchange.
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
