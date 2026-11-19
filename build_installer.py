"""Compile an unsigned per-user installer from an integrity-checked portable app."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import uuid
from studyframe import __version__


def verify_bundle(bundle):
    bundle = Path(bundle).resolve()
    for name in ('StudyFrame.exe', '_internal', 'LICENSE', 'THIRD_PARTY_NOTICES.txt'):
        if not (bundle/name).exists():
            raise ValueError('The portable package is incomplete: ' + name)
    manifest_path = bundle/'manifest.json'
    if manifest_path.is_symlink() or getattr(manifest_path.lstat(),'st_file_attributes',0)&1024:
        raise ValueError('Unsafe manifest path.')
    with manifest_path.open('rb') as source:
        raw = source.read(1024*1024+1)
    if len(raw) > 1024*1024:
        raise ValueError('Manifest too large.')
    manifest = json.loads(raw)
    if manifest.get('version') != __version__:
        raise ValueError('Build the current portable version first.')
    entries = manifest.get('files')
    if not isinstance(entries, list) or not entries or len(entries)>10000:
        raise ValueError('Invalid manifest.')
    expected = set()
    for entry in entries:
        path = bundle/entry['path']
        if (not path.resolve().is_relative_to(bundle) or path.is_symlink() or
            any(getattr(p.lstat(),'st_file_attributes',0)&1024 for p in [path,*path.parents] if p.is_relative_to(bundle))):
            raise ValueError('Unsafe manifest path.')
        if entry['path'] in expected or not path.is_file() or path.stat().st_size != entry['size']:
            raise ValueError('Portable file mismatch.')
        with path.open('rb') as source:
            if hashlib.file_digest(source,'sha256').hexdigest()!=entry['sha256']:
                raise ValueError('Portable file mismatch.')
        expected.add(entry['path'])
    actual = set()
    for path in bundle.rglob('*'):
        if path.is_symlink() or getattr(path.lstat(),'st_file_attributes',0)&1024:
            raise ValueError('Portable package contains a link/reparse point.')
        if path.is_file():
            actual.add(path.relative_to(bundle).as_posix())
    if actual != expected | {'manifest.json'}:
        raise ValueError('Unexpected or missing portable file.')


def build(compiler):
    if sys.platform != 'win32':
        raise ValueError('Build installers on Windows x64.')
    compiler = Path(compiler).resolve()
    if not compiler.is_file():
        raise ValueError('Supply an installed trusted Inno Setup 6 ISCC.exe.')
    root = Path(__file__).resolve().parent
    bundle = root/'out'/f'portable-v{__version__}'/'StudyFrame'
    verify_bundle(bundle)
    name = f'StudyFrame-{__version__}-windows-x64-setup.exe'
    output = root/'out'/name
    if output.exists():
        raise ValueError('Installer already exists; refusing to overwrite.')
    stage = root/'out'/('.installer-build-'+uuid.uuid4().hex)
    stage.mkdir()
    subprocess.run([str(compiler),'/DAppVersion='+__version__, '/DBundleDir='+str(bundle),
                    '/DStageDir='+str(stage), str(root/'installer.iss')],check=True,cwd=root)
    if not (stage/name).is_file():
        raise ValueError('Compiler did not produce the installer.')
    (stage/name).rename(output)
    return output


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--compiler',required=True)
    print(build(parser.parse_args().compiler))
