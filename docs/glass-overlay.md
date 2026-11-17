# Glass desktop companion (v0.4)

The tabbed worksheet is replaced by one compact window. Python/Qt capture and
provider code remain; no web runtime or new dependency. The surface uses translucent
rounded gradient paint and a frameless window, not a native-blur or Mica promise.
Actual appearance depends on the desktop compositor. The overlay remains an
ordinary visible application and can appear in recording/sharing/monitoring.
No capture-exclusion API, hidden process, anti-detection or global keyboard hook.

## Two deliberate actions

**Capture & ask**: choose a display in the visible selector, optionally write a
question, then click. After briefly hiding its own window, StudyFrame captures
that display, binds the fresh bytes to the prepared question and sends them once
to the shown provider. Blank new questions use a screen-explanation prompt. This
button is the send authorization; it does not assert that the unseen pixels were
previewed. A missing key opens connection settings and performs no capture. No
per-frame checkbox or tab switch. The answer appears in the same panel. Ctrl+Enter
is equivalent while the app has focus; it is not a global hotkey.

**Preview**: Capture for preview only or Load image stays local. Crop and
prepare the request, inspect the exact text/image, check review approval and Send
reviewed capture. This path preserves the earlier inspection-before-send choice.
Selecting a file/capture is not authorization for this separate reviewed send.

The selected display and provider are disclosed under the question. Direct sends
can include any notifications, other windows or private material visible there.
Use preview/crop first when needed. Nothing is sent on startup, collapse, drag,
resize, pinning, opening a drawer or changing the display/provider/key.

## Minimal controls

- Drag the title area. The native window move is preferred, with a local drag
  fallback. The lower-right grip resizes the window. Display names/geometry are
  local metadata; no source thumbnails are made during selection.
- Ellipsis opens the connection drawer. Choose free OpenRouter or separately
  labelled paid OpenAI and enter your own key. It stays session-only. Provider
  changes clear the key, prior exchange and prepared approval.
- Minus collapses to a small bar. Plus expands without losing question/answer.
  A request can finish while collapsed; expand to read it. The Close button stays
  accessible and cancels local waiting. Keep-on-top is in connection settings.
- Follow up includes only the last question/answer after a new question is typed.
  A deliberate direct capture can attach new pixels to that one exchange. Changing
  the selected display/provider, notes or manually replacing/cropping the material
  drops that context. Blank follow-ups never send automatically.
- Copy answer is explicit. Text remains plain, including model HTML/code. Nothing
  executes or opens links. Clear session drops key/text/image references, without
  secure memory-erasure or clipboard-history promises.

## Request ownership and limits

One action at a time. A click binds question/context/style/provider/key to a pending
capture. Input, source, provider or key changes cancel it. Cancel/Clear/Close disarm
the delayed capture. A failed/blocked/disconnected/oversized capture never falls
back to an older snapshot. Late provider replies cannot finish another request.
No automatic retries or automatic paid fallback. Existing free-price/data policy,
8MiB PNG,16million pixels,8192dimension,60second local deadline,1MiB answer-response
and1500output-token limits remain. Cancel cannot undo remote processing/charges.
Real provider enforcement, capture/compositor permissions, high-DPI manual layout,
live quality and personal usefulness remain unverified. No paid call or personal
screen transmission was performed during this implementation.

## Reproducible synthetic checks and practice

```powershell
.venv/Scripts/python.exe -m unittest discover -s tests -v
.venv/Scripts/python.exe -m examples.demo --overlay-answer --snapshot out/glass-answer.png
.venv/Scripts/python.exe -m examples.demo --collapsed --snapshot out/glass-collapsed.png
```

Demos label their answer synthetic; they do not capture the operator's desktop or
call a model. Use a new output path: existing artifacts are refused.98tests include
13new overlay cases alongside prior behavior. The earlier tab assertions now check
the actual preview drawer and answer visibility, not removed UI plumbing.

For60–90minutes, use a synthetic code display. Predict range(3), inspect display and
provider, compare direct send with local preview, cancel before the timer finishes,
change the source, collapse/expand and check that the answer stays literal. For a
live trial, enter your own key only inside the app and authorize the chosen send.
Explain why Capture & ask authorizes fresh pixels but preview selection does not.
Practice/learning and live answer quality are not claimed complete.

Qt contract: https://doc.qt.io/qt-6/qwidget.html#creating-translucent-windows
