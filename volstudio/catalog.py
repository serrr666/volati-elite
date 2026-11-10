"""Discover installed plugins in an isolated process; never invent plugin availability."""
from __future__ import annotations

import json
import os
import subprocess
import sys
from importlib.metadata import version

CATALOG = {"version": None, "plugins": [], "warnings": [], "status": "loading"}

GROUPS = {
    "process": ("pslist", "psscan", "pstree", "cmdline", "envars", "handles", "getsids", "getservicesids", "privs", "privileges", "threads", "thrdscan", "sessions", "psaux", "pscallstack", "dlllist", "librarylist", "maps", "memmap", "vadinfo", "vadwalk", "pidhashtable", "joblinks", "ptrace", "elfs", "capabilities"),
    "network": ("netscan", "netstat", "sockstat", "sockscan", "ifconfig", "addr", "link", "socketfilters", "arp"),
    "malware": ("malfind", "psxview", "hollowprocesses", "ldrmodules", "yarascan", "vadyarascan", "vmayarascan", "suspiciousthreads", "suspendedthreads", "skeletonkeycheck"),
    "registry": ("hivelist", "hivescan", "userassist", "amcache", "shimcachemem", "printkey", "hashdump", "lsadump", "cachedump"),
    "files": ("filescan", "dumpfiles", "mftscan", "ads", "residentdata", "lsof", "listfiles", "files", "mount", "mountinfo", "inodepages", "recoverfs", "symlinkscan"),
    "kernel": ("modules", "modscan", "driverscan", "driverirp", "callbacks", "ssdt", "kmsg", "dmesg", "lsmod", "moduleextract", "unloadedmodules", "kallsyms", "kthreads", "devicetree", "kpcrs", "iomem", "checksyscall", "checksysctl", "checktraptable"),
    "timeline": ("timeliner", "bash", "cmdscan", "consoles", "boottime"),
    "system": ("info", "banners", "verinfo", "svcscan", "svclist", "vmcoreinfo", "crashinfo", "frameworkinfo", "isfinfo"),
}


def category(name):
    parts = name.lower().split(".")
    if "registry" in parts:
        return "registry"
    if "malware" in parts:
        return "malware"
    if "orphan_kernel_threads" in parts:
        return "kernel"
    # Whole class/module names prevent collisions such as ReSIDentData -> SIDs.
    names = {part.replace("_", "") for part in parts[-2:]}
    for group, parts in GROUPS.items():
        if names.intersection(parts):
            return group
    return "other"


def discover(plugin_dirs):
    import volatility3.plugins
    from volatility3 import framework
    from volatility3.framework.configuration import requirements
    from pathlib import Path

    volatility3.plugins.__path__ = [str(Path(p).resolve()) for p in plugin_dirs] + list(volatility3.plugins.__path__)
    failures = framework.import_files(volatility3.plugins, True)
    plugins = []
    for name, cls in framework.list_plugins().items():
        args = []
        for r in cls.get_requirements():
            kind = None
            if isinstance(r, requirements.BooleanRequirement):
                kind = "boolean"
            elif isinstance(r, requirements.IntRequirement):
                kind = "integer"
            elif isinstance(r, requirements.ChoiceRequirement):
                kind = "choice"
            elif isinstance(r, requirements.ListRequirement):
                kind = "list_int" if r.element_type is int else "list"
            elif isinstance(r, requirements.StringRequirement):
                kind = "string"
            if kind:
                args.append({"name": r.name, "type": kind, "description": r.description,
                             "optional": r.optional, "default": r.default,
                             "choices": list(getattr(r, "choices", []))})
        doc = (cls.__doc__ or "").strip()
        plugins.append({"id": name, "name": name.split(".")[-1],
                        "os": name.split(".")[0] if name.split(".")[0] in ("windows", "linux", "mac") else "generic",
                        "category": category(name), "description": doc, "args": args,
                        "version": ".".join(map(str, getattr(cls, "_version", (1, 0, 0))))})
    return {"version": version("volatility3"), "plugins": sorted(plugins, key=lambda p: p["id"]),
            "warnings": failures, "status": "ready"}


def refresh(settings, publish=True):
    global CATALOG
    try:
        if getattr(sys, "frozen", False):
            from . import db
            output = db.DATA / "catalog-discovery.json"
            output.parent.mkdir(parents=True,exist_ok=True)
            command = [sys.executable,"--catalog",str(output),json.dumps(settings["plugin_dirs"])]
        else:
            command = [sys.executable,"-m","volstudio.catalog",json.dumps(settings["plugin_dirs"])]
        proc = subprocess.run(command,
                              capture_output=True, text=True, encoding="utf-8", timeout=120,
                              env={**os.environ, "PYTHONUTF8": "1"},
                              creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
        if proc.returncode:
            raise RuntimeError(proc.stderr[-4000:])
        result = json.loads(output.read_text(encoding="utf-8")) if getattr(sys,"frozen",False) else json.loads(proc.stdout)
    except Exception as exc:
        result = {"version": None, "plugins": [], "warnings": [str(exc)], "status": "error"}
    if publish:
        CATALOG=result
    return result


def get_plugin(plugin_id):
    return next((p for p in CATALOG["plugins"] if p["id"] == plugin_id), None)


def validate_params(plugin, params):
    arguments = {a["name"]: a for a in plugin["args"]}
    result = {}
    for key, value in params.items():
        if key not in arguments:
            raise ValueError(f"Unknown plugin parameter: {key}")
        a = arguments[key]
        if value is None or value == "" or value == []:
            continue
        if a["type"] == "boolean":
            if not isinstance(value, bool):
                raise ValueError(f"{key}: expected boolean")
        elif a["type"] == "integer":
            value = integer(value)
        elif a["type"].startswith("list"):
            value = value if isinstance(value, list) else str(value).replace(",", " ").split()
            value = [integer(v) for v in value] if a["type"] == "list_int" else [str(v) for v in value]
        else:
            value = str(value)
            if a["type"] == "choice" and value not in a["choices"]:
                raise ValueError(f"{key}: invalid choice")
        result[key] = value
    for a in arguments.values():
        if not a["optional"] and a["default"] is None and a["name"] not in result:
            raise ValueError(f"Required parameter: {a['name']}")
    return result


def integer(value):
    if isinstance(value,bool) or isinstance(value,float):
        raise ValueError("Expected an integer, not a boolean or fraction")
    if isinstance(value,str):
        text=value.strip()
        return int(text,0 if text.lstrip('+-').lower().startswith(('0x','0o','0b')) else 10)
    return int(value)


if __name__ == "__main__":
    print(json.dumps(discover(json.loads(sys.argv[1])), ensure_ascii=False, default=str))
