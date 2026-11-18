"""Owned-window Windows effects, with explicit capability/read-back results.

The accent composition export is a guarded, undocumented compatibility API.
Display affinity is documented, but does not protect against every recorder.
No process-wide setting, hook, or other application's window is modified.
"""
import ctypes
import sys
from dataclasses import dataclass


class AccentPolicy(ctypes.Structure):
    _fields_ = [('state', ctypes.c_int32), ('flags', ctypes.c_uint32),
                ('tint', ctypes.c_uint32), ('animation', ctypes.c_uint32)]


class CompositionData(ctypes.Structure):
    _fields_ = [('attribute', ctypes.c_int32), ('data', ctypes.c_void_p),
                ('size', ctypes.c_size_t)]


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
            return WindowEffects(False, False, 'Native glass and capture exclusion require Windows.')
        try:
            api = ctypes.WinDLL('user32', use_last_error=True, winmode=0x800)
            build = sys.getwindowsversion().build
            api.SetWindowCompositionAttribute.argtypes = [ctypes.c_void_p, ctypes.POINTER(CompositionData)]
            api.SetWindowCompositionAttribute.restype = ctypes.c_int32
        except (OSError, AttributeError):
            # A missing compatibility export must not prevent documented privacy.
            if api is None:
                return WindowEffects(False, False, 'Windows effects unavailable; overlay is not excluded.')
    glass = False
    if build is not None and build >= 17763:
        try:
            accent = AccentPolicy(4, 0, 0x60201712, 0)
            data = CompositionData(19, ctypes.cast(ctypes.pointer(accent), ctypes.c_void_p), ctypes.sizeof(accent))
            glass = bool(api.SetWindowCompositionAttribute(hwnd, ctypes.byref(data)))
        except (OSError, AttributeError):
            pass
    material = 'Native Acrylic accepted (compatibility API).' if glass else 'Painted fallback; native Acrylic unavailable.'
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
