# Reproducible standalone desktop build. No external Python, Node or browser required.
from pathlib import Path
import os
import sys
import PySide6
from PyInstaller.utils.hooks import collect_submodules,collect_data_files,copy_metadata

root=Path(SPECPATH)
# Avoid collecting unrelated DLLs from tools on the developer's PATH.
# The Qt wheel uses Windows' unversioned ICU API; a conda/Poppler ICU with
# the same filename exports versioned names and prevents QtCore from loading.
os.environ['PATH']=os.pathsep.join([
    sys.base_prefix, str(Path(sys.prefix)/'Scripts'),
    str(Path(os.environ['SystemRoot'])/'System32'), os.environ['SystemRoot'],
])
datas=[(str(root/'frontend'/'dist'),'frontend/dist'),(str(root/'assets'),'assets'),(str(root/'frontend'/'src'/'locales'),'locale-data')]
datas+=collect_data_files('volatility3',include_py_files=True)
datas+=copy_metadata('volatility3')
for name in ('LICENSE','THIRD_PARTY_NOTICES.md'):
    if (root/name).exists():
        datas.append((str(root/name),'.'))
hidden=collect_submodules('volatility3')+[
    'uvicorn.logging','uvicorn.loops.asyncio','uvicorn.protocols.http.h11_impl',
    'uvicorn.protocols.websockets.websockets_impl','uvicorn.lifespan.on',
    'yara','capstone','Crypto.Cipher.AES','Crypto.Cipher.ARC4','Crypto.Cipher.DES','Crypto.Cipher.DES3',
    'ijson.backends.yajl2_c','volstudio.app','volstudio.catalog','volstudio.engine_worker','volstudio.pipeline',
]
a=Analysis([str(root/'desktop_entry.py')],pathex=[str(root)],binaries=[],datas=datas,hiddenimports=hidden,
           hookspath=[],runtime_hooks=[],excludes=['pytest','IPython','matplotlib','numpy','pandas','tkinter'],noarchive=False)
qt_root=Path(PySide6.__file__).resolve().parent
def foreign_icu(entry):
    name=Path(entry[0]).name.lower()
    return (name.startswith(('icuuc','icuin','icudt')) and name.endswith('.dll')
            and not Path(entry[1]).resolve().is_relative_to(qt_root))
# Also sanitize an Analysis restored from a build cache made with an older PATH.
a.binaries=[entry for entry in a.binaries if not foreign_icu(entry)]
pyz=PYZ(a.pure)
exe=EXE(pyz,a.scripts,a.binaries,a.datas,[],name='VolatiElite',debug=False,bootloader_ignore_signals=False,
        strip=False,upx=False,console=False,disable_windowed_traceback=False,
        icon=str(root/'assets'/'app.ico'),version=str(root/'version_info.txt'))
