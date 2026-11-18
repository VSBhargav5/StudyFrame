from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
from studyframe.launcher import default_model, main


class LauncherTests(unittest.TestCase):
    def test_frozen_model_uses_executable_folder_not_unpack_or_working_directory(self):
        with tempfile.TemporaryDirectory() as folder, \
             patch.object(sys,'frozen',True,create=True), patch.object(sys,'executable',str(Path(folder)/'StudyFrame.exe')):
            model = default_model()
            self.assertTrue(model.parent.parent.samefile(folder))
            self.assertEqual(model.parent.name,'models')
            self.assertEqual(model.name,'vosk-model-small-en-us-0.15')

    def test_worker_dispatch_cannot_start_a_second_gui(self):
        with patch.object(sys,'argv',['StudyFrame.exe','--speech-worker','--source','loopback']), \
             patch('studyframe.launcher.worker_pipes') as pipes, \
             patch('studyframe.speech_worker.main',return_value=0) as worker, \
             patch('studyframe.app.main') as gui:
            self.assertEqual(main(),0)
        pipes.assert_called_once(); worker.assert_called_once_with(['--source','loopback']); gui.assert_not_called()
