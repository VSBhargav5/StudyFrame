# Rounded capsule and capture exclusion (v0.6)

StudyFrame opens as a 360 × 90 logical-pixel capsule. + expands its question/answer
workspace; − collapses it. … opens connection/privacy settings; Voice opens
[microphone/computer playback controls](speech.md). Drag its free title area.
× closes and cancels. The same window preserves session state; the capsule shows
answer-ready/listening and capture status. No startup capture, recording, model
call, global keyboard hook or process hiding.

## Why the rectangular halo is gone

v0.5's Acrylic request visibly blurred the background, but Windows also blurred
the rectangle outside Qt's rounded surface. A successful API return and rounded
inner border did not prove correct clipping. The user identified this in the
shipped screenshot. Subsequent native window/blur-region and alternate composition
probes still failed the outside-corner pixel check on build 26300.

v0.6 removes that accent-backdrop request. It uses a correctly rounded Qt alpha
surface with translucent gradient paint. **Fully frosted native blur with clean
capsule edges remains unresolved.** No ongoing background screenshot simulates
blur, no new rendering backend is silently introduced, and the painted appearance
is not represented as native glass. The compatibility export and unsuccessful
clipping helpers are absent from the shipped runtime.

The guarded synthetic capture compares 36 pixels at the four outer corners with
the overlay visible/excluded. Earlier Acrylic changed all 36; the corrected
painted capsule left all 36 equal to the sharp background. The inner capsule still
differs. This checks the actual reported artifact, alongside visual inspection.

## Capture exclusion is separate

SetWindowDisplayAffinity requests WDA_EXCLUDEFROMCAPTURE (0x11), supported from
Windows 10 build 19041. Earlier Windows is labelled unsupported rather than
silently accepting black-box monitor behavior as exclusion. GetWindowDisplayAffinity
must confirm the requested value. Off requests/checks WDA_NONE. Status distinguishes
confirmed/off/unconfirmed. Pin/show/handle changes reapply it; resize/DPI changes
preserve shape. Calls target only this app's HWND; no system preferences change.

API acceptance is **not a guarantee for every recorder**, remote session or capture
mechanism. Test your own path with synthetic material. Native/OS dialogs are not
promised excluded. StudyFrame still hides its overlay before its own selected-
display capture, independently of the setting. Other material on that display may
be sent by your explicit Capture & ask action; preview/crop first when needed.
Audio captured by other applications is outside this setting.

## Reproduce the evidence

```powershell
$env:QT_QPA_PLATFORM='windows'
.venv/Scripts/python.exe -m unittest discover -s tests -v
.venv/Scripts/python.exe -m examples.native_glass --output out/capsule-check-new
```

The second command refuses existing output paths. It creates an opaque always-on-
top synthetic backdrop with its overlay above it. Before bounded screen capture,
it checks sampled points for other occluding windows and refuses if displaced or
occluded. It records visible/excluded/restored capsule, expanded answer and synthetic
voice panel PNGs plus status/corner counts in JSON. No audio/model/key is used.
Do not move the fixture. Earlier QA lost a non-topmost backdrop to Codex; those
artifacts were discarded and ordering/occlusion guards added before final checks.

Windows build 26300 verified rounded outside corners and disappearance/restoration
through this Qt screen-capture path. Unusual DPI, all native dialogs, other
recorders and personal acceptance remain unverified. Native input tests now open
and scroll the real review drawer before clicks; hidden-widget clicks were not
valid user interaction after native hit regions were applied.

For 60–90 minutes, predict the images/corner counts and run the synthetic check.
Expand/collapse, preserve an answer, and trace fresh screenshot send separately
from exclusion. Explain why correct shape, blur and capture privacy are different
properties. No learning/usefulness completion is claimed. The tradeoff is a correct
rounded translucent capsule instead of misleading, incorrectly clipped native blur.

Primary contracts:

- [Windows affinity](https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-setwindowdisplayaffinity)
- [Affinity read-back](https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-getwindowdisplayaffinity)
- [Qt translucent windows](https://doc.qt.io/qt-6/qwidget.html#creating-translucent-windows)
