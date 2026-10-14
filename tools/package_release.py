"""Build a reproducible manual-install archive; HACS uses the tagged source."""
import json
from pathlib import Path
import zipfile
ROOT=Path(__file__).resolve().parents[1]
DEST=ROOT/'release';DEST.mkdir(exist_ok=True)
files=sorted((ROOT/'custom_components/arandjelovac_live').rglob('*'))
files+=[ROOT/'README.md',ROOT/'lovelace.yaml',ROOT/'LICENSE']
with zipfile.ZipFile(DEST/'arandjelovac_live.zip','w',zipfile.ZIP_DEFLATED) as archive:
    for path in files:
        if not path.is_file() or '__pycache__' in path.parts or path.suffix=='.pyc':continue
        info=zipfile.ZipInfo(path.relative_to(ROOT).as_posix(),date_time=(2026,10,14,0,0,0))
        info.compress_type=zipfile.ZIP_DEFLATED
        archive.writestr(info,path.read_bytes())
print(DEST/'arandjelovac_live.zip')
