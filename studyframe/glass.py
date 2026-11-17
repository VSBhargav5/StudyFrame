"""Code-painted translucent surface and ordinary, visible window dragging."""
from PySide6.QtCore import Qt, QRectF, QPointF
from PySide6.QtGui import QColor, QLinearGradient, QPainter, QPainterPath, QPen, QRadialGradient
from PySide6.QtWidgets import QWidget


class GlassPanel(QWidget):
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        area = QRectF(self.rect()).adjusted(7, 7, -7, -7)
        painter.setPen(Qt.PenStyle.NoPen)
        for distance in range(6, 0, -1):
            painter.setBrush(QColor(0, 0, 0, 5))
            painter.drawRoundedRect(area.adjusted(-distance, -distance, distance, distance), 25, 25)
        path = QPainterPath()
        path.addRoundedRect(area, 22, 22)
        surface = QLinearGradient(area.topLeft(), area.bottomRight())
        surface.setColorAt(0, QColor(34, 42, 65, 204))
        surface.setColorAt(0.55, QColor(16, 23, 36, 224))
        surface.setColorAt(1, QColor(21, 26, 43, 209))
        painter.fillPath(path, surface)
        painter.save()
        painter.setClipPath(path)
        glow = QRadialGradient(QPointF(area.right()-40, area.top()+12), 260)
        glow.setColorAt(0, QColor(123, 119, 255, 38))
        glow.setColorAt(1, QColor(123, 119, 255, 0))
        painter.fillRect(area, glow)
        painter.restore()
        painter.setPen(QPen(QColor(207, 222, 255, 54), 1))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawPath(path)


class DragBar(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.offset = None
        self.setCursor(Qt.CursorShape.SizeAllCursor)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            handle = self.window().windowHandle()
            if handle is not None and handle.startSystemMove():
                return
            self.offset = event.globalPosition().toPoint()-self.window().pos()
            event.accept()

    def mouseMoveEvent(self, event):
        if self.offset is not None and event.buttons() & Qt.MouseButton.LeftButton:
            self.window().move(event.globalPosition().toPoint()-self.offset)
            event.accept()

    def mouseReleaseEvent(self, event):
        self.offset = None
        super().mouseReleaseEvent(event)
