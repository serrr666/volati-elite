"""File-based worker protocol also works in a windowed, frozen executable."""
import json
import sys
import traceback
from pathlib import Path


def run(job_path):
    job = json.loads(Path(job_path).read_text(encoding="utf-8"))
    with open(job["stdout"], "w", encoding="utf-8") as out, open(job["stderr"], "w", encoding="utf-8", buffering=1) as err:
        sys.stdout, sys.stderr = out, err
        sys.argv = ["vol", *job["args"]]
        try:
            from . import rendering  # register the streaming renderer through Volatility's public interface
            from . import vmware  # register read-only monolithic checkpoint support
            from volatility3.cli import main
            main()
        except SystemExit as exc:
            return exc.code if isinstance(exc.code, int) else 1
        except BaseException:
            traceback.print_exc(file=err)
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(run(sys.argv[1]))
