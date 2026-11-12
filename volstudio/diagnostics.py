import re


CONSOLE_PLUGINS = {"windows.consoles.Consoles", "windows.cmdscan.CmdScan"}
UNSUPPORTED_BUILD = re.compile(
    r"^NotImplementedError: This version of Windows is not supported: "
    r"(?P<nt>\d{1,3}\.\d{1,3}) \d{1,5}\.(?P<build>\d{1,8})!?\s*$",
    re.MULTILINE,
)


def unsupported_console_build(plugin: str, error: str | None) -> str | None:
    if plugin not in CONSOLE_PLUGINS or not error:
        return None
    match = UNSUPPORTED_BUILD.search(error)
    return f"{match['nt']}.{match['build']}" if match else None
