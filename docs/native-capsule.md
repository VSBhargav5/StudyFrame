# Rounded capsule and capture exclusion (v0.8)

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

v0.6 removed that accent request and shipped correctly rounded translucent Qt
paint. v0.8 adds a deliberate, Windows-only compositor integration: a separate
owned non-activating HWND hosts `CreateHostBackdropBrush`, clipped by
`CompositionRoundedRectangleGeometry`. The existing Qt controls sit above it.
The compositor handles the backdrop; the app does not read back or periodically
capture desktop pixels to fake blur. No backend/request/audio rewrite was needed.

This costs seven Windows-only PyWinRT dependencies and explicit companion-window
lifecycle handling. The companion tracks physical HWND bounds, inset/radius and
pinning; it hides when Qt hides/minimizes, including before an explicit screenshot.
Both layers get independent capture-affinity read-back before showing the native
surface. An unavailable API/binding or unconfirmed companion affinity closes the
companion and leaves the rounded Qt fallback. The dispatcher is shared within the
app and shut down with message pumping after its visuals close.

On build 26300 at 125% scaling, an opaque synthetic striped fixture visibly blurs
inside the rounded capsule, while all 36 sampled outside-corner pixels remain
sharp/unchanged. The excluded capture also matches the entirely hidden-overlay
baseline. This establishes the tested host/path, not all monitors or recorders.
Windows transparency/accessibility/power policies can affect material appearance;
there is no claim that an accepted API proves blur on every machine.

## Capture exclusion is separate

SetWindowDisplayAffinity requests WDA_EXCLUDEFROMCAPTURE (0x11), supported from
Windows 10 build 19041. Earlier Windows is labelled unsupported rather than
silently accepting black-box monitor behavior as exclusion. GetWindowDisplayAffinity
must confirm the requested value. Off requests/checks WDA_NONE. Status distinguishes
confirmed/off/unconfirmed. Pin/show/handle changes reapply it; resize/DPI changes
preserve shape. Calls target only this app's two owned HWNDs; no system preferences change.

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
properties. No learning/usefulness completion is claimed. The tradeoff is a Windows-specific native companion and dispatcher lifecycle
in return for a truly rounded backdrop, with safe Qt fallback on unsupported hosts.

Primary contracts:

- [Windows affinity](https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-setwindowdisplayaffinity)
- [Affinity read-back](https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-getwindowdisplayaffinity)
- [Qt translucent windows](https://doc.qt.io/qt-6/qwidget.html#creating-translucent-windows)


Primary contracts: [host backdrop brush](https://learn.microsoft.com/en-us/uwp/api/windows.ui.composition.compositor.createhostbackdropbrush),
[desktop composition interop](https://pywinrt.readthedocs.io/en/latest/api/windows/ui/composition/interop/),
[dispatcher lifecycle](https://pywinrt.readthedocs.io/en/latest/api/windows/system/interop/),
[freezing PyWinRT tables](https://pywinrt.readthedocs.io/en/latest/freezing/).


## Readability over light applications (v0.8.1)

A user photo showed that the first native material washed out over a light window:
frost was present, but the tint and secondary text did not provide enough contrast.
The corrected material keeps a dark minimum tint, limits the pale glow, and raises
secondary/placeholder/action text contrast and size. It still uses the native
backdrop; no desktop sampling, automatic theme inference or image upload was added.
A rendered regression checks sampled interior material pixels against actual
widget palette colors on pure white and black backgrounds, in native and fallback
paint modes, requiring at least 4.5:1 for the checked enabled text colors. This is
a targeted check, not an accessibility certification for the whole app.

Reproduce actual native visual checks without opening personal windows:

```powershell
.venv/Scripts/python.exe -m examples.native_glass --background light --output out/light-check-new
.venv/Scripts/python.exe -m examples.native_glass --background dark --output out/dark-check-new
```

These checks retain the corner and hidden-baseline exclusion comparisons. The
visual tradeoff is less desktop show-through in exchange for stable legibility.


## v0.13 configurable clear canvas

The default is25% tint, with0Full clear,50Frosted and78Readable presets and a0–90
slider. Shadow painting now clips outside the rounded surface, so zero tint has
zero painted alpha at the empty canvas center. This does not remove control/text
backing or native frost; no screenshot is sampled for blur. Very low tint trades
readability over some backgrounds for transparency. Readable remains available.
Tint persists as non-secret version2 setup, with version1 compatibility. Affinity,
corner clipping, pinning, exclusion readback and the unsupported-OS fallback remain
separate from appearance. Never call capture exclusion guaranteed invisibility.
