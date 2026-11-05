import hashlib
import importlib.util
import io
import sqlite3
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
spec = importlib.util.spec_from_file_location(
    "careerpilot_local_update", ROOT / "scripts/local_update.py"
)
updater = importlib.util.module_from_spec(spec)
spec.loader.exec_module(updater)


@pytest.fixture(autouse=True)
def local_storage(monkeypatch):
    # API fixtures use a shared temporary data root; updater tests exercise their own app folders.
    monkeypatch.delenv("CAREERPILOT_DATA_DIR", raising=False)


def archive(files):
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w") as z:
        for name, content in files.items():
            z.writestr("Release/" + name, content)
    return out.getvalue()


def test_source_update_preserves_data_and_creates_backup(tmp_path):
    root = tmp_path / "CareerPilot folder"
    root.mkdir()
    (root / "start.py").write_text("old launcher")
    private = root / "data/private"
    private.mkdir(parents=True)
    (private / ".env").write_text("PRIVATE_SETTING=kept")
    with sqlite3.connect(private / "careerpilot.db") as db:
        db.execute("CREATE TABLE saved (title TEXT)")
        db.execute("INSERT INTO saved VALUES (?)", ("Fictional existing record",))
    raw = archive(
        {
            "start.py": "new launcher",
            "README.md": "new instructions",
            "apps/api/example.py": "new source",
        }
    )
    backup = updater.install(raw, hashlib.sha256(raw).hexdigest(), root, run_steps=False)
    assert (root / "start.py").read_text() == "new launcher"
    assert (backup / "source/start.py").read_text() == "old launcher"
    assert (private / ".env").read_text() == "PRIVATE_SETTING=kept"
    with sqlite3.connect(backup / "before-update.db") as db:
        assert db.execute("SELECT title FROM saved").fetchone()[0] == "Fictional existing record"


@pytest.mark.parametrize(
    "name",
    [
        "../escape.py",
        "data/private/.env",
        ".git/config",
        "apps/../../escape.py",
        "apps/api/.venv/evil.py",
        "unexpected.exe",
    ],
)
def test_update_rejects_unsafe_or_private_archive_paths(name):
    with pytest.raises(ValueError):
        updater.source_members(archive({"start.py": "source", name: "unsafe"}))


def test_hash_mismatch_and_running_app_change_nothing(tmp_path):
    (tmp_path / "start.py").write_text("original")
    raw = archive({"start.py": "changed"})
    with pytest.raises(ValueError):
        updater.install(raw, "0" * 64, tmp_path, run_steps=False)
    private = tmp_path / "data/private"
    private.mkdir(parents=True)
    (private / "runner.lock").mkdir()
    with pytest.raises(ValueError):
        updater.install(raw, hashlib.sha256(raw).hexdigest(), tmp_path, run_steps=False)
    assert (tmp_path / "start.py").read_text() == "original"


def test_update_failure_rolls_back_source_and_database(tmp_path, monkeypatch):
    (tmp_path / "start.py").write_text("original")
    private = tmp_path / "data/private"
    private.mkdir(parents=True)
    api = tmp_path / "apps/api/.venv/bin/python"
    api.parent.mkdir(parents=True)
    api.write_text("test interpreter")
    with sqlite3.connect(private / "careerpilot.db") as db:
        db.execute("CREATE TABLE keep (id INTEGER)")
        db.execute("INSERT INTO keep VALUES (7)")

    class Result:
        returncode = 0
        stdout = str(private / "careerpilot.db")

    monkeypatch.setattr(updater.subprocess, "run", lambda *a, **kw: Result())

    def fail(*a, **kw):
        raise RuntimeError("Fictional migration failure")

    monkeypatch.setattr(updater, "run", fail)
    raw = archive({"start.py": "new source", "apps/api/new.py": "new file"})
    with pytest.raises(RuntimeError):
        updater.install(raw, hashlib.sha256(raw).hexdigest(), tmp_path, run_steps=True)
    assert (tmp_path / "start.py").read_text() == "original" and not (
        tmp_path / "apps/api/new.py"
    ).exists()
    with sqlite3.connect(private / "careerpilot.db") as db:
        assert db.execute("SELECT id FROM keep").fetchone()[0] == 7
