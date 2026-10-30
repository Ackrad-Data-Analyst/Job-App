import asyncio
import base64
import csv
import hashlib
import io
import json
import re
import secrets
import uuid
from datetime import timedelta
from itertools import product

from fastapi import APIRouter, Depends, FastAPI, HTTPException, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import Field
from sqlalchemy import desc, select, text
from sqlalchemy.orm import Session
from sqlalchemy.orm.exc import StaleDataError

from .config import DATA, OUTPUTS, PRIVATE, database, settings
from .documents import TEMPLATES, check, compose, write_files
from .initialize import STARTERS, import_seed
from .matching import fit, prefs, roles
from .models import (
    FACTS,
    STAGES,
    Activity,
    Application,
    Candidate,
    Document,
    Employer,
    Evidence,
    Feed,
    Note,
    Preferences,
    Reminder,
    SavedSearch,
    Vacancy,
    now,
)
from .schemas import (
    CandidateInput,
    EmployerInput,
    FactInput,
    FeedInput,
    Input,
    JobInput,
    NoteInput,
    PreferencesInput,
    SavedInput,
    SearchInput,
    StageInput,
)
from .sources import Providers, canonical, capture, fingerprint, unique

app = FastAPI(title="CareerPilot", version="0.3.0", docs_url=None, redoc_url=None)
bearer = HTTPBearer(auto_error=False)
providers = Providers()


def auth(c: HTTPAuthorizationCredentials | None = Depends(bearer)):
    if not c or not secrets.compare_digest(c.credentials, settings().api_token):
        raise HTTPException(401, "Private access required")


api = APIRouter(prefix="/api", dependencies=[Depends(auth)])


@app.exception_handler(RequestValidationError)
async def private_errors(request, error):
    return JSONResponse(
        status_code=422,
        content={
            "detail": [
                {k: v for k, v in item.items() if k in {"loc", "msg", "type"}}
                for item in error.errors()
            ]
        },
    )


@app.middleware("http")
async def headers(request, next):
    r = await next(request)
    r.headers["Cache-Control"] = "no-store"
    r.headers["X-Content-Type-Options"] = "nosniff"
    return r


@app.get("/health")
def health():
    return {"status": "ok"}


def pack(row, exclude=()):
    return {c.name: getattr(row, c.name) for c in row.__table__.columns if c.name not in exclude}


def need(db, model, id):
    value = db.get(model, id)
    if value is None:
        raise HTTPException(404, "Record not found")
    return value


def owner(db):
    p = db.scalar(select(Candidate))
    if not p:
        raise HTTPException(503, "Initialize the private database first")
    return p


def log(db, action, message, id=None):
    db.add(Activity(action=action, message=message, application_id=id))


def commit(db):
    try:
        db.commit()
    except StaleDataError:
        db.rollback()
        raise HTTPException(409, "Record changed. Refresh before saving.") from None


def view(db, a):
    j = need(db, Vacancy, a.vacancy_id)
    e = need(db, Employer, j.employer_id)
    job = {**pack(j), "employer": e.name}
    return {**pack(a), "job": job, "fit": fit(db, job)}


def docview(db, d):
    return {**pack(d), "checks": {**d.checks, **check(db, d.content, d.claims, d.country_template)}}


def locked(db, id):
    a = db.scalar(select(Application).where(Application.id == id).with_for_update())
    if not a:
        raise HTTPException(404, "Application not found")
    return a


@api.get("/ready")
def ready(db: Session = Depends(database)):
    db.execute(text("SELECT 1"))
    owner(db)
    return {"status": "ready"}


@api.get("/profile")
def profile(db: Session = Depends(database)):
    return {
        "candidate": pack(owner(db)),
        **{
            k: [pack(f) for f in db.scalars(select(m).order_by(desc(m.created_at)))]
            for k, m in FACTS.items()
        },
    }


