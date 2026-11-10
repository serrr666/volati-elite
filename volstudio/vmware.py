"""Read-only mapping for uncompressed, monolithic VMware checkpoints.

Format reference: Volatility Foundation's VMware-Snapshot-File documentation.
No VM is resumed, no executable is run, and no extracted RAM copy is required.
Split VMEM + metadata remains handled by Volatility's original VmwareStacker.
"""
from __future__ import annotations

import logging
import struct
from dataclasses import dataclass
from typing import Callable

MAGICS = {b'\xd0\xbe\xd2\xbe', b'\xd1\xba\xd1\xba', b'\xd2\xbe\xd2\xbe', b'\xd3\xbe\xd3\xbe'}


class CheckpointError(ValueError):
    pass


@dataclass(frozen=True)
class Layout:
    version: int
    segments: tuple[tuple[int, int, int, int], ...]
    memory_bytes: int


def checkpoint_layout(read: Callable[[int, int], bytes], size: int) -> Layout:
    """Parse only bounded metadata; skip the (potentially huge) memory payload.

    Segments contain physical address, file offset, length, mapped length.
    Missing regions remain unmapped; never invent zero-filled physical memory.
    """
    def take(offset, count):
        if offset < 0 or count < 0 or count > 65536 or offset + count > size:
            raise CheckpointError('VMware metadata points outside the file')
        if count == 0:
            return b''
        value = read(offset, count)
        if len(value) != count:
            raise CheckpointError('Truncated VMware metadata')
        return value

    magic, _, groups = struct.unpack('<4sII', take(0, 12))
    if magic not in MAGICS:
        raise CheckpointError('Not a VMware checkpoint')
    if not 0 < groups <= 4096 or 12 + groups * 80 > size:
        raise CheckpointError('Invalid VMware group table')
    version = magic[0] & 15
    memory_at = None
    for i in range(groups):
        name, location, _ = struct.unpack('<64sQQ', take(12 + i * 80, 80))
        if name.rstrip(b'\0') == b'memory':
            if memory_at is not None:
                raise CheckpointError('Duplicate VMware memory group')
            memory_at = location
    if memory_at is None:
        raise CheckpointError('VMware checkpoint has no memory group')

    tags = {}
    cursor = memory_at
    for _ in range(20000):
        flags, name_length = take(cursor, 2)
        if flags == name_length == 0:
            break
        name = take(cursor + 2, name_length)
        indices_count = (flags >> 6) & 3
        indices_at = cursor + 2 + name_length
        indices = struct.unpack('<' + 'I' * indices_count, take(indices_at, indices_count * 4))
        data_at = indices_at + indices_count * 4
        disk_length = memory_length = flags & 63
        if disk_length in (62, 63):
            width = 4 if version == 0 else 8
            sizes = take(data_at, width * 2 + 2)
            disk_length = int.from_bytes(sizes[:width], 'little')
            memory_length = int.from_bytes(sizes[width:width * 2], 'little')
            padding = int.from_bytes(sizes[width * 2:], 'little')
            data_at += width * 2 + 2 + padding
        if data_at + disk_length > size:
            raise CheckpointError('VMware data block points outside the file')
        key = (name, indices)
        if key in tags:
            raise CheckpointError('Duplicate VMware memory tag')
        scalar = int.from_bytes(take(data_at, disk_length), 'little') if disk_length <= 8 else None
        tags[key] = (data_at, disk_length, memory_length, scalar)
        cursor = data_at + disk_length
    else:
        raise CheckpointError('VMware memory tag limit exceeded')

    blocks = [value for (name, _), value in tags.items() if name == b'Memory']
    if len(blocks) != 1:
        raise CheckpointError('No single embedded RAM block; this checkpoint may require a companion VMEM file')
    block_at, disk_length, memory_length, _ = blocks[0]
    if disk_length != memory_length or not disk_length or disk_length % 4096:
        raise CheckpointError('Compressed or non-page-aligned VMware RAM is not supported')

    def scalar(name, indices=()):
        value = tags.get((name, indices))
        if value is None or value[3] is None:
            raise CheckpointError('Missing VMware memory mapping field: ' + name.decode('ascii'))
        return value[3]

    region_tag = tags.get((b'regionsCount', ()))
    regions = region_tag[3] if region_tag else 0
    if regions is None or regions > 4096:
        raise CheckpointError('Invalid VMware memory region count')
    segments = []
    if not regions:
        segments.append((0, block_at, disk_length, disk_length))
    else:
        for i in range(regions):
            physical = scalar(b'regionPPN', (i,)) * 4096
            relative = scalar(b'regionPageNum', (i,)) * 4096
            length = scalar(b'regionSize', (i,)) * 4096
            if not length or relative + length > disk_length or physical + length > 2**64:
                raise CheckpointError('Invalid VMware RAM region extent')
            segments.append((physical, block_at + relative, length, length))
    segments.sort()
    for previous, current in zip(segments, segments[1:]):
        if previous[0] + previous[2] > current[0]:
            raise CheckpointError('Overlapping VMware physical memory regions')
    return Layout(version, tuple(segments), sum(s[2] for s in segments))


# Public Volatility extension points. Importing this module registers the stacker
# through StackerLayerInterface's subclass discovery, without patching the CLI.
from volatility3.framework import exceptions, interfaces
from volatility3.framework.configuration import requirements
from volatility3.framework.layers import physical, segmented


class MonolithicVmwareLayer(segmented.SegmentedLayer):
    def _load_segments(self):
        base = self.context.layers[self._base_layer]
        layout = checkpoint_layout(base.read, base.maximum_address + 1)
        self._segments = list(layout.segments)

    @classmethod
    def get_requirements(cls):
        return [requirements.TranslationLayerRequirement(name='base_layer', optional=False)]


class MonolithicVmwareStacker(interfaces.automagic.StackerLayerInterface):
    stack_order = 19

    @classmethod
    def stack(cls, context, layer_name, progress_callback=None):
        base = context.layers[layer_name]
        if not isinstance(base, physical.FileLayer) or base.maximum_address < 11:
            return None
        if base.read(0, 4) not in MAGICS:
            return None
        name = context.layers.free_layer_name('MonolithicVmwareLayer')
        config = interfaces.configuration.path_join('automagic', 'layer_stacker', 'stack', name)
        context.config[config + '.base_layer'] = layer_name
        try:
            return MonolithicVmwareLayer(context, config, name)
        except (CheckpointError, exceptions.InvalidAddressException) as exc:
            logging.getLogger(__name__).warning('VMware checkpoint mapping unavailable: %s', exc)
            return None
