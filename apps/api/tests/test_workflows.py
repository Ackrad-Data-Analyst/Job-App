import base64
import json

import pytest
from careerpilot.documents import TEMPLATES, check, compose
from careerpilot.matching import fit, salary_comparison
from careerpilot.models import (
    Feed,
    Vacancy,
)
from careerpilot.schemas import FactInput, JobInput
from sqlalchemy import select


def stage(c, a, s, **kwargs):
    current = c.get("/api/applications/" + a["id"]).json()
    return c.put(
        "/api/applications/" + a["id"] + "/stage",
        json={"stage": s, "version": current["version"], **kwargs},
    )


def test_private_routes_and_no_key_echo(client):
    assert client.get("/health", headers={"Authorization": ""}).status_code == 200
    for p in [
        "/api/profile",
        "/api/applications",
        "/api/preferences",
        "/api/sources",
        "/api/storage",
    ]:
        r = client.get(p, headers={"Authorization": ""})
        assert r.status_code == 401
    assert "test-only-token" not in client.get("/api/sources").text
    assert client.get("/api/profile").headers["cache-control"] == "no-store"


def test_empty_install_has_no_fictional_jobs(client, db):
    assert client.get("/api/applications").json() == []
    assert list(db.scalars(select(Feed))) == []
    p = client.get("/api/preferences").json()
    assert [x["country"] for x in p["countries"]][:2] == ["Canada", "UAE"]
    assert all(x["authorization"] == "unknown" and x["min_salary"] is None for x in p["countries"])


def test_fact_permissions_and_learning(person, job):
    f = person.get("/api/applications/" + job["id"]).json()["fit"]
    assert "Python" in f["required"]["confirmed"]
    assert "Civil 3D" in f["required"]["learning"]
    assert "Civil 3D" not in f["required"]["confirmed"]
    skills = person.get("/api/profile").json()["skills"]
    python = next(s for s in skills if s["title"] == "Python")
    body = {
        k: python[k]
        for k in [
            "title",
            "organization",
            "details",
            "start_date",
            "end_date",
            "status",
            "allowed_on_resume",
            "learning",
            "note",
        ]
    }
    body["allowed_on_resume"] = False
    assert person.put("/api/profile/skills/" + python["id"], json=body).status_code == 200
    assert (
        "Python"
        in person.get("/api/applications/" + job["id"]).json()["fit"]["required"]["missing"]
    )


@pytest.mark.parametrize(
    "field,value",
    [("title", ""), ("start_date", "2026-99"), ("end_date", "yesterday"), ("status", "invented")],
)
def test_invalid_facts_rejected(field, value):
    with pytest.raises(ValueError):
        FactInput.model_validate({"title": "Civil engineer", field: value})


def test_backwards_dates_rejected():
    with pytest.raises(ValueError):
        FactInput(title="Role", start_date="2026-09", end_date="2026-08")


def test_required_source_and_safe_urls():
    for url in ["javascript:alert(1)", "https://user:secret@example.invalid/job"]:
        with pytest.raises(ValueError):
            JobInput(title="Civil engineer", employer="Example", url=url)
    with pytest.raises(ValueError):
        JobInput(title="Civil engineer", employer="Example")


def test_duplicate_capture_tracks_one_application(client, job):
    j = job["job"]
    body = {k: j[k] for k in ["title", "employer", "country", "location", "url", "description"]}
    body["url"] += "?utm_source=example"
    r = client.post("/api/jobs", json=body)
    assert r.json()["id"] == job["id"]
    assert len(client.get("/api/applications").json()) == 1