@api.put("/profile")
def update_profile(body: CandidateInput, db: Session = Depends(database)):
    p = owner(db)
    for k, v in body.model_dump().items():
        setattr(p, k, v)
    log(db, "profile_updated", "Owner updated professional overview and permissions.")
    commit(db)
    return pack(p)


@api.post("/profile/{kind}", status_code=201)
def create_fact(kind: str, body: FactInput, db: Session = Depends(database)):
    if kind not in FACTS:
        raise HTTPException(404, "Unknown fact category")
    f = FACTS[kind](candidate_id=owner(db).id, **body.model_dump())
    db.add(f)
    log(db, "fact_added", f"{kind} added as {body.status}.")
    commit(db)
    return pack(f)


@api.put("/profile/{kind}/{id}")
def update_fact(kind: str, id: str, body: FactInput, db: Session = Depends(database)):
    if kind not in FACTS:
        raise HTTPException(404, "Unknown fact category")
    f = need(db, FACTS[kind], id)
    for k, v in body.model_dump().items():
        setattr(f, k, v)
    log(db, "fact_updated", f"{kind} verification or content updated.")
    commit(db)
    return pack(f)


@api.delete("/profile/{kind}/{id}", status_code=204)
def delete_fact(kind: str, id: str, db: Session = Depends(database)):
    if kind not in FACTS:
        raise HTTPException(404, "Unknown fact category")
    db.delete(need(db, FACTS[kind], id))
    log(db, "fact_deleted", "Owner removed a career fact.")
    commit(db)
    return Response(status_code=204)


class SeedInput(Input):
    data: str = Field(max_length=200000)


@api.post("/profile-import")
def profile_import(body: SeedInput, db: Session = Depends(database)):
    import gzip

    try:
        value = (
            json.loads(body.data)
            if body.data.startswith("{")
            else json.loads(gzip.decompress(base64.b64decode(body.data, validate=True)))
        )
        if not import_seed(db, value):
            raise HTTPException(
                409,
                "Your profile is already populated. Existing records were preserved; use the editor for changes.",
            )
        return {"imported": True}
    except (ValueError, TypeError, KeyError, OSError):
        raise HTTPException(
            422, "Invalid private profile seed. No records were replaced."
        ) from None


@api.get("/preferences")
def preferences(db: Session = Depends(database)):
    return prefs(db)


@api.put("/preferences")
def save_preferences(body: PreferencesInput, db: Session = Depends(database)):
    db.scalar(select(Preferences)).data = body.model_dump()
    log(db, "preferences_updated", "Markets, career scope and private preferences updated.")
    commit(db)
    return prefs(db)


@api.get("/roles")
def role_list(db: Session = Depends(database)):
    return roles(db)


@api.get("/applications")
def applications(db: Session = Depends(database)):
    return [
        view(db, a) for a in db.scalars(select(Application).order_by(desc(Application.created_at)))
    ]


def setjob(db, body, j=None):
    e = db.scalar(select(Employer).where(Employer.name == body.employer))
    if not e:
        e = Employer(name=body.employer)
        db.add(e)
        db.flush()
    if not j:
        j = Vacancy(employer_id=e.id, title=body.title, fingerprint=fingerprint(body.model_dump()))
        db.add(j)
    for k, v in body.model_dump(exclude={"employer"}).items():
        setattr(j, k, v)
    j.employer_id = e.id
    j.fingerprint = fingerprint(body.model_dump())
    return j


@api.post("/jobs", status_code=201)
def save_job(body: JobInput, db: Session = Depends(database)):
    existing = next(
        (
            j
            for j in db.scalars(select(Vacancy))
            if (body.url and j.url and canonical(body.url) == canonical(j.url))
            or j.fingerprint == fingerprint(body.model_dump())
        ),
        None,
    )
    if existing:
        return view(db, db.scalar(select(Application).where(Application.vacancy_id == existing.id)))
    j = setjob(db, body)
    db.flush()
    a = Application(candidate_id=owner(db).id, vacancy_id=j.id)
    db.add(a)
    db.flush()
    log(db, "job_saved", "Job saved as owner-unverified. Nothing was sent.", a.id)
    commit(db)
    return view(db, a)


