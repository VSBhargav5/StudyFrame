"""Owned-window Windows effects, with explicit capability/read-back results.

Native Acrylic is deliberately disabled: its rectangular halo ignores the rounded
Qt alpha boundary. Display affinity does not protect against every recorder.
No process-wide setting, hook, or other application's window is modified.
"""
import ctypes
import sys
from dataclasses import dataclass

FALLBACK_MATERIAL = 'Rounded translucent surface; native blur disabled to avoid a rectangular halo.'


@dataclass(frozen=True)
class WindowEffects:
    glass: bool
    excluded: bool
    detail: str
    capture_confirmed: bool = False


def apply_window_effects(hwnd, exclude, *, api=None, build=None):
    """Apply to StudyFrame's own top-level HWND, then read back capture affinity.

    Passing api/build is only for deterministic offline contract tests. A success
    result describes API acceptance, not a guarantee of visible blur or privacy.
    """
    if api is None:
        if sys.platform != 'win32':
            return WindowEffects(False, False, 'Windows capture exclusion unavailable on this platform.')
        try:
            api = ctypes.WinDLL('user32', use_last_error=True, winmode=0x800)
            build = sys.getwindowsversion().build
        except OSError:
            return WindowEffects(False, False, 'Windows capture exclusion unavailable; overlay is not excluded.')
    # Accent/Acrylic ignores the rounded alpha boundary on this supported host.
    # Do not trade a false glass claim for the rectangular halo the user reported.
    glass = False
    material = FALLBACK_MATERIAL
    if build is None or build < 19041:
        return WindowEffects(glass, False, material + ' Capture exclusion requires Windows 10 build 19041 or newer.')
    try:
        api.SetWindowDisplayAffinity.argtypes = [ctypes.c_void_p, ctypes.c_uint32]
        api.SetWindowDisplayAffinity.restype = ctypes.c_int32
        api.GetWindowDisplayAffinity.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_uint32)]
        api.GetWindowDisplayAffinity.restype = ctypes.c_int32
        requested = 0x11 if exclude else 0
        accepted = bool(api.SetWindowDisplayAffinity(hwnd, requested))
        observed = ctypes.c_uint32()
        queried = bool(api.GetWindowDisplayAffinity(hwnd, ctypes.byref(observed)))
        verified = accepted and queried and observed.value == requested
    except (OSError, AttributeError):
        verified = False
    if verified:
        privacy = ('Windows reports capture exclusion on. Other recording tools may differ.' if exclude
                   else 'Capture exclusion is off; the overlay can appear in captures.')
    else:
        privacy = 'Capture setting could not be confirmed. Treat the overlay as visible to capture tools.'
    return WindowEffects(glass, bool(exclude and verified), material + ' ' + privacy, verified)
