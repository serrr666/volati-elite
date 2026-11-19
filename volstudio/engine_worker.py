"""File-based worker protocol also works in a windowed, frozen executable."""
import json
import os
import sys
import traceback
from pathlib import Path
from .artifact_files import MANIFEST


def run_with_artifact_history(output_dir):
    from volatility3.cli import CommandLine

    with (output_dir / MANIFEST).open('w', encoding='utf-8', buffering=1) as manifest:
        class TrackingCLI(CommandLine):
            def file_handler_class_factory(self, direct=True):
                handler = super().file_handler_class_factory(direct)

                class TrackedFile(handler):
                    def close(self):
                        if self.closed:
                            return
                        self.flush()
                        if direct:
                            size = os.fstat(self.fileno()).st_size
                        else:
                            size = self.getbuffer().nbytes
                        super().close()
                        manifest.write(json.dumps({'name': self.preferred_filename, 'size': size}) + '\n')

                return TrackedFile

        TrackingCLI().run()


def run(job_path):
    job = json.loads(Path(job_path).read_text(encoding="utf-8"))
    with open(job["stdout"], "w", encoding="utf-8") as out, open(job["stderr"], "w", encoding="utf-8", buffering=1) as err:
        sys.stdout, sys.stderr = out, err
        sys.argv = ["vol", *job["args"]]
        try:
            from . import rendering  # register the streaming renderer through Volatility's public interface
            from . import vmware  # register read-only monolithic checkpoint support
            run_with_artifact_history(Path(job["stdout"]).parent)
        except SystemExit as exc:
            return exc.code if isinstance(exc.code, int) else 1
        except BaseException:
            traceback.print_exc(file=err)
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(run(sys.argv[1]))