@api.get("/applications/{id}")
def detail(id: str, db: Session = Depends(database)):
    a = need(db, Application, id)
    j = need(db, Vacancy, a.vacancy_id)
    return {
        **view(db, a),
        "employer": pack(need(db, Employer, j.employer_id)),
        "documents": [
            docview(db, d)
            for d in db.scalars(
                select(Document)
                .where(Document.application_id == id)
                .order_by(desc(Document.created_at))
            )
        ],
        "notes": [
            pack(n)
            for n in db.scalars(
                select(Note).where(Note.application_id == id).order_by(desc(Note.created_at))
            )
        ],
        "activity": [
            pack(x)
            for x in db.scalars(
                select(Activity)
                .where(Activity.application_id == id)
                .order_by(desc(Activity.created_at))
            )
        ],
        "reminders": [
            pack(r) for r in db.scalars(select(Reminder).where(Reminder.application_id == id))
        ],
        "evidence_files": [
            pack(e, {"storage_key"})
            for e in db.scalars(select(Evidence).where(Evidence.application_id == id))
        ],
    }


@api.put("/applications/{id}/job")
def edit_job(id: str, body: JobInput, db: Session = Depends(database)):
    a = locked(db, id)
    if a.submitted_at or a.stage == "Approved":
        raise HTTPException(
            409,
            "Return an unsubmitted application to review before editing. Submitted history is retained.",
        )
    j = need(db, Vacancy, a.vacancy_id)
    if j.is_demo:
        raise HTTPException(409, "Fictional examples cannot become real vacancies")
    if body.url and any(
        x.id != j.id and x.url and canonical(x.url) == canonical(body.url)
        for x in db.scalars(select(Vacancy))
    ):
        raise HTTPException(409, "That source URL is already tracked.")
    setjob(db, body, j)
    j.verification = "unverified"
    a.updated_at = now()
    a.approved_at = None
    for d in db.scalars(
        select(Document).where(
            Document.application_id == id, Document.status.in_(["generated", "approved"])
        )
    ):
        d.status = "superseded"
        d.approved_at = None
    log(
        db,
        "job_updated",
        "Source text/pay updated. Authenticity and drafts require fresh review.",
        id,
    )
    commit(db)
    return view(db, a)


class VerifyInput(Input):
    confirmed: bool


@api.put("/applications/{id}/verification")
def verify(id: str, body: VerifyInput, db: Session = Depends(database)):
    a = locked(db, id)
    j = need(db, Vacancy, a.vacancy_id)
    if j.is_demo or a.stage in {"Approved", "Submitted", "Interview", "Offer"}:
        raise HTTPException(
            409, "Return to review before changing authenticity; fictional jobs cannot be verified."
        )
    if body.confirmed and not j.url:
        raise HTTPException(409, "A verifiable original source URL is required.")
    j.verification = "verified" if body.confirmed else "unverified"
    log(db, "source_verified", "Owner updated original-source verification.", id)
    commit(db)
    return view(db, a)


