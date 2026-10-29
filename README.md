# StudyFrame

A personal Python desktop workspace for studying code and screenshots on Windows.

The first slice helps you organize a question: choose a saved screenshot, inspect
it, add notes or code, and prepare a hint, explanation, or debugging request.
You can then explicitly send the reviewed text and selected image to OpenAI for
study help. This integration is tested offline; live answer quality and account
access have not yet been verified.

## Run on Windows

Python 3.11 or newer is required. From this repository in PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m studyframe
```

No Node.js, Electron, local server, or database is required. An API key is needed
only for live AI requests. Dependencies
are the pinned PySide6 Essentials and Shiboken wheels. Optional package install:
`python -m pip install .` exposes the `studyframe` desktop entry point.

## What works

- Choose one saved PNG/JPEG; inspect, replace, or remove its local preview.
- Image loading checks content, reads one bounded byte snapshot, handles JPEG
  orientation, and rejects unreadable or oversized images.
- Prepare a text request in hint, explain, or debug mode. Pasted code retains its
  indentation. Copy sends **text only** to the clipboard; the image is not attached.
- Editing inputs or changing/removing the image invalidates the prepared request.
  Cancelling selection or failing to load a replacement retains the prior state.
- Clear session drops the app's references to the text/image; the original file
  and system clipboard are unchanged. This is not secure memory erasure.

Nothing is automatically captured, uploaded, persisted as history, or executed.
There is no local OCR, screen capture, audio capture, telemetry, or model SDK.
The file picker and OS clipboard are operating-system facilities; OS/cloud
clipboard history is outside StudyFrame's control.

Limits: 8 MiB per selected file, 8192 pixels per dimension, 16 million pixels,
4,000 question characters and 20,000 context characters (Python Unicode code
points, checked before question trimming). Qt has a 64 MiB image allocation cap;
this is not a whole-process memory limit. Only the first still preview is used;
Qt-reported animations are rejected, but there is no independent APNG parser.
Large supported images decode synchronously; UI responsiveness is not benchmarked.

## Verify and learn

For AI help: prepare your question, inspect the full text and image, enter your
own OpenAI API key in the masked session field, check the review box, then click
**Send reviewed request**. Never paste a key into an issue, chat, or repository.
The app sends to `https://api.openai.com/v1/responses` using `gpt-4.1-mini`.
The whole selected file, including embedded metadata, is sent; no chat history
is included. API usage is billed. The key is not saved by the app and Clear
session removes it from the field; this is not secure memory erasure.

The request is asynchronous, limited to 1,500 output tokens, with a 60-second
local deadline and 1 MiB response cap. No automatic retries or redirects occur.
Cancel/close stops the local request; it cannot guarantee provider cancellation
or prevent charges. Failures retain your question. Changes discard the old
answer and require a new review. Answers are plain text and never executed.
`store=false` is sent, but does not promise zero provider retention.

See [AI workflow and first principles](docs/ai-workflow.md) for the provider
contract, limits, and a 60–90 minute exercise.

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe -m examples.demo --snapshot out/demo.png
```

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
