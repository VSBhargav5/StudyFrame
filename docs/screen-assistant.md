# Screen assistant, not a saved-image-only worksheet

StudyFrame is the active original Python implementation. RoleWeave is paused as
a local MVP; CueDesk remains the reference rather than a second active app.
This is an incremental return to screen assistance, not a claim of full Cue parity.

1. Run Launch-StudyFrame.cmd. Confirm v0.3.0 in the title.
2. Click Capture screen, choose a display, and confirm. The app hides for a short
   compositor delay and captures one display. Review what actually appeared; an
   OS permission failure or removed monitor keeps the old image. No AI call occurs.
3. Crop the relevant code/diagram if needed. The captured timestamp and pixel/hash
   information identify this still. A screen change does not silently update it.
4. Write a question, choose Explain / Hint / Debug, and Review screen & question.
   Explain is the initial style. Notes are optional, not a required worksheet.
5. Choose the provider, enter its own key in the app, review the complete text and
   image, approve, and Send reviewed request. Copy text alone does not attach pixels.
6. Read/verify the answer. Follow up, or capture again for new pixels. New material
   drops the earlier exchange. Keep on top is optional; there is no hidden overlay.

## Capture boundaries

Only a user-selected display is requested with QScreen.grabWindow(0); display
listing reads metadata, not thumbnails. The app briefly hides itself, but actual
compositor timing, protected content, unusual scaling and OS capture permissions
remain unverified. A capture can include other apps/notifications visible on that
display. Crop and inspect before sending. The assistant is not hidden from screen
sharing/recording tools and has no stealth functionality.

Preflight physical pixel bounds use screen geometry and scale, then actual pixels
are checked again. Limit8192per dimension,16million pixels,8MiB PNG. Physical
high-DPI pixels map directly to crop coordinates; the new PNG has DPR1 and no source
text metadata. Memory is bounded for the image, not the whole process. Oversized,
blocked or removed sources fail without replacing the previous snapshot. No automatic
resizing/truncation. Cancel, Clear and Close disarm the delayed capture.

No background monitor, live video, audio, remote control or code execution. Adding
continuous watching needs an explicit capture/session budget and suitable provider
support; a free request quota is not an unlimited streaming service. Next useful
gate is a permitted real-screen trial, followed by observed fixes and a deliberately
started/stopped bounded watch mode. Do not silently add a timed upload loop.

## Transport and first-principles practice

The preview holds exact still bytes; base64 is encoding, not image understanding.
Inference happens only at Send. One asynchronous request:60second local deadline,
1MiB response,1500output tokens, no app retries/redirects. Free routing fixes
openrouter/free plus zero prompt/completion/request/image price ceilings, no
provider fallbacks and a data-collection-deny preference. This may leave no eligible
provider. The app never relaxes these conditions automatically. Quotas, account
access, correct routing enforcement, OCR accuracy and answer quality are unverified
live. Both OpenRouter and an upstream provider process the selected request.
Cancellation does not undo remote processing. No secrets are read from files/env.

For60–90minutes, use a separate synthetic screen showing range(3). Predict0,1,2.
Capture/crop without a key and confirm nothing is sent. Prepare an explanation,
inspect its text/image, change provider and confirm approval/key/context clear.
Cancel another pending capture and verify the old image remains. Compare physical
pixels with crop coordinates. Explain why capturing a screen and asking a model
are different actions, and why a still cannot describe changes made afterward.
Live key/account/call quality and learning completion require actual user evidence.

```powershell
.venv/Scripts/python.exe -m unittest discover -s tests -v
```

Current85offline tests include15new capture/free-route regressions. Tests use fake
displays and mocked provider replies, never the operator's personal desktop.
Qt contract: https://doc.qt.io/qtforpython-6/PySide6/QtGui/QScreen.html