@api.put("/applications/{id}/stage")
def change_stage(id: str, body: StageInput, db: Session = Depends(database)):
    a = locked(db, id)
    j = need(db, Vacancy, a.vacancy_id)
    if body.stage not in STAGES:
        raise HTTPException(422, "Unknown application stage")
    if body.version != a.version:
        raise HTTPException(409, "Application changed. Refresh first.")
    if body.stage == a.stage:
        return view(db, a)
    docs = list(
        db.scalars(
            select(Document).where(
                Document.application_id == id, Document.status.in_(["generated", "approved"])
            )
        )
    )
    if body.stage == "Approved":
        if (
            a.stage != "Draft Ready"
            or not body.approval
            or j.verification != "verified"
            or j.is_demo
        ):
            raise HTTPException(
                409,
                "Approval requires Draft Ready, your checked original source and an explicit approval click.",
            )
        if any(d.status != "approved" or not docview(db, d)["checks"]["passed"] for d in docs):
            raise HTTPException(409, "Review and approve every current generated draft first.")
        a.approved_at = now()
    elif body.stage == "Submitted":
        if a.stage != "Approved" or not a.approved_at:
            raise HTTPException(
                409, "Explicit prior approval is required before recording submission."
            )
        if not body.evidence:
            raise HTTPException(422, "Record evidence of your manual submission.")
        if any(not docview(db, d)["checks"]["passed"] for d in docs):
            raise HTTPException(409, "A document has stale claims. Return to review.")
        a.submitted_at = now()
        a.evidence = body.evidence
        for days in [7, 14]:
            db.add(
                Reminder(
                    application_id=id,
                    title=f"Review manual follow-up after {days} days",
                    due_at=a.submitted_at + timedelta(days=days),
                )
            )
    elif body.stage in {"Interview", "Offer"}:
        if not a.submitted_at:
            raise HTTPException(409, "Record an approved manual submission first.")
    elif body.stage not in {"Rejected", "Withdrawn"}:
        if a.submitted_at:
            raise HTTPException(
                409, "Submission history is retained. Use Interview, Offer, Rejected or Withdrawn."
            )
        a.approved_at = None
    a.stage = body.stage
    log(db, "stage_changed", f"Moved to {body.stage}. No external action was performed.", id)
    commit(db)
    return view(db, a)


@api.post("/applications/{id}/notes", status_code=201)
def note(id: str, body: NoteInput, db: Session = Depends(database)):
    need(db, Application, id)
    n = Note(application_id=id, **body.model_dump())
    db.add(n)
    log(db, "note_added", "Private note or employer response recorded manually.", id)
    commit(db)
    return pack(n)


class GenerateInput(Input):
    kind: str = Field(pattern="^(resume|cover_letter)$")
    country: str = Field(max_length=80)
    contact_index: int | None = Field(default=None, ge=0, le=19)


@api.get("/templates")
def templates():
    return TEMPLATES


@api.post("/applications/{id}/documents")
def generate(id: str, body: GenerateInput, db: Session = Depends(database)):
    a = locked(db, id)
    j = need(db, Vacancy, a.vacancy_id)
    if a.stage in {"Approved", "Submitted", "Interview", "Offer"} or j.is_demo:
        raise HTTPException(
            409, "Return an unsubmitted application to review before generating drafts."
        )
    try:
        content, claims, checks = compose(
            db, view(db, a)["job"], body.kind, body.country, body.contact_index
        )
        identifier = str(uuid.uuid4())
        conversion, files = write_files(content, body.country, identifier)
    except ValueError as e:
        raise HTTPException(422, str(e)) from None
    for old in db.scalars(
        select(Document).where(
            Document.application_id == id,
            Document.kind == body.kind,
            Document.status.in_(["generated", "approved"]),
        )
    ):
        old.status = "superseded"
    d = Document(
        id=identifier,
        application_id=id,
        kind=body.kind,
        country_template=body.country,
        content=content,
        claims=claims,
        checks={**checks, **files},
        conversion=conversion,
    )
    db.add(d)
    a.updated_at = now()
    log(db, "document_generated", f"{body.kind} generated from checked facts; {conversion}.", id)
    commit(db)
    return docview(db, d)


@api.get("/documents/{id}")
def document(id: str, db: Session = Depends(database)):
    return docview(db, need(db, Document, id))


@api.post("/documents/{id}/approve")
def approve_document(id: str, db: Session = Depends(database)):
    d = need(db, Document, id)
    if d.status not in {"generated", "approved"} or not docview(db, d)["checks"]["passed"]:
        raise HTTPException(
            409, "Draft is superseded or its claims are stale. Generate a new checked version."
        )
    d.status = "approved"
    d.approved_at = now()
    log(
        db,
        "document_approved",
        "Owner explicitly approved this checked draft. Nothing was sent.",
        d.application_id,
    )
    commit(db)
    return docview(db, d)


