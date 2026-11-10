"""Conservative source classification, independent of OS identification."""
from pathlib import Path
import re
import struct



def _ext_filesystem(head):
    # A magic alone can occur in unrelated bytes. Require coherent geometry
    # and inode sizes before treating the source as a disk/partition image.
    if len(head)<2048 or head[1080:1082]!=b'\x53\xef':
        return False
    sb=head[1024:2048]
    inodes,blocks,reserved,free_blocks,free_inodes,first,log_block=struct.unpack_from('<7I',sb)
    per_group=struct.unpack_from('<I',sb,32)[0]
    inodes_group=struct.unpack_from('<I',sb,40)[0]
    revision=struct.unpack_from('<I',sb,76)[0]
    if log_block>6 or revision>1:return False
    block_size=1024<<log_block
    inode_size=128 if revision==0 else struct.unpack_from('<H',sb,88)[0]
    return (inodes>0 and blocks>first and first==(1 if log_block==0 else 0)
            and reserved<=blocks and free_blocks<=blocks and free_inodes<=inodes
            and 0<per_group<=8*block_size and 0<inodes_group<=8*block_size
            and 128<=inode_size<=block_size and inode_size&(inode_size-1)==0)


def _inspect_source(path):
    path = Path(path)
    with path.open('rb') as stream:
        head = stream.read(65536)
        if head[:4] in (b'\xd0\xbe\xd2\xbe', b'\xd1\xba\xd1\xba', b'\xd2\xbe\xd2\xbe', b'\xd3\xbe\xd3\xbe'):
            from .vmware import CheckpointError, checkpoint_layout
            def read(offset, length):
                stream.seek(offset);return stream.read(length)
            try:
                checkpoint_layout(read, path.stat().st_size)
                return {'kind':'memory','format':'VMware checkpoint · embedded RAM',
                        'message':'Память читается непосредственно из контейнера VMware. Конвертация и копирование образа не требуются.'}
            except CheckpointError as exc:
                return {'kind':'unsupported','format':'VMware checkpoint · mapping unavailable',
                        'message':'Не удалось отобразить память VMware. Проверьте комплект VMSS/VMEM и журнал; сжатые блоки пока не поддерживаются. '+str(exc)}
    if head.startswith(b'ADSEGMENTEDFILE\x00'):
        return {'kind':'unsupported','format':'AD1 logical evidence container','message':'Это контейнер файлов AD1 (FTK), а не прямой образ RAM. Откройте его в FTK Imager и извлеките дамп памяти, если он есть внутри. Поиск строк читает байты контейнера без распаковки; его смещения не являются адресами памяти.'}
    if b'.debug_info' in head[:128] and b'DW_TAG_' in head:
        return {'kind':'auxiliary','format':'DWARF text · Volatility 2 profile data',
                'message':'Это текстовое описание типов Volatility 2, а не образ памяти. Доступен поиск строк; для анализа Linux в Volatility 3 нужен RAM-образ и подходящий ISF JSON.'}
    if re.search(rb'(?m)^[0-9a-fA-F]{8,16}\s+[A-Za-z]\s+\S+',head) and path.name.lower().startswith('system.map'):
        return {'kind':'auxiliary','format':'Linux System.map · kernel address map',
                'message':'Это карта адресов ядра, а не образ памяти. Она сама по себе не содержит процессов Linux и не заменяет ISF JSON.'}
    if b'snapshot.' in head and (path.suffix.lower()=='.vmsd' or head.startswith(b'.encoding')):
        return {'kind':'auxiliary','format':'VMware snapshot inventory · VMSD metadata',
                'message':'Это описание снимков VMware, а не содержимое RAM. Откройте соответствующий VMSS/VMEM/VMSN; поиск строк в метаданных доступен.'}
    if _ext_filesystem(head):
        return {'kind':'auxiliary','format':'ext filesystem partition image','message':'Это образ раздела с файловой системой ext, а не снимок RAM. Плагины процессов и сети здесь неприменимы. Используйте инструмент анализа дисков; поиск строк читает байты раздела без восстановления файлов.'}
    if head.startswith(b'\x7fELF'):
        byte_order='<' if len(head)>5 and head[5]==1 else '>' if len(head)>5 and head[5]==2 else None
        elf_type=struct.unpack_from(byte_order+'H',head,16)[0] if byte_order and len(head)>=18 else None
        if elf_type in (2,3):
            return {'kind':'auxiliary','format':'ELF executable or shared object','message':'Это ELF-файл программы или библиотеки, а не ELF core dump. Он не подтверждён как снимок RAM всей системы. Доступен поиск строк.'}
        if len(head)>4 and head[4]==1:
            return {'kind':'unsupported','format':'ELF32 container',
                    'message':'Слой ELF в установленном Volatility 3 поддерживает ELF64. Этот ELF32 нельзя автоматически считать совместимым RAM-образом; поиск строк доступен.'}
        fmt='ELF64 memory container'
    elif head[:4]==b'PAGE' and head[4:8] in (b'DUMP',b'DU64'):
        fmt='Windows crash dump'
    elif head.startswith(b'EMiL'):
        fmt='LiME memory container'
    elif head[:4].lower() in (b'hibr',b'wake'):
        fmt='Windows hibernation container'
    elif head.startswith(b'MZ'):
        return {'kind':'auxiliary','format':'PE file or process image',
                'message':'Файл начинается с PE/MZ. Это может быть программа или дамп отдельного процесса; он не подтверждён как снимок RAM всей системы. Доступны поиск строк и общие сканеры.'}
    else:
        fmt='Unknown container / possible raw memory'
    return {'kind':'memory','format':fmt,'message':''}


