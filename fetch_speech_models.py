"""Explicit build-time fetch of two fixed licensed speech archives, no runtime download."""
import argparse
import hashlib
import json
from pathlib import Path,PurePosixPath
import stat
import urllib.request
import uuid
import zipfile

MODELS={
    'vosk-model-small-en-us-0.15':'30f26242c4eb449f948e42cb302dd7a686cb29a3423a8367f99ff41780942498',
    'vosk-model-small-en-in-0.4':'20663dcac4d5cb783a579c54d98339344a688e4ec6e1b4a4b059fd1235454cc7',
}
MAX_ARCHIVE=64*1024*1024
MAX_EXPANDED=200*1024*1024


def extract_model(archive,stage,name):
    root=Path(stage).resolve()
    with zipfile.ZipFile(archive) as source:
        entries=source.infolist()
        if len(entries)>1000 or sum(e.file_size for e in entries)>MAX_EXPANDED:raise ValueError('Model archive exceeds its extraction limits.')
        seen=set()
        for entry in entries:
            path=PurePosixPath(entry.filename)
            if (not path.parts or path.is_absolute() or path.parts[0]!=name or '..' in path.parts
                    or '\\' in entry.filename or ':' in entry.filename or
                    stat.S_IFMT(entry.external_attr>>16)==stat.S_IFLNK):
                raise ValueError('Unsafe model archive path.')
            folded=entry.filename.rstrip('/').casefold()
            if folded in seen:raise ValueError('Duplicate model archive path.')
            seen.add(folded)
            if not (root/Path(*path.parts)).resolve().is_relative_to(root):raise ValueError('Model path escaped stage.')
        for entry in entries:
            target=root/Path(*PurePosixPath(entry.filename).parts)
            if entry.is_dir():target.mkdir(parents=True,exist_ok=True)
            else:
                target.parent.mkdir(parents=True,exist_ok=True)
                with target.open('xb') as output:output.write(source.read(entry))
    if not (root/name/'am/final.mdl').is_file() or not (root/name/'conf/model.conf').is_file():
        raise ValueError('Incomplete model archive.')


def fetch_models(destination):
    destination=Path(destination).resolve()
    if destination.exists():raise FileExistsError('Choose a new destination; existing paths are never overwritten.')
    destination.parent.mkdir(parents=True,exist_ok=True)
    stage=destination.parent/('.speech-stage-'+uuid.uuid4().hex)
    if not stage.resolve().is_relative_to(destination.parent):raise ValueError('Stage escaped target parent.')
    stage.mkdir()
    downloads=stage/'downloads';downloads.mkdir()
    provenance=[]
    for name,expected in MODELS.items():
        url='https://alphacephei.com/vosk/models/'+name+'.zip'
        archive=downloads/(name+'.zip');digest=hashlib.sha256();size=0
        with urllib.request.urlopen(url,timeout=60) as response,archive.open('xb') as output:
            while True:
                chunk=response.read(1024*1024)
                if not chunk:break
                size+=len(chunk)
                if size>MAX_ARCHIVE:raise ValueError('Model download exceeded limit.')
                digest.update(chunk);output.write(chunk)
        if digest.hexdigest()!=expected:raise ValueError('Model archive checksum mismatch; nothing published.')
        extract_model(archive,stage,name)
        provenance.append({'model':name,'archive_sha256':expected,'source':url,'license':'Apache-2.0'})
    (stage/'models-manifest.json').write_text(json.dumps(provenance,indent=2),encoding='utf-8')
    if destination.exists():raise FileExistsError('Destination appeared; stage retained without overwrite.')
    # Windows directory rename fails if the destination exists. Failed stages stay.
    stage.rename(destination)
    return provenance


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--destination',type=Path,required=True)
    args=parser.parse_args()
    try:result=fetch_models(args.destination)
    except (OSError,ValueError,zipfile.BadZipFile) as exc:parser.exit(1,f'Build-time model setup failed: {type(exc).__name__}. Existing destinations preserved; failed stage retained.\n')
    print(json.dumps(result));return 0


if __name__=='__main__':raise SystemExit(main())
