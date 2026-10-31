"""Read one explicitly selected image into a bounded, local byte snapshot."""

from dataclasses import dataclass
import hashlib
import os
from pathlib import Path
import stat

from PySide6.QtCore import QBuffer, QByteArray, QIODevice, QRect
from PySide6.QtGui import QImage, QImageReader, QPainter


MAX_FILE_BYTES = 8 * 1024 * 1024
MAX_PIXELS = 16_000_000
MAX_DIMENSION = 8192
DECODE_LIMIT_MIB = 64


class ImageError(ValueError):
    """The selected file cannot be used as a study image."""


@dataclass(frozen=True)
class LoadedImage:
    data: bytes
    image: QImage
    sha256: str
    width: int
    height: int
    format: str


def crop_image(source: LoadedImage, x: int, y: int, width: int, height: int) -> LoadedImage:
    """Create a new PNG from selected oriented pixels, without source metadata.

    Coordinates are in the decoded preview's pixels; right/bottom are exclusive.
    The original snapshot and source file are never modified or reopened.
    """
    if (any(type(value) is not int for value in (x, y, width, height))
            or x < 0 or y < 0 or width < 1 or height < 1
            or x + width > source.width or y + height > source.height):
        raise ImageError("Choose a nonempty crop inside the image.")
    image = QImage(width, height, QImage.Format.Format_ARGB32)
    if image.isNull():
        raise ImageError("There was not enough memory to crop this image.")
    image.fill(0)
    painter = QPainter(image)
    painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Source)
    painter.drawImage(QRect(0, 0, width, height), source.image, QRect(x, y, width, height))
    painter.end()
    encoded = QByteArray()
    buffer = QBuffer(encoded)
    buffer.open(QIODevice.OpenModeFlag.WriteOnly)
    if not image.save(buffer, "PNG"):
        raise ImageError("The crop could not be encoded. Previous image kept.")
    data = bytes(encoded)
    if len(data) > MAX_FILE_BYTES:
        raise ImageError("The cropped PNG exceeds 8 MiB. Choose a smaller area.")
    return LoadedImage(data, image, hashlib.sha256(data).hexdigest(), width, height, "png")


def load_image(path: str | Path) -> LoadedImage:
    """Validate and decode the same bytes; never reopen the path for preview.

    Extension names are not trusted. The decoded image is for local display;
    no OCR, capture, upload, or persistent copy is performed here.
    """
    try:
        selected = Path(path)
        if not stat.S_ISREG(selected.stat().st_mode):
            raise ImageError("Choose a regular PNG or JPEG file.")
        with selected.open("rb") as source:
            info = os.fstat(source.fileno())
            if not stat.S_ISREG(info.st_mode):
                raise ImageError("Choose a regular PNG or JPEG file.")
            if info.st_size > MAX_FILE_BYTES:
                raise ImageError("Choose an image no larger than 8 MiB.")
            data = source.read(MAX_FILE_BYTES + 1)
    except (OSError, TypeError, ValueError) as exc:
        if isinstance(exc, ImageError):
            raise
        raise ImageError("The selected file could not be read. Choose another image.") from exc

    if len(data) > MAX_FILE_BYTES:
        raise ImageError("Choose an image no larger than 8 MiB.")
    if not data:
        raise ImageError("The selected file is empty.")

    buffer = QBuffer()
    buffer.setData(QByteArray(data))
    buffer.open(QIODevice.OpenModeFlag.ReadOnly)
    reader = QImageReader(buffer)
    reader.setDecideFormatFromContent(True)
    image_format = bytes(reader.format()).decode("ascii", errors="replace").lower()
    if image_format not in {"png", "jpeg"}:
        raise ImageError("Choose a valid PNG or JPEG image.")
    size = reader.size()
    if not size.isValid() or size.isEmpty():
        raise ImageError("The image dimensions could not be read.")
    if max(size.width(), size.height()) > MAX_DIMENSION:
        raise ImageError("Image width and height must each be at most 8192 pixels.")
    if size.width() * size.height() > MAX_PIXELS:
        raise ImageError("Choose an image with at most 16 million pixels.")
    if reader.supportsAnimation() or reader.imageCount() > 1:
        raise ImageError("Choose a still image rather than an animation.")
    QImageReader.setAllocationLimit(DECODE_LIMIT_MIB)
    reader.setAutoTransform(True)
    image = reader.read()
    if image.isNull():
        raise ImageError("The image could not be decoded. It may be damaged.")
    return LoadedImage(
        data=data,
        image=image,
        sha256=hashlib.sha256(data).hexdigest(),
        width=image.width(),
        height=image.height(),
        format=image_format,
    )
