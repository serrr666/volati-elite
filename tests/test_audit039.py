import struct
import pytest
from volstudio.preflight import inspect_source
from volstudio import runner,db

def ext_superblock():
    data=bytearray(4096)
    struct.pack_into('<7I',data,1024,100,1000,0,100,20,0,2)
    struct.pack_into('<I',data,1056,32768)
    struct.pack_into('<I',data,1064,8192)
    data[1080:1082]=b'\x53\xef'
    struct.pack_into('<I',data,1100,1)
    struct.pack_into('<H',data,1112,256)
    return data

def test_ext_partition_is_not_queued_as_system_ram(tmp_path):
    p=tmp_path/'renamed.mem';p.write_bytes(ext_superblock())
    r=inspect_source(p,'en')
    assert r['kind']=='auxiliary' and 'partition' in r['format']
    assert 'not a RAM' in r['message'] and 'without recovering files' in r['message']

@pytest.mark.parametrize('offset,fmt,value',[(1024,'I',0),(1028,'I',0),(1048,'I',30),(1056,'I',0),(1064,'I',0),(1100,'I',9),(1112,'H',127),(1112,'H',129),(1036,'I',1001)])
def test_isolated_ext_magic_or_bad_geometry_does_not_block_memory(tmp_path,offset,fmt,value):
    d=ext_superblock();struct.pack_into('<'+fmt,d,offset,value)
    p=tmp_path/'ram.img';p.write_bytes(d)
    assert inspect_source(p)['kind']=='memory'

@pytest.mark.parametrize('bits',[1,2])
@pytest.mark.parametrize('elftype',[2,3])
def test_elf_executable_is_not_a_core_dump(tmp_path,bits,elftype):
    d=bytearray(4096);d[:6]=b'\x7fELF'+bytes([bits,1]);struct.pack_into('<H',d,16,elftype)
    p=tmp_path/'renamed.img';p.write_bytes(d)
    assert inspect_source(p)['kind']=='auxiliary'

def test_linux_both_requirements_does_not_blame_image_corruption(monkeypatch):
    monkeypatch.setattr(db,'settings',lambda:{'language':'en'})
    raw='Unsatisfied requirement plugins.PsList.kernel.layer_name; Unable to validate plugins.PsList.kernel.symbol_table_name'
    text=runner.friendly_error(raw,'linux')
    assert 'ISF JSON' in text and 'does not prove image corruption' in text and text.endswith(raw)
    assert 'ISF JSON' not in runner.friendly_error(raw,'windows')
