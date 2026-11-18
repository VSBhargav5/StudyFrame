import ctypes
import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
import unittest
from unittest.mock import Mock, patch

from PySide6.QtWidgets import QApplication
from studyframe.app import StudyWindow
from studyframe.windows_effects import (
    AccentPolicy, CompositionData, WindowEffects, apply_window_effects,
)


class WindowsEffectsTests(unittest.TestCase):
    def api(self, affinity=0x11):
        api = Mock()
        api.SetWindowCompositionAttribute.return_value = 1
        api.SetWindowDisplayAffinity.return_value = 1
        def read(hwnd, pointer):
            ctypes.cast(pointer, ctypes.POINTER(ctypes.c_uint32))[0] = affinity
            return 1
        api.GetWindowDisplayAffinity.side_effect = read
        return api

    def test_owned_handle_acrylic_abi_and_confirmed_exclusion(self):
        api = self.api()
        def composition(hwnd, pointer):
            self.assertEqual(hwnd, 0x123456789)
            data = ctypes.cast(pointer, ctypes.POINTER(CompositionData)).contents
            self.assertEqual(data.attribute, 19)
            self.assertEqual(data.size, 16)
            accent = ctypes.cast(data.data, ctypes.POINTER(AccentPolicy)).contents
            self.assertEqual((accent.state, accent.tint), (4, 0x60201712))
            return 1
        api.SetWindowCompositionAttribute.side_effect = composition
        result = apply_window_effects(0x123456789, True, api=api, build=26300)
        self.assertTrue(result.glass); self.assertTrue(result.excluded)
        api.SetWindowDisplayAffinity.assert_called_once_with(0x123456789, 0x11)
        self.assertIn('Other recording tools may differ', result.detail)

    def test_exclusion_off_is_explicitly_cleared_and_read_back(self):
        api = self.api(0)
        result = apply_window_effects(7, False, api=api, build=26300)
        self.assertFalse(result.excluded)
        api.SetWindowDisplayAffinity.assert_called_once_with(7, 0)
        self.assertIn('exclusion is off', result.detail)

    def test_failed_set_read_or_mismatched_affinity_never_claims_exclusion(self):
        for failure in ('set', 'read', 'mismatch'):
            with self.subTest(failure=failure):
                api = self.api(1 if failure == 'mismatch' else 0x11)
                if failure == 'set': api.SetWindowDisplayAffinity.return_value = 0
                if failure == 'read': api.GetWindowDisplayAffinity.side_effect = lambda *args: 0
                result = apply_window_effects(7, True, api=api, build=26300)
                self.assertFalse(result.excluded)
                self.assertIn('could not be confirmed', result.detail)

    def test_missing_private_export_keeps_documented_privacy_working(self):
        api = self.api()
        api.SetWindowCompositionAttribute.side_effect = AttributeError('missing export')
        result = apply_window_effects(7, True, api=api, build=26300)
        self.assertFalse(result.glass); self.assertTrue(result.excluded)
        self.assertIn('Painted fallback', result.detail)

    def test_old_windows_does_not_silently_use_black_box_monitor_affinity(self):
        api = self.api()
        result = apply_window_effects(7, True, api=api, build=18362)
        self.assertFalse(result.excluded)
        api.SetWindowDisplayAffinity.assert_not_called()
        api.GetWindowDisplayAffinity.assert_not_called()

    def test_other_platform_does_not_load_windows_libraries(self):
        with patch('studyframe.windows_effects.sys.platform', 'linux'):
            result = apply_window_effects(7, True)
        self.assertFalse(result.glass); self.assertFalse(result.excluded)


class EffectsLifecycleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): cls.app = QApplication.instance() or QApplication([])

    def test_capsule_startup_is_small_round_and_expands_without_losing_state(self):
        window = StudyWindow(start_collapsed=True)
        self.addCleanup(window.deleteLater); self.addCleanup(window.close)
        window.show(); self.app.processEvents()
        self.assertLessEqual(window.width(), 380)
        self.assertLessEqual(window.height(), 105)
        self.assertTrue(window.scroll.isHidden())
        self.assertTrue(window.centralWidget().compact)
        for button in (window.capture_button, window.settings_toggle, window.collapse_button, window.close_button):
            self.assertTrue(button.isVisible())
            self.assertLess(button.mapTo(window, button.rect().bottomRight()).x(), window.width())
        window.answer.setPlainText('Synthetic answer')
        self.assertIn('Answer ready', window.privacy_badge.text())
        window.settings_toggle.setChecked(True); self.app.processEvents()
        self.assertFalse(window.collapse_button.isChecked())
        self.assertTrue(window.settings_pane.isVisible())
        self.assertEqual(window.answer.toPlainText(), 'Synthetic answer')
        self.assertGreaterEqual(window.width(), 470)

    def test_toggle_pin_hide_restore_and_failed_reapply_update_visible_status(self):
        window = StudyWindow()
        self.addCleanup(window.deleteLater); self.addCleanup(window.close)
        with patch('studyframe.app.QApplication.platformName', return_value='windows'), \
             patch('studyframe.app.apply_window_effects', return_value=WindowEffects(True, True, 'confirmed')) as apply:
            window.show(); self.app.processEvents(); self.app.processEvents()
            self.assertTrue(window.exclude_capture.isChecked())
            self.assertEqual(window.privacy_badge.text(), 'Capture excluded')
            self.assertTrue(window.centralWidget().native_material)
            window.exclude_capture.setChecked(False)
            self.assertFalse(apply.call_args.args[1])
            window.exclude_capture.setChecked(True)
            before = apply.call_count
            window.pin.setChecked(False); self.app.processEvents(); self.app.processEvents()
            self.assertGreater(apply.call_count, before)
            before = apply.call_count
            window.hide(); window.show(); self.app.processEvents(); self.app.processEvents()
            self.assertGreater(apply.call_count, before)
            apply.return_value = WindowEffects(False, False, 'unavailable')
            window.update_window_effects()
            self.assertFalse(window.centralWidget().native_material)
            self.assertEqual(window.privacy_badge.text(), 'Capture unconfirmed')
            self.assertEqual(window.effects_info.text(), 'unavailable')
            window.collapse_button.setChecked(True); self.app.processEvents()
            self.assertTrue(window.privacy_badge.isVisible())
