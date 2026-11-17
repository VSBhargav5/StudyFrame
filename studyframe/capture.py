"""One explicitly chosen display; local still pixels, never a live upload."""
import hashlib
import math

from PySide6.QtCore import QBuffer, QByteArray, QIODevice, QRect
from PySide6.QtGui import QImage, QPainter
from studyframe.images import LoadedImage, ImageError, MAX_DIMENSION, MAX_PIXELS, MAX_FILE_BYTES


def capture_screen(screen):
    try:
        geometry, ratio = screen.geometry(), screen.devicePixelRatio()
        if not math.isfinite(ratio) or ratio <= 0:
            raise ImageError('The selected display has an invalid scale.')
        width, height = math.ceil(geometry.width()*ratio), math.ceil(geometry.height()*ratio)
        if min(width,height) < 1 or max(width,height) > MAX_DIMENSION or width*height > MAX_PIXELS:
            raise ImageError('Display exceeds the capture pixel limit. Use a smaller display or load a cropped image.')
        source = screen.grabWindow(0).toImage()
    except RuntimeError:
        raise ImageError('The selected display is no longer available. Choose it again.') from None
    width,height = source.width(),source.height()
    if source.isNull():
        raise ImageError('Screen capture was unavailable or blocked. Previous image kept.')
    if max(width,height) > MAX_DIMENSION or width*height > MAX_PIXELS:
        raise ImageError('Captured display exceeds the pixel limit. Previous image kept.')
    # Copy physical pixels into a metadata-free, DPR=1 image, keeping crop coordinates exact.
    image = QImage(width,height,QImage.Format.Format_ARGB32)
    if image.isNull():raise ImageError('Not enough memory to capture this display.')
    image.fill(0)
    painter = QPainter(image)
    painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Source)
    painter.drawImage(QRect(0,0,width,height),source,QRect(0,0,width,height))
    painter.end()
    encoded = QByteArray(); buffer = QBuffer(encoded)
    buffer.open(QIODevice.OpenModeFlag.WriteOnly)
    if not image.save(buffer,'PNG'):raise ImageError('Could not encode the capture. Previous image kept.')
    data = bytes(encoded)
    if len(data) > MAX_FILE_BYTES:raise ImageError('Captured PNG exceeds8MiB. Use a smaller display or load a cropped image.')
    return LoadedImage(data,image,hashlib.sha256(data).hexdigest(),width,height,'png')
