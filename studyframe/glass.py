"""Code-painted translucent surface and ordinary, visible window dragging."""
from PySide6.QtCore import Qt, QRectF, QPointF
from PySide6.QtGui import QColor, QLinearGradient, QPainter, QPainterPath, QPen, QRadialGradient
from PySide6.QtWidgets import QWidget


class GlassPanel(QWidget):
    native_material = False
    compact = False
    tint = None

    def set_tint(self,value):
        if type(value) is not int or not 0<=value<=90:raise ValueError('Glass tint must be0–90.')
        self.tint=value
        self.update()

    def set_native_material(self, enabled):
        self.native_material = enabled
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        area = QRectF(self.rect()).adjusted(7, 7, -7, -7)
        radius = area.height()/2 if self.compact else 22
        painter.setPen(Qt.PenStyle.NoPen)
        path = QPainterPath()
        path.addRoundedRect(area, radius, radius)
        # Keep the shadow outside: an interior shadow fill made even zero tint dark.
        outside=QPainterPath();outside.addRect(QRectF(self.rect()))
        painter.save();painter.setClipPath(outside.subtracted(path))
        for distance in range(6, 0, -1):
            painter.setBrush(QColor(0, 0, 0, 5))
            painter.drawRoundedRect(area.adjusted(-distance, -distance, distance, distance), radius+3, radius+3)
        painter.restore()
        surface = QLinearGradient(area.topLeft(), area.bottomRight())
        # Frost alone does not guarantee readable text over a white application.
        # Keep a dark material floor without sampling the user's desktop.
        if self.tint is None:
            alphas=(194,208,196) if self.native_material else (212,224,216)
        else:
            alpha=round(255*self.tint/100)
            alphas=(alpha,min(255,alpha+12),min(255,alpha+2)) if alpha else (0,0,0)
        surface.setColorAt(0, QColor(34, 42, 65, alphas[0]))
        surface.setColorAt(0.55, QColor(16, 23, 36, alphas[1]))
        surface.setColorAt(1, QColor(21, 26, 43, alphas[2]))
        painter.fillPath(path, surface)
        painter.save()
        painter.setClipPath(path)
        glow = QRadialGradient(QPointF(area.right()-40, area.top()+12), 260)
        glow.setColorAt(0, QColor(123, 119, 255, 0 if self.tint==0 else 18))
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
