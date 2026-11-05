#!/usr/bin/env python3
"""Build a standalone pinned updater, optionally containing private owner corrections."""

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def build(revision, sha256, output, profile_path=None):
    source = (ROOT / "scripts/local_update.py").read_text()
    marker = "if __name__=='__main__':"
    # Source is formatted before release; accept its standard quote/space form.
    if marker not in source:
        marker = 'if __name__ == "__main__":'
    source = source[: source.index(marker)]
    payload = json.loads(profile_path.read_text(encoding="utf-8-sig")) if profile_path else None
    source += (
        '\nif __name__ == "__main__":\n    try:\n        main('
        + repr(revision)
        + ","
        + repr(sha256)
        + ",json.loads("
        + repr(json.dumps(payload, ensure_ascii=False))
        + '))\n    except (ValueError,OSError,RuntimeError) as error:\n        print("Update could not complete: "+str(error))\n        raise SystemExit(1)\n'
    )
    output.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    output.write_text(source, encoding="utf-8")
    output.chmod(0o600)
    print(
        "Standalone pinned updater created. Contains private profile: "
        + str(bool(payload))
        + ". Do not publish a personal updater."
    )


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("revision")
    p.add_argument("sha256")
    p.add_argument("output", type=Path)
    p.add_argument("--profile", type=Path)
    args = p.parse_args()
    build(args.revision, args.sha256, args.output, args.profile)
