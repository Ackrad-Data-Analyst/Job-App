#!/usr/bin/env python3
"""Build a private, self-contained correction script. Never commit its output."""

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BOOTSTRAP = '''#!/usr/bin/env python3
"""Private CareerPilot profile correction. Keep this file private."""
import argparse
import os
from pathlib import Path
import subprocess
import sys

_parser = argparse.ArgumentParser(description=__doc__)
_parser.add_argument('--app', type=Path)
_args = _parser.parse_args()
_choices = [_args.app] if _args.app else [Path(__file__).resolve().parent, Path.cwd(), Path.home() / 'Downloads' / 'Job-App-careerpilot-recovery']
_app = next((p.resolve() for p in _choices if p and (p / 'start.py').is_file() and (p / 'apps/api').is_dir()), None)
if _app is None:
    raise SystemExit('App folder not found. Run this script with --app followed by the folder containing start.bat.')
_environment = _app / 'apps/api/.venv'
_python = _environment / ('Scripts/python.exe' if os.name == 'nt' else 'bin/python')
if not _python.is_file():
    raise SystemExit('Start CareerPilot once to install dependencies, then stop it before applying this correction.')
if Path(sys.prefix).resolve() != _environment.resolve():
    _result = subprocess.run([str(_python), str(Path(__file__).resolve()), '--app', str(_app)], cwd=_app, check=False)
    if sys.stdin.isatty():
        input('Press Enter to close. ')
    raise SystemExit(_result.returncode)
os.chdir(_app)
sys.path.insert(0, str(_app / 'apps/api'))
'''


def build(seed_path, output):
    # The generated file contains personal data and must stay outside tracked source.
    value = json.loads(seed_path.read_text(encoding="utf-8-sig"))
    body = (ROOT / "apps/api/careerpilot/profile_update.py").read_text()
    start = body.index("    parser = argparse.ArgumentParser(")
    end = body.index("    prepared(value)", start)
    body = body[:start] + "    value = json.loads(_PROFILE_JSON)\n" + body[end:]
    body = body.replace("import argparse\n", "").replace("from .", "from careerpilot.")
    output.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    payload = json.dumps(value, ensure_ascii=False)
    output.write_text(
        BOOTSTRAP + "\n_PROFILE_JSON = " + repr(payload) + "\n\n" + body, encoding="utf-8"
    )
    output.chmod(0o600)
    print("Private profile updater created. It contains personal information; do not publish it.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("seed", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    build(args.seed, args.output)
