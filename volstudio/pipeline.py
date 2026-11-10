"""Typed streaming pipelines. No command shell, eval, or whole-image reads."""
from __future__ import annotations

import hashlib
import json
import operator
import re
import sqlite3
import sys
import time
import traceback
from functools import lru_cache
from pathlib import Path
from typing import Literal
from decimal import Decimal, InvalidOperation

from pydantic import BaseModel, Field, model_validator

CHUNK_SIZE = 4 * 1024 * 1024
STRING_FRAGMENT = 65536


class Step(BaseModel):
    op: Literal["contains", "exclude", "compare", "select", "split", "unique"]
    field: str = Field(default="", max_length=256)
    value: str = Field(default="", max_length=4096)
    fields: list[str] = Field(default_factory=list, max_length=100)
    ignore_case: bool = True
    comparison: Literal["eq", "ne", "gt", "ge", "lt", "le"] = "eq"
    delimiter: str = Field(default="", max_length=16)

    @model_validator(mode="after")
    def valid(self):
        self.field = self.field.strip()
        self.fields = [field.strip() for field in self.fields]
        if self.op in ("contains", "exclude", "compare") and not self.value:
            raise ValueError("Введите значение фильтра")
        if self.op in ("compare", "split") and not self.field:
            raise ValueError("Выберите поле")
        if self.op == "select" and not self.fields:
            raise ValueError("Выберите хотя бы одно поле")
        if any(not f or len(f) > 256 for f in self.fields):
            raise ValueError("Некорректное имя поля")
        if self.op == "compare" and self.comparison not in ("eq", "ne"):
            number(self.value)  # Validate before accepting the job.
        return self


class PipelineInput(BaseModel):
    source: Literal["image", "results"] = "results"
    source_run: str = Field(default="", max_length=64)
    encoding: Literal["ascii", "utf16le", "both"] = "both"
    unicode: bool = False
    min_length: int = Field(default=4, ge=4, le=256)
    max_rows: int = Field(default=50000, ge=1, le=1000000)
    steps: list[Step] = Field(default_factory=list, max_length=20)

    @model_validator(mode="after")
    def normalize_source(self):
        # A file scan has no parent plugin run. Do not retain a stale selection
        # in the persisted request, command, or execution provenance.
        if self.source == "image":
            self.source_run = ""
        return self


def number(value):
    text = str(value).strip()
    try:
        value = int(text, 0) if text.lower().lstrip("+-").startswith(("0x", "0o", "0b")) else Decimal(text)
    except (TypeError, ValueError, InvalidOperation):
        raise ValueError("Для числового сравнения требуется число")
    if isinstance(value, Decimal) and not value.is_finite():
        raise ValueError("Требуется конечное число")
    return value


class StringStream:
    """Keep only a bounded unfinished run; split long runs without dropping bytes."""
    def __init__(self, encoding, minimum):
        self.encoding, self.minimum = encoding, minimum
        self.width = 1 if encoding == "ascii" else 2
        self.pattern = re.compile(rb"[\x20-\x7e]+" if self.width == 1 else rb"(?:[\x20-\x7e]\x00|[\x00-\xff]\x04)+")
        # Skip short interior ASCII runs inside the C regex engine. Keep a
        # short trailing run so strings spanning chunks are never discarded.
        # UTF-16 retains its original matching/alignment semantics.
        self.required=None
        self.ignore_case=True
        self.scanned_rows=0
        self.continuation_pattern=None
        if self.width==1:
            unit=rb"[\x20-\x7e]"
            bounded=unit+b"{"+str(minimum).encode()+b",}|"+unit+b"{1,"+str(minimum-1).encode()+b"}\\Z"
            self.pattern=re.compile(bounded)
            self.continuation_pattern=re.compile(bounded+b"|\\A"+unit+b"{1,"+str(minimum-1).encode()+b"}")
        self.pending = b""
        self.continued = False

    def feed(self, chunk, position, eof=False):
        data = self.pending + chunk
        base = position - len(self.pending)
        previous_continued = self.continued
        self.pending, self.continued = b"", False
        held = False
        pattern=self.continuation_pattern if previous_continued and self.continuation_pattern is not None else self.pattern
        matches=pattern.finditer(data)
        for match in matches:
            start, end = match.span()
            continued = previous_continued and start == 0
            trailing = end >= len(data) - (self.width - 1) and not eof
            raw = match.group()
            if len(raw) < self.minimum * self.width and not continued and not trailing:
                continue
            size = STRING_FRAGMENT * self.width
            cursor = 0
            while len(raw) - cursor >= size:
                yield self.row(raw[cursor:cursor+size], base+start+cursor, True)
                cursor += size
                continued = True
            remainder = raw[cursor:]
            if trailing:
                self.pending = remainder + data[end:]
                self.continued = continued
                held = True
            elif remainder and (continued or len(remainder) >= self.minimum * self.width):
                yield self.row(remainder, base+start+cursor, continued)
        if self.width == 2 and data and not eof and not held:
            self.pending = data[-1:]

    def row(self, raw, offset, fragment):
        self.scanned_rows+=1
        # The first ASCII Text/contains filter can reject binary fragments
        # before allocating decoded text and dictionaries. apply_steps still
        # validates every candidate using the original Unicode-aware semantics.
        if self.required is not None and self.required not in (raw.lower() if self.ignore_case else raw):
            return None
        return {"Offset": f"0x{offset:x}", "Encoding": self.encoding,
                "Text": raw.decode("ascii" if self.encoding == "ascii" else "utf-16le"), "Fragment": fragment,
                "_source_offset": f"0x{offset:x}"}


