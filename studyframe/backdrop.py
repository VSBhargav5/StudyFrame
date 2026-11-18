"""Rounded Windows compositor backdrop behind our Qt window, never a screenshot.

The separate non-activating HWND avoids Qt's layered-window/Acrylic rectangle.
It owns no input, content, credentials or capture loop. Unsupported hosts retain
the ordinary rounded Qt surface. Imports stay lazy so other platforms still run.
"""
import ctypes
import sys
import weakref

from PySide6.QtCore import QEventLoop, QTimer
from PySide6.QtWidgets import QApplication
from studyframe.windows_effects import apply_window_effects


class _Runtime:
    def __init__(self, app):
        from winrt.windows.system.interop import create_dispatcher_queue_controller
        self.queue = create_dispatcher_queue_controller()
        self.windows = weakref.WeakSet()
        app.aboutToQuit.connect(self.close)

    def close(self):
        for window in list(self.windows):
            window.close()
        if self.queue is None:
            return
        action = self.queue.shutdown_queue_async()
        loop = QEventLoop()
        timer = QTimer()
        timer.setInterval(10)
        timer.timeout.connect(lambda: loop.quit() if int(action.status) != 0 else None)
        timer.start()
        # Keep pumping the owning thread until the dispatcher has shut down.
        if int(action.status) == 0:
            loop.exec()
        timer.stop()
        self.queue = None


class NativeBackdrop:
    def __init__(self, window):
        from winrt.windows.ui.composition import Compositor
        from winrt.windows.ui.composition.interop import create_desktop_window_target
        self.window = weakref.ref(window)
        self.hwnd = None
        self.target = self.compositor = None
        app = QApplication.instance()
        if not hasattr(app, '_studyframe_composition'):
            app._studyframe_composition = _Runtime(app)
        app._studyframe_composition.windows.add(self)
        self.user = ctypes.WinDLL('user32', use_last_error=True, winmode=0x800)
        self.user.CreateWindowExW.argtypes = [ctypes.c_uint32, ctypes.c_wchar_p, ctypes.c_wchar_p,
                                            ctypes.c_uint32, ctypes.c_int, ctypes.c_int, ctypes.c_int,
                                            ctypes.c_int, ctypes.c_void_p, ctypes.c_void_p,
                                            ctypes.c_void_p, ctypes.c_void_p]
        self.user.CreateWindowExW.restype = ctypes.c_void_p
        self.user.SetWindowPos.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_int,
                                          ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_uint32]
        self.user.ShowWindow.argtypes = [ctypes.c_void_p, ctypes.c_int]
        self.user.DestroyWindow.argtypes = [ctypes.c_void_p]
        self.user.GetWindowRect.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
        self.user.SetWindowRgn.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_int]
        self.gdi = ctypes.WinDLL('gdi32', use_last_error=True, winmode=0x800)
        self.gdi.CreateRoundRectRgn.argtypes = [ctypes.c_int] * 6
        self.gdi.CreateRoundRectRgn.restype = ctypes.c_void_p
        self.gdi.DeleteObject.argtypes = [ctypes.c_void_p]
        self.region_shape = None
        try:
            # No redirection bitmap, taskbar button, activation or intercepted clicks.
            self.hwnd = self.user.CreateWindowExW(0x00200000 | 0x08000000 | 0x80 | 0x20,
                                                 'Static', '', 0x80000000,
                                                 0, 0, 1, 1, None, None, None, None)
            if not self.hwnd:
                raise ctypes.WinError(ctypes.get_last_error())
            dwm = ctypes.WinDLL('dwmapi', winmode=0x800)
            dwm.DwmSetWindowAttribute.argtypes = [ctypes.c_void_p, ctypes.c_uint32,
                                                 ctypes.c_void_p, ctypes.c_uint32]
            enabled = ctypes.c_int(1)
            if dwm.DwmSetWindowAttribute(self.hwnd, 17, ctypes.byref(enabled), 4) != 0:
                raise OSError('Host backdrop is unavailable.')
            self.compositor = Compositor()
            self.target = create_desktop_window_target(self.compositor, self.hwnd)
            self.visual = self.compositor.create_sprite_visual()
            self.visual.brush = self.compositor.create_host_backdrop_brush()
            self.geometry = self.compositor.create_rounded_rectangle_geometry()
            self.visual.clip = self.compositor.create_geometric_clip(self.geometry)
            self.target.root = self.visual
            window.destroyed.connect(self.close)
        except Exception:
            self.close()
            raise

    def sync(self):
        from winrt.windows.foundation.numerics import Vector2, Vector3
        window = self.window()
        if not self.hwnd or window is None:
            return
        if not window.isVisible() or window.isMinimized():
            self.hide()
            return
        # Native HWND rectangles are physical pixels, including fractional DPI.
        rect = (ctypes.c_long * 4)()
        if not self.user.GetWindowRect(int(window.winId()), rect):
            raise ctypes.WinError(ctypes.get_last_error())
        x, y, right, bottom = rect
        width, height = right - x, bottom - y
        scale = window.devicePixelRatioF()
        inset = 7 * scale
        inner_width, inner_height = max(1, width - 2*inset), max(1, height - 2*inset)
        radius = inner_height / 2 if window.centralWidget().compact else 22 * scale
        self.visual.size = Vector2(inner_width, inner_height)
        self.visual.offset = Vector3(inset, inset, 0)
        self.geometry.size = Vector2(inner_width, inner_height)
        self.geometry.corner_radius = Vector2(radius, radius)
        # Geometric clips limit compositor pixels, not the native input rectangle.
        # Keep the companion's hit region inside Qt's own shape as well, so its
        # invisible outside corners cannot intercept another application's clicks.
        diameter = height if window.centralWidget().compact else round(56 * scale)
        shape = (width, height, diameter)
        if shape != self.region_shape:
            region = self.gdi.CreateRoundRectRgn(1, 1, width - 1, height - 1, diameter, diameter)
            if not region:
                raise ctypes.WinError(ctypes.get_last_error())
            if not self.user.SetWindowRgn(self.hwnd, region, True):
                self.gdi.DeleteObject(region)
                raise ctypes.WinError(ctypes.get_last_error())
            # Windows owns the region after a successful SetWindowRgn.
            self.region_shape = shape
        if not window.pin.isChecked():
            # Remove the old topmost band when Qt is unpinned, without activation.
            self.user.SetWindowPos(self.hwnd, ctypes.c_void_p(-2), 0, 0, 0, 0, 0x13)
        if not self.user.SetWindowPos(self.hwnd, int(window.winId()), x, y, width, height, 0x10 | 0x40):
            raise ctypes.WinError(ctypes.get_last_error())

    def configure(self, exclude):
        affinity = apply_window_effects(self.hwnd, exclude)
        if not affinity.capture_confirmed:
            self.hide()
            raise OSError('Backdrop capture setting could not be confirmed.')
        self.sync()

    def hide(self):
        if self.hwnd:
            self.user.ShowWindow(self.hwnd, 0)

    def close(self):
        self.hide()
        if self.target is not None:
            self.target.root = None
            self.target.close()
            self.target = None
        if self.compositor is not None:
            self.compositor.close()
            self.compositor = None
        if self.hwnd:
            self.user.DestroyWindow(self.hwnd)
            self.hwnd = None


def create_backdrop(window):
    if sys.platform != 'win32' or QApplication.platformName() != 'windows' or sys.getwindowsversion().build < 22000:
        return None
    return NativeBackdrop(window)
