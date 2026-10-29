import hashlib
import os
from pathlib import Path
import struct
import tempfile
import unittest
from unittest.mock import patch
import zlib

from PySide6.QtCore import QBuffer, QByteArray, QIODevice
from PySide6.QtGui import QImage

from studyframe.images import ImageError, MAX_FILE_BYTES, load_image


def encoded_image(image_format="PNG", width=20, height=10):
    image = QImage(width, height, QImage.Format.Format_RGB32)
    image.fill(0xFF346789)
    encoded = QByteArray()
    device = QBuffer(encoded)
    device.open(QIODevice.OpenModeFlag.WriteOnly)
    if not image.save(device, image_format):
        raise AssertionError("Synthetic fixture could not be encoded")
    return bytes(encoded)


def oversized_header(width, height):
    """Change only a small PNG's dimensions, without allocating a huge fixture."""
    data = encoded_image()
    header = struct.pack(">II", width, height) + data[24:29]
    checksum = struct.pack(">I", zlib.crc32(b"IHDR" + header))
    return data[:16] + header + checksum + data[33:]


class ImageTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def write(self, data, name="selected.png"):
        path = self.root / name
        path.write_bytes(data)
        return path

    def test_png_keeps_exact_snapshot_and_dimensions(self):
        data = encoded_image()
        result = load_image(self.write(data))
        self.assertEqual(result.data, data)
        self.assertEqual(result.sha256, hashlib.sha256(data).hexdigest())
        self.assertEqual((result.width, result.height, result.format), (20, 10, "png"))
        self.assertFalse(result.image.isNull())

    def test_jpeg_is_accepted(self):
        result = load_image(self.write(encoded_image("JPEG"), "selected.jpg"))
        self.assertEqual((result.width, result.height, result.format), (20, 10, "jpeg"))

    def test_jpeg_orientation_is_applied_to_preview_and_dimensions(self):
        jpeg = encoded_image("JPEG")
        # A single TIFF orientation entry: rotate the stored pixels 90 degrees.
        tiff = b"II" + struct.pack("<HIH", 42, 8, 1)
        tiff += struct.pack("<HHI", 0x0112, 3, 1) + struct.pack("<H", 6) + b"\0\0"
        tiff += struct.pack("<I", 0)
        exif = b"Exif\0\0" + tiff
        oriented = jpeg[:2] + b"\xff\xe1" + struct.pack(">H", len(exif) + 2) + exif + jpeg[2:]
        result = load_image(self.write(oriented, "rotated.jpg"))
        self.assertEqual((result.width, result.height), (10, 20))
        self.assertEqual(result.data, oriented)

    def test_content_detection_does_not_depend_on_extension(self):
        result = load_image(self.write(encoded_image(), "selected.bin"))
        self.assertEqual(result.format, "png")

    def test_renaming_other_format_to_png_does_not_allow_it(self):
        with self.assertRaisesRegex(ImageError, "valid PNG or JPEG"):
            load_image(self.write(encoded_image("BMP")))

    def test_empty_file_is_rejected(self):
        with self.assertRaisesRegex(ImageError, "empty"):
            load_image(self.write(b""))

    def test_malformed_file_is_rejected(self):
        with self.assertRaisesRegex(ImageError, "valid PNG or JPEG"):
            load_image(self.write(b"not an image"))

    def test_truncated_png_cannot_be_used(self):
        with self.assertRaises(ImageError):
            load_image(self.write(encoded_image()[:45]))

    def test_file_limit_is_enforced(self):
        path = self.write(b"")
        with path.open("wb") as source:
            source.truncate(MAX_FILE_BYTES + 1)
        with self.assertRaisesRegex(ImageError, "8 MiB"):
            load_image(path)

    def test_read_is_bounded_if_file_grows_after_stat(self):
        path = self.write(encoded_image())
        original_fstat = os.fstat

        def stat_then_grow(descriptor):
            before = original_fstat(descriptor)
            with path.open("ab") as writer:
                writer.truncate(MAX_FILE_BYTES + 1)
            return before

        with patch("studyframe.images.os.fstat", stat_then_grow):
            with self.assertRaisesRegex(ImageError, "8 MiB"):
                load_image(path)

    def test_dimension_limit_is_checked_before_decode(self):
        with self.assertRaisesRegex(ImageError, "8192"):
            load_image(self.write(oversized_header(8193, 1)))

    def test_pixel_limit_is_checked_before_decode(self):
        with self.assertRaisesRegex(ImageError, "16 million"):
            load_image(self.write(oversized_header(4096, 4096)))

    def test_directory_is_rejected(self):
        with self.assertRaisesRegex(ImageError, "regular"):
            load_image(self.root)

    def test_missing_file_error_does_not_expose_path(self):
        with self.assertRaises(ImageError) as raised:
            load_image(self.root / "private-account-name.png")
        self.assertNotIn(str(self.root), str(raised.exception))
        self.assertNotIn("private-account-name", str(raised.exception))

    def test_permission_failure_is_a_user_error(self):
        path = self.write(encoded_image())
        with patch.object(Path, "open", side_effect=PermissionError("secret path")):
            with self.assertRaisesRegex(ImageError, "could not be read") as raised:
                load_image(path)
        self.assertNotIn("secret path", str(raised.exception))

    def test_snapshot_survives_source_replacement(self):
        data = encoded_image()
        path = self.write(data)
        result = load_image(path)
        path.write_bytes(b"replaced")
        self.assertEqual(result.data, data)
        self.assertEqual(result.sha256, hashlib.sha256(data).hexdigest())
        self.assertEqual(result.image.pixelColor(0, 0).name(), "#346789")


if __name__ == "__main__":
    unittest.main()
