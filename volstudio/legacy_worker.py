"""Launch the separately installed engine from a dedicated Studio worker."""
import ctypes
import json
import os
from pathlib import Path
import subprocess
import sys
import traceback

from .legacy import PLUGINS, PROFILE, runtime


def run(job_path):
    job = json.loads(Path(job_path).read_text(encoding='utf-8'))
    with open(job['stderr'], 'wb') as log:
        try:
            python, entry = runtime() or (None, None)
            if python is None:
                raise RuntimeError('Volatility 2 component is unavailable')
            if job['profile'] != PROFILE or job['plugin'] not in PLUGINS:
                raise ValueError('Unsupported Volatility 2 request')
            cwd = Path(job_path).parent
            env = os.environ.copy()
            for key in ('VOLSTUDIO_TOKEN', 'PYTHONPATH', 'PYTHONHOME', 'PYTHONUTF8', 'VOLATILITY_LOCATION', 'VOLATILITY_PROFILE'):
                env.pop(key, None)
            if getattr(sys, 'frozen', False):
                ctypes.windll.kernel32.SetDllDirectoryW(None)
                bundled = Path(sys._MEIPASS).resolve()
                env['PATH'] = os.pathsep.join(path for path in env.get('PATH', '').split(os.pathsep)
                                              if path and not Path(path.strip('"')).resolve().is_relative_to(bundled))
            bridge = Path(__file__).with_name('legacy_bridge.py').read_text(encoding='ascii')
            payload = {**job, 'entry': str(entry), 'plugin': PLUGINS[job['plugin']], 'result': job['stdout'],
                       'partial': str(cwd / 'legacy-result.part'), 'config': str(cwd / 'legacy.conf'),
                       'cache': str(cwd / 'legacy-cache')}
            process = subprocess.run([str(python), '-E', '-s', '-B', '-c', bridge], cwd=cwd, env=env,
                                     input=(json.dumps(payload) + '\n').encode('ascii'), stdout=log, stderr=log,
                                     creationflags=subprocess.CREATE_NO_WINDOW)
            return process.returncode or (0 if Path(job['stdout']).is_file() else 1)
        except Exception:
            log.write(traceback.format_exc().encode('utf-8', errors='replace'))
            return 1


if __name__ == '__main__':
    raise SystemExit(run(sys.argv[1]))
