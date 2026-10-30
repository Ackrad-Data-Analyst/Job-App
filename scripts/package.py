#!/usr/bin/env python3
"""Package tracked source; personal seed requires an explicit private build flag."""

import argparse
import hashlib
import subprocess
import sys
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from check_private import check

ROOT = Path(__file__).resolve().parents[1]


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--personal", action="store_true")
    p.add_argument("--output", type=Path, default=ROOT / "dist")
    a = p.parse_args()
    files = (
        subprocess.check_output(["git", "ls-files", "-z"], cwd=ROOT)
        .decode()
        .strip("\0")
        .split("\0")
    )
    errors = check(files, lambda f: (ROOT / f).read_bytes())
    if errors:
        raise SystemExit("\n".join(errors))
    seed = ROOT / "data/private/profile.seed.json"
    if a.personal and not seed.is_file():
        raise SystemExit("Private seed missing. No substitute profile will be invented.")
    a.output.mkdir(parents=True, exist_ok=True)
    target = a.output / ("CareerPilot-Personal.zip" if a.personal else "CareerPilot-Source.zip")
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as z:
        for f in files:
            z.write(ROOT / f, "CareerPilot/" + f)
        if a.personal:
            z.write(seed, "CareerPilot/data/private/profile.seed.json")
    digest = hashlib.sha256(target.read_bytes()).hexdigest()
    (target.with_suffix(".zip.sha256")).write_text(digest + "  " + target.name + "\n")
    print(str(target) + " (" + str(target.stat().st_size) + " bytes)")
    print("SHA256 " + digest)
    print(
        "Contains private profile: "
        + str(a.personal)
        + ". No database, keys, logs or generated documents included."
    )


if __name__ == "__main__":
    main()
