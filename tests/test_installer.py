import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from build_installer import verify_bundle
from studyframe import __version__


class InstallerTests(unittest.TestCase):
    def test_only_complete_exact_versioned_bundle_can_be_packaged(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            (root/'_internal').mkdir()
            files=[]
            for name in ('StudyFrame.exe','LICENSE','THIRD_PARTY_NOTICES.txt','_internal/test.bin'):
                data=b'synthetic package bytes';(root/name).write_bytes(data)
                files.append({'path':name,'size':len(data),'sha256':hashlib.sha256(data).hexdigest()})
            manifest=root/'manifest.json'
            manifest.write_text(json.dumps({'version':__version__,'files':files}))
            verify_bundle(root)
            (root/'unexpected.txt').write_text('not in manifest')
            with self.assertRaises(ValueError): verify_bundle(root)
            (root/'unexpected.txt').unlink()
            (root/'_internal/test.bin').write_bytes(b'changed')
            with self.assertRaises(ValueError): verify_bundle(root)
            files[-1]['path']='../outside'
            manifest.write_text(json.dumps({'version':__version__,'files':files}))
            with self.assertRaises(ValueError): verify_bundle(root)
            manifest.write_text(json.dumps({'version':'wrong','files':files}))
            with self.assertRaises(ValueError): verify_bundle(root)
