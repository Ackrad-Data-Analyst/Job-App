"""Fictional isolated browser fixture. Never reads the owner's real data/."""

import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "api"))
os.environ["CAREERPILOT_DATA_DIR"] = tempfile.mkdtemp(prefix="careerpilot-browser-")
os.environ["API_TOKEN"] = "browser-fixture-only-token-000000000000000"
import uvicorn
from alembic import command
from alembic.config import Config
from careerpilot.config import engine
from careerpilot.initialize import import_seed, initialize
from sqlalchemy.orm import Session

cfg = Config("alembic.ini")
command.upgrade(cfg, "head")
with Session(engine()) as db:
    initialize(db)
    import_seed(
        db,
        {
            "candidate": {
                "name": "Alex Example (fictional)",
                "summary": "Civil engineering and GIS experience.",
                "status": "confirmed",
            },
            "skills": [
                {"title": "Python", "status": "confirmed"},
                {"title": "QGIS", "status": "confirmed"},
            ],
            "education": [
                {
                    "title": "Bachelor of Civil Engineering",
                    "organization": "Example University (fictional)",
                    "end_date": "2025-06",
                    "status": "confirmed",
                }
            ],
            "experience": [
                {
                    "title": "Graduate Civil Engineer",
                    "organization": "Example Council (fictional)",
                    "details": "Prepared quantity take-offs and drainage inspection reports.",
                    "end_date": "2026-06",
                    "status": "confirmed",
                }
            ],
        },
    )
uvicorn.run("careerpilot.main:app", host="127.0.0.1", port=8100, access_log=False)
