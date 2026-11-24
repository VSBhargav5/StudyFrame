"""Disposable Windows CI lifecycle check. Never run against a personal install."""
import argparse
import ctypes
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time


def verify(installer, workspace):
    if sys.platform != 'win32': raise ValueError('Windows only.')
    installer=Path(installer).resolve(); workspace=Path(workspace).resolve()
    workspace.mkdir(parents=True,exist_ok=False)
    destination=workspace/'installed'
    command=[str(installer),'/VERYSILENT','/SUPPRESSMSGBOXES','/NORESTART','/DIR='+str(destination)]
    subprocess.run(command,check=True,timeout=180)
    executable=destination/'StudyFrame.exe'
    before=hashlib.sha256(executable.read_bytes()).hexdigest()
    report=workspace/'installed-runtime.json'
    runtime=[str(executable),'--self-test','--output',str(report)]
    bundled=destination/'models/vosk-model-small-en-us-0.15'
    if bundled.is_dir():runtime+=['--model',str(bundled)]
    subprocess.run(runtime,check=True,timeout=90)
    assert json.loads(report.read_text())['ok']
    # A genuine running-app mutex must block replacement, rather than kill it.
    kernel=ctypes.WinDLL('kernel32',use_last_error=True,winmode=0x800)
    kernel.CreateMutexW.argtypes=[ctypes.c_void_p,ctypes.c_int,ctypes.c_wchar_p]
    kernel.CreateMutexW.restype=ctypes.c_void_p
    kernel.CloseHandle.argtypes=[ctypes.c_void_p]
    handle=kernel.CreateMutexW(None,False,'Local\\StudyFrame.Application')
    if not handle: raise ctypes.WinError(ctypes.get_last_error())
    try:
        blocked=subprocess.run(command,timeout=60)
        assert blocked.returncode != 0
        assert hashlib.sha256(executable.read_bytes()).hexdigest()==before
    finally:
        kernel.CloseHandle(handle)
    # The app's actual configuration location is outside the install directory.
    from PySide6.QtCore import QCoreApplication
    from studyframe.preferences import Preferences
    app=QCoreApplication.instance() or QCoreApplication([])
    app.setApplicationName('StudyFrame')
    settings=Preferences.default().path
    if settings.exists(): raise ValueError('CI config already exists; refusing to overwrite.')
    settings.parent.mkdir(parents=True,exist_ok=True)
    sentinel=b'{"synthetic-installer-preservation":true}'
    settings.write_bytes(sentinel)
    subprocess.run(command,check=True,timeout=180)
    assert settings.read_bytes()==sentinel
    uninstall=destination/'unins000.exe'
    subprocess.run([str(uninstall),'/VERYSILENT','/SUPPRESSMSGBOXES','/NORESTART'],check=True,timeout=90)
    for _ in range(50):
        if not executable.exists(): break
        time.sleep(0.2)
    assert not executable.exists() and settings.read_bytes()==sentinel
    print(json.dumps({'installed_runtime':True,'active_update_blocked':True,
                      'reinstall':True,'uninstall':True,'settings_preserved':True}))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--installer',required=True);parser.add_argument('--workspace',required=True)
    args=parser.parse_args();verify(args.installer,args.workspace)
