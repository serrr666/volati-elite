"""Explicit synthetic fixtures for exploring the interface without a memory image."""
from datetime import datetime, timedelta, timezone

PROCESSES = [
    (4, 0, "System", 180), (88, 4, "Registry", 4), (336, 4, "smss.exe", 3),
    (476, 448, "csrss.exe", 13), (552, 448, "wininit.exe", 1),
    (684, 552, "services.exe", 7), (712, 552, "lsass.exe", 10),
    (940, 684, "svchost.exe", 24), (1120, 684, "svchost.exe", 15),
    (1384, 684, "spoolsv.exe", 9), (2248, 2144, "explorer.exe", 54),
    (3680, 2248, "msedge.exe", 34), (3744, 3680, "msedge.exe", 19),
    (4128, 2248, "WindowsTerminal.exe", 16), (4280, 4128, "powershell.exe", 12),
    (4860, 4280, "rundll32.exe", 5), (5204, 2248, "notepad.exe", 6),
]


def rows(plugin):
    name = plugin.split(".")[-1].lower()
    if name in ("pslist", "psscan", "pstree", "psxview"):
        return [{"PID": pid, "PPID": ppid, "ImageFileName": image, "Offset(V)": hex(0xffffa30450000000 + pid * 0x1000),
                 "Threads": threads, "Handles": 90 + threads * 17, "SessionId": 0 if pid < 2000 else 1,
                 "Wow64": False, "CreateTime": f"2026-10-28T09:{10 + i:02}:04+00:00", "ExitTime": None}
                for i, (pid, ppid, image, threads) in enumerate(PROCESSES)]
    if name in ("netscan", "netstat", "sockscan"):
        data = [(4, "System", "0.0.0.0", 445, "0.0.0.0", 0, "LISTENING"),
                (940, "svchost.exe", "0.0.0.0", 135, "0.0.0.0", 0, "LISTENING"),
                (3680, "msedge.exe", "192.0.2.24", 50481, "203.0.113.20", 443, "ESTABLISHED"),
                (3680, "msedge.exe", "192.0.2.24", 50482, "203.0.113.21", 443, "ESTABLISHED"),
                (4280, "powershell.exe", "192.0.2.24", 51024, "198.51.100.42", 8443, "ESTABLISHED"),
                (1120, "svchost.exe", "192.0.2.24", 5353, "224.0.0.251", 5353, "N/A")]
        return [{"Offset": hex(0xffffa3045abc0000 + i * 0x100), "Proto": "TCPv4" if i < 5 else "UDPv4",
                 "LocalAddr": local, "LocalPort": lp, "ForeignAddr": remote, "ForeignPort": rp,
                 "State": state, "PID": pid, "Owner": owner, "Created": "2026-10-28T09:24:18+00:00"}
                for i, (pid, owner, local, lp, remote, rp, state) in enumerate(data)]
    if name == "cmdline":
        args = {4280: 'powershell.exe -NoProfile -File C:\\Lab\\collect.ps1',
                4860: 'rundll32.exe C:\\Lab\\sample.dll,EntryPoint', 5204: 'notepad.exe C:\\Lab\\notes.txt'}
        return [{"PID": pid, "Process": image, "Args": args.get(pid, f"C:\\Windows\\System32\\{image}")}
                for pid, _, image, _ in PROCESSES]
    if name == "malfind":
        return [{"PID": 4860, "Process": "rundll32.exe", "Start VPN": "0x1f200000", "End VPN": "0x1f20ffff",
                 "Tag": "VadS", "Protection": "PAGE_EXECUTE_READWRITE", "CommitCharge": 3,
                 "PrivateMemory": 1, "File output": "Disabled", "Notes": "Synthetic executable private region; review required"}]
    if name == "dlllist":
        return [{"PID": pid, "Process": "rundll32.exe", "Base": hex(0x7ff600000000 + i * 0x100000),
                 "Size": size, "Name": n, "Path": path, "LoadTime": "2026-10-28T09:25:04+00:00"}
                for i, (n, path, size) in enumerate([
                    ("rundll32.exe", "C:\\Windows\\System32\\rundll32.exe", 86016),
                    ("ntdll.dll", "C:\\Windows\\System32\\ntdll.dll", 2064384),
                    ("kernel32.dll", "C:\\Windows\\System32\\kernel32.dll", 815104),
                    ("sample.dll", "C:\\Lab\\sample.dll", 65536)]) for pid in [4860]]
    if name == "info":
        return [{"Variable": k, "Value": v} for k, v in {
            "Kernel Base": "0xf8032bc00000", "DTB": "0x1aa000", "Symbols": "SYNTHETIC DEMO — no image analysed",
            "Is64Bit": "True", "IsPAE": "False", "layer_name": "WindowsIntel32e", "Number of Processors": "8",
            "SystemTime": "2026-10-28T09:32:00+00:00", "NtMajorVersion": "10", "NtMinorVersion": "0",
            "NTBuildLab": "22621.1.amd64fre.ni_release.220506-1250"}.items()]
    if name == "svcscan":
        return [{"PID": pid, "Name": n, "Display": d, "State": "SERVICE_RUNNING", "Start": "AUTO_START", "Binary": b}
                for pid, n, d, b in [(940, "RpcSs", "Remote Procedure Call", "svchost.exe -k rpcss"),
                                     (1384, "Spooler", "Print Spooler", "spoolsv.exe")]]
    raise ValueError("Для этого плагина нет демонстрационных данных. Откройте дамп для настоящего анализа.")
