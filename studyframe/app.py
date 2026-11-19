"""Local study workspace. Explicit display capture and reviewed vision help; no background watching."""

import sys
from pathlib import Path
from datetime import datetime
from studyframe import __version__

from PySide6.QtCore import Qt, QTimer, QElapsedTimer, QEvent, QRectF, QUrl
from PySide6.QtGui import QPixmap, QPainterPath, QRegion, QDesktopServices
from PySide6.QtWidgets import (
    QApplication, QComboBox, QFileDialog, QHBoxLayout, QLabel, QMainWindow,
    QPlainTextEdit, QPushButton, QScrollArea, QVBoxLayout, QWidget, QLineEdit, QCheckBox, QDialog, QInputDialog, QFrame, QSizeGrip, QProgressBar, QMessageBox,
)

from studyframe.images import ImageError, LoadedImage, load_image, crop_image
from studyframe.crop import CropDialog
from studyframe.requests import RequestError, prepare_request
from studyframe.provider import StudyProvider, payload, PROVIDERS, provider_config
from studyframe.capture import capture_screen
from studyframe.glass import GlassPanel, DragBar
from studyframe.windows_effects import apply_window_effects, WindowEffects, FALLBACK_MATERIAL
from studyframe.backdrop import create_backdrop
from studyframe.speech import SpeechSession
from studyframe.preferences import Preferences
from studyframe.launcher import default_model


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
        self.native_backdrop = None
        self.backdrop_attempted = False
        self.screen_handle = None
        self.request_failed = False
        self.request_clock = QElapsedTimer()
        self.first_text_ms = None
        self.partial_answer = False
        self.wait_timer = QTimer(self)
        self.wait_timer.setInterval(1000)
        self.wait_timer.timeout.connect(self.update_wait_feedback)
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
        self.voice_button = QPushButton('Voice')
        self.voice_button.setAccessibleName('Voice question controls')
        self.voice_button.setToolTip('Prepare local microphone or computer-audio transcription')
        title.addWidget(self.voice_button)
        self.capture_button = QPushButton('Capture && ask')
        self.capture_button.setAccessibleName('Capture & ask')
        self.capture_button.setObjectName('primary')
        self.capture_button.setShortcut('Ctrl+Return')
        self.capture_button.setToolTip('Capture the selected display and send its fresh pixels to the selected model. Ctrl+Enter while focused.')
        title.addWidget(self.capture_button)
        self.top_cancel = QPushButton('Cancel request')
        self.top_cancel.setAccessibleName('Cancel request without scrolling')
        self.top_cancel.hide()
        title.addWidget(self.top_cancel)
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
        self.feedback = QLabel()
        self.feedback.setObjectName('requestFeedback')
        self.feedback.setTextFormat(Qt.TextFormat.PlainText)
        self.feedback.setWordWrap(True)
        self.feedback.hide()
        root.addWidget(self.feedback)

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
        self.provider_badge = QPushButton('Connect · free')
        self.provider_badge.setObjectName('routeBadge')
        self.provider_badge.setAccessibleName('Open model connection settings')
        self.provider_badge.setToolTip('Enter a session key. Entering a key does not send a test request.')
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
        for label,value in [('Quick answer','quick'),('Explain','explain'),('Hint','hint'),('Debug','debug')]:self.mode.addItem(label,value)
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
        self.answer.setPlaceholderText('Your answer appears here as it arrives.\n\nCapture a screen or ask with a reviewed voice transcript.')
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
        self.speech_device = QComboBox()
        self.speech_device.setAccessibleName('Exact audio device')
        self.speech_device.addItem('Windows default device',None)
        self.speech_device.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        self.speech_device.setMinimumContentsLength(10)
        voice.addWidget(self.speech_device)
        self.speech_model = QLineEdit(str(default_model()))
        self.speech_model.setAccessibleName('Local Vosk model folder')
        self.speech_model.setPlaceholderText('Choose an extracted Vosk model folder')
        voice.addWidget(self.speech_model)
        actions = QHBoxLayout()
        self.speech_browse = QPushButton('Model folder…')
        self.speech_prepare = QPushButton('Prepare audio')
        self.speech_record = QPushButton('Listen')
        self.speech_record.setEnabled(False)
        self.speech_discard = QPushButton('Discard')
        for button in (self.speech_browse, self.speech_prepare, self.speech_record, self.speech_discard): actions.addWidget(button)
        voice.addLayout(actions)
        self.speech_level = QProgressBar()
        self.speech_level.setRange(0,100)
        self.speech_level.setValue(0)
        self.speech_level.setTextVisible(False)
        self.speech_level.setAccessibleName('Selected audio source signal level')
        self.speech_level.setToolTip('Live signal level for the selected source. A flat meter can indicate muted or missing audio.')
        self.speech_level.setFixedHeight(5)
        voice.addWidget(self.speech_level)
        self.speech_note = QLabel('Prepare audio loads the local model without recording. When Ready, click Listen '
                                  'and speak only after Listening now appears. Clips last up to 30 seconds. '
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
        settings.addWidget(QLabel(f'MODEL CONNECTION · StudyFrame {__version__}'))
        self.provider_choice = QComboBox()
        self.provider_choice.setAccessibleName('AI provider')
        for identifier in ('openrouter_free','openai'):self.provider_choice.addItem(PROVIDERS[identifier]['label'],identifier)
        settings.addWidget(self.provider_choice)
        self.connection_info = QLabel()
        self.connection_info.setWordWrap(True)
        self.connection_info.setTextFormat(Qt.TextFormat.PlainText)
        self.connection_info.setObjectName('muted')
        settings.addWidget(self.connection_info)
        self.key_help = QPushButton('Get your own key in browser')
        self.key_help.setToolTip('Opens the selected provider’s official key page. No account linking or test request.')
        settings.addWidget(self.key_help)
        self.key = QLineEdit()
        self.key.setEchoMode(QLineEdit.EchoMode.Password)
        settings.addWidget(self.key)
        self.connection_done = QPushButton('Use this session key')
        self.connection_done.setEnabled(False)
        settings.addWidget(self.connection_done)
        self.quota_button = QPushButton('Check free usage · no model request')
        self.quota_button.setEnabled(False)
        settings.addWidget(self.quota_button)
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
        # Connection is a first-use task, not a drawer below a full answer panel.
        content.insertWidget(0, self.settings_pane)

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
        self.status = QLabel('Connect a model, then Capture & ask.', panel)
        self.status.setWordWrap(True)
        self.status.setTextFormat(Qt.TextFormat.PlainText)
        self.status.setObjectName('muted')
        # One prominent feedback banner; do not repeat long errors in the footer.
        self.status.hide()
        self.privacy_badge = QLabel('Checking capture…')
        self.capture_state = 'Checking capture…'
        self.privacy_badge.setObjectName('muted')
        footer.addWidget(self.privacy_badge)
        self.size_grip = QSizeGrip(self)
        self.size_grip.setFixedSize(14,14)
        footer.addWidget(self.size_grip,0,Qt.AlignmentFlag.AlignBottom)
        root.addLayout(footer)
        self.setStyleSheet("""
            QMainWindow, QWidget { background: transparent; color: #e8edf8; font-family: 'Segoe UI', sans-serif; font-size: 13px; }
            QLabel#brand { font-size: 17px; font-weight: 650; }
            QLabel#brandMark { border-radius: 10px; background: qlineargradient(x1:0,y1:0,x2:1,y2:1,stop:0 #b6a0ff,stop:1 #79d6e2); color: #152338; font-size: 17px; font-weight: 800; }
            QLabel#muted { color: #d0dcf0; font-size: 12px; }
            QLabel#eyebrow { color: #d0dcf0; font-size: 11px; font-weight: 600; letter-spacing: 2px; }
            QLabel#requestFeedback { color: #edf2ff; background: rgba(18,27,45,115); border: 1px solid rgba(190,213,246,45); border-radius: 9px; padding: 8px; font-size: 12px; }
            QPushButton#routeBadge { color: #93e5ce; font-size: 11px; font-weight: 600; background: rgba(90,220,180,18); border: 1px solid rgba(115,231,194,35); border-radius: 9px; padding: 5px 9px; }
            QPlainTextEdit, QLineEdit, QComboBox { background: rgba(12,18,31,125); color: #f0f4fc; placeholder-text-color: #d0dcf0; border: 1px solid rgba(177,199,239,40); border-radius: 11px; padding: 9px; selection-background-color: #625a94; }
            QPlainTextEdit { font-size: 14px; }
            QComboBox { padding: 6px 10px; }
            QComboBox QAbstractItemView { background: #1d263b; color: #e8edf8; selection-background-color: #454d78; }
            QPushButton { background: rgba(165,184,225,14); border: 1px solid rgba(183,202,240,30); border-radius: 9px; padding: 7px 10px; font-weight: 500; }
            QPushButton:hover { background: rgba(178,196,238,35); border-color: rgba(199,216,250,85); }
            QPushButton#primary { background: qlineargradient(x1:0,y1:0,x2:1,y2:1,stop:0 #d0bcff,stop:1 #9ddde9); border: 1px solid #d5d4fc; color: #20263f; font-weight: 700; }
            QPushButton#primary:hover { background: #d3d8ff; }
            QPushButton#ghost { background: transparent; border-color: transparent; color: #c5d1e6; padding: 5px 7px; font-size: 12px; }
            QPushButton#ghost:hover { background: rgba(167,187,228,22); color: #eef1ff; }
            QPushButton#windowButton { background: transparent; border: none; padding: 0; font-size: 19px; color: #d0d9ec; }
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
        self.top_cancel.clicked.connect(self.cancel_request)
        self.review_capture_button.clicked.connect(self.choose_screen)
        self.screen_choice.currentIndexChanged.connect(self.source_changed)
        self.settings_toggle.toggled.connect(self.show_settings)
        self.provider_badge.clicked.connect(lambda: self.settings_toggle.setChecked(True))
        self.connection_done.clicked.connect(self.finish_connection)
        self.quota_button.clicked.connect(self.check_free_usage)
        self.key_help.clicked.connect(self.open_key_help)
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
        self.provider.quota_received.connect(self.receive_quota)
        if hasattr(self.provider,'partial'):self.provider.partial.connect(self.receive_partial)
        self.followup_button.clicked.connect(self.start_followup)
        self.new_topic_button.clicked.connect(self.new_topic)
        self.save_setup_button.clicked.connect(self.save_setup)
        self.voice_button.clicked.connect(self.open_voice)
        self.speech_browse.clicked.connect(self.choose_speech_model)
        self.speech_record.clicked.connect(self.record_speech)
        self.speech_prepare.clicked.connect(self.prepare_speech)
        self.speech_source.currentIndexChanged.connect(self.audio_setup_changed)
        self.speech_model.textChanged.connect(self.audio_setup_changed)
        self.speech_discard.clicked.connect(self.discard_speech)
        self.ask_speech.clicked.connect(self.ask_transcript)
        self.speech_text.textChanged.connect(self.update_speech_controls)
        self.speech.changed.connect(self.update_speech_controls)
        self.speech.status.connect(self.speech_note.setText)
        self.speech.failed.connect(self.speech_failed)
        self.speech.transcript.connect(self.receive_transcript)
        self.speech.level.connect(self.speech_level.setValue)
        self.speech.devices.connect(self.receive_devices)
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
        QApplication.instance().screenAdded.connect(self.display_changed)
        QApplication.instance().screenRemoved.connect(self.display_changed)

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

    def update_connection(self):
        key = self.key.text()
        valid = bool(key) and key.isascii() and not any(c.isspace() or ord(c)<32 or ord(c)==127 for c in key)
        self.connection_done.setEnabled(valid and not self.busy)
        self.quota_button.setEnabled(valid and not self.busy and not self.speech.active and self.provider_choice.currentData()=='openrouter_free')
        self.capture_button.setText('Capture && ask' if valid else 'Connect model')
        self.provider_badge.setText(('Key entered' if valid else 'Connect') +
                                    (' · free' if self.provider_choice.currentData() == 'openrouter_free' else ' · paid'))

    def finish_connection(self):
        if not self.connection_done.isEnabled():
            return
        self.settings_toggle.setChecked(False)
        self.show_feedback('Session key ready. No test request sent. Capture a screen or open Voice to ask text only.')
        self.question.setFocus()

    def open_key_help(self):
        url = ('https://openrouter.ai/settings/keys' if self.provider_choice.currentData()=='openrouter_free'
               else 'https://platform.openai.com/api-keys')
        QDesktopServices.openUrl(QUrl(url))

    def check_free_usage(self):
        if self.busy or self.speech.active or not self.quota_button.isEnabled():return
        self.set_busy(True)
        self.show_feedback('Checking OpenRouter usage metadata only. No question, image, audio or model request is sent.')
        try:
            self.provider.check_quota(self.key.text())
            self.update_capsule_status()
        except ValueError as exc:self.receive_error(str(exc))

    def receive_quota(self, text):
        if not self.busy:return
        self.set_busy(False)
        self.show_feedback(text)

    def showEvent(self, event):
        super().showEvent(event)
        handle = self.windowHandle()
        if handle is not None and handle is not self.screen_handle:
            self.screen_handle = handle
            handle.screenChanged.connect(self.display_changed)
        self.fit_to_screen()
        # Window flags (pin/unpin) can recreate the HWND. Reapply on every show.
        self.update_window_effects()
        self.effects_timer.stop()

    def fit_to_screen(self):
        screen = self.screen() or QApplication.primaryScreen()
        if screen is None:
            return
        area = screen.availableGeometry().adjusted(8, 8, -8, -8)
        if not area.isValid():
            return
        self.resize(min(self.width(), area.width()), min(self.height(), area.height()))
        self.move(max(area.left(), min(self.x(), area.right()-self.width()+1)),
                  max(area.top(), min(self.y(), area.bottom()-self.height()+1)))

    def display_changed(self, *args):
        if self.pending_screen is not None and self.pending_screen not in QApplication.screens():
            self.cancel_request()
            self.status.setText('The selected display disconnected. Choose a display before capturing again.')
        self.refresh_screens()
        self.update_receipt()
        if self.isVisible():
            self.fit_to_screen()

    def event(self, event):
        if event.type() in (QEvent.Type.WinIdChange, QEvent.Type.DevicePixelRatioChange,
                            QEvent.Type.WindowStateChange, QEvent.Type.ActivationChange,
                            QEvent.Type.ZOrderChange) and hasattr(self, 'effects_timer'):
            self.effects_timer.start(0)
        return super().event(event)

    def hideEvent(self, event):
        if self.native_backdrop is not None:
            self.native_backdrop.hide()
        super().hideEvent(event)

    def moveEvent(self, event):
        super().moveEvent(event)
        if getattr(self, 'native_backdrop', None) is not None:
            self.sync_backdrop()

    def sync_backdrop(self):
        try:
            self.native_backdrop.sync()
        except (OSError, RuntimeError):
            self.native_backdrop.close()
            self.native_backdrop = None
            self.effects_timer.start(0)

    def update_window_effects(self):
        if not self.isVisible():
            return
        if QApplication.platformName() == 'windows':
            result = apply_window_effects(int(self.winId()), self.exclude_capture.isChecked())
        else:
            result = WindowEffects(False, False, 'Native glass and capture exclusion unavailable on this Qt platform.')
        try:
            if not self.backdrop_attempted:
                self.backdrop_attempted = True
                self.native_backdrop = create_backdrop(self)
            if self.native_backdrop is not None:
                self.native_backdrop.configure(self.exclude_capture.isChecked())
                result = WindowEffects(True, result.excluded,
                                       'Rounded Windows host-backdrop frost; appearance follows system transparency settings. '
                                       + result.detail.removeprefix(FALLBACK_MATERIAL).lstrip(), result.capture_confirmed)
        except (ImportError, OSError, RuntimeError, AttributeError):
            if self.native_backdrop is not None:
                self.native_backdrop.close()
                self.native_backdrop = None
            result = WindowEffects(False, result.excluded,
                                   result.detail + ' Compositor backdrop unavailable; rounded Qt fallback active.',
                                   result.capture_confirmed)
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
            phase = getattr(self.speech, 'phase', '')
            audio = {'preparing':'Preparing audio', 'starting':'Starting audio', 'listening':'Listening now',
                     'stopping':'Finishing audio'}.get(phase, 'Audio active')
            working='Checking usage' if getattr(self.provider,'mode','answer')=='quota' else 'Thinking'
            prefix = (audio if self.speech.active else working if self.busy else 'Request failed · expand' if self.request_failed else 'Answer ready · expand' if self.answer.toPlainText() else 'StudyFrame') + ' · '
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

    def audio_setup_changed(self):
        self.speech.cancel()
        self.speech_device.clear()
        self.speech_device.addItem('Windows default device',None)
        self.speech_note.setText('Audio setup changed. Prepare audio before Listen; no recording started.')
        self.update_speech_controls()

    def receive_devices(self, options):
        self.speech_device.clear()
        self.speech_device.addItem('Windows default device',None)
        for device in options:
            self.speech_device.addItem(device['name'],device['id'])

    def prepare_speech(self):
        if self.busy or self.speech.active:
            return
        self.speech.prepare(self.speech_source.currentData(), self.speech_model.text())

    def record_speech(self):
        if self.busy:
            return
        if self.speech.active:
            self.speech.stop()
            return
        self.speech_text.clear()
        self.speech_level.setValue(0)
        self.speech.listen(self.speech_device.currentData())

    def update_speech_controls(self):
        active = self.speech.active
        preparing = getattr(self.speech, 'phase', '') == 'preparing'
        self.voice_button.setText('Cancel setup' if preparing else 'Stop audio' if active else 'Voice')
        self.voice_button.setEnabled(not self.busy)
        self.speech_record.setText('Stop' if active and not preparing else 'Listen')
        self.speech_record.setEnabled(not self.busy and (active and not preparing or getattr(self.speech, 'prepared', False)))
        self.speech_prepare.setEnabled(not self.busy and not active)
        for widget in (self.speech_source, self.speech_device, self.speech_model, self.speech_browse, self.speech_text):
            widget.setEnabled(not self.busy and not active)
        self.ask_speech.setEnabled(bool(self.speech_text.toPlainText().strip()) and not active and not self.busy)
        self.capture_button.setEnabled(not self.busy and not active)
        self.prepare_button.setEnabled(not self.busy and not active)
        self.update_send()
        self.update_connection()
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
        self.update_connection()
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
        self.update_connection()

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
        if visible:QTimer.singleShot(0,self,self.reveal_preview)

    def reveal_preview(self):
        if self.review_pane.isVisible():
            self.render_image()
            self.scroll.ensureWidgetVisible(self.image_label)

    def show_feedback(self, message, *, failed=False):
        self.request_failed = failed
        self.feedback.setText(message)
        self.feedback.setVisible(not self.collapse_button.isChecked())
        self.status.setText(message)
        self.update_capsule_status()

    def reveal_answer(self):
        self.collapse_button.setChecked(False)
        self.settings_toggle.setChecked(False)
        self.review_toggle.setChecked(False)
        self.speech_pane.hide()
        QTimer.singleShot(0,self,lambda:self.scroll.ensureWidgetVisible(self.answer) if self.isVisible() else None)

    def collapse_overlay(self, collapsed):
        self.brand_name.setVisible(not collapsed and self.width()>=580)
        self.status.hide()
        self.size_grip.setVisible(not collapsed)
        self.feedback.setVisible(not collapsed and bool(self.feedback.text()))
        self.centralWidget().compact = collapsed
        self.privacy_badge.setAlignment(Qt.AlignmentFlag.AlignCenter if collapsed else Qt.AlignmentFlag.AlignLeft)
        if collapsed:
            self.expanded_size = self.size()
            self.scroll.hide()
            self.collapse_button.setText('+')
            self.collapse_button.setAccessibleName('Expand answer panel')
            self.root_layout.setContentsMargins(20,14,20,12)
            self.root_layout.setSpacing(6)
            self.setMinimumSize(420,90)
            self.resize(420,90)
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
        if self.isVisible():
            self.fit_to_screen()

    def capture_and_ask(self):
        if self.busy or self.speech.active:return
        if not self.key.text():
            self.settings_toggle.setChecked(True)
            self.show_feedback('Add your session key in connection settings, then Capture & ask. Nothing captured or sent.')
            return
        key = self.key.text()
        if not key.isascii() or any(c.isspace() or ord(c)<32 or ord(c)==127 for c in key):
            self.settings_toggle.setChecked(True)
            self.show_feedback('The key contains spaces or unsupported characters. Correct the masked key field. Nothing captured or sent.')
            return
        screen = self.screen_choice.currentData()
        if screen is None or screen not in QApplication.screens():
            self.refresh_screens()
            self.collapse_button.setChecked(False)
            self.show_feedback('Selected display is unavailable. Review the display selection and click again.')
            return
        question = self.question.toPlainText().strip()
        if not question and self.followup_context is not None:
            self.collapse_button.setChecked(False)
            self.show_feedback('Type a follow-up question before capturing again.')
            return
        question = question or 'Explain what is on this screen.'
        try:
            text = prepare_request(question,self.context.toPlainText(),self.mode.currentData(),previous=self.followup_context)
        except RequestError as exc:
            self.collapse_button.setChecked(False)
            self.show_feedback(str(exc))
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
        self.connection_info.setText(config['model']+' · '+config['endpoint']+'\nThe entered key is used by explicit requests. This button closes setup; it does not authenticate or send a test.')
        self.disclosure.setText(
            'OpenRouter and a selected upstream model receive the reviewed text/image. '
            'Only the free router is allowed, with zero-price caps and no paid fallback. '
            'OpenRouter may try another eligible free provider; the app does not resubmit automatically. '
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
            self.show()
            self.reveal_answer()
            self.show_feedback(str(exc)+' Previous selection kept; nothing sent.',failed=True)
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
        if not busy:self.wait_timer.stop()
        self.capture_button.setVisible(not busy)
        self.top_cancel.setVisible(busy)
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

        self.update_connection()

    def send_request(self):
        if not self.send_button.isEnabled():
            return
        body = payload(self.preview.toPlainText(),self.attachment,self.provider_choice.currentData())
        self.send_prepared(body,self.question.toPlainText().strip())

    def send_prepared(self, body, question):
        if self.speech.active:
            return
        self.answer.clear()
        self.reveal_answer()
        self.copy_answer_button.setEnabled(False)
        self.last_exchange = None
        self.partial_answer = False
        self.first_text_ms = None
        self.request_clock.start()
        self.sent_question = question
        self.set_busy(True)
        self.update_wait_feedback()
        self.wait_timer.start()
        try:
            self.provider.send(body,self.key.text(),self.provider_choice.currentData())
        except ValueError as exc:
            self.receive_error(str(exc))

    def update_wait_feedback(self):
        if not self.busy:return
        seconds=self.request_clock.elapsed()/1000
        state='Receiving answer' if self.partial_answer else 'Waiting for first text'
        self.show_feedback(f'{state} · {seconds:.0f}s · Cancel above. Free-provider queues can vary.')

    def receive_partial(self, text):
        if not self.busy:return
        if self.first_text_ms is None:self.first_text_ms=self.request_clock.elapsed()
        self.partial_answer=True
        cursor=self.answer.textCursor()
        cursor.movePosition(cursor.MoveOperation.End)
        cursor.insertText(text)
        self.update_wait_feedback()

    def receive_answer(self, text):
        if not self.busy:
            return
        self.set_busy(False)
        self.consent.setChecked(False)
        self.answer.setPlainText(text)
        self.partial_answer=False
        self.reveal_answer()
        self.last_exchange = (self.sent_question, text)
        self.followup_context = None
        self.followup_note.setText("Select Follow up to include this last exchange in your next question.")
        self.followup_button.setEnabled(True)
        self.copy_answer_button.setEnabled(True)
        self.review_toggle.setChecked(False)
        self.answer.setFocus()
        timing=f'{self.request_clock.elapsed()/1000:.1f}s total' if self.request_clock.isValid() else ''
        if self.first_text_ms is not None:timing+=f' · first text {self.first_text_ms/1000:.1f}s'
        self.show_feedback('Answer received · '+timing+' · Model: '+(getattr(self.provider,'model_used','') or 'not reported'))

    def receive_error(self, message):
        if not self.busy:
            return
        self.set_busy(False)
        self.consent.setChecked(False)
        if getattr(self.provider,'mode','answer')=='answer':self.reveal_answer()
        if self.partial_answer and getattr(self.provider,'mode','answer')=='answer':message='Partial answer — not completed. '+message
        self.show_feedback(message,failed=True)

    def cancel_request(self):
        checking_usage=self.busy and getattr(self.provider,'mode','answer')=='quota'
        self.direct_request = None
        if self.pending_screen is not None:
            self.capture_timer.stop()
            self.pending_screen = None
            self.show()
            self.cancel_button.setText('Cancel request')
        self.provider.cancel()
        self.set_busy(False)
        self.consent.setChecked(False)
        self.show_feedback('Usage check cancelled. No model request was made.' if checking_usage else
                           ('Partial answer — cancelled locally. ' if self.partial_answer else 'Cancelled locally. ')+
                           'A provider may still process what was already sent; cancellation does not reverse charges.')

    def closeEvent(self, event):
        self.save_setup()
        self.speech.cancel()
        self.effects_timer.stop()
        if self.native_backdrop is not None:
            self.native_backdrop.close()
            self.native_backdrop = None
        self.backdrop_attempted = False
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
        self.request_failed = False
        self.feedback.clear()
        self.feedback.hide()
        self.update_capsule_status()
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
        if hasattr(self,'collapse_button'):
            self.brand_name.setVisible(not self.collapse_button.isChecked() and self.width()>=580)
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
    from studyframe.launcher import hold_install_mutex
    try:
        hold_install_mutex()
    except OSError:
        QMessageBox.critical(None, 'StudyFrame could not start',
                             'The application session could not be reserved safely. Close older StudyFrame instances and retry.')
        return 1
    window = StudyWindow(start_collapsed=True, preferences=Preferences.default())
    window.show()
    return app.exec()
