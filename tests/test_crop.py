import base64
import hashlib
import json
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from PySide6.QtCore import QCoreApplication, QEvent, QPoint, QRect, Qt
from PySide6.QtGui import QColor, QImage
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QDialog, QDialogButtonBox

from studyframe.app import StudyWindow
from studyframe.crop import CropCanvas, CropDialog
from studyframe.images import crop_image, load_image, ImageError
from studyframe.provider import payload


class CropTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "synthetic.png"
        image = QImage(100, 50, QImage.Format.Format_ARGB32)
        image.fill(QColor("red"))
        for x in range(25, 75):
            for y in range(10, 40):
                image.setPixelColor(x, y, QColor(10, 20, 30, 128))
        image.setText("private-note", "synthetic-original-metadata")
        self.assertTrue(image.save(str(self.path)))
        self.source = load_image(self.path)

    def show(self, widget):
        widget.show()
        self.app.processEvents()
        def dispose():
            widget.close()
            widget.deleteLater()
            QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
            self.app.processEvents()
        self.addCleanup(dispose)
        return widget

    def test_crop_encodes_only_selected_oriented_pixels_without_source_metadata(self):
        original = self.path.read_bytes()
        result = crop_image(self.source, 25, 10, 50, 30)
        decoded = QImage.fromData(result.data)
        self.assertEqual((result.width, result.height, result.format), (50, 30, "png"))
        self.assertEqual(decoded.pixelColor(0, 0), QColor(10, 20, 30, 128))
        self.assertEqual(decoded.pixelColor(49, 29), QColor(10, 20, 30, 128))
        self.assertEqual(decoded.textKeys(), [])
        self.assertNotIn(b"synthetic-original-metadata", result.data)
        self.assertEqual(result.sha256, hashlib.sha256(result.data).hexdigest())
        self.assertEqual(self.path.read_bytes(), original)
        self.assertEqual(self.source.data, original)

    def test_crop_rejects_outside_empty_and_non_integer_coordinates(self):
        for coords in ((-1, 0, 2, 2), (0, 0, 0, 1), (99, 0, 2, 1), (0, 49, 1, 2),
                       (0.5, 0, 1, 1), (True, 0, 1, 1), (0, 0, -1, 2)):
            with self.subTest(coords=coords), self.assertRaises(ImageError):
                crop_image(self.source, *coords)

    def test_crop_uses_snapshot_even_after_original_file_is_replaced(self):
        self.path.write_bytes(b"replaced")
        result = crop_image(self.source, 25, 10, 50, 30)
        self.assertEqual(result.image.pixelColor(0, 0), QColor(10, 20, 30, 128))

    def test_encoded_crop_limit_failure_preserves_source(self):
        with patch("studyframe.images.MAX_FILE_BYTES", 1):
            with self.assertRaisesRegex(ImageError, "8 MiB"):
                crop_image(self.source, 0, 0, 1, 1)
        self.assertTrue(self.source.data)

    def test_one_pixel_and_full_image_crops(self):
        self.assertEqual(crop_image(self.source, 99, 49, 1, 1).image.pixelColor(0, 0), QColor("red"))
        full = crop_image(self.source, 0, 0, 100, 50)
        self.assertEqual(full.image.size(), self.source.image.size())
        self.assertEqual(full.image.textKeys(), [])

    def test_drag_maps_display_coordinates_to_source_pixels_in_both_directions(self):
        canvas = self.show(CropCanvas(self.source.image))
        canvas.resize(416, 216)
        self.app.processEvents()
        self.assertEqual(canvas.image_rect().x(), 8)
        for start, end in ((QPoint(108, 48), QPoint(308, 168)), (QPoint(308, 168), QPoint(108, 48))):
            QTest.mousePress(canvas, Qt.MouseButton.LeftButton, pos=start)
            QTest.mouseMove(canvas, end)
            QTest.mouseRelease(canvas, Qt.MouseButton.LeftButton, pos=end)
            self.assertEqual(canvas.selection, QRect(25, 10, 50, 30))

    def test_margin_click_is_ignored_and_release_outside_is_clamped(self):
        canvas = self.show(CropCanvas(self.source.image))
        canvas.resize(416, 216)
        self.app.processEvents()
        QTest.mouseClick(canvas, Qt.MouseButton.LeftButton, pos=QPoint(1, 1))
        self.assertTrue(canvas.selection.isEmpty())
        QTest.mousePress(canvas, Qt.MouseButton.LeftButton, pos=QPoint(108, 48))
        QTest.mouseRelease(canvas, Qt.MouseButton.LeftButton, pos=QPoint(415, 215))
        self.assertEqual(canvas.selection, QRect(25, 10, 75, 40))

    def test_pixel_controls_allow_keyboard_selection_and_reject_outside(self):
        dialog = self.show(CropDialog(self.source.image))
        apply = dialog.buttons.button(QDialogButtonBox.StandardButton.Ok)
        self.assertFalse(apply.isEnabled())
        dialog.fields[2].setValue(50)
        dialog.fields[3].setValue(30)
        dialog.fields[0].setValue(25)
        dialog.fields[1].setValue(10)
        self.assertTrue(apply.isEnabled())
        self.assertEqual(dialog.selected_rect(), QRect(25, 10, 50, 30))
        dialog.fields[0].setValue(99)
        self.assertFalse(apply.isEnabled())

    def test_cancel_keeps_attachment_preview_and_consent(self):
        window = self.show(StudyWindow())
        window.select_image(self.path)
        window.question.setPlainText("Explain")
        window.prepare()
        window.consent.setChecked(True)
        previous = window.preview.toPlainText()
        with patch("studyframe.app.CropDialog.exec", return_value=QDialog.DialogCode.Rejected):
            window.choose_crop()
        self.assertIs(window.attachment, window.original_attachment)
        self.assertEqual(window.preview.toPlainText(), previous)
        self.assertTrue(window.consent.isChecked())

    def test_apply_changes_payload_resets_followup_and_restores_exact_original(self):
        window = self.show(StudyWindow())
        window.select_image(self.path)
        original = window.attachment
        window.question.setPlainText("Explain")
        window.prepare()
        window.followup_context = ("previous", "answer")
        window.consent.setChecked(True)
        window.apply_crop(QRect(25, 10, 50, 30))
        self.assertEqual(window.preview.toPlainText(), "")
        self.assertFalse(window.consent.isChecked())
        self.assertIsNone(window.followup_context)
        self.assertTrue(window.restore_button.isEnabled())
        body = json.loads(payload("question", window.attachment))
        data = base64.b64decode(body["input"][0]["content"][1]["image_url"].split(",")[1])
        self.assertEqual(data, window.attachment.data)
        self.assertEqual(QImage.fromData(data).size(), window.attachment.image.size())
        self.assertNotEqual(data, original.data)
        window.restore_image()
        self.assertIs(window.attachment, original)
        self.assertEqual(window.attachment.data, original.data)
        self.assertFalse(window.restore_button.isEnabled())

    def test_crop_controls_disable_during_request_and_clear_releases_original(self):
        window = self.show(StudyWindow())
        window.select_image(self.path)
        original = window.attachment
        window.set_busy(True)
        window.apply_crop(QRect(0, 0, 1, 1))
        self.assertIs(window.attachment, original)
        self.assertFalse(window.crop_button.isEnabled())
        window.set_busy(False)
        self.assertTrue(window.crop_button.isEnabled())
        window.clear_session()
        self.assertIsNone(window.original_attachment)
        self.assertFalse(window.crop_button.isEnabled())
        self.assertFalse(window.restore_button.isEnabled())
