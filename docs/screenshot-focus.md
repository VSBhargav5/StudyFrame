# Study only the part you choose

v0.2.0 adds a real crop editor for saved screenshots. This is not screen capture
or OCR. Original PNG/JPEG input is read once and orientation is applied before
selection. Drag a rectangle, or enter Left/Top/Width/Height in decoded pixels.
The displayed rectangle maps back to source pixels, independently of display
scaling. Drag bounds round outward to include touched pixels. Coordinates use
left/top inclusive and right/bottom exclusive limits.

Use selected area allocates a fresh image and draws only selected pixels into
it. It encodes a PNG, checks the 8 MiB limit and hashes the resulting bytes. The
preview and provider payload use this same attachment. Source metadata is not
copied; pixels inside the crop can still contain personal information. No file
is written. The source snapshot remains in memory for Restore original, which
restores the exact original bytes including metadata. Clear/removal releases
both attachments. This is not secure memory erasure.

Crop/restore invalidate request text, answers, consent and follow-up context.
Cancel and failed cropping preserve the prior state. Controls are disabled while
a provider request runs. The source file is never changed or reopened for crop
or restore. Cropping a crop uses its current pixels; Restore original returns to
the first selected file snapshot, not an intermediate crop.

The crop encoder uses an additional image allocation and synchronous PNG encoding;
whole-process memory and latency are not benchmarked. A crop can encode larger
than a compressed JPEG, so an oversized PNG is refused without replacing the
current attachment. This is a selection tool, not a general editor/redaction tool.

## Try it without AI

```powershell
.\.venv\Scripts\python.exe -m examples.demo --crop-editor
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

During a 60–90 minute learning session, crop just the two loop lines. Predict
the output and crop dimensions before applying it. Inspect the changed dimension,
byte count and hash in the app, then Restore original and explain why its hash
returns exactly. Trace `crop_image`, `CropCanvas.drag_to` and the payload regression
test. Change a pixel coordinate and predict which row/column changes.

Tradeoff: selecting a smaller relevant area can remove surrounding context and
information from a request, but the omitted context might be needed to answer.
Compare two selections on a permitted example before assuming a crop improves
model quality. No live call, model-quality or learning outcome is established by
the synthetic tests.

## Recognize the installed build

The window shows StudyFrame 0.2.0. Launch-StudyFrame.cmd always starts this
checkout with its own environment. Source updates do not automatically refresh
a previously installed wheel; reinstall that entry point after updates. The
previous installed 0.1.0 copy was found to lack AI send/follow-up actions even
though project source contained them. The local installed copy is refreshed
as part of this release's verification. An installer is still not provided.

## Qt runtime compatibility

Linux Python 3.11 CI twice passed the widget assertions with Qt/PySide 6.12.0
then aborted at interpreter shutdown with `none_dealloc`. Explicit test-widget
disposal did not resolve it. This build pins PySide6 Essentials and Shiboken to
6.11.3 while preserving Python 3.11 coverage. A separate-process raster-call
regression also checks normal runtime exit. The failure is recorded in PR #4;
the exact native root cause was not independently proved. The package publisher's
[6.11.3 release](https://pypi.org/project/PySide6-Essentials/6.11.3/) is the source
for the supported wheel. Keep all Windows/Linux CI lanes when changing this pin.
