"""A native runtime failure must fail CI even when widget assertions pass."""
import subprocess
import sys
import unittest


class QtRuntimeTests(unittest.TestCase):
    def test_repeated_raster_calls_exit_normally(self):
        program = """
from PySide6.QtGui import QColor, QImage, QPainter
image = QImage(8, 8, QImage.Format.Format_ARGB32)
painter = QPainter(image)
color = QColor('blue')
for index in range(5000):
    painter.setPen(color)
    painter.fillRect(0, 0, 8, 8, color)
painter.end()
print('Qt raster calls completed')
"""
        result = subprocess.run([sys.executable, "-c", program], capture_output=True,
                                text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr[-3000:])
        self.assertIn("Qt raster calls completed", result.stdout)