def test_approval_and_submission_gates(client, job):
    assert stage(client, job, "Submitted", evidence="Clicked apply").status_code == 409
    assert stage(client, job, "Approved", approval=True).status_code == 409
    assert stage(client, job, "Draft Ready").status_code == 200
    assert stage(client, job, "Approved", approval=True).status_code == 409
    assert (
        client.put(
            "/api/applications/" + job["id"] + "/verification", json={"confirmed": True}
        ).status_code
        == 200
    )
    assert stage(client, job, "Approved").status_code == 409
    assert stage(client, job, "Approved", approval=True).status_code == 200
    assert stage(client, job, "Submitted").status_code == 422
    r = stage(
        client,
        job,
        "Submitted",
        evidence="Owner manually applied; confirmation reference EXAMPLE-1.",
    )
    assert r.status_code == 200
    assert len(client.get("/api/reminders").json()) == 2
    assert stage(client, job, "Discovered").status_code == 409
    assert stage(client, job, "Interview").status_code == 200
    assert stage(client, job, "Offer").status_code == 200
    assert "No external action" in client.get("/api/applications/" + job["id"]).text


def test_optimistic_conflict(client, job):
    assert stage(client, job, "Under Review").status_code == 200
    assert (
        client.put(
            "/api/applications/" + job["id"] + "/stage",
            json={"stage": "Shortlisted", "version": job["version"]},
        ).status_code
        == 409
    )


def test_demo_cannot_be_verified_or_approved(client, job, db):
    db.get(Vacancy, job["vacancy_id"]).is_demo = True
    db.commit()
    assert (
        client.put(
            "/api/applications/" + job["id"] + "/verification", json={"confirmed": True}
        ).status_code
        == 409
    )
    stage(client, job, "Draft Ready")
    assert stage(client, job, "Approved", approval=True).status_code == 409


def test_notes_evidence_reminders_and_csv(client, job):
    assert (
        client.post(
            "/api/applications/" + job["id"] + "/notes",
            json={"kind": "employer_response", "body": "Fictional test response."},
        ).status_code
        == 201
    )
    r = client.post(
        "/api/applications/" + job["id"] + "/evidence",
        json={
            "filename": "../../confirmation.txt",
            "media_type": "text/plain",
            "data": base64.b64encode(b"Example confirmation only").decode(),
        },
    )
    assert r.status_code == 201 and "/" not in r.json()["filename"]
    assert (
        client.get("/api/evidence/" + r.json()["id"] + "/download").content
        == b"Example confirmation only"
    )
    assert (
        client.post(
            "/api/applications/" + job["id"] + "/evidence",
            json={
                "filename": "fake.pdf",
                "media_type": "application/pdf",
                "data": base64.b64encode(b"not a PDF").decode(),
            },
        ).status_code
        == 422
    )
    assert client.get("/api/tracker/export").content.startswith(b"\xef\xbb\xbf")


@pytest.mark.parametrize("country", list(TEMPLATES))
def test_country_documents_fact_traceability(person, job, db, country):
    j = job["job"]
    content, claims, checks = compose(db, j, "resume", country)
    assert checks["passed"]
    assert "Civil 3D (currently learning)" in content
    assert "AutoCAD (2D only)" in content
    for bad in ["MCA", "GPA", "CGPA", "visa", "relocation", "authorised to work"]:
        assert bad not in content
    assert "Expected" not in content  # completed fictional degree
    changed = content.replace("quantity take-offs", "invented 90% improvement")
    assert not check(db, changed, claims, country)["passed"]


def test_unverified_and_excluded_facts_never_drafted(person, job, db):
    for status in ["unverified", "excluded"]:
        person.post(
            "/api/profile/experience",
            json={
                "title": "Invented Forbidden Role " + status,
                "details": "Invented duties",
                "status": status,
            },
        )
    person.post(
        "/api/profile/education", json={"title": "MCA in Cyber Security", "status": "confirmed"}
    )
    content, _, _ = compose(db, job["job"], "resume", "Canada")
    assert "Forbidden" not in content and "MCA" not in content


