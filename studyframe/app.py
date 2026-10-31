"""Local study workspace. Selecting an image never starts capture or inference."""

import sys
from pathlib import Path
from studyframe import __version__

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QApplication, QComboBox, QFileDialog, QHBoxLayout, QLabel, QMainWindow,
    QPlainTextEdit, QPushButton, QScrollArea, QVBoxLayout, QWidget, QLineEdit, QCheckBox, QTabWidget, QDialog,
)

from studyframe.images import ImageError, LoadedImage, load_image, crop_image
from studyframe.crop import CropDialog
from studyframe.requests import RequestError, prepare_request
from studyframe.provider import StudyProvider, payload, MODEL


class StudyWindow(QMainWindow):
    def __init__(self, provider=None):
        super().__init__()
        self.provider = provider or StudyProvider(self)
        self.busy = False
        self.last_exchange = None
        self.followup_context = None
        self.sent_question = ""
        self.attachment: LoadedImage | None = None
        self.original_attachment = None
        self.image_name = ""
        self.setWindowTitle(f"StudyFrame {__version__}")
        self.resize(1100, 780)
        self.setMinimumSize(760, 620)
        body = QWidget()
        root = QVBoxLayout(body)
        root.setContentsMargins(24, 20, 24, 20)
        root.setSpacing(12)
        title = QLabel("StudyFrame")
        title.setObjectName("title")
        root.addWidget(title)
        root.addWidget(QLabel(f"Screenshot focus · v{__version__} · Choose an image, crop the relevant area, then ask."))
        self.notice = QLabel(
            "Prepare locally, then choose whether to send to OpenAI. "
            "AI answers can be wrong: predict, ask, then verify."
        )
        self.notice.setWordWrap(True)
        root.addWidget(self.notice)
        columns = QHBoxLayout()
        left, right = QVBoxLayout(), QVBoxLayout()
        columns.addLayout(left, 1)
        columns.addLayout(right, 1)
        root.addLayout(columns, 1)
        self.tabs = QTabWidget()
        self.tabs.setAccessibleName("Study workflow")
        right.addWidget(self.tabs)
        question_page, review_page, answer_page = QWidget(), QWidget(), QWidget()
        question_layout, review_layout, answer_layout = QVBoxLayout(question_page), QVBoxLayout(review_page), QVBoxLayout(answer_page)
        self.tabs.addTab(question_page, "1. Question")
        self.tabs.addTab(review_page, "2. Review and send")
        self.tabs.addTab(answer_page, "3. Answer")

        left.addWidget(QLabel("1. Add what you are studying"))
        image_actions = QHBoxLayout()
        self.choose_button = QPushButton("Choose screenshot…")
        self.remove_button = QPushButton("Remove image")
        self.remove_button.setEnabled(False)
        image_actions.addWidget(self.choose_button)
        image_actions.addWidget(self.remove_button)
        left.addLayout(image_actions)
        crop_actions = QHBoxLayout()
        self.crop_button = QPushButton("Crop / focus area…")
        self.restore_button = QPushButton("Restore original")
        self.crop_button.setEnabled(False)
        self.restore_button.setEnabled(False)
        crop_actions.addWidget(self.crop_button)
        crop_actions.addWidget(self.restore_button)
        left.addLayout(crop_actions)
        self.image_label = QLabel("Choose a saved PNG or JPEG. Nothing is captured automatically.")
        self.image_label.setWordWrap(True)
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_label.setMinimumSize(300, 190)
        self.image_label.setObjectName("imagePreview")
        left.addWidget(self.image_label, 1)
        self.image_info = QLabel("No image selected")
        self.image_info.setWordWrap(True)
        self.image_info.setTextFormat(Qt.TextFormat.PlainText)
        left.addWidget(self.image_info)
        left.addWidget(QLabel("Optional notes or code"))
        self.context = QPlainTextEdit()
        self.context.setAccessibleName("Notes or code")
        self.context.setPlaceholderText("Paste a small example or explain what you tried…")
        left.addWidget(self.context, 1)

        question_layout.addWidget(QLabel("Choose how to learn"))
        self.mode = QComboBox()
        self.mode.setAccessibleName("Learning mode")
        for label, value in [("Give me a hint", "hint"), ("Explain the idea", "explain"), ("Help me debug", "debug")]:
            self.mode.addItem(label, value)
        question_layout.addWidget(self.mode)
        question_layout.addWidget(QLabel("Your question"))
        self.question = QPlainTextEdit()
        self.question.setAccessibleName("Your question")
        self.question.setPlaceholderText("What would you like to understand?")
        question_layout.addWidget(self.question, 1)
        self.followup_note = QLabel("New question. No previous exchange will be sent.")
        self.followup_note.setWordWrap(True)
        question_layout.addWidget(self.followup_note)
        self.new_topic_button = QPushButton("Start a new question")
        question_layout.addWidget(self.new_topic_button)
        self.prepare_button = QPushButton("Prepare request")
        self.prepare_button.setObjectName("primary")
        question_layout.addWidget(self.prepare_button)
        self.preview = QPlainTextEdit()
        self.preview.setReadOnly(True)
        self.preview.setAccessibleName("Prepared text request")
        self.preview.setPlaceholderText("Your prepared text will appear here. It is not an AI answer.")
        review_layout.addWidget(self.preview, 1)
        copy_note = QLabel("Copy includes text only. The image preview is not interpreted or attached.")
        copy_note.setWordWrap(True)
        review_layout.addWidget(copy_note)
        actions = QHBoxLayout()
        self.copy_button = QPushButton("Copy text")
        self.copy_button.setEnabled(False)
        self.clear_button = QPushButton("Clear session")
        actions.addWidget(self.copy_button)
        review_layout.addLayout(actions)
        review_layout.addWidget(QLabel(f"OpenAI · {MODEL} · api.openai.com"))
        self.key = QLineEdit()
        self.key.setEchoMode(QLineEdit.EchoMode.Password)
        self.key.setPlaceholderText("Your OpenAI API key — this session only")
        self.key.setAccessibleName("OpenAI API key")
        review_layout.addWidget(self.key)
        disclosure = QLabel("Send uses the image preview: original file bytes, or the selected crop as a new PNG. "
                            "A follow-up includes the previous question and answer shown above. "
                            "API charges apply; store=false is not a zero-retention guarantee.")
        disclosure.setWordWrap(True)
        review_layout.addWidget(disclosure)
        self.consent = QCheckBox("I reviewed the text and image for sending")
        review_layout.addWidget(self.consent)
        self.send_button = QPushButton("Send reviewed request")
        self.send_button.setEnabled(False)
        self.cancel_button = QPushButton("Cancel request")
        self.cancel_button.setEnabled(False)
        review_layout.addWidget(self.send_button)
        self.answer = QPlainTextEdit()
        self.answer.setReadOnly(True)
        self.answer.setAccessibleName("AI study answer")
        self.answer.setPlaceholderText("AI answer — verify it with a small example. No code is executed.")
        answer_layout.addWidget(self.answer, 1)
        self.copy_answer_button = QPushButton("Copy answer")
        self.copy_answer_button.setEnabled(False)
        answer_layout.addWidget(self.copy_answer_button)
        self.followup_button = QPushButton("Ask a follow-up")
        self.followup_button.setEnabled(False)
        answer_layout.addWidget(self.followup_button)
        footer = QHBoxLayout()
        footer.addWidget(self.cancel_button)
        footer.addWidget(self.clear_button)
        root.addLayout(footer)
        self.status = QLabel("Ready. Start with one question.")
        self.status.setWordWrap(True)
        self.status.setTextFormat(Qt.TextFormat.PlainText)
        root.addWidget(self.status)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(body)
        self.setCentralWidget(scroll)
        self.setStyleSheet("""
            QMainWindow, QWidget { background: #f4f6f9; color: #183047; }
            QLabel#title { font-size: 26px; font-weight: 700; }
            QLabel { font-size: 13px; }
            QPlainTextEdit, QComboBox { background: white; border: 1px solid #a9b8c7;
                border-radius: 6px; padding: 8px; font-size: 14px; }
            QPushButton { background: #e3eaf1; border: 1px solid #9bacbc;
                border-radius: 6px; padding: 9px; font-size: 13px; }
            QPushButton#primary { background: #165a86; color: white; }
            QPushButton:disabled { background: #e7ebef; color: #6f7e8b; }
            QPushButton:focus, QPlainTextEdit:focus, QComboBox:focus { border: 2px solid #2579ad; }
            QLabel#imagePreview { background: #e7edf3; border: 1px dashed #91a7ba; padding: 8px; }
        """)
        self.choose_button.clicked.connect(self.choose_image)
        self.remove_button.clicked.connect(self.remove_image)
        self.crop_button.clicked.connect(self.choose_crop)
        self.restore_button.clicked.connect(self.restore_image)
        self.prepare_button.clicked.connect(self.prepare)
        self.copy_button.clicked.connect(self.copy_text)
        self.copy_answer_button.clicked.connect(self.copy_answer)
        self.clear_button.clicked.connect(self.clear_session)
        self.question.textChanged.connect(self.invalidate)
        self.context.textChanged.connect(self.material_changed)
        self.mode.currentIndexChanged.connect(self.invalidate)
        self.consent.toggled.connect(self.update_send)
        self.key.textChanged.connect(self.update_send)
        self.send_button.clicked.connect(self.send_request)
        self.cancel_button.clicked.connect(self.cancel_request)
        self.provider.succeeded.connect(self.receive_answer)
        self.provider.failed.connect(self.receive_error)
        self.followup_button.clicked.connect(self.start_followup)
        self.new_topic_button.clicked.connect(self.new_topic)

    def material_changed(self):
        self.followup_context = None
        self.followup_note.setText("New question. No previous exchange will be sent.")
        self.invalidate()

    def new_topic(self):
        self.material_changed()
        self.question.clear()
        self.tabs.setCurrentIndex(0)
        self.question.setFocus()

    def start_followup(self):
        if self.last_exchange is None or self.busy:
            return
        try:
            prepare_request("Check follow-up bounds", previous=self.last_exchange)
        except RequestError as exc:
            self.status.setText(str(exc))
            return
        self.followup_context = self.last_exchange
        self.question.clear()
        self.invalidate()
        self.followup_note.setText("Follow-up: the last question and AI answer will appear in the request preview. "
                                   "Current image and notes are included again. Editing either starts a new question.")
        self.tabs.setCurrentIndex(0)
        self.question.setFocus()

    def update_send(self):
        self.send_button.setEnabled(bool(self.preview.toPlainText()) and bool(self.key.text())
                                    and self.consent.isChecked() and not self.busy)

    def set_busy(self, busy):
        self.busy = busy
        for widget in (self.question, self.context, self.mode, self.choose_button,
                       self.prepare_button, self.key, self.consent):
            widget.setEnabled(not busy)
        self.remove_button.setEnabled(not busy and self.attachment is not None)
        self.crop_button.setEnabled(not busy and self.attachment is not None)
        self.restore_button.setEnabled(not busy and self.original_attachment is not None
                                       and self.attachment is not self.original_attachment)
        self.cancel_button.setEnabled(busy)
        self.followup_button.setEnabled(not busy and self.last_exchange is not None)
        self.update_send()

    def send_request(self):
        if not self.send_button.isEnabled():
            return
        body = payload(self.preview.toPlainText(), self.attachment)
        self.answer.clear()
        self.copy_answer_button.setEnabled(False)
        self.sent_question = self.question.toPlainText().strip()
        self.set_busy(True)
        self.status.setText("Waiting for OpenAI. You can cancel; submitted requests may still be billed.")
        try:
            self.provider.send(body, self.key.text())
        except ValueError as exc:
            self.receive_error(str(exc))

    def receive_answer(self, text):
        if not self.busy:
            return
        self.set_busy(False)
        self.consent.setChecked(False)
        self.answer.setPlainText(text)
        self.last_exchange = (self.sent_question, text)
        self.followup_context = None
        self.followup_note.setText("New question. Use Ask a follow-up on the Answer tab to include the last exchange.")
        self.followup_button.setEnabled(True)
        self.copy_answer_button.setEnabled(True)
        self.tabs.setCurrentIndex(2)
        self.status.setText("AI answer received. Check its reasoning with a small example before relying on it.")

    def receive_error(self, message):
        if not self.busy:
            return
        self.set_busy(False)
        self.consent.setChecked(False)
        self.status.setText(message)

    def cancel_request(self):
        self.provider.cancel()
        self.set_busy(False)
        self.consent.setChecked(False)
        self.status.setText("Cancelled locally. OpenAI may still process and bill what was already sent.")

    def closeEvent(self, event):
        self.provider.cancel()
        self.key.clear()
        super().closeEvent(event)

    def invalidate(self):
        if self.busy:
            self.cancel_request()
        self.consent.setChecked(False)
        self.answer.clear()
        self.last_exchange = None
        self.followup_button.setEnabled(False)
        self.copy_answer_button.setEnabled(False)
        self.preview.clear()
        self.copy_button.setEnabled(False)
        self.update_send()
        self.status.setText("Inputs changed. Prepare a new request when ready.")

    def choose_image(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Choose a saved screenshot", "", "Images (*.png *.jpg *.jpeg)"
        )
        if path:
            self.select_image(path)

    def select_image(self, path):
        # A failed replacement retains the previous selection and request.
        try:
            selected = load_image(path)
        except ImageError as exc:
            self.status.setText(f"{exc} Previous selection kept.")
            return
        self.attachment = selected
        self.original_attachment = selected
        self.image_name = Path(path).name
        self.material_changed()
        self.update_image_info()
        self.remove_button.setEnabled(True)
        self.crop_button.setEnabled(True)
        self.restore_button.setEnabled(False)
        self.render_image()
        self.status.setText("Image selected locally. No text extraction or AI analysis has run.")

    def update_image_info(self):
        if self.attachment is None:
            self.image_info.setText("No image selected")
            return
        image = self.attachment
        kind = "Original" if image is self.original_attachment else "Cropped PNG"
        self.image_info.setText(f"{self.image_name} · {kind} · {image.width} × {image.height} · "
                                f"{len(image.data):,} bytes · SHA256 {image.sha256[:12]}…")

    def choose_crop(self):
        if self.attachment is None or self.busy:
            return
        dialog = CropDialog(self.attachment.image, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.apply_crop(dialog.selected_rect())

    def apply_crop(self, rect):
        if self.attachment is None or self.busy:
            return
        try:
            cropped = crop_image(self.attachment, rect.x(), rect.y(), rect.width(), rect.height())
        except ImageError as exc:
            self.status.setText(str(exc))
            return
        self.attachment = cropped
        self.material_changed()
        self.update_image_info()
        self.restore_button.setEnabled(True)
        self.render_image()
        self.status.setText("Crop applied locally. Only these pixels will be sent after a new review. Original file unchanged.")

    def restore_image(self):
        if self.original_attachment is None or self.busy:
            return
        self.attachment = self.original_attachment
        self.material_changed()
        self.update_image_info()
        self.restore_button.setEnabled(False)
        self.render_image()
        self.status.setText("Original byte snapshot restored, including original metadata. Prepare and review again before sending.")

    def render_image(self):
        if self.attachment is not None:
            available = self.image_label.contentsRect().size()
            self.image_label.setPixmap(QPixmap.fromImage(self.attachment.image).scaled(
                max(1, available.width() - 16), max(1, available.height() - 16),
                Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation,
            ))

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, "image_label"):
            self.render_image()

    def remove_image(self):
        self.attachment = None
        self.original_attachment = None
        self.image_name = ""
        self.image_label.clear()
        self.image_label.setText("Choose a saved PNG or JPEG. Nothing is captured automatically.")
        self.image_info.setText("No image selected")
        self.remove_button.setEnabled(False)
        self.crop_button.setEnabled(False)
        self.restore_button.setEnabled(False)
        self.material_changed()

    def prepare(self):
        self.invalidate()
        try:
            text = prepare_request(self.question.toPlainText(), self.context.toPlainText(), self.mode.currentData(),
                                   previous=self.followup_context)
        except RequestError as exc:
            self.status.setText(str(exc))
            return
        self.preview.setPlainText(text)
        self.copy_button.setEnabled(True)
        self.update_send()
        self.tabs.setCurrentIndex(1)
        self.status.setText("Text request prepared locally. No AI answer or transmission has occurred.")

    def copy_text(self):
        text = self.preview.toPlainText()
        if text and self.copy_button.isEnabled():
            QApplication.clipboard().setText(text)
            self.status.setText("Text copied. The clipboard may keep it after this session is cleared.")

    def copy_answer(self):
        if self.copy_answer_button.isEnabled():
            QApplication.clipboard().setText(self.answer.toPlainText())
            self.status.setText("AI answer copied. Verify it before relying on it; clipboard history may retain it.")

    def clear_session(self):
        self.cancel_request()
        self.sent_question = ""
        self.key.clear()
        self.question.clear()
        self.context.clear()
        self.mode.setCurrentIndex(0)
        self.remove_image()
        self.tabs.setCurrentIndex(0)
        self.status.setText("Session cleared. Your original image file and clipboard are unchanged.")


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("StudyFrame")
    window = StudyWindow()
    window.show()
    return app.exec()
