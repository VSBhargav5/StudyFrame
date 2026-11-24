import hashlib
import io
from pathlib import Path
import stat
import tempfile
import unittest
from unittest.mock import patch
import zipfile
from fetch_speech_models import fetch_models,extract_model


NAME='vosk-model-small-en-us-0.15'


def archive(entries=None):
    buffer=io.BytesIO()
    with zipfile.ZipFile(buffer,'w') as z:
        for name,data in (entries or [(NAME+'/am/final.mdl',b'model'),(NAME+'/conf/model.conf',b'config')]):z.writestr(name,data)
    return buffer.getvalue()


class SpeechAssetTests(unittest.TestCase):
    def test_fixed_public_download_hash_and_publication_then_refuse_overwrite(self):
        data=archive()
        with tempfile.TemporaryDirectory() as folder:
            destination=Path(folder)/'new-models'
            with patch('fetch_speech_models.MODELS',{NAME:hashlib.sha256(data).hexdigest()}), \
                 patch('fetch_speech_models.urllib.request.urlopen',return_value=io.BytesIO(data)) as request:
                fetch_models(destination)
                self.assertTrue((destination/NAME/'am/final.mdl').is_file())
                self.assertEqual(request.call_args.args[0],'https://alphacephei.com/vosk/models/'+NAME+'.zip')
                with self.assertRaises(FileExistsError):fetch_models(destination)
                self.assertEqual(request.call_count,1)

    def test_wrong_hash_or_oversized_download_never_publishes_destination(self):
        data=archive()
        for limit,checksum in [(64*1024*1024,'wrong'),(1,hashlib.sha256(data).hexdigest())]:
            with tempfile.TemporaryDirectory() as folder:
                destination=Path(folder)/'models'
                with patch('fetch_speech_models.MODELS',{NAME:checksum}),patch('fetch_speech_models.MAX_ARCHIVE',limit), \
                     patch('fetch_speech_models.urllib.request.urlopen',return_value=io.BytesIO(data)):
                    with self.assertRaises(ValueError):fetch_models(destination)
                self.assertFalse(destination.exists())

    def test_unsafe_duplicate_or_symlink_entries_fail_before_extracting(self):
        link=zipfile.ZipInfo(NAME+'/link');link.external_attr=(stat.S_IFLNK|0o777)<<16
        cases=[[(NAME+'/../escape',b'x')],[(NAME+'/A',b'x'),(NAME+'/a',b'y')],[(link,b'outside')]]
        for entries in cases:
            with tempfile.TemporaryDirectory() as folder:
                with self.assertRaises(ValueError):extract_model(io.BytesIO(archive(entries)),Path(folder),NAME)
                self.assertFalse(list(Path(folder).iterdir()))