@lru_cache(maxsize=1)
def printable_unicode():
    """Use Unicode printable scalar values; exclude controls and lone surrogates."""
    ranges=[];start=None
    for code in range(0x110001):
        allowed=code<0x110000 and chr(code).isprintable()
        if allowed and start is None:start=code
        if not allowed and start is not None:
            escape=lambda value: f'\\U{value:08x}'
            ranges.append(escape(start) if code-1==start else escape(start)+'-'+escape(code-1))
            start=None
    return re.compile('['+''.join(ranges)+']+')


class UnicodeStringStream:
    """One byte-alignment lane, bounded UTF-16 decoding with exact byte offsets.

    The opt-in Unicode scan uses both lanes: an unaligned string is valid evidence.
    Binary data can also decode as printable Unicode; the GUI discloses that noise.
    """
    def __init__(self, minimum, alignment):
        self.minimum,self.alignment=minimum,alignment
        self.pending=b'';self.continued=False;self.started=False
        self.pattern=printable_unicode()

    def feed(self, chunk, position, eof=False):
        if not self.started:
            # CHUNK_SIZE may be one byte; consume the lane's prefix only once.
            if self.alignment:
                skip=min(len(chunk),self.alignment);chunk=chunk[skip:];position+=skip
                self.alignment-=skip
                if self.alignment:return
            self.started=True
        data=self.pending+chunk;base=position-len(self.pending)
        previous=self.continued;self.pending=b'';self.continued=False
        usable=len(data)&~1
        if not eof and usable>=2 and 0xD800<=int.from_bytes(data[usable-2:usable],'little')<=0xDBFF:
            usable-=2
        decoded=data[:usable].decode('utf-16le',errors='surrogatepass');tail=data[usable:]
        char_cursor=byte_cursor=0;held=False
        for match in self.pattern.finditer(decoded):
            start,end=match.span()
            byte_cursor+=len(decoded[char_cursor:start].encode('utf-16le',errors='surrogatepass'))
            continued=previous and start==0
            text=match.group();offset=base+byte_cursor;cursor=0
            while len(text)-cursor>=STRING_FRAGMENT:
                part=text[cursor:cursor+STRING_FRAGMENT]
                yield self.row(part,offset,True)
                offset+=len(part.encode('utf-16le'));cursor+=len(part);continued=True
            remainder=text[cursor:]
            if end==len(decoded) and not eof:
                self.pending=remainder.encode('utf-16le')+tail
                self.continued=continued;held=True
            elif remainder and (continued or len(text)>=self.minimum):
                yield self.row(remainder,offset,continued)
            byte_cursor+=len(text.encode('utf-16le'));char_cursor=end
        if not held and not eof:self.pending=tail

    @staticmethod
    def row(text,offset,fragment):
        return {'Offset':hex(offset),'Encoding':'utf16le','Text':text,'Fragment':fragment,'_source_offset':hex(offset)}


def image_rows(path, config, progress, counters=None):
    encodings = ("ascii", "utf16le") if config.encoding == "both" else (config.encoding,)
    streams=[]
    for encoding in encodings:
        if encoding=='utf16le' and config.unicode:
            streams.extend(UnicodeStringStream(config.min_length,alignment) for alignment in (0,1))
        else:
            streams.append(StringStream(encoding,config.min_length))
    first=config.steps[0] if config.steps else None
    fast=bool(counters is not None and not config.unicode and first and first.op=='contains' and first.field=='Text' and first.value.isascii())
    if fast:
        for stream in streams:
            needle=first.value.lower() if first.ignore_case else first.value
            stream.required=needle.encode('ascii' if stream.width==1 else 'utf-16le')
            stream.ignore_case=first.ignore_case
    position = 0
    size = path.stat().st_size
    try:
        with path.open("rb") as source:
            while chunk := source.read(CHUNK_SIZE):
                progress(position + len(chunk), size)
                for stream in streams:
                    for row in stream.feed(chunk,position):
                        if row is not None:yield row
                position += len(chunk)
            for stream in streams:
                for row in stream.feed(b"",position,eof=True):
                    if row is not None:yield row
    finally:
        if fast:counters['scanned_records']=sum(stream.scanned_rows for stream in streams)


