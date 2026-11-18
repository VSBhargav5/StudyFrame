# Native glass capsule and capture exclusion

StudyFrame v0.5 opens as a 360 × 90 logical-pixel capsule. The surface is rounded,
draggable and pinned by default. **+** expands the question/answer workspace; **−**
returns to the capsule. **…** opens connection and privacy settings, expanding if
needed. **×** closes and cancels the session. An arriving answer remains available
behind **+**, with “Answer ready” in the capsule. No model call occurs on startup.

## Glass and privacy are separate contracts

Glass changes how the background looks through the window. Capture exclusion asks
Windows to omit this app-owned top-level window from supported capture paths.
Neither implies the other. The capsule always shows capture status; settings
describe the material result and Windows read-back. A checked box alone is not
proof of exclusion. Unconfirmed/unsupported results are labelled unconfirmed.

Native Acrylic uses the guarded `SetWindowCompositionAttribute` accent policy
compatibility export. It is undocumented and may change with Windows updates;
there is no promise of future support. Missing/rejected exports retain the original
painted fallback without blocking documented capture-affinity calls. No dependency
or copied third-party implementation is included. Tint is reduced only after
native composition accepts the request. Actual appearance depends on composition,
transparency preferences and the session; the app does not change system settings.

The documented `SetWindowDisplayAffinity` request is `WDA_EXCLUDEFROMCAPTURE`
(`0x11`), available from Windows 10 build 19041. Earlier Windows is labelled
unsupported rather than silently treating a blacked-out monitor-affinity window
as exclusion. `GetWindowDisplayAffinity` must confirm the requested value. Turning
the setting off explicitly requests and checks `WDA_NONE`. Effects are reapplied
on show/window-handle changes, including pin/unpin and restoration after capture.
Calls target StudyFrame's own HWND only. There are no hooks or process concealment.

Capture exclusion is **not a universal privacy/security guarantee**. Windows API
success does not establish compatibility with every meeting app, recorder, remote
session or capture mechanism. Verify your own capture path with synthetic material
before relying on it. StudyFrame's own capture workflow still hides its overlay
before taking the selected display snapshot, independently of this setting.
It never uploads continuously. Personal material on the selected display can still
be sent by the explicit Capture & ask action; preview/crop first when appropriate.

## Reproduce the evidence

```powershell
$env:QT_QPA_PLATFORM='windows'
.venv/Scripts/python.exe -m unittest discover -s tests -v
.venv/Scripts/python.exe -m examples.native_glass --output out/native-check-new
```

The second command opens an opaque synthetic backdrop and an owned StudyFrame
window, captures only the overlay's rectangle inside that backdrop, and closes
both. It refuses an existing output directory or an insufficient display size.
No credentials, personal desktop capture or model/network requests are involved.
The report records API/read-back status; inspect the PNGs rather than inferring
glass from a successful API return. Do not move the windows during this check.

On Windows build 26300, native Acrylic visibly blurred the synthetic stripes and
blue/yellow boundary. The capsule disappeared from `glass-excluded.png`, leaving
the sharp underlying pattern, and returned in `glass-restored.png` after exclusion
was turned off. `glass-answer.png` verified the expanded panel. This establishes
that bounded Qt screen-capture path on that machine, not universal recorder support.
106 native Windows offline tests passed. An initial fontless Windows offscreen
run failed three existing mouse-click tests; the full native Windows run passed.
The documented DWM system-backdrop route was also tried: it returned success but
remained opaque here, so it is not used or represented as working glass.

## A focused practice session

Spend 60–90 minutes with synthetic code only. Predict the difference between the
visible/excluded/restored images before running the check. Open the capsule,
expand it, enter a harmless question and collapse again. Explain why a glass
appearance does not prove capture exclusion, and why API acceptance is weaker
evidence than checking an actual capture. Then trace `update_window_effects` and
the fresh screenshot send separately. The tradeoff is a Windows compatibility API
for actual blur, with a safe visual fallback and explicitly qualified privacy.
No practice completion or live AI usefulness is claimed by these checks.

Primary contracts:

- [Windows display affinity](https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-setwindowdisplayaffinity)
- [Windows affinity read-back](https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-getwindowdisplayaffinity)
- [DWM system backdrops](https://learn.microsoft.com/en-us/windows/win32/api/dwmapi/ne-dwmapi-dwm_systembackdrop_type)
- [Qt translucent windows](https://doc.qt.io/qt-6/qwidget.html#creating-translucent-windows)
- [Primary compatibility implementation inspected for API shape](https://github.com/zhiyiYo/PyQt-Frameless-Window/blob/master/qframelesswindow/windows/window_effect.py)
