"""Local study workspace. Explicit display capture and reviewed vision help; no background watching."""

import sys
from pathlib import Path
from datetime import datetime
from studyframe import __version__

from PySide6.QtCore import Qt, QTimer, QEvent, QRectF
from PySide6.QtGui import QPixmap, QPainterPath, QRegion
from PySide6.QtWidgets import (
    QApplication, QComboBox, QFileDialog, QHBoxLayout, QLabel, QMainWindow,
    QPlainTextEdit, QPushButton, QScrollArea, QVBoxLayout, QWidget, QLineEdit, QCheckBox, QDialog, QInputDialog, QFrame, QSizeGrip, QProgressBar,
)

from studyframe.images import ImageError, LoadedImage, load_image, crop_image
from studyframe.crop import CropDialog
from studyframe.requests import RequestError, prepare_request
from studyframe.provider import StudyProvider, payload, PROVIDERS, provider_config
from studyframe.capture import capture_screen
from studyframe.glass import GlassPanel, DragBar
from studyframe.windows_effects import apply_window_effects, WindowEffects
from studyframe.speech import SpeechSession
from studyframe.preferences import Preferences


class StudyWindow(QMainWindow):
    def __init__(self, provider=None, *, start_collapsed=False, speech=None, preferences=None):
        super().__init__()
        self.provider = provider or StudyProvider(self)
        self.speech = speech or SpeechSession(self)
        self.preferences = preferences
        self.busy = False
        self.pending_screen = None
        self.capture_timer = QTimer(self)
        self.capture_timer.setSingleShot(True)
        self.capture_timer.timeout.connect(self.complete_capture)
        self.last_exchange = None
        self.followup_context = None
        self.sent_question = ""
        self.attachment: LoadedImage | None = None
        self.original_attachment = None
        self.image_name = ""
        self.direct_request = None
        self.expanded_size = None
        self.effects_timer = QTimer(self)
        self.effects_timer.setSingleShot(True)
        self.effects_timer.timeout.connect(self.update_window_effects)
        self.setWindowTitle(f"StudyFrame {__version__} - Screen companion")
        self.setWindowFlags(Qt.WindowType.Window | Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.resize(630, 660)
        self.setMinimumSize(470, 110)
        panel = GlassPanel()
        self.setCentralWidget(panel)
        root = QVBoxLayout(panel)
        self.root_layout = root
        root.setContentsMargins(25, 21, 25, 18)
        root.setSpacing(12)

        self.drag_bar = DragBar()
        title = QHBoxLayout(self.drag_bar)
        title.setContentsMargins(0, 0, 0, 0)
        title.setSpacing(9)
        mark = QLabel('sf')
        mark.setObjectName('brandMark')
        mark.setAlignment(Qt.AlignmentFlag.AlignCenter)
        mark.setFixedSize(32,32)
        title.addWidget(mark)
        name = QLabel('StudyFrame')
        self.brand_name = name
        name.setObjectName('brand')
        name.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        name.setToolTip(f'StudyFrame {__version__} - visible desktop companion')
        title.addWidget(name)
        title.addStretch()
        self.capture_button = QPushButton('Capture && ask')
        self.capture_button.setAccessibleName('Capture & ask')
        self.capture_button.setObjectName('primary')
        self.capture_button.setShortcut('Ctrl+Return')
        self.capture_button.setToolTip('Capture the selected display and send its fresh pixels to the selected model. Ctrl+Enter while focused.')
        title.addWidget(self.capture_button)
        self.settings_toggle = QPushButton('…')
        self.settings_toggle.setCheckable(True)
        self.settings_toggle.setAccessibleName('Connection settings')
        self.settings_toggle.setToolTip('Connect a model')
        self.collapse_button = QPushButton('−')
        self.collapse_button.setCheckable(True)
        self.collapse_button.setAccessibleName('Collapse overlay')
        self.close_button = QPushButton('×')
        self.close_button.setAccessibleName('Close StudyFrame')
        for button in (self.settings_toggle,self.collapse_button,self.close_button):
            button.setObjectName('windowButton')
            button.setFixedSize(28,30)
            title.addWidget(button)
        root.addWidget(self.drag_bar)
        self.progress = QProgressBar()
        self.progress.setRange(0,0)
        self.progress.setTextVisible(False)
        self.progress.setFixedHeight(2)
        self.progress.hide()
        root.addWidget(self.progress)

        self.content = QWidget()
        content = QVBoxLayout(self.content)
        content.setContentsMargins(0,0,0,0)
        content.setSpacing(12)
        self.scroll = QScrollArea()
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll.setWidgetResizable(True)
        self.scroll.setWidget(self.content)
        root.addWidget(self.scroll,1)
        source_row = QHBoxLayout()
        self.screen_choice = QComboBox()
        self.screen_choice.setAccessibleName('Capture display')
        self.screen_choice.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        self.screen_choice.setMinimumContentsLength(6)
        self.refresh_screens()
        self.provider_badge = QLabel('FREE ROUTE')
        self.provider_badge.setObjectName('routeBadge')
        source_row.addWidget(self.screen_choice,1)
        source_row.addWidget(self.provider_badge)
        content.addLayout(source_row)
        self.question = QPlainTextEdit()
        self.question.setAccessibleName('Your question')
        self.question.setPlaceholderText('What would you like to understand on this screen?')
        self.question.setFixedHeight(76)
        content.addWidget(self.question)
        style_row = QHBoxLayout()
        self.mode = QComboBox()
        self.mode.setAccessibleName('Answer style')
        for label,value in [('Explain','explain'),('Hint','hint'),('Debug','debug')]:self.mode.addItem(label,value)
        self.review_toggle = QPushButton('Preview')
        self.review_toggle.setToolTip('Preview or crop the captured image')
        self.review_toggle.setCheckable(True)
        self.review_toggle.setObjectName('ghost')
        self.new_topic_button = QPushButton('New')
        self.new_topic_button.setAccessibleName('New question')
        self.new_topic_button.setToolTip('Start a new question')
        self.new_topic_button.setObjectName('ghost')
        style_row.addWidget(self.mode)
        style_row.addStretch()
        style_row.addWidget(self.new_topic_button)
        style_row.addWidget(self.review_toggle)
        content.addLayout(style_row)
        self.capture_notice = QLabel()
        self.capture_notice.setObjectName('muted')
        self.capture_notice.setWordWrap(True)
        self.capture_notice.setTextFormat(Qt.TextFormat.PlainText)
        content.addWidget(self.capture_notice)
        answer_label = QLabel('YOUR ANSWER')
        answer_label.setObjectName('eyebrow')
        content.addWidget(answer_label)
        self.answer = QPlainTextEdit()
        self.answer.setReadOnly(True)
        self.answer.setAccessibleName('AI study answer')
        self.answer.setPlaceholderText('A little clarity, right here.\n\nCapture your screen to ask the model about it. Your answer will appear in this space.')
        self.answer.setMinimumHeight(180)
        content.addWidget(self.answer,1)
        answer_actions = QHBoxLayout()
        self.copy_answer_button = QPushButton('Copy')
        self.copy_answer_button.setAccessibleName('Copy answer')
        self.copy_answer_button.setToolTip('Copy answer')
        self.followup_button = QPushButton('Follow up')
        self.cancel_button = QPushButton('Cancel')
        for button in (self.copy_answer_button,self.followup_button,self.cancel_button):
            button.setObjectName('ghost')
            button.setEnabled(False)
            answer_actions.addWidget(button)
        answer_actions.addStretch()
        self.clear_button = QPushButton('Clear')
        self.clear_button.setAccessibleName('Clear session')
        self.clear_button.setToolTip('Clear session, including the session key')
        self.clear_button.setObjectName('ghost')
        answer_actions.addWidget(self.clear_button)
        content.addLayout(answer_actions)
        self.followup_note = QLabel('New question · no previous exchange included.')
        self.followup_note.setWordWrap(True)
        self.followup_note.setObjectName('muted')
        content.addWidget(self.followup_note)

        self.speech_pane = QFrame()
        self.speech_pane.setObjectName('drawer')
        voice = QVBoxLayout(self.speech_pane)
        voice.addWidget(QLabel('VOICE QUESTION · LOCAL TRANSCRIPTION'))
        self.speech_source = QComboBox()
        self.speech_source.addItem('Computer audio · default playback device', 'loopback')
        self.speech_source.addItem('Microphone · default input device', 'microphone')
        self.speech_source.setAccessibleName('Speech audio source')
        voice.addWidget(self.speech_source)
        self.speech_model = QLineEdit(str(Path(__file__).resolve().parents[1] / 'models/vosk-model-small-en-us-0.15'))
        self.speech_model.setAccessibleName('Local Vosk model folder')
        self.speech_model.setPlaceholderText('Choose an extracted Vosk model folder')
        voice.addWidget(self.speech_model)
        actions = QHBoxLayout()
        self.speech_browse = QPushButton('Model folder…')
        self.speech_record = QPushButton('Listen')
        self.speech_discard = QPushButton('Discard')
        for button in (self.speech_browse, self.speech_record, self.speech_discard): actions.addWidget(button)
        voice.addLayout(actions)
        self.speech_level = QProgressBar()
        self.speech_level.setRange(0,100)
        self.speech_level.setValue(0)
        self.speech_level.setTextVisible(False)
        self.speech_level.setAccessibleName('Selected audio source signal level')
        self.speech_level.setToolTip('Live signal level for the selected source. A flat meter can indicate muted or missing audio.')
        self.speech_level.setFixedHeight(5)
        voice.addWidget(self.speech_level)
        self.speech_note = QLabel('Listen records up to 30 seconds from the selected source. Stop finishes early. '
                                  'Audio stays local; review/edit the transcript, then Ask text only. '
                                  'Optional setup: docs/speech.md.')
        self.speech_note.setObjectName('muted')
        self.speech_note.setWordWrap(True)
        self.speech_note.setTextFormat(Qt.TextFormat.PlainText)
        voice.addWidget(self.speech_note)
        self.speech_text = QPlainTextEdit()
        self.speech_text.setAccessibleName('Reviewed speech transcript')
        self.speech_text.setPlaceholderText('Your local transcript appears here. Correct recognition errors before asking.')
        self.speech_text.setFixedHeight(100)
        voice.addWidget(self.speech_text)
        self.ask_speech = QPushButton('Ask text only')
        self.ask_speech.setToolTip('Send only the reviewed transcript and answer style to the chosen provider. No screenshot, audio or notes.')
        self.ask_speech.setEnabled(False)
        voice.addWidget(self.ask_speech)
        self.speech_pane.hide()
        content.addWidget(self.speech_pane)

        self.settings_pane = QFrame()
        self.settings_pane.setObjectName('drawer')
        settings = QVBoxLayout(self.settings_pane)
        settings.setSpacing(9)
        settings.addWidget(QLabel('CONNECT YOUR MODEL'))
        self.provider_choice = QComboBox()
        self.provider_choice.setAccessibleName('AI provider')
        for identifier in ('openrouter_free','openai'):self.provider_choice.addItem(PROVIDERS[identifier]['label'],identifier)
        settings.addWidget(self.provider_choice)
        self.connection_info = QLabel()
        self.connection_info.setWordWrap(True)
        self.connection_info.setTextFormat(Qt.TextFormat.PlainText)
        self.connection_info.setObjectName('muted')
        settings.addWidget(self.connection_info)
        self.key = QLineEdit()
        self.key.setEchoMode(QLineEdit.EchoMode.Password)
        settings.addWidget(self.key)
        self.disclosure = QLabel()
        self.disclosure.setWordWrap(True)
        self.disclosure.setObjectName('muted')
        settings.addWidget(self.disclosure)
        self.pin = QCheckBox('Keep above other windows')
        self.pin.setChecked(True)
        settings.addWidget(self.pin)
        self.exclude_capture = QCheckBox('Exclude overlay from supported captures')
        self.exclude_capture.setChecked(True)
        self.exclude_capture.setToolTip('Windows capture exclusion for this overlay only. Not a guarantee for every recorder.')
        settings.addWidget(self.exclude_capture)
        self.effects_info = QLabel('Checking Windows effects when the window opens…')
        self.effects_info.setObjectName('muted')
        self.effects_info.setWordWrap(True)
        settings.addWidget(self.effects_info)
        self.save_setup_button = QPushButton('Save setup')
        self.save_setup_button.setEnabled(preferences is not None)
        settings.addWidget(self.save_setup_button)
        self.setup_note = QLabel('Only provider, audio source, model folder and pinning are saved locally. '
                                'Keys, questions and transcripts are never saved. Capture exclusion starts on each time.')
        self.setup_note.setObjectName('muted')
        self.setup_note.setWordWrap(True)
        settings.addWidget(self.setup_note)
        self.settings_pane.hide()
        content.addWidget(self.settings_pane)

        self.review_pane = QFrame()
        self.review_pane.setObjectName('drawer')
        review = QVBoxLayout(self.review_pane)
        review.setSpacing(8)
        self.review_capture_button = QPushButton('Capture for preview only…')
        review.addWidget(self.review_capture_button)
        image_actions = QHBoxLayout()
        image_actions.setSpacing(4)
        self.choose_button = QPushButton('Load…')
        self.choose_button.setToolTip('Load a saved image')
        self.remove_button = QPushButton('Remove')
        self.crop_button = QPushButton('Crop…')
        self.restore_button = QPushButton('Reset')
        self.restore_button.setToolTip('Restore the original image')
        for button in (self.choose_button,self.remove_button,self.crop_button,self.restore_button):image_actions.addWidget(button)
        review.addLayout(image_actions)
        self.remove_button.setEnabled(False)
        self.crop_button.setEnabled(False)
        self.restore_button.setEnabled(False)
        self.image_label = QLabel('No captured image yet')
        self.image_label.setObjectName('imagePreview')
        self.image_label.setWordWrap(True)
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_label.setFixedHeight(130)
        review.addWidget(self.image_label)
        self.image_info = QLabel('No image selected')
        self.image_info.setTextFormat(Qt.TextFormat.PlainText)
        self.image_info.setWordWrap(True)
        self.image_info.setObjectName('muted')
        review.addWidget(self.image_info)
        self.context = QPlainTextEdit()
        self.context.setAccessibleName('Notes or code')
        self.context.setPlaceholderText('Optional notes or code…')
        self.context.setFixedHeight(80)
        review.addWidget(self.context)
        self.prepare_button = QPushButton('Prepare reviewed request')
        review.addWidget(self.prepare_button)
        self.preview = QPlainTextEdit()
        self.preview.setReadOnly(True)
        self.preview.setAccessibleName('Prepared text request')
        self.preview.setFixedHeight(130)
        review.addWidget(self.preview)
        self.copy_button = QPushButton('Copy request text')
        self.copy_button.setEnabled(False)
        review.addWidget(self.copy_button)
        self.consent = QCheckBox('Reviewed text + image')
        self.consent.setAccessibleName('I reviewed this text and image for sending')
        review.addWidget(self.consent)
        self.send_button = QPushButton('Send reviewed capture')
        self.send_button.setEnabled(False)
        review.addWidget(self.send_button)
        self.review_pane.hide()
        content.addWidget(self.review_pane)

        footer = QHBoxLayout()
        self.status = QLabel('Connect a model, then Capture & ask.')
        self.status.setWordWrap(True)
        self.status.setTextFormat(Qt.TextFormat.PlainText)
        self.status.setObjectName('muted')
        self.status.setMaximumHeight(44)
        footer.addWidget(self.status,1)
        self.privacy_badge = QLabel('Checking capture…')
        self.capture_state = 'Checking capture…'
        self.privacy_badge.setObjectName('muted')
        footer.addWidget(self.privacy_badge)
        self.voice_button = QPushButton('Voice')
        self.voice_button.setObjectName('ghost')
        self.voice_button.setAccessibleName('Voice question controls')
        footer.addWidget(self.voice_button)
        self.size_grip = QSizeGrip(self)
        self.size_grip.setFixedSize(14,14)
        footer.addWidget(self.size_grip,0,Qt.AlignmentFlag.AlignBottom)
        root.addLayout(footer)
        self.setStyleSheet("""
            QMainWindow, QWidget { background: transparent; color: #e8edf8; font-family: 'Segoe UI', sans-serif; font-size: 13px; }
            QLabel#brand { font-size: 17px; font-weight: 650; }
            QLabel#brandMark { border-radius: 10px; background: qlineargradient(x1:0,y1:0,x2:1,y2:1,stop:0 #b6a0ff,stop:1 #79d6e2); color: #152338; font-size: 17px; font-weight: 800; }
            QLabel#muted { color: #9aaac0; font-size: 11px; }
            QLabel#eyebrow { color: #b0c0d8; font-size: 10px; font-weight: 600; letter-spacing: 2px; }
            QLabel#routeBadge { color: #93e5ce; font-size: 10px; font-weight: 600; background: rgba(90,220,180,18); border: 1px solid rgba(115,231,194,35); border-radius: 9px; padding: 5px 9px; }
            QPlainTextEdit, QLineEdit, QComboBox { background: rgba(12,18,31,115); border: 1px solid rgba(177,199,239,35); border-radius: 11px; padding: 9px; selection-background-color: #625a94; }
            QPlainTextEdit { font-size: 14px; }
            QComboBox { padding: 6px 10px; }
            QComboBox QAbstractItemView { background: #1d263b; color: #e8edf8; selection-background-color: #454d78; }
            QPushButton { background: rgba(165,184,225,14); border: 1px solid rgba(183,202,240,30); border-radius: 9px; padding: 7px 10px; font-weight: 500; }
            QPushButton:hover { background: rgba(178,196,238,35); border-color: rgba(199,216,250,85); }
            QPushButton#primary { background: qlineargradient(x1:0,y1:0,x2:1,y2:1,stop:0 #d0bcff,stop:1 #9ddde9); border: 1px solid #d5d4fc; color: #20263f; font-weight: 700; }
            QPushButton#primary:hover { background: #d3d8ff; }
            QPushButton#ghost { background: transparent; border-color: transparent; color: #aebcd1; padding: 5px 7px; font-size: 11px; }
            QPushButton#ghost:hover { background: rgba(167,187,228,22); color: #eef1ff; }
            QPushButton#windowButton { background: transparent; border: none; padding: 0; font-size: 19px; color: #a8b4cd; }
            QPushButton#windowButton:hover { background: rgba(200,210,240,30); color: white; }
            QPushButton:disabled { color: #66748e; background: rgba(30,40,60,30); border-color: rgba(140,160,200,15); }
            QPlainTextEdit:focus, QLineEdit:focus, QComboBox:focus { border-color: #a6a1dd; }
            QCheckBox::indicator { width: 15px; height: 15px; border: 1px solid #8496b4; border-radius: 4px; background: #1b2437; }
            QCheckBox::indicator:checked { background: #b7b2ef; border: 2px solid #dedcff; }
            QFrame#drawer { border: 1px solid rgba(183,202,240,35); border-radius: 13px; background: rgba(9,15,27,70); padding: 9px; }
            QLabel#imagePreview { background: rgba(9,14,23,100); border: 1px dashed #4b5d79; border-radius: 10px; }
            QScrollBar:vertical { width: 5px; background: transparent; margin: 0; }
            QScrollBar::handle:vertical { background: #526079; border-radius: 2px; min-height: 25px; }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: transparent; }
            QProgressBar { border: none; background: rgba(140,160,210,25); }
            QProgressBar::chunk { background: #b3a7ee; }
        """)
        self.capture_button.clicked.connect(self.capture_and_ask)
        self.review_capture_button.clicked.connect(self.choose_screen)
        self.screen_choice.currentIndexChanged.connect(self.source_changed)
        self.settings_toggle.toggled.connect(self.show_settings)
        self.review_toggle.toggled.connect(self.show_review)
        self.collapse_button.toggled.connect(self.collapse_overlay)
        self.close_button.clicked.connect(self.close)
        self.pin.toggled.connect(self.pin_window)
        self.exclude_capture.toggled.connect(self.update_window_effects)
        self.provider_choice.currentIndexChanged.connect(self.provider_changed)
        self.choose_button.clicked.connect(self.choose_image)
        self.remove_button.clicked.connect(self.remove_image)
        self.crop_button.clicked.connect(self.choose_crop)
        self.restore_button.clicked.connect(self.restore_image)
        self.prepare_button.clicked.connect(self.prepare)
        self.copy_button.clicked.connect(self.copy_text)
        self.copy_answer_button.clicked.connect(self.copy_answer)
        self.clear_button.clicked.connect(self.clear_session)
        self.question.textChanged.connect(self.invalidate)
        self.answer.textChanged.connect(self.update_capsule_status)
        self.context.textChanged.connect(self.material_changed)
        self.mode.currentIndexChanged.connect(self.invalidate)
        self.consent.toggled.connect(self.update_send)
        self.key.textChanged.connect(self.key_changed)
        self.send_button.clicked.connect(self.send_request)
        self.cancel_button.clicked.connect(self.cancel_request)
        self.provider.succeeded.connect(self.receive_answer)
        self.provider.failed.connect(self.receive_error)
        self.followup_button.clicked.connect(self.start_followup)
        self.new_topic_button.clicked.connect(self.new_topic)
        self.save_setup_button.clicked.connect(self.save_setup)
        self.voice_button.clicked.connect(self.open_voice)
        self.speech_browse.clicked.connect(self.choose_speech_model)
        self.speech_record.clicked.connect(self.record_speech)
        self.speech_discard.clicked.connect(self.discard_speech)
        self.ask_speech.clicked.connect(self.ask_transcript)
        self.speech_text.textChanged.connect(self.update_speech_controls)
        self.speech.changed.connect(self.update_speech_controls)
        self.speech.status.connect(self.speech_note.setText)
        self.speech.failed.connect(self.speech_failed)
        self.speech.transcript.connect(self.receive_transcript)
        self.speech.level.connect(self.speech_level.setValue)
        self.provider_changed()
        if preferences is not None:
            saved = preferences.load()
            if saved:
                self.provider_choice.setCurrentIndex(self.provider_choice.findData(saved['provider']))
                self.speech_source.setCurrentIndex(self.speech_source.findData(saved['source']))
                self.speech_model.setText(saved['model'])
                self.pin.blockSignals(True)
                self.pin.setChecked(saved['pin'])
                self.pin.blockSignals(False)
                self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, saved['pin'])
            if preferences.warning:
                self.setup_note.setText(preferences.warning)
        self.status.setText('Connect a model, then Capture & ask.')
        if start_collapsed:
            self.collapse_button.setChecked(True)

    def save_setup(self):
        if self.preferences is None:
            return
        try:
            self.preferences.save(self.provider_choice.currentData(), self.speech_source.currentData(),
                                  self.speech_model.text(), self.pin.isChecked())
        except (OSError, ValueError):
            self.setup_note.setText('Setup could not be saved. Existing saved setup was preserved; session still works.')
        else:
            self.setup_note.setText('Setup saved locally. Keys, questions, images and transcripts were not saved.')

    def showEvent(self, event):
        super().showEvent(event)
        # Window flags (pin/unpin) can recreate the HWND. Reapply on every show.
        self.update_window_effects()
        self.effects_timer.stop()

    def event(self, event):
        if event.type() in (QEvent.Type.WinIdChange, QEvent.Type.DevicePixelRatioChange) and hasattr(self, 'effects_timer'):
            self.effects_timer.start(0)
        return super().event(event)

    def update_window_effects(self):
        if not self.isVisible():
            return
        if QApplication.platformName() == 'windows':
            result = apply_window_effects(int(self.winId()), self.exclude_capture.isChecked())
        else:
            result = WindowEffects(False, False, 'Native glass and capture exclusion unavailable on this Qt platform.')
        self.centralWidget().set_native_material(result.glass)
        self.effects_info.setText(result.detail)
        self.capture_state = ('Capture excluded' if result.excluded else
                              ('Capture visible' if result.capture_confirmed and not self.exclude_capture.isChecked()
                               else 'Capture unconfirmed'))
        self.update_capsule_status()
        self.privacy_badge.setToolTip(result.detail)
        self.collapse_button.setToolTip(result.detail)
        # Always visible, including the collapsed bar; never infer privacy from tint.
        self.drag_bar.setToolTip(result.detail)
        self.settings_toggle.setToolTip(result.detail + ' Open connection and privacy settings.')
        self.exclude_capture.setAccessibleDescription(result.detail)

    def update_capsule_status(self):
        prefix = ''
        if self.collapse_button.isChecked():
            prefix = ('Listening' if self.speech.active else 'Thinking' if self.busy else 'Answer ready · expand' if self.answer.toPlainText() else 'StudyFrame') + ' · '
        self.privacy_badge.setText(prefix + self.capture_state)

    def open_voice(self):
        if self.speech.active:
            self.speech.stop()
            return
        self.collapse_button.setChecked(False)
        self.speech_pane.show()
        QTimer.singleShot(0, self, lambda: self.scroll.ensureWidgetVisible(self.speech_pane))

    def choose_speech_model(self):
        folder = QFileDialog.getExistingDirectory(self, 'Choose extracted trusted Vosk model folder')
        if folder:
            self.speech_model.setText(folder)

    def record_speech(self):
        if self.busy:
            return
        if self.speech.active:
            self.speech.stop()
            return
        self.speech_text.clear()
        self.speech_level.setValue(0)
        self.speech.start(self.speech_source.currentData(), self.speech_model.text())

    def update_speech_controls(self):
        active = self.speech.active
        self.voice_button.setText('Stop audio' if active else 'Voice')
        self.voice_button.setEnabled(not self.busy)
        self.speech_record.setText('Stop' if active else 'Listen')
        self.speech_record.setEnabled(not self.busy)
        for widget in (self.speech_source, self.speech_model, self.speech_browse, self.speech_text):
            widget.setEnabled(not self.busy and not active)
        self.ask_speech.setEnabled(bool(self.speech_text.toPlainText().strip()) and not active and not self.busy)
        self.capture_button.setEnabled(not self.busy and not active)
        self.prepare_button.setEnabled(not self.busy and not active)
        self.update_send()
        self.update_capsule_status()

    def discard_speech(self):
        self.speech.cancel()
        self.speech_text.clear()
        self.speech_level.setValue(0)
        self.speech_note.setText('Local speech session discarded. Nothing was sent.')
        self.update_speech_controls()

    def speech_failed(self, message):
        self.speech_note.setText(message)
        self.update_speech_controls()

    def receive_transcript(self, text):
        self.speech_text.setPlainText(text)
        self.speech_note.setText('Transcript is local. Check and edit it; Ask text only sends this text, never audio or a screenshot.')
        self.update_speech_controls()
        self.open_voice()

    def ask_transcript(self):
        if self.busy or self.speech.active:
            return
        if not self.key.text():
            self.settings_toggle.setChecked(True)
            self.speech_note.setText('Connect the shown model with a session key, then Ask text only.')
            return
        try:
            text = self.speech_text.toPlainText()
            prepared = prepare_request(text, '', self.mode.currentData())
        except RequestError as exc:
            self.speech_note.setText(str(exc))
            return
        self.send_prepared(payload(prepared, None, self.provider_choice.currentData()), text.strip())
        self.speech_pane.hide()

    def refresh_screens(self):
        previous = self.screen_choice.currentData()
        self.screen_choice.blockSignals(True)
        self.screen_choice.clear()
        for index,screen in enumerate(QApplication.screens()):
            try:
                size = screen.geometry()
                self.screen_choice.addItem(f'Display {index+1} · {size.width()} × {size.height()}',screen)
            except RuntimeError:
                continue
        for index in range(self.screen_choice.count()):
            if self.screen_choice.itemData(index) is previous:self.screen_choice.setCurrentIndex(index)
        self.screen_choice.blockSignals(False)

    def update_receipt(self):
        free = self.provider_choice.currentData() == 'openrouter_free'
        self.provider_badge.setText('FREE ROUTE' if free else 'PAID ROUTE')
        provider = 'OpenRouter' if free else 'OpenAI (paid)'
        screen = self.screen_choice.currentText() or 'the selected display'
        self.capture_notice.setText(f'Capture & ask sends {screen} and your question to {provider}. Preview / crop first when needed.')

    def source_changed(self):
        self.material_changed()
        self.update_receipt()

    def key_changed(self):
        if self.busy:self.cancel_request()
        self.consent.setChecked(False)
        self.update_send()

    def show_settings(self, visible):
        if visible:self.collapse_button.setChecked(False)
        self.settings_pane.setVisible(visible)
        if visible:QTimer.singleShot(0,self,self.reveal_connection)

    def reveal_connection(self):
        if self.settings_pane.isVisible() and self.isVisible():
            self.scroll.ensureWidgetVisible(self.key)
            self.key.setFocus()

    def show_review(self, visible):
        if visible:self.collapse_button.setChecked(False)
        self.review_pane.setVisible(visible)
        if visible:QTimer.singleShot(0,self,self.render_image)

    def collapse_overlay(self, collapsed):
        self.brand_name.setVisible(not collapsed)
        self.status.setVisible(not collapsed)
        self.size_grip.setVisible(not collapsed)
        self.centralWidget().compact = collapsed
        self.privacy_badge.setAlignment(Qt.AlignmentFlag.AlignCenter if collapsed else Qt.AlignmentFlag.AlignLeft)
        if collapsed:
            self.expanded_size = self.size()
            self.scroll.hide()
            self.collapse_button.setText('+')
            self.collapse_button.setAccessibleName('Expand answer panel')
            self.root_layout.setContentsMargins(20,14,20,12)
            self.root_layout.setSpacing(6)
            self.setMinimumSize(360,90)
            self.resize(360,90)
        else:
            self.scroll.show()
            self.collapse_button.setText('−')
            self.collapse_button.setAccessibleName('Collapse to capsule')
            self.root_layout.setContentsMargins(25,21,25,18)
            self.root_layout.setSpacing(12)
            self.setMinimumSize(470,110)
            if self.expanded_size is not None:self.resize(self.expanded_size)
        self.update_capsule_status()
        self.update_window_shape()

    def capture_and_ask(self):
        if self.busy or self.speech.active:return
        if not self.key.text():
            self.settings_toggle.setChecked(True)
            self.status.setText('Add your session key in connection settings, then Capture & ask.')
            return
        key = self.key.text()
        if not key.isascii() or any(c.isspace() or ord(c)<32 or ord(c)==127 for c in key):
            self.status.setText('Enter a valid API key in connection settings.')
            return
        screen = self.screen_choice.currentData()
        if screen is None or screen not in QApplication.screens():
            self.refresh_screens()
            self.status.setText('Selected display is unavailable. Review the display selection and click again.')
            return
        question = self.question.toPlainText().strip()
        if not question and self.followup_context is not None:
            self.status.setText('Type a follow-up question before capturing again.')
            return
        question = question or 'Explain what is on this screen.'
        try:
            text = prepare_request(question,self.context.toPlainText(),self.mode.currentData(),previous=self.followup_context)
        except RequestError as exc:
            self.status.setText(str(exc))
            return
        self.settings_toggle.setChecked(False)
        self.review_toggle.setChecked(False)
        self.begin_capture(screen,(text,question,self.provider_choice.currentData(),key))

    def begin_capture(self, screen, direct=None):
        self.direct_request = direct
        self.pending_screen = screen
        self.set_busy(True)
        self.status.setText('Capturing the selected display…' if direct else 'Capturing a local preview only…')
        self.hide()
        self.capture_timer.start(350)

    def provider_changed(self):
        self.key.clear()
        config = provider_config(self.provider_choice.currentData())
        self.key.setPlaceholderText(config['label']+' key - session only')
        self.key.setAccessibleName(config['label']+' API key')
        self.connection_info.setText(config['model']+' · '+config['endpoint'])
        self.disclosure.setText(
            'OpenRouter and a selected upstream model receive the reviewed text/image. '
            'Only the free router is allowed, with zero-price caps and no paid fallback. '
            'Providers disallowing data collection are requested; this is not a zero-retention guarantee. '
            'Availability and limits vary. A follow-up includes the displayed previous exchange.'
            if self.provider_choice.currentData() == 'openrouter_free' else
            'OpenAI receives the reviewed text/image, including a displayed previous exchange for follow-ups. '
            'This route is paid. store=false is not a zero-retention guarantee.')
        self.material_changed()
        self.update_receipt()

    def pin_window(self, checked):
        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, checked)
        if self.pending_screen is None:self.show()

    def choose_screen(self):
        if self.busy:return
        screens = QApplication.screens()
        if not screens:
            self.status.setText('No display is available for capture.')
            return
        try:
            labels = [f'{i+1} · {screen.name()} · {screen.geometry().width()} × {screen.geometry().height()} logical pixels'
                      for i,screen in enumerate(screens)]
        except RuntimeError:
            self.status.setText('Displays changed. Choose a screen again.')
            return
        choice,accepted = QInputDialog.getItem(self,'Capture one display','Choose a display. The app briefly hides; capture stays local.',labels,0,False)
        if not accepted or choice not in labels:return
        self.begin_capture(screens[labels.index(choice)])

    def complete_capture(self):
        screen = self.pending_screen
        if screen is None:return
        direct = self.direct_request
        self.pending_screen = None
        self.direct_request = None
        self.capture_timer.stop()
        try:
            selected = capture_screen(screen)
        except ImageError as exc:
            self.set_busy(False)
            self.consent.setChecked(False)
            self.status.setText(str(exc)+' Previous selection kept; nothing sent.')
            self.show()
            return
        self.set_busy(False)
        self.attachment = selected
        self.original_attachment = selected
        self.image_name = 'Display capture '+datetime.now().astimezone().isoformat(timespec='seconds')
        self.material_changed()
        self.update_image_info()
        self.render_image()
        self.show()
        if direct is None:
            if not self.question.toPlainText().strip():self.question.setPlainText('Explain what is on this screen.')
            self.review_toggle.setChecked(True)
            self.status.setText('Captured locally. Crop or prepare a reviewed request; nothing sent.')
            return
        text,question,provider,key = direct
        if provider != self.provider_choice.currentData() or key != self.key.text():
            self.status.setText('Connection changed. Nothing sent; capture again.')
            return
        self.preview.setPlainText(text)
        self.copy_button.setEnabled(True)
        self.send_prepared(payload(text,selected,provider),question)

    def material_changed(self):
        self.followup_context = None
        self.followup_note.setText("New question. No previous exchange will be sent.")
        self.invalidate()

    def new_topic(self):
        self.material_changed()
        self.question.clear()
        self.review_toggle.setChecked(False)
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
        self.review_toggle.setChecked(False)
        self.question.setFocus()

    def update_send(self):
        self.send_button.setEnabled(bool(self.preview.toPlainText()) and bool(self.key.text())
                                    and self.consent.isChecked() and not self.busy and not self.speech.active)

    def set_busy(self, busy):
        self.busy = busy
        self.update_capsule_status()
        for widget in (self.question, self.context, self.mode, self.choose_button,
                       self.prepare_button, self.key, self.consent, self.capture_button, self.provider_choice, self.pin):
            widget.setEnabled(not busy)
        self.remove_button.setEnabled(not busy and self.attachment is not None)
        self.crop_button.setEnabled(not busy and self.attachment is not None)
        self.restore_button.setEnabled(not busy and self.original_attachment is not None
                                       and self.attachment is not self.original_attachment)
        for widget in (self.screen_choice,self.review_capture_button,self.settings_toggle,self.review_toggle):widget.setEnabled(not busy)
        self.progress.setVisible(busy)
        self.cancel_button.setEnabled(busy)
        self.followup_button.setEnabled(not busy and self.last_exchange is not None)
        self.update_send()
        self.update_speech_controls()

    def send_request(self):
        if not self.send_button.isEnabled():
            return
        body = payload(self.preview.toPlainText(),self.attachment,self.provider_choice.currentData())
        self.send_prepared(body,self.question.toPlainText().strip())

    def send_prepared(self, body, question):
        if self.speech.active:
            return
        self.answer.clear()
        self.copy_answer_button.setEnabled(False)
        self.sent_question = question
        self.set_busy(True)
        self.status.setText('Thinking · '+PROVIDERS[self.provider_choice.currentData()]['label'])
        try:
            self.provider.send(body,self.key.text(),self.provider_choice.currentData())
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
        self.followup_note.setText("Select Follow up to include this last exchange in your next question.")
        self.followup_button.setEnabled(True)
        self.copy_answer_button.setEnabled(True)
        self.review_toggle.setChecked(False)
        self.answer.setFocus()
        self.status.setText("AI answer received. Model: "+(getattr(self.provider,"model_used","") or "not reported")+". Verify its reasoning with a small example.")

    def receive_error(self, message):
        if not self.busy:
            return
        self.set_busy(False)
        self.consent.setChecked(False)
        self.status.setText(message)

    def cancel_request(self):
        self.direct_request = None
        if self.pending_screen is not None:
            self.capture_timer.stop()
            self.pending_screen = None
            self.show()
            self.cancel_button.setText('Cancel request')
        self.provider.cancel()
        self.set_busy(False)
        self.consent.setChecked(False)
        self.status.setText("Cancelled locally. A provider may still process what was already sent; cancellation does not reverse charges.")

    def closeEvent(self, event):
        self.save_setup()
        self.speech.cancel()
        self.effects_timer.stop()
        self.direct_request = None
        self.capture_timer.stop()
        self.pending_screen = None
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
        self.update_window_shape()
        if hasattr(self, 'effects_timer'):
            self.effects_timer.start(0)
        if hasattr(self, "image_label"):
            self.render_image()

    def update_window_shape(self):
        if QApplication.platformName() == 'windows' and hasattr(self, 'collapse_button'):
            path = QPainterPath()
            radius = self.height()/2 if self.collapse_button.isChecked() else 28
            path.addRoundedRect(QRectF(self.rect()), radius, radius)
            self.setMask(QRegion(path.toFillPolygon().toPolygon()))

    def remove_image(self):
        self.attachment = None
        self.original_attachment = None
        self.image_name = ""
        self.image_label.clear()
        self.image_label.setText("Capture a display or load a saved image. No background watching.")
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
        self.collapse_button.setChecked(False)
        self.review_toggle.setChecked(True)
        QTimer.singleShot(0,self,lambda:self.scroll.ensureWidgetVisible(self.preview) if self.review_pane.isVisible() else None)
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
        self.discard_speech()
        self.cancel_request()
        self.sent_question = ""
        self.key.clear()
        self.question.clear()
        self.context.clear()
        self.mode.setCurrentIndex(0)
        self.remove_image()
        self.review_toggle.setChecked(False)
        self.status.setText("Session cleared. Your original image file and clipboard are unchanged.")


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("StudyFrame")
    window = StudyWindow(start_collapsed=True, preferences=Preferences.default())
    window.show()
    return app.exec()