def test_pdf_docx_download_and_stale_fact(person, job):
    from io import BytesIO

    from docx import Document as Word
    from pypdf import PdfReader

    r = person.post(
        "/api/applications/" + job["id"] + "/documents",
        json={"kind": "resume", "country": "Canada"},
    )
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["checks"]["passed"] and d["checks"]["pages"] == 1
    pdf = person.get("/api/documents/" + d["id"] + "/download/pdf")
    assert pdf.status_code == 200
    assert len(PdfReader(BytesIO(pdf.content)).pages) == 1
    word = Word(BytesIO(person.get("/api/documents/" + d["id"] + "/download/docx").content))
    assert not word.tables and not word.inline_shapes
    assert person.post("/api/documents/" + d["id"] + "/approve", json={}).status_code == 200
    profile = person.get("/api/profile").json()["candidate"]
    person.put(
        "/api/profile",
        json={
            k: ("Different fictional name" if k == "name" else profile[k])
            for k in ["name", "headline", "summary", "status", "allowed_on_resume", "note"]
        },
    )
    assert person.get("/api/documents/" + d["id"]).json()["checks"]["passed"] is False
    assert person.get("/api/documents/" + d["id"] + "/download/pdf").status_code == 409


def test_cover_letter_generic_and_sourced_contact(person, job, db):
    content, _, checks = compose(db, job["job"], "cover_letter", "Canada")
    assert checks["passed"] and "Dear Hiring Manager," in content
    assert "I am applying for the Junior Civil Engineer role" in content
    assert "Yours sincerely," in content


def test_edit_job_invalidates_source_and_draft(person, job):
    person.post(
        "/api/applications/" + job["id"] + "/documents",
        json={"kind": "resume", "country": "Canada"},
    ).json()
    person.put("/api/applications/" + job["id"] + "/verification", json={"confirmed": True})
    j = job["job"]
    body = {k: j[k] for k in ["title", "employer", "country", "location", "url", "description"]}
    body["description"] += " Added source requirement."
    assert person.put("/api/applications/" + job["id"] + "/job", json=body).status_code == 200
    a = person.get("/api/applications/" + job["id"]).json()
    assert a["job"]["verification"] == "unverified" and a["documents"][0]["status"] == "superseded"


def test_career_profile_import_is_non_destructive(client):
    seed = {
        "candidate": {"name": "Fictional imported owner", "status": "confirmed"},
        "skills": [{"title": "SQL", "status": "unverified", "allowed_on_resume": False}],
    }
    assert client.post("/api/profile-import", json={"data": json.dumps(seed)}).status_code == 200
    assert client.get("/api/profile").json()["skills"][0]["status"] == "unverified"
    assert client.post("/api/profile-import", json={"data": json.dumps(seed)}).status_code == 409


@pytest.mark.parametrize(
    "restriction",
    [
        "Full driving licence required.",
        "French required.",
        "Professional Engineer required.",
        "Security clearance required.",
        "Primavera P6 required.",
        "Citizens only.",
    ],
)
def test_requirement_blockers(person, job, db, restriction):
    j = {**job["job"], "description": "Required qualifications\n" + restriction}
    f = fit(db, j)
    assert f["blockers"] and f["recommendation"] == "Skip"


def test_salary_unknown_and_dated_currency_rates(client):
    p = client.get("/api/preferences").json()
    country = p["countries"][0]
    country["min_salary"] = 60000
    j = {"salary_min": None, "salary_max": None, "salary_currency": "CAD", "salary_period": "year"}
    r = salary_comparison(j, p, country)
    assert r["minimum_status"] != "Below country minimum."
    j.update(salary_min=40000, salary_max=50000)
    assert salary_comparison(j, p, country)["minimum_status"] == "Below country minimum."
    j.update(salary_currency="USD")
    p["exchange_rates"] = {"USD": 1.4}
    assert salary_comparison(j, p, country).get("min") is None
    p["exchange_rate_date"] = "2026-10-30"
    assert salary_comparison(j, p, country)["min"] == 56000


def test_preferences_do_not_infer_work_authorization(client):
    p = client.get("/api/preferences").json()
    p["countries"].reverse()
    assert client.put("/api/preferences", json=p).status_code == 200
    assert client.get("/api/preferences").json()["countries"][0]["country"] == "Italy"
    assert all(
        c["authorization"] == "unknown" for c in client.get("/api/preferences").json()["countries"]
    )
