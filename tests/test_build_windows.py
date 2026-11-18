import unittest
from unittest.mock import patch
from build_windows import build_environment


class BuildEnvironmentTests(unittest.TestCase):
    def test_packaging_does_not_inherit_unrelated_dll_path_or_credentials(self):
        with patch('build_windows.os.environ', {'SystemRoot':r'C:\Windows',
                  'PATH':'unrelated-tool-libraries','OPENAI_API_KEY':'synthetic-do-not-read'}):
            environment = build_environment()
        self.assertNotIn('unrelated-tool-libraries',environment['PATH'])
        self.assertNotIn('OPENAI_API_KEY',environment)
        self.assertIn('System32',environment['PATH'])