def result_rows(database, run_id, progress):
    uri = Path(database).resolve().as_uri() + "?mode=ro"
    with sqlite3.connect(uri, uri=True) as connection:
        total = connection.execute("SELECT COUNT(*) FROM result_rows WHERE run_id=?", (run_id,)).fetchone()[0]
        for count, (idx, data) in enumerate(connection.execute("SELECT idx,data FROM result_rows WHERE run_id=? ORDER BY idx", (run_id,)), 1):
            row = json.loads(data)
            row.update(_source_run=run_id, _source_row=idx)
            yield row
            if count % 1000 == 0:
                progress(count, total)
        progress(total, total)


def text(value):
    if value is None:
        return ""
    return json.dumps(value, ensure_ascii=False) if isinstance(value, (dict, list)) else str(value)


def apply_steps(row, steps, distinct):
    provenance = {k: v for k, v in row.items() if k.startswith("_source_")}
    for index, step in enumerate(steps):
        if step.op in ("contains", "exclude"):
            haystack = text(row.get(step.field)) if step.field else "\n".join(text(v) for k, v in row.items() if not k.startswith("_source_"))
            needle = step.value
            if step.ignore_case:
                haystack, needle = haystack.casefold(), needle.casefold()
            found = needle in haystack
            if found != (step.op == "contains"):
                return None
        elif step.op == "compare":
            value = row.get(step.field)
            if value is None:
                return None
            compare = getattr(operator, step.comparison)
            if step.comparison in ("eq", "ne"):
                left, right = text(value), step.value
                if step.ignore_case:
                    left, right = left.casefold(), right.casefold()
            else:
                try:
                    left, right = number(value), number(step.value)
                except ValueError:
                    return None
            if not compare(left, right):
                return None
        elif step.op == "select":
            row = {name: row.get(name) for name in step.fields}
        elif step.op == "split":
            parts = text(row.get(step.field)).split(step.delimiter or None, 199)
            row = {**row, **{f"Field{i}": part for i, part in enumerate(parts, 1)}}
        elif step.op == "unique":
            fields = step.fields or sorted(k for k in row if not k.startswith("_source_"))
            digest = hashlib.sha256(json.dumps([row.get(k) for k in fields], sort_keys=True, ensure_ascii=False).encode()).digest()
            if not distinct.execute("INSERT OR IGNORE INTO seen VALUES (?,?)", (index, digest)).rowcount:
                return None
    return {**row, **provenance}


def execute(job):
    config = PipelineInput.model_validate(job["config"])
    output = Path(job["stdout"])
    scanned = emitted = read_units = total_units = 0
    last = 0.0
    def progress(done, total):
        nonlocal last, read_units, total_units
        read_units, total_units = done, total
        now = time.monotonic()
        if now - last >= .3 or done == total:
            print(f"Progress: {min(99, done / max(total, 1) * 100):.1f} Pipeline · {done:,}/{total:,}", flush=True)
            last = now
    if config.source == "image":
        path = Path(job["image"])
        before = path.stat()
        source_stats={}
        rows = image_rows(path, config, progress,source_stats)
    else:
        rows = result_rows(job["database"], config.source_run, progress)
    limited = False
    with sqlite3.connect(output.parent / "pipeline-distinct.sqlite3") as distinct, output.open("w", encoding="utf8", buffering=65536) as out:
        distinct.execute("CREATE TABLE IF NOT EXISTS seen(step INTEGER, digest BLOB, PRIMARY KEY(step,digest)) WITHOUT ROWID")
        for row in rows:
            scanned += 1
            result = apply_steps(row, config.steps, distinct)
            if result is None:
                continue
            if emitted >= config.max_rows:
                limited = True
                break
            out.write(json.dumps(result, ensure_ascii=False) + "\n")
            emitted += 1
        rows.close()
    if config.source == "image":
        scanned=source_stats.get('scanned_records',scanned)
    if config.source == "image":
        after = path.stat()
        if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
            raise ValueError("Source image changed during pipeline execution")
    summary = {"source": config.source, "source_run": config.source_run, "scanned_records": scanned,
               "output_rows": emitted, "limit_reached": limited, "max_rows": config.max_rows,
               "processed_units": read_units, "total_units": total_units, "unit": "bytes" if config.source == "image" else "rows",
               "string_fragment_chars": STRING_FRAGMENT if config.source == "image" else None}
    Path(job["summary"]).write_text(json.dumps(summary), encoding="utf8")
    print(json.dumps(summary), flush=True)
    return summary


def run(job_path):
    job = json.loads(Path(job_path).read_text(encoding="utf8"))
    with Path(job["stderr"]).open("w", encoding="utf8", buffering=1) as log:
        sys.stdout = sys.stderr = log
        try:
            execute(job)
            return 0
        except Exception:
            traceback.print_exc()
            return 1


if __name__ == "__main__":
    raise SystemExit(run(sys.argv[1]))