EN = {
 'Это образ раздела с файловой системой ext, а не снимок RAM. Плагины процессов и сети здесь неприменимы. Используйте инструмент анализа дисков; поиск строк читает байты раздела без восстановления файлов.':'This is an ext filesystem partition image, not a RAM capture. Process and network memory plugins do not apply. Use a disk forensics tool; string search reads partition bytes without recovering files.',
 'Это ELF-файл программы или библиотеки, а не ELF core dump. Он не подтверждён как снимок RAM всей системы. Доступен поиск строк.':'This is an ELF executable or shared library, not an ELF core dump. It is not a confirmed full-system RAM capture. String search is available.',

 'Это контейнер файлов AD1 (FTK), а не прямой образ RAM. Откройте его в FTK Imager и извлеките дамп памяти, если он есть внутри. Поиск строк читает байты контейнера без распаковки; его смещения не являются адресами памяти.':'This is an AD1 file container (FTK), not a directly readable RAM image. Open it in FTK Imager and extract a memory dump if one is included. String search reads container bytes without extraction; its offsets are not memory addresses.',
 'Память читается непосредственно из контейнера VMware. Конвертация и копирование образа не требуются.':'Memory is read directly from the VMware container; no conversion or image copy is required.',
 'Это текстовое описание типов Volatility 2, а не образ памяти. Доступен поиск строк; для анализа Linux в Volatility 3 нужен RAM-образ и подходящий ISF JSON.':'This is a Volatility 2 text type description, not a memory image. String search is available; Volatility 3 Linux analysis requires a RAM image and matching ISF JSON.',
 'Это карта адресов ядра, а не образ памяти. Она сама по себе не содержит процессов Linux и не заменяет ISF JSON.':'This is a kernel address map, not a memory image. It does not contain Linux processes and cannot replace ISF JSON.',
 'Это описание снимков VMware, а не содержимое RAM. Откройте соответствующий VMSS/VMEM/VMSN; поиск строк в метаданных доступен.':'This is VMware snapshot inventory metadata, not RAM. Open the corresponding VMSS/VMEM/VMSN; metadata string search is available.',
 'Слой ELF в установленном Volatility 3 поддерживает ELF64. Этот ELF32 нельзя автоматически считать совместимым RAM-образом; поиск строк доступен.':'The installed Volatility 3 ELF layer supports ELF64. This ELF32 container cannot be treated as a compatible RAM image; string search is available.',
 'Файл начинается с PE/MZ. Это может быть программа или дамп отдельного процесса; он не подтверждён как снимок RAM всей системы. Доступны поиск строк и общие сканеры.':'The file starts with PE/MZ. It may be an executable or an individual process image, not a confirmed full-system RAM capture. String search and generic scanners are available.',
}

def inspect_source(path, language='ru'):
    result=_inspect_source(path)
    if language=='en':
        message=result['message']
        prefix='Не удалось отобразить память VMware. Проверьте комплект VMSS/VMEM и журнал; сжатые блоки пока не поддерживаются. '
        result['message']=('VMware memory mapping is unavailable. Check the VMSS/VMEM file set and log; compressed blocks are not supported. '+message[len(prefix):]) if message.startswith(prefix) else EN.get(message,message)
    return result
