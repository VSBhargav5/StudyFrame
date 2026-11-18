import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
import unittest
from unittest.mock import Mock, patch

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication
from studyframe.app import StudyWindow
from studyframe.backdrop import NativeBackdrop, create_backdrop
from studyframe.windows_effects import WindowEffects


class BackdropTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def window(self):
        window = StudyWindow(start_collapsed=True)
        self.addCleanup(window.deleteLater)
        self.addCleanup(window.close)
        return window

    def test_unsupported_platform_never_imports_or_creates_native_renderer(self):
        with patch('studyframe.backdrop.sys.platform', 'linux'), \
             patch('studyframe.backdrop.NativeBackdrop') as native:
            self.assertIsNone(create_backdrop(Mock()))
            native.assert_not_called()

    def test_companion_is_hidden_during_capture_and_reconfigured_on_restore(self):
        backdrop = Mock()
        with patch('studyframe.app.create_backdrop', return_value=backdrop):
            window = self.window()
            window.show(); self.app.processEvents()
            backdrop.configure.assert_called_with(True)
            self.assertTrue(window.centralWidget().native_material)
            before = backdrop.configure.call_count
            window.begin_capture(self.app.primaryScreen())
            self.assertFalse(window.isVisible())
            backdrop.hide.assert_called()
            # Cancelling a pending screenshot does not acquire any pixels.
            with patch('studyframe.app.capture_screen') as capture:
                window.cancel_request(); self.app.processEvents()
                capture.assert_not_called()
            self.assertGreater(backdrop.configure.call_count, before)
            window.close()
            backdrop.close.assert_called_once()

    def test_unconfirmed_companion_affinity_never_leaves_a_visible_unexcluded_layer(self):
        backdrop = Mock()
        backdrop.configure.side_effect = OSError('unconfirmed')
        with patch('studyframe.app.create_backdrop', return_value=backdrop), \
             patch('studyframe.app.QApplication.platformName', return_value='windows'), \
             patch('studyframe.app.apply_window_effects', return_value=WindowEffects(False, True, 'main confirmed', True)):
            window = self.window()
            window.show(); self.app.processEvents()
            backdrop.close.assert_called_once()
            self.assertIsNone(window.native_backdrop)
            self.assertFalse(window.centralWidget().native_material)
            self.assertIn('fallback', window.effects_info.text())
            self.assertIn('Capture excluded', window.privacy_badge.text())

    def test_missing_bindings_fall_back_without_blocking_questions(self):
        with patch('studyframe.app.create_backdrop', side_effect=ImportError('missing')):
            window = self.window()
            window.show(); self.app.processEvents()
            window.question.setPlainText('Explain range(3)')
            self.assertFalse(window.centralWidget().native_material)
            self.assertEqual(window.question.toPlainText(), 'Explain range(3)')

    def test_companion_configure_requires_set_and_readback_before_show(self):
        backdrop = NativeBackdrop.__new__(NativeBackdrop)
        backdrop.hwnd = 55
        backdrop.hide, backdrop.sync = Mock(), Mock()
        for requested in (True, False):
            before = backdrop.sync.call_count
            with patch('studyframe.backdrop.apply_window_effects', return_value=WindowEffects(False, False, 'failed')):
                with self.assertRaises(OSError):
                    backdrop.configure(requested)
            self.assertEqual(backdrop.sync.call_count, before)
            with patch('studyframe.backdrop.apply_window_effects', return_value=WindowEffects(False, requested, 'ok', True)) as affinity:
                backdrop.configure(requested)
                affinity.assert_called_once_with(55, requested)
        self.assertEqual(backdrop.sync.call_count, 2)

    @unittest.skipUnless(os.name == 'nt', 'Windows compositor lifecycle')
    def test_native_companion_has_exact_physical_bounds_and_cleans_up(self):
        if self.app.platformName() != 'windows':
            self.skipTest('Native Qt required')
        window = self.window()
        window.show(); self.app.processEvents()
        backdrop = window.native_backdrop
        if backdrop is None:
            self.skipTest('Windows host-backdrop API unavailable')
        import ctypes
        user = backdrop.user
        user.IsWindow.argtypes = [ctypes.c_void_p]
        user.IsWindowVisible.argtypes = [ctypes.c_void_p]
        def bounds(hwnd):
            rect = (ctypes.c_long * 4)()
            self.assertTrue(user.GetWindowRect(hwnd, rect))
            return tuple(rect)
        hwnd = backdrop.hwnd
        self.assertEqual(bounds(hwnd), bounds(int(window.winId())))
        user.GetWindowRgn.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
        backdrop.gdi.PtInRegion.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_int]
        region = backdrop.gdi.CreateRoundRectRgn(0, 0, 1, 1, 0, 0)
        try:
            self.assertNotEqual(user.GetWindowRgn(hwnd, region), 0)
            self.assertFalse(backdrop.gdi.PtInRegion(region, 0, 0))
            self.assertTrue(backdrop.gdi.PtInRegion(region, 40, 40))
        finally:
            backdrop.gdi.DeleteObject(region)
        window.move(window.x()+25, window.y()+15); self.app.processEvents()
        self.assertEqual(bounds(hwnd), bounds(int(window.winId())))
        window.pin.setChecked(False); self.app.processEvents(); self.app.processEvents()
        self.assertEqual(bounds(hwnd), bounds(int(window.winId())))
        window.collapse_button.setChecked(False); self.app.processEvents(); self.app.processEvents()
        self.assertEqual(bounds(hwnd), bounds(int(window.winId())))
        window.showMinimized(); self.app.processEvents(); self.app.processEvents()
        self.assertFalse(user.IsWindowVisible(hwnd))
        window.showNormal(); self.app.processEvents(); self.app.processEvents()
        self.assertTrue(user.IsWindowVisible(hwnd))
        window.hide(); self.app.processEvents()
        self.assertFalse(user.IsWindowVisible(hwnd))
        window.close()
        self.assertFalse(user.IsWindow(hwnd))
