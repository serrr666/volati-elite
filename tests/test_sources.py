import hashlib
import json
import struct

import pytest

from volstudio.vmware import checkpoint_layout, CheckpointError, MonolithicVmwareStacker
from volstudio.preflight import inspect_source
from volstudio import db, symbol_store


def checkpoint(regions=None, compressed=False, duplicate=False):
    def tag(name,value,indices=()):
        return bytes([len(value)|(len(indices)<<6),len(name)])+name+struct.pack('<'+'I'*len(indices),*indices)+value
    tags=b''
    if regions:
        tags+=tag(b'regionsCount',struct.pack('<I',len(regions)))
        for i,(physical,relative,length) in enumerate(regions):
            for name,value in [(b'regionPPN',physical),(b'regionPageNum',relative),(b'regionSize',length)]:
                tags+=tag(name,struct.pack('<I',value),(i,))
    if duplicate:
        tags+=tag(b'regionsCount',b'\0')*2
    ram=b'A'*4096+b'B'*4096
    tags+=bytes([62,6])+b'Memory'+struct.pack('<QQH',len(ram),len(ram)+(4096 if compressed else 0),0)+ram+b'\0\0'
    return struct.pack('<4sII',b'\xd2\xbe\xd2\xbe',0,1)+struct.pack('<64sQQ',b'memory',92,0)+tags


def layout(data):
    requests=[]
    def read(offset,count):
        requests.append(count);return data[offset:offset+count]
    result=checkpoint_layout(read,len(data))
    assert max(requests)<=80  # RAM payload is never read by the metadata parser.
    return result


def test_vmware_single_block_and_public_stacker(tmp_path):
    from volatility3.framework import contexts, exceptions
    from volatility3.framework.layers.physical import FileLayer
    data=checkpoint();p=tmp_path/'memory.vmss';p.write_bytes(data)
    ctx=contexts.Context();ctx.config['test.location']=p.as_uri()
    base=FileLayer(ctx,'test','source');ctx.layers.add_layer(base)
    mapped=MonolithicVmwareStacker.stack(ctx,'source')
    ctx.layers.add_layer(mapped)
    assert mapped.read(4094,4)==b'AABB'
    assert mapped.maximum_address==8191
    assert layout(data).memory_bytes==8192
    assert p.read_bytes()==data


def test_vmware_regions_preserve_physical_holes(tmp_path):
    from volatility3.framework import contexts, exceptions
    from volatility3.framework.layers.physical import FileLayer
    data=checkpoint([(0,0,1),(8,1,1)])
    p=tmp_path/'s.vmss';p.write_bytes(data)
    ctx=contexts.Context();ctx.config['test.location']=p.as_uri()
    ctx.layers.add_layer(FileLayer(ctx,'test','source'))
    mapped=MonolithicVmwareStacker.stack(ctx,'source');ctx.layers.add_layer(mapped)
    assert mapped.read(8*4096,4)==b'BBBB'
    with pytest.raises(exceptions.InvalidAddressException):mapped.read(4096,1)
    assert layout(data).segments[1][0]==8*4096


@pytest.mark.parametrize('data',[
    checkpoint(compressed=True),checkpoint(duplicate=True),checkpoint([(0,0,2),(1,0,1)]),
    checkpoint([(0,2,1)]),checkpoint()[:-4],b'\xd2\xbe\xd2\xbe'+b'\xff'*8,
])
def test_vmware_malformed_or_unavailable_mapping_is_rejected(data):
    with pytest.raises(CheckpointError):checkpoint_layout(lambda o,n:data[o:o+n],len(data))


@pytest.mark.parametrize('name,data,kind',[
    ('module.dwarf',b'.debug_info\nDW_TAG_compile_unit\n','auxiliary'),
    ('System.map-2.6.32-38-server',b'ffffffff81000000 T start_kernel\n','auxiliary'),
    ('s.vmsd',b'.encoding = "UTF-8"\nsnapshot.numSnapshots = "1"','auxiliary'),
    ('s.core',b'\x7fELF\x01'+b'\0'*100,'unsupported'),
    ('program.exe',b'MZ'+b'\0'*100,'auxiliary'),
    ('memory.dmp',b'PAGEDUMP'+b'\0'*100,'memory'),
    ('raw.bin',b'\0'*100,'memory'),
    ('s.vmss',checkpoint(),'memory'),
])
def test_preflight_distinguishes_auxiliary_from_memory(tmp_path,name,data,kind):
    p=tmp_path/name;p.write_bytes(data)
    result=inspect_source(p,'en')
    assert result['kind']==kind
    assert not any('\u0400'<=c<='\u04ff' for c in result['message'])


def test_symbol_import_copies_data_and_retains_source_hashes(tmp_path,monkeypatch):
    data=tmp_path/'app';source=tmp_path/'evidence-library';source.mkdir()
    monkeypatch.setattr(db,'DATA',data)
    (source/'windows').mkdir()
    original=b'{"metadata":{},"symbols":{}}'
    p=source/'windows/a.json';p.write_bytes(original)
    (source/'plugin.py').write_text('raise RuntimeError("must not run")')
    (source/'memory.raw').write_bytes(b'RAM')
    before={str(p.relative_to(source)):(p.stat().st_mtime_ns,p.read_bytes()) for p in source.rglob('*') if p.is_file()}
    paths=symbol_store.prepare([str(source)])
    managed=__import__('pathlib').Path(paths[1])
    assert paths[0]==str(data/'symbol-downloads')
    assert (managed/'windows/a.json').read_bytes()==original
    assert not (managed/'plugin.py').exists() and not (managed/'memory.raw').exists()
    manifest=json.loads((managed/'.studio-symbol-manifest').read_text())
    assert manifest['files'][0]['sha256']==hashlib.sha256(original).hexdigest()
    assert symbol_store.prepare([str(source)])==paths
    after={str(p.relative_to(source)):(p.stat().st_mtime_ns,p.read_bytes()) for p in source.rglob('*') if p.is_file()}
    assert before==after
    p.write_bytes(original+b' ')
    new=symbol_store.prepare([str(source)])
    assert new[1]!=paths[1] and (managed/'windows/a.json').read_bytes()==original


def test_cancelled_symbol_import_removes_only_own_staging(tmp_path,monkeypatch):
    monkeypatch.setattr(db,'DATA',tmp_path/'app')
    source=tmp_path/'source';source.mkdir();(source/'a.json').write_bytes(b'x'*100)
    stop=False
    def progress(_):
        nonlocal stop
        stop=True
    with pytest.raises(InterruptedError):symbol_store.prepare([str(source)],progress,lambda:stop)
    assert not list((db.DATA/'symbol-libraries').glob('.staging-*'))
    assert (source/'a.json').read_bytes()==b'x'*100


@pytest.mark.parametrize('system,expected',[('light','light'),('dark','dark'),(None,'dark'),('unavailable','dark')])
def test_initial_theme_follows_windows_with_dark_fallback(system,expected,monkeypatch,tmp_path):
    from volstudio import localization
    if localization.os.name!='nt':pytest.skip('Windows application theme integration')
    def read():
        if system=='unavailable':raise OSError('Registry setting is unavailable')
        return system
    monkeypatch.setattr(localization,'windows_app_theme',read)
    monkeypatch.setattr(db,'DATA',tmp_path/'theme-state');db.init()
    assert localization.default_theme()==expected
    assert db.settings()['theme']==expected
    # A saved explicit choice always wins over the system default.
    selected='dark' if expected=='light' else 'light'
    db.save_settings({'theme':selected})
    assert db.settings()['theme']==selected
