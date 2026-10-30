import os
import tempfile

os.environ["API_TOKEN"] = "test-only-token-000000000000000000000000"
os.environ["CAREERPILOT_DATA_DIR"] = tempfile.mkdtemp(prefix="careerpilot-tests-")

import pytest
from careerpilot.config import database
from careerpilot.initialize import initialize
from careerpilot.main import app
from careerpilot.models import Base
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool


@pytest.fixture
def db(tmp_path, monkeypatch):
    import careerpilot.documents as docs
    import careerpilot.main as main

    monkeypatch.setattr(docs, "OUTPUTS", tmp_path / "outputs")
    monkeypatch.setattr(main, "OUTPUTS", tmp_path / "outputs")
    monkeypatch.setattr(main, "PRIVATE", tmp_path)
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )

    @event.listens_for(engine, "connect")
    def fk(c, _):
        c.execute("PRAGMA foreign_keys=ON")

    Base.metadata.create_all(engine)
    with Session(engine) as session:
        initialize(session)
        yield session
    engine.dispose()


@pytest.fixture
def client(db):
    app.dependency_overrides[database] = lambda: db
    with TestClient(app, headers={"Authorization": "Bearer " + os.environ["API_TOKEN"]}) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
def person(client):
    client.put(
        "/api/profile",
        json={
            "name": "Alex Example (fictional)",
            "summary": "Civil engineering and GIS experience.",
            "status": "confirmed",
            "allowed_on_resume": True,
        },
    )
    for kind, body in [
        ("skills", {"title": "Python"}),
        ("skills", {"title": "QGIS"}),
        ("skills", {"title": "Civil 3D", "learning": True}),
        ("skills", {"title": "AutoCAD (2D only)"}),
        (
            "education",
            {
                "title": "Bachelor of Civil Engineering",
                "organization": "Example University (fictional)",
                "end_date": "2025-06",
            },
        ),
        (
            "experience",
            {
                "title": "Graduate Civil Engineer",
                "organization": "Example Council (fictional)",
                "details": "Prepared quantity take-offs and drainage inspection reports.",
                "end_date": "2026-06",
            },
        ),
        ("identity", {"title": "Email", "details": "alex@example.invalid"}),
    ]:
        r = client.post(
            "/api/profile/" + kind, json={**body, "status": "confirmed", "allowed_on_resume": True}
        )
        assert r.status_code == 201
    return client


@pytest.fixture
def job(client):
    r = client.post(
        "/api/jobs",
        json={
            "title": "Junior Civil Engineer",
            "employer": "Example Infrastructure (fictional)",
            "country": "Canada",
            "location": "Regina",
            "url": "https://example.invalid/job/1",
            "description": "Required qualifications\nPython, QGIS and Civil 3D.\nPreferred qualifications\nHEC-RAS. Full-time civil infrastructure drainage design.",
        },
    )
    assert r.status_code == 201
    return r.json()
