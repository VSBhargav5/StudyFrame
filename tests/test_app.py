"""Real Qt widget behavior with synthetic input and an isolated clipboard stub."""

import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from PySide6.QtCore import Qt
from PySide6.QtGui import QImage
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from studyframe.app import StudyWindow


class WindowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / "synthetic.png"
        image = QImage(60, 30, QImage.Format.Format_RGB32)
        image.fill(Qt.GlobalColor.blue)
        self.assertTrue(image.save(str(self.path)))
        self.window = StudyWindow()
        self.window.show()
        self.app.processEvents()

    def tearDown(self):
        self.window.close()
        self.window.deleteLater()
        self.app.processEvents()
        self.temp.cleanup()

    def prepare(self):
        self.window.question.setPlainText("Why does this loop skip the final item?")
        self.window.context.setPlainText("for i in range(3):\n    print(i)")
        QTest.mouseClick(self.window.prepare_button, Qt.MouseButton.LeftButton)
        self.assertTrue(self.window.preview.toPlainText())
        self.assertTrue(self.window.copy_button.isEnabled())

    def test_prepare_and_copy_use_visible_text_only(self):
        self.window.select_image(self.path)
        self.prepare()
        clipboard = Mock()
        with patch("studyframe.app.QApplication.clipboard", return_value=clipboard):
            QTest.mouseClick(self.window.copy_button, Qt.MouseButton.LeftButton)
        clipboard.setText.assert_called_once_with(self.window.preview.toPlainText())
        self.assertNotIn(str(self.path), self.window.preview.toPlainText())
        self.assertNotIn(self.window.attachment.sha256, self.window.preview.toPlainText())

    def test_question_context_and_mode_changes_invalidate_preview(self):
        for change in [lambda: self.window.question.insertPlainText("?"),
                       lambda: self.window.context.insertPlainText("# change"),
                       lambda: self.window.mode.setCurrentIndex(1)]:
            self.prepare()
            change()
            self.assertEqual(self.window.preview.toPlainText(), "")
            self.assertFalse(self.window.copy_button.isEnabled())

    def test_image_selection_and_removal_invalidate_preview(self):
        self.prepare()
        self.window.select_image(self.path)
        self.assertIsNotNone(self.window.attachment)
        self.assertFalse(self.window.image_label.pixmap().isNull())
        self.assertEqual(self.window.preview.toPlainText(), "")
        self.prepare()
        QTest.mouseClick(self.window.remove_button, Qt.MouseButton.LeftButton)
        self.assertIsNone(self.window.attachment)
        self.assertEqual(self.window.preview.toPlainText(), "")
        self.assertFalse(self.window.remove_button.isEnabled())

    def test_picker_cancel_preserves_current_session(self):
        self.window.select_image(self.path)
        self.prepare()
        previous = self.window.attachment
        text = self.window.preview.toPlainText()
        with patch("studyframe.app.QFileDialog.getOpenFileName", return_value=("", "")):
            self.window.choose_image()
        self.assertIs(self.window.attachment, previous)
        self.assertEqual(self.window.preview.toPlainText(), text)

    def test_picker_loads_only_explicit_selection(self):
        with patch("studyframe.app.QFileDialog.getOpenFileName", return_value=(str(self.path), "Images")):
            QTest.mouseClick(self.window.choose_button, Qt.MouseButton.LeftButton)
        self.assertEqual(self.window.attachment.width, 60)

    def test_failed_replacement_preserves_image_and_request(self):
        self.window.select_image(self.path)
        self.prepare()
        previous = self.window.attachment
        text = self.window.preview.toPlainText()
        broken = Path(self.temp.name) / "broken.png"
        broken.write_bytes(b"not an image")
        self.window.select_image(broken)
        self.assertIs(self.window.attachment, previous)
        self.assertEqual(self.window.preview.toPlainText(), text)
        self.assertIn("Previous selection kept", self.window.status.text())

    def test_blank_question_shows_error_without_old_preview(self):
        self.prepare()
        self.window.question.setPlainText("   ")
        self.window.prepare()
        self.assertEqual(self.window.preview.toPlainText(), "")
        self.assertFalse(self.window.copy_button.isEnabled())
        self.assertTrue(self.window.status.text())

    def test_clear_drops_session_without_touching_source_or_clipboard(self):
        original = self.path.read_bytes()
        self.window.select_image(self.path)
        self.prepare()
        clipboard = Mock()
        with patch("studyframe.app.QApplication.clipboard", return_value=clipboard):
            QTest.mouseClick(self.window.clear_button, Qt.MouseButton.LeftButton)
        clipboard.setText.assert_not_called()
        self.assertEqual(self.window.question.toPlainText(), "")
        self.assertEqual(self.window.context.toPlainText(), "")
        self.assertEqual(self.window.preview.toPlainText(), "")
        self.assertIsNone(self.window.attachment)
        self.assertEqual(self.path.read_bytes(), original)

    def test_tabs_move_from_question_to_review_and_clear_returns_to_question(self):
        self.assertEqual(self.window.tabs.currentIndex(), 0)
        self.prepare()
        self.assertEqual(self.window.tabs.currentIndex(), 1)
        self.window.clear_session()
        self.assertEqual(self.window.tabs.currentIndex(), 0)

    def test_copy_answer_requires_a_current_completed_answer(self):
        clipboard = Mock()
        with patch("studyframe.app.QApplication.clipboard", return_value=clipboard):
            self.window.copy_answer()
            clipboard.setText.assert_not_called()
            self.window.busy = True
            self.window.receive_answer("Synthetic <b>plain text</b> answer")
            self.assertEqual(self.window.tabs.currentIndex(), 2)
            self.window.copy_answer()
            clipboard.setText.assert_called_once_with("Synthetic <b>plain text</b> answer")
            self.window.question.setPlainText("A different question")
            self.assertFalse(self.window.copy_answer_button.isEnabled())


if __name__ == "__main__":
    unittest.main()
