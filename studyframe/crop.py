"""Select an area of an already-loaded image; no screen capture or file writes."""
import math

from PySide6.QtCore import QPointF, QRect, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import (
    QDialog, QDialogButtonBox, QHBoxLayout, QLabel, QSpinBox,
    QVBoxLayout, QWidget,
)


class CropCanvas(QWidget):
    selectionChanged = Signal(QRect)

    def __init__(self, image, parent=None):
        super().__init__(parent)
        self.image = image
        self.selection = QRect()
        self.anchor = None
        self.setMinimumSize(320, 200)
        self.setAccessibleName("Crop image: drag to select an area, or use the pixel controls below")
        self.setCursor(Qt.CursorShape.CrossCursor)

    def image_rect(self):
        scale = min((self.width() - 16) / self.image.width(), (self.height() - 16) / self.image.height())
        width, height = self.image.width() * scale, self.image.height() * scale
        return QRectF((self.width() - width) / 2, (self.height() - height) / 2, width, height)

    def set_selection(self, rect):
        self.selection = rect
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor("#102437"))
        area = self.image_rect()
        painter.drawImage(area, self.image)
        if not self.selection.isEmpty():
            scale = area.width() / self.image.width()
            selected = QRectF(area.x() + self.selection.x() * scale,
                              area.y() + self.selection.y() * scale,
                              self.selection.width() * scale, self.selection.height() * scale)
            painter.setPen(QPen(QColor("#00e5ff"), 2))
            painter.fillRect(selected, QColor(0, 229, 255, 40))
            painter.drawRect(selected)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self.image_rect().contains(event.position()):
            self.anchor = event.position()

    def mouseMoveEvent(self, event):
        if self.anchor is not None:
            self.drag_to(event.position())

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self.anchor is not None:
            self.drag_to(event.position())
            self.anchor = None

    def resizeEvent(self, event):
        self.anchor = None  # A resize must not reinterpret an in-progress drag.
        super().resizeEvent(event)

    def drag_to(self, point):
        area = self.image_rect()
        start = QPointF(max(area.left(), min(self.anchor.x(), area.right())),
                        max(area.top(), min(self.anchor.y(), area.bottom())))
        end = QPointF(max(area.left(), min(point.x(), area.right())),
                      max(area.top(), min(point.y(), area.bottom())))
        scale = self.image.width() / area.width()
        x0 = max(0, math.floor((min(start.x(), end.x()) - area.x()) * scale))
        y0 = max(0, math.floor((min(start.y(), end.y()) - area.y()) * scale))
        x1 = min(self.image.width(), math.ceil((max(start.x(), end.x()) - area.x()) * scale))
        y1 = min(self.image.height(), math.ceil((max(start.y(), end.y()) - area.y()) * scale))
        rect = QRect(x0, y0, x1 - x0, y1 - y0)
        self.set_selection(rect)
        self.selectionChanged.emit(rect)


class CropDialog(QDialog):
    def __init__(self, image, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Focus your screenshot — StudyFrame")
        self.resize(850, 620)
        layout = QVBoxLayout(self)
        note = QLabel("Drag around the code, question or diagram you want to study. "
                      "Only the selected pixels will replace the image for sending. "
                      "This edits a saved image locally; nothing is captured or sent.")
        note.setWordWrap(True)
        layout.addWidget(note)
        self.canvas = CropCanvas(image)
        layout.addWidget(self.canvas, 1)
        controls = QHBoxLayout()
        self.fields = []
        for label, maximum, initial in (("Left", image.width() - 1, 0), ("Top", image.height() - 1, 0),
                                         ("Width", image.width(), image.width()), ("Height", image.height(), image.height())):
            controls.addWidget(QLabel(label))
            spin = QSpinBox()
            spin.setAccessibleName(f"Crop {label.lower()} in pixels")
            spin.setRange(0 if label in ("Left", "Top") else 1, maximum)
            spin.setValue(initial)
            controls.addWidget(spin)
            self.fields.append(spin)
            spin.valueChanged.connect(self.from_fields)
        layout.addLayout(controls)
        self.info = QLabel("Select an area, or adjust the pixel controls.")
        layout.addWidget(self.info)
        self.buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self.buttons.button(QDialogButtonBox.StandardButton.Ok).setText("Use selected area")
        self.buttons.button(QDialogButtonBox.StandardButton.Ok).setEnabled(False)
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        layout.addWidget(self.buttons)
        self.canvas.selectionChanged.connect(self.from_canvas)

    def from_canvas(self, rect):
        if rect.isEmpty():
            self.buttons.button(QDialogButtonBox.StandardButton.Ok).setEnabled(False)
            return
        for field, value in zip(self.fields, (rect.x(), rect.y(), rect.width(), rect.height())):
            field.blockSignals(True)
            field.setValue(value)
            field.blockSignals(False)
        self.from_fields()

    def from_fields(self):
        if not hasattr(self, "buttons"):
            return
        x, y, width, height = [field.value() for field in self.fields]
        valid = x + width <= self.canvas.image.width() and y + height <= self.canvas.image.height()
        self.buttons.button(QDialogButtonBox.StandardButton.Ok).setEnabled(valid)
        self.canvas.set_selection(QRect(x, y, width, height) if valid else QRect())
        self.info.setText(f"Selected {width} × {height} pixels at ({x}, {y})." if valid else "Selection goes outside the image. Adjust position or size.")

    def selected_rect(self):
        return self.canvas.selection
