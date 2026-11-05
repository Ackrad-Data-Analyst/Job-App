#!/usr/bin/env python3
"""Install a pinned, hash-checked CareerPilot source update with private backups."""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import re
import shutil
import sqlite3
import stat
import subprocess
import urllib.request
import uuid
import zipfile
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath

REPOSITORY = "Ackrad-Data-Analyst/Job-App"
ALLOWED_ROOTS = {"apps", "scripts", "examples", ".githooks"}
ALLOWED_FILES = {
    ".gitignore",
    ".nvmrc",
    ".python-version",
    ".env.example",
    "README.md",
    "SETUP-VALIDATION.md",
    "DOWNLOAD-AND-RUN.txt",
    "package.json",
    "package-lock.json",
    "start.py",
    "start.bat",
    "start.command",
    "start.sh",
    "stop.bat",
    "stop.command",
    "stop.sh",
}


def source_members(raw):
    archive = zipfile.ZipFile(io.BytesIO(raw))
    result = []
    total = 0
    if len(archive.infolist()) > 2000:
        raise ValueError("Unexpected number of files in source archive.")
    for entry in archive.infolist():
        p = PurePosixPath(entry.filename)
        if p.is_absolute() or ".." in p.parts or any(":" in v or "\\" in v for v in p.parts):
            raise ValueError("Unsafe archive path.")
        if stat.S_ISLNK(entry.external_attr >> 16):
            raise ValueError("Source archive contains a symbolic link.")
        if entry.is_dir():
            continue
        if len(p.parts) < 2:
            raise ValueError("Expected one source archive root folder.")
        relative = Path(*p.parts[1:])
        if any(
            part in {"data", ".git", "node_modules", ".venv", ".next", ".launcher-venv"}
            for part in relative.parts
        ):
            raise ValueError("Archive contains private/runtime files.")
        if relative.parts[0] not in ALLOWED_ROOTS and relative.as_posix() not in ALLOWED_FILES:
            raise ValueError("Unexpected source archive file: " + relative.as_posix())
        total += entry.file_size
        if entry.file_size > 8000000 or total > 40000000:
            raise ValueError("Source archive exceeds bounded extraction size.")
        result.append((relative, archive.read(entry), entry.external_attr >> 16))
    if not any(p.as_posix() == "start.py" for p, _, _ in result):
        raise ValueError("Source archive is missing the launcher.")
    if len({p.as_posix() for p, _, _ in result}) != len(result):
        raise ValueError("Duplicate source archive path.")
    return result


def app_folder(explicit=None):
    paths = (
        [explicit]
        if explicit
        else [
            Path(__file__).resolve().parent,
            Path.cwd(),
            Path.home() / "Downloads" / "Job-App-careerpilot-recovery",
        ]
    )
    for path in paths:
        if path and (path / "start.py").is_file() and (path / "apps/api").is_dir():
            return path.resolve()
    raise ValueError(
        "CareerPilot folder not found. Use --app followed by the folder containing start.bat."
    )


def run(command, cwd, env):
    result = subprocess.run([str(v) for v in command], cwd=cwd, env=env, check=False)
    if result.returncode:
        raise RuntimeError(
            "A local update step failed. The previous source and database will be restored."
        )