@api.get("/documents/{id}/download/{format}")
def download_document(id: str, format: str, db: Session = Depends(database)):
    d = need(db, Document, id)
    if not docview(db, d)["checks"]["passed"]:
        raise HTTPException(409, "Source facts changed. Generate a fresh checked draft.")
    if format == "txt":
        return Response(
            d.content,
            media_type="text/plain",
            headers={"Content-Disposition": f'attachment; filename="CareerPilot-{d.kind}.txt"'},
        )
    if format not in {"docx", "pdf"}:
        raise HTTPException(404, "Unsupported document format")
    path = OUTPUTS / d.id / ("draft." + format)
    if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != d.checks.get(
        format + "_sha256"
    ):
        raise HTTPException(409, "File missing or changed; generate it again.")
    return FileResponse(
        path,
        filename=f"CareerPilot-{d.kind}.{format}",
        media_type="application/pdf"
        if format == "pdf"
        else "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )


class Upload(Input):
    filename: str = Field(min_length=1, max_length=240)
    media_type: str = Field(
        pattern="^(image/png|image/jpeg|application/pdf|message/rfc822|text/plain)$"
    )
    data: str = Field(max_length=7000000)


@api.post("/applications/{id}/evidence", status_code=201)
def evidence(id: str, body: Upload, db: Session = Depends(database)):
    need(db, Application, id)
    try:
        data = base64.b64decode(body.data, validate=True)
    except ValueError:
        raise HTTPException(422, "Invalid file encoding") from None
    if len(data) > 5000000:
        raise HTTPException(413, "File must be 5 MB or smaller")
    magic = {
        "image/png": b"\x89PNG\r\n\x1a\n",
        "image/jpeg": b"\xff\xd8\xff",
        "application/pdf": b"%PDF-",
    }
    if body.media_type in magic and not data.startswith(magic[body.media_type]):
        raise HTTPException(422, "File does not match the selected type")
    folder = PRIVATE / "evidence"
    folder.mkdir(mode=0o700, exist_ok=True)
    key = str(uuid.uuid4())
    path = folder / key
    path.write_bytes(data)
    path.chmod(0o600)
    name = re.sub(r"[^\w .()-]", "_", body.filename.replace("\\", "/").rsplit("/", 1)[-1])
    record = Evidence(application_id=id, filename=name, storage_key=key)
    db.add(record)
    log(db, "evidence_uploaded", "Owner uploaded private confirmation evidence.", id)
    commit(db)
    return pack(record, {"storage_key"})


@api.get("/evidence/{id}/download")
def evidence_download(id: str, db: Session = Depends(database)):
    e = need(db, Evidence, id)
    if not re.fullmatch("[a-f0-9-]{36}", e.storage_key):
        raise HTTPException(404, "File unavailable")
    return FileResponse(
        PRIVATE / "evidence" / e.storage_key,
        filename=e.filename,
        media_type="application/octet-stream",
    )


@api.get("/reminders")
def reminders(db: Session = Depends(database)):
    return [pack(r) for r in db.scalars(select(Reminder).order_by(Reminder.due_at))]


@api.post("/reminders/{id}/complete")
def complete_reminder(id: str, db: Session = Depends(database)):
    r = need(db, Reminder, id)
    r.completed = True
    log(
        db,
        "reminder_completed",
        "Manual follow-up reminder completed; nothing sent.",
        r.application_id,
    )
    commit(db)
    return pack(r)


@api.get("/employers")
def employers(db: Session = Depends(database)):
    return [pack(e) for e in db.scalars(select(Employer).order_by(Employer.name))]


@api.post("/employers", status_code=201)
def create_employer(body: EmployerInput, db: Session = Depends(database)):
    e = Employer(**body.model_dump())
    db.add(e)
    log(db, "employer_added", "Owner added a private employer research record.")
    commit(db)
    return pack(e)


@api.put("/employers/{id}")
def edit_employer(id: str, body: EmployerInput, db: Session = Depends(database)):
    e = need(db, Employer, id)
    for k, v in body.model_dump().items():
        setattr(e, k, v)
    log(db, "employer_updated", "Research and owner-sourced contacts updated.")
    commit(db)
    return pack(e)


@api.get("/sources")
def sources(db: Session = Depends(database)):
    from .sources import PUBLIC

    cfg = settings()
    return {
        "feeds": [pack(f) for f in db.scalars(select(Feed).order_by(Feed.employer))],
        "providers": {
            k: {
                "docs": v[1],
                "countries": "Employer-defined worldwide; first 100/title/country for SmartRecruiters, first 1,000 for other boards",
            }
            for k, v in PUBLIC.items()
        },
        "apis": [
            {
                "name": "Adzuna",
                "countries": "Canada, USA, Australia, UK, New Zealand, Italy",
                "configured": bool(cfg.adzuna_app_id and cfg.adzuna_app_key),
                "docs": "https://developer.adzuna.com/",
            },
            {
                "name": "USAJOBS",
                "countries": "USA federal only",
                "configured": bool(cfg.usajobs_api_key and cfg.usajobs_email),
                "docs": "https://developer.usajobs.gov/",
            },
            {
                "name": "Remotive",
                "countries": "Remote only; source geography restrictions apply",
                "configured": True,
                "docs": "https://github.com/remotive-com/remote-jobs-api",
            },
        ],
        "openai_configured": bool(cfg.openai_api_key),
        "ai_mode": "Local rules and extractive drafting; OpenAI calls and daily scheduling are disabled.",
    }


@api.post("/sources/feeds", status_code=201)
def add_feed(body: FeedInput, db: Session = Depends(database)):
    f = db.scalar(select(Feed).where(Feed.provider == body.provider, Feed.slug == body.slug))
    if not f:
        f = Feed(**body.model_dump())
        db.add(f)
    log(db, "feed_added", "Owner added a disabled feed, pending actual verification.")
    commit(db)
    return pack(f)


@api.post("/sources/feeds/{id}/verify")
async def verify_feed(id: str, db: Session = Depends(database)):
    f = need(db, Feed, id)
    try:
        rows = await providers.feed(f.provider, f.slug, f.employer)
        f.enabled = True
        f.verified_at = now()
        f.last_error = ""
        ok = True
        message = f"Public feed responded with {len(rows)} listings."
    except ValueError as e:
        f.enabled = False
        f.last_error = str(e)
        ok = False
        message = str(e)
    log(
        db,
        "feed_checked",
        "Public feed check " + ("succeeded." if ok else "failed; source remains disabled."),
    )
    commit(db)
    return {"ok": ok, "message": message, "feed": pack(f)}


@api.delete("/sources/feeds/{id}", status_code=204)
def delete_feed(id: str, db: Session = Depends(database)):
    db.delete(need(db, Feed, id))
    log(db, "feed_deleted", "Owner removed an employer feed.")
    commit(db)
    return Response(status_code=204)


@api.post("/sources/bootstrap")
async def starter_check(db: Session = Depends(database)):
    result = []
    for name, slug in STARTERS:
        f = db.scalar(select(Feed).where(Feed.provider == "smartrecruiters", Feed.slug == slug))
        if not f:
            f = Feed(employer=name, provider="smartrecruiters", slug=slug)
            db.add(f)
            db.flush()
        result.append(await verify_feed(f.id, db))
    return {"results": result}


@api.post("/search")
async def search(body: SearchInput, db: Session = Depends(database)):
    try:
        return await asyncio.wait_for(providers.search(db, body), 60)
    except TimeoutError:
        raise HTTPException(
            504,
            "Source time limit reached. Retry with fewer feeds; no substitute vacancies were created.",
        ) from None


class CaptureInput(Input):
    url: str = Field(max_length=2048)
    permitted: bool = False


@api.post("/capture")
async def capture_job(body: CaptureInput):
    try:
        return await asyncio.wait_for(capture(body.url, body.permitted), 40)
    except (ValueError, OSError) as e:
        raise HTTPException(
            422, str(e) if isinstance(e, ValueError) else "Read failed. Paste the text instead."
        ) from None


@api.get("/saved-searches")
def saved_searches(db: Session = Depends(database)):
    return [pack(s) for s in db.scalars(select(SavedSearch).order_by(desc(SavedSearch.created_at)))]


@api.post("/saved-searches", status_code=201)
def save_search(body: SavedInput, db: Session = Depends(database)):
    s = SavedSearch(**body.model_dump())
    db.add(s)
    log(db, "search_saved", "Saved an on-demand search; no schedule enabled.")
    commit(db)
    return pack(s)


@api.delete("/saved-searches/{id}", status_code=204)
def delete_search(id: str, db: Session = Depends(database)):
    db.delete(need(db, SavedSearch, id))
    log(db, "search_removed", "Owner removed a saved search.")
    commit(db)
    return Response(status_code=204)


@api.post("/saved-searches/{id}/run")
async def run_saved(id: str, offset: int = 0, db: Session = Depends(database)):
    s = need(db, SavedSearch, id)
    queries = list(product(s.titles, s.countries, s.sources))
    if offset < 0 or offset >= len(queries):
        raise HTTPException(422, "Invalid batch offset")
    jobs = []
    errors = []
    for title, country, source in queries[offset : offset + 3]:
        try:
            r = await search(SearchInput(title=title, country=country, source=source), db)
            jobs += r["jobs"]
            errors += [f"{title}/{country}/{source}: " + x for x in r["errors"]]
        except HTTPException as e:
            errors.append(f"{title}/{country}/{source}: " + str(e.detail))
    next_offset = offset + 3 if offset + 3 < len(queries) else None
    s.result = {
        "jobs": unique(jobs),
        "errors": errors,
        "next_offset": next_offset,
        "total_queries": len(queries),
        "completed": min(3, len(queries) - offset),
    }
    s.last_run = now()
    log(
        db,
        "search_run",
        "Owner ran a bounded search batch. No job was automatically saved or submitted.",
    )
    commit(db)
    return pack(s)


@api.get("/activity")
def activity(db: Session = Depends(database)):
    return [
        pack(a) for a in db.scalars(select(Activity).order_by(desc(Activity.created_at)).limit(30))
    ]


@api.get("/tracker/export")
def export(db: Session = Depends(database)):
    out = io.StringIO()
    out.write("\ufeff")
    w = csv.writer(out)
    w.writerow(
        [
            "Title",
            "Employer",
            "Country",
            "Location",
            "Stage",
            "Score",
            "Source URL",
            "Captured",
            "Approved",
            "Submitted",
            "Fictional",
        ]
    )
    for a in db.scalars(select(Application)):
        v = view(db, a)
        j = v["job"]
        values = [
            j["title"],
            j["employer"],
            j["country"],
            j["location"],
            a.stage,
            v["fit"]["score"],
            j["url"],
            a.created_at,
            a.approved_at,
            a.submitted_at,
            j["is_demo"],
        ]
        w.writerow(
            [
                "'" + str(x)
                if str(x or "").lstrip().startswith(("=", "+", "-", "@", "\t", "\r"))
                else x
                for x in values
            ]
        )
    return Response(
        out.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="CareerPilot-tracker.csv"'},
    )


@api.get("/storage")
def storage():
    return {
        "data": str(DATA),
        "private": str(PRIVATE),
        "outputs": str(OUTPUTS),
        "backup": "Stop CareerPilot, then copy the entire data folder to a private backup. Protect it; it contains personal records and keys.",
    }


app.include_router(api)
