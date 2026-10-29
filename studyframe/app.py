"""Local study workspace. Selecting an image never starts capture or inference."""

import sys
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QApplication, QComboBox, QFileDialog, QHBoxLayout, QLabel, QMainWindow,
    QPlainTextEdit, QPushButton, QScrollArea, QVBoxLayout, QWidget,
)

from studyframe.images import ImageError, LoadedImage, load_image
from studyframe.requests import RequestError, prepare_request


class StudyWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.attachment: LoadedImage | None = None
        self.setWindowTitle("StudyFrame")
        self.resize(1100, 780)
        self.setMinimumSize(760, 620)
        body = QWidget()
        root = QVBoxLayout(body)
        root.setContentsMargins(24, 20, 24, 20)
        root.setSpacing(12)
        title = QLabel("StudyFrame")
        title.setObjectName("title")
        root.addWidget(title)
        root.addWidget(QLabel("Make sense of the code and material in front of you."))
        self.notice = QLabel(
            "Local workspace · No AI connected. Images stay in this session; "
            "copied text goes to your clipboard."
        )
        self.notice.setWordWrap(True)
        root.addWidget(self.notice)
        columns = QHBoxLayout()
        left, right = QVBoxLayout(), QVBoxLayout()
        columns.addLayout(left, 1)
        columns.addLayout(right, 1)
        root.addLayout(columns, 1)

        left.addWidget(QLabel("1. Add what you are studying"))
        image_actions = QHBoxLayout()
        self.choose_button = QPushButton("Choose screenshot…")
        self.remove_button = QPushButton("Remove image")
        self.remove_button.setEnabled(False)
        image_actions.addWidget(self.choose_button)
        image_actions.addWidget(self.remove_button)
        left.addLayout(image_actions)
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

        right.addWidget(QLabel("2. Choose how to learn"))
        self.mode = QComboBox()
        self.mode.setAccessibleName("Learning mode")
        for label, value in [("Give me a hint", "hint"), ("Explain the idea", "explain"), ("Help me debug", "debug")]:
            self.mode.addItem(label, value)
        right.addWidget(self.mode)
        right.addWidget(QLabel("Your question"))
        self.question = QPlainTextEdit()
        self.question.setAccessibleName("Your question")
        self.question.setPlaceholderText("What would you like to understand?")
        self.question.setMaximumHeight(115)
        right.addWidget(self.question)
        self.prepare_button = QPushButton("Prepare request")
        self.prepare_button.setObjectName("primary")
        right.addWidget(self.prepare_button)
        self.preview = QPlainTextEdit()
        self.preview.setReadOnly(True)
        self.preview.setAccessibleName("Prepared text request")
        self.preview.setPlaceholderText("Your prepared text will appear here. It is not an AI answer.")
        right.addWidget(self.preview, 1)
        copy_note = QLabel("Copy includes text only. The image preview is not interpreted or attached.")
        copy_note.setWordWrap(True)
        right.addWidget(copy_note)
        actions = QHBoxLayout()
        self.copy_button = QPushButton("Copy text")
        self.copy_button.setEnabled(False)
        self.clear_button = QPushButton("Clear session")
        actions.addWidget(self.copy_button)
        actions.addWidget(self.clear_button)
        right.addLayout(actions)
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
        self.prepare_button.clicked.connect(self.prepare)
        self.copy_button.clicked.connect(self.copy_text)
        self.clear_button.clicked.connect(self.clear_session)
        self.question.textChanged.connect(self.invalidate)
        self.context.textChanged.connect(self.invalidate)
        self.mode.currentIndexChanged.connect(self.invalidate)

    def invalidate(self):
        self.preview.clear()
        self.copy_button.setEnabled(False)
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
        self.invalidate()
        self.image_info.setText(f"{Path(path).name} · {selected.width} × {selected.height} · Local preview")
        self.remove_button.setEnabled(True)
        self.render_image()
        self.status.setText("Image selected locally. No text extraction or AI analysis has run.")

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
        self.image_label.clear()
        self.image_label.setText("Choose a saved PNG or JPEG. Nothing is captured automatically.")
        self.image_info.setText("No image selected")
        self.remove_button.setEnabled(False)
        self.invalidate()

    def prepare(self):
        self.invalidate()
        try:
            text = prepare_request(self.question.toPlainText(), self.context.toPlainText(), self.mode.currentData())
        except RequestError as exc:
            self.status.setText(str(exc))
            return
        self.preview.setPlainText(text)
        self.copy_button.setEnabled(True)
        self.status.setText("Text request prepared locally. No AI answer or transmission has occurred.")

    def copy_text(self):
        text = self.preview.toPlainText()
        if text and self.copy_button.isEnabled():
            QApplication.clipboard().setText(text)
            self.status.setText("Text copied. The clipboard may keep it after this session is cleared.")

    def clear_session(self):
        self.question.clear()
        self.context.clear()
        self.mode.setCurrentIndex(0)
        self.remove_image()
        self.status.setText("Session cleared. Your original image file and clipboard are unchanged.")


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("StudyFrame")
    window = StudyWindow()
    window.show()
    return app.exec()
