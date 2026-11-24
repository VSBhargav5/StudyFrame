"""Build a new unsigned Windows portable folder/ZIP; never overwrite a running build."""
import argparse
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import uuid
import zipfile
from studyframe import __version__


def build_environment():
    # Do not inherit tool-specific DLL directories or inspect credential variables.
    names = ('SystemRoot','WINDIR','TEMP','TMP','COMSPEC','USERPROFILE','APPDATA','LOCALAPPDATA','QT_QPA_PLATFORM')
    environment = {name:os.environ[name] for name in names if name in os.environ}
    windows = Path(environment.get('SystemRoot',r'C:\Windows'))
    environment['PATH'] = os.pathsep.join(map(str,[Path(sys.executable).parent,Path(sys.base_prefix),windows/'System32',windows]))
    environment['PYTHONUTF8'] = '1'
    return environment


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--model', type=Path, help='Optional trusted vosk-model-small-en-us-0.15 folder to bundle')
    parser.add_argument('--indian-model', type=Path, help='Optional trusted vosk-model-small-en-in-0.4 folder to bundle')
    args = parser.parse_args()
    if sys.platform != 'win32': parser.error('Build on Windows x64.')
    repo = Path(__file__).resolve().parent
    out = repo / 'out'; out.mkdir(exist_ok=True)
    target = out / f'portable-v{__version__}'
    archive = out / f'StudyFrame-{__version__}-windows-x64.zip'
    if target.exists() or archive.exists(): parser.error('Versioned output already exists; it will not be overwritten.')
    if args.model:
        args.model = args.model.resolve()
        if args.model.name != 'vosk-model-small-en-us-0.15' or not (args.model/'am/final.mdl').is_file():
            parser.error('Bundle only the trusted extracted small US-English model; other models can be selected in the app.')
        if any(p.is_symlink() or getattr(p.lstat(),'st_file_attributes',0) & 1024 for p in args.model.rglob('*')):
            parser.error('Model folder contains a link/reparse point; refusing to bundle it.')
    if args.indian_model:
        args.indian_model=args.indian_model.resolve()
        if args.indian_model.name!='vosk-model-small-en-in-0.4' or not (args.indian_model/'am/final.mdl').is_file():
            parser.error('Choose the trusted small Indian-English0.4 model folder.')
        if any(p.is_symlink() or getattr(p.lstat(),'st_file_attributes',0)&1024 for p in args.indian_model.rglob('*')):
            parser.error('Indian model contains a link/reparse point.')
    stage = out / ('.windows-build-' + uuid.uuid4().hex)
    stage.mkdir()
    subprocess.run([sys.executable,'-m','PyInstaller','--noconfirm','--windowed','--onedir',
                    '--name','StudyFrame','--distpath',str(stage/'dist'),'--workpath',str(stage/'work'),
                    '--specpath',str(stage),'--paths',str(repo),'--collect-all','soundcard','--collect-all','vosk',
                    '--collect-all','rapidocr','--collect-all','onnxruntime',
                    str(repo/'desktop.py')],cwd=repo,env=build_environment(),check=True)
    bundle = stage/'dist/StudyFrame'
    for name in ('LICENSE','README.md'):
        shutil.copyfile(repo/name,bundle/name)
    shutil.copytree(repo/'docs',bundle/'docs')
    shutil.copytree(repo/'third_party',bundle/'third_party')
    # Public installed package license files only. Do not sweep project/user files.
    for distribution in importlib.metadata.distributions():
        root = Path(distribution.locate_file('')).resolve()
        label = distribution.metadata.get('Name','dependency').replace('/','_').replace('\\','_')
        for entry in distribution.files or ():
            if not (any(part.lower() in ('license','licenses') for part in Path(entry).parts)
                    or Path(entry).name.upper().startswith(('LICENSE','COPYING','NOTICE'))):
                continue
            source = Path(distribution.locate_file(entry)).resolve()
            if not source.is_relative_to(root) or not source.is_file() or source.stat().st_size > 1024*1024:
                continue
            relative = source.relative_to(root)
            # Avoid repeating the long distribution/version directory beneath
            # its own package label (WinRT exceeded MAX_PATH on this checkout).
            if relative.parts[0].endswith(('.dist-info', '.egg-info')):
                relative = Path(*relative.parts[1:])
            destination = bundle/'licenses'/label/relative
            destination.parent.mkdir(parents=True,exist_ok=True)
            if not destination.exists(): shutil.copyfile(source,destination)
    python_license = Path(sys.base_prefix)/'LICENSE.txt'
    if python_license.is_file(): shutil.copyfile(python_license,bundle/'licenses/Python-LICENSE.txt')
    if args.model:
        shutil.copytree(args.model,bundle/'models/vosk-model-small-en-us-0.15')
    if args.indian_model:
        shutil.copytree(args.indian_model,bundle/'models/vosk-model-small-en-in-0.4')
    (bundle/'THIRD_PARTY_NOTICES.txt').write_text(
        'StudyFrame uses unchanged dynamically linked Qt/PySide (LGPL/GPL/commercial options), '
        'Python, NumPy, Vosk, SoundCard, RapidOCR/PaddleOCR models, ONNX Runtime, OpenCV, Pillow and their dependencies. See licenses/ and third_party/ocr/ for license/notice texts.\n'
        'Qt/PySide source and replacement information: https://download.qt.io/official_releases/QtForPython/\n'
        'This portable folder permits replacement of its dynamic Qt libraries. No changes to Qt sources are included.\n'
        'Optional models: Alpha Cephei small US English0.15 and Indian English0.4, Apache-2.0 as listed at https://alphacephei.com/vosk/models .\n'
        'Do not treat package hashes as signing/authenticity or proof of model accuracy.\n',encoding='utf-8')
    report = bundle/'runtime-check.json'
    command = [str(bundle/'StudyFrame.exe'),'--self-test','--output',str(report)]
    if args.model: command += ['--model',str(bundle/'models/vosk-model-small-en-us-0.15')]
    subprocess.run(command,cwd=stage,env=build_environment(),check=True,timeout=90)
    if not json.loads(report.read_text(encoding='utf-8')).get('ok'): raise RuntimeError('Runtime check failed.')
    manifest = {'version':__version__,'kind':'unsigned-portable','files':[]}
    for file in sorted(bundle.rglob('*')):
        if file.is_file():
            manifest['files'].append({'path':file.relative_to(bundle).as_posix(),
                                      'size':file.stat().st_size,'sha256':hashlib.sha256(file.read_bytes()).hexdigest()})
    (bundle/'manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    staged_zip = stage/'portable.zip'
    with zipfile.ZipFile(staged_zip,'x',zipfile.ZIP_DEFLATED) as target_zip:
        for file in bundle.rglob('*'):
            if file.is_file(): target_zip.write(file,'StudyFrame/'+file.relative_to(bundle).as_posix())
    # Both destinations are new; failed/old stages are retained for inspection.
    if not all(path.resolve().is_relative_to(out.resolve()) for path in (bundle,target,staged_zip,archive)):
        raise RuntimeError('Resolved publication paths escaped the intended output directory.')
    target.mkdir()
    bundle.rename(target/'StudyFrame')
    staged_zip.rename(archive)
    print(json.dumps({'folder':str(target/'StudyFrame'),'zip':str(archive),
                      'zip_sha256':hashlib.sha256(archive.read_bytes()).hexdigest()}))
    return 0


if __name__ == '__main__': raise SystemExit(main())