def install(raw, expected_sha, root, profile=None, run_steps=True):
    if hashlib.sha256(raw).hexdigest() != expected_sha:
        raise ValueError("Source checksum mismatch. No files were changed.")
    members = source_members(raw)
    data = Path(os.environ.get("CAREERPILOT_DATA_DIR", str(root / "data"))).resolve()
    private = data / "private"
    if (private / "runner.lock").exists():
        raise ValueError(
            "Stop CareerPilot using stop.bat, wait for it to stop, then run this update again."
        )
    api_python = (
        root / "apps/api/.venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    )
    if run_steps and not api_python.is_file():
        raise ValueError(
            "Start the existing app once to install its environment, then stop it and update."
        )
    private.mkdir(parents=True, exist_ok=True, mode=0o700)
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S") + "-" + uuid.uuid4().hex[:6]
    backup = private / "source-backups" / stamp
    backup.mkdir(parents=True, mode=0o700)
    env = {**os.environ, "CAREERPILOT_DATA_DIR": str(data), "NEXT_TELEMETRY_DISABLED": "1"}
    db_path = private / "careerpilot.db"
    # Ask the already installed configuration for its DB path, without outputting keys.
    if run_steps:
        probe = "from careerpilot.config import settings; from sqlalchemy.engine import make_url; u=make_url(settings().database_url); assert u.get_backend_name()=='sqlite','Local updater requires SQLite'; print(u.database)"
        result = subprocess.run(
            [str(api_python), "-c", probe],
            cwd=root / "apps/api",
            env=env,
            text=True,
            capture_output=True,
            check=False,
        )
        if result.returncode:
            raise ValueError(
                "Cannot establish a local SQLite backup safely. Existing files were preserved."
            )
        db_path = Path(result.stdout.strip()).resolve()
    saved_db = backup / "before-update.db"
    if db_path.is_file():
        with sqlite3.connect(db_path) as source, sqlite3.connect(saved_db) as target:
            source.backup(target)
        saved_db.chmod(0o600)
    previous = []
    for relative, _, _ in members:
        target = root / relative
        if not target.resolve().is_relative_to(root):
            raise ValueError("Existing source path leaves the app folder.")
        existed = target.is_file()
        previous.append((relative, existed))
        if existed:
            copy = backup / "source" / relative
            copy.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            shutil.copy2(target, copy)
    seed = private / "profile.seed.json"
    seed_existed = seed.exists()
    if profile is not None and seed_existed:
        shutil.copy2(seed, backup / "previous-profile.seed.json")
    try:
        for relative, content, mode in members:
            target = root / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(content)
            if os.name != "nt":
                target.chmod(mode & 0o777 or 0o644)
        if run_steps:
            print("Applying the database migration. Existing records are retained.", flush=True)
            run([api_python, "-m", "alembic", "upgrade", "head"], root / "apps/api", env)
        if profile is not None:
            # This payload is private and never part of a request to GitHub or an employer.
            corrected = backup / "owner-profile-correction.json"
            corrected.write_text(json.dumps(profile, ensure_ascii=False), encoding="utf-8")
            corrected.chmod(0o600)
            if run_steps:
                print(
                    "Applying your supplied profile corrections and search preferences.", flush=True
                )
                run(
                    [api_python, "-m", "careerpilot.profile_update", corrected],
                    root / "apps/api",
                    env,
                )
            seed.write_text(json.dumps(profile, ensure_ascii=False, indent=2), encoding="utf-8")
            seed.chmod(0o600)
    except BaseException:
        for relative, existed in previous:
            target = root / relative
            if existed:
                shutil.copy2(backup / "source" / relative, target)
            elif target.is_file():
                target.unlink()
        if saved_db.is_file():
            for suffix in ["-wal", "-shm"]:
                journal = Path(str(db_path) + suffix)
                if journal.exists():
                    journal.unlink()
            shutil.copy2(saved_db, db_path)
        if profile is not None:
            if seed_existed:
                shutil.copy2(backup / "previous-profile.seed.json", seed)
            elif seed.exists():
                seed.unlink()
        raise
    print(
        "Update complete. Your old source and database are backed up privately in data/private/source-backups.",
        flush=True,
    )
    print(
        "Open start.bat. It will rebuild the browser app, then open CareerPilot. In Job sources, check employer pages before relying on feed availability.",
        flush=True,
    )
    return backup


def main(revision=None, expected_sha=None, profile=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--app", type=Path)
    parser.add_argument(
        "--archive",
        type=Path,
        help="Use an already downloaded source archive; checksum is still required",
    )
    parser.add_argument("--revision", default=revision)
    parser.add_argument("--sha256", default=expected_sha)
    args = parser.parse_args()
    if not re.fullmatch("[a-f0-9]{40}", args.revision or "") or not re.fullmatch(
        "[a-f0-9]{64}", args.sha256 or ""
    ):
        raise ValueError("A pinned source revision and SHA256 are required.")
    root = app_folder(args.app)
    private = Path(os.environ.get("CAREERPILOT_DATA_DIR", str(root / "data"))) / "private"
    if (private / "runner.lock").exists():
        raise ValueError("Stop CareerPilot using stop.bat before running this updater.")
    if args.archive:
        raw = args.archive.read_bytes()
    else:
        print(
            "Downloading the pinned public app source from GitHub. Your profile stays on this computer.",
            flush=True,
        )
        url = f"https://github.com/{REPOSITORY}/archive/{args.revision}.zip"
        with urllib.request.urlopen(url, timeout=45) as response:
            raw = response.read(12000001)
            if len(raw) > 12000000:
                raise ValueError("Source download exceeds the bounded size.")
    install(raw, args.sha256, root, profile)


if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError, RuntimeError) as error:
        raise SystemExit(str(error)) from None
