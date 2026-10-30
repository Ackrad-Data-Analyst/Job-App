import uuid
from datetime import UTC, datetime

from sqlalchemy import JSON, Boolean, CheckConstraint, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def now():
    return datetime.now(UTC)


class Base(DeclarativeBase):
    pass


class Record:
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, onupdate=now)


class Candidate(Record, Base):
    __tablename__ = "candidates"
    name: Mapped[str] = mapped_column(String(160), default="My profile")
    headline: Mapped[str] = mapped_column(String(240), default="")
    summary: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(20), default="unverified")
    allowed_on_resume: Mapped[bool] = mapped_column(Boolean, default=True)
    note: Mapped[str] = mapped_column(Text, default="")
    __table_args__ = (CheckConstraint("status IN ('confirmed','unverified','excluded')"),)


class CareerFact(Record):
    candidate_id: Mapped[str] = mapped_column(ForeignKey("candidates.id"), index=True)
    title: Mapped[str] = mapped_column(String(240))
    organization: Mapped[str] = mapped_column(String(240), default="")
    details: Mapped[str] = mapped_column(Text, default="")
    start_date: Mapped[str] = mapped_column(String(10), default="")
    end_date: Mapped[str] = mapped_column(String(10), default="")
    status: Mapped[str] = mapped_column(String(20), default="unverified")
    allowed_on_resume: Mapped[bool] = mapped_column(Boolean, default=True)
    learning: Mapped[bool] = mapped_column(Boolean, default=False)
    note: Mapped[str] = mapped_column(Text, default="")


class Experience(CareerFact, Base):
    __tablename__ = "experiences"


class Education(CareerFact, Base):
    __tablename__ = "education"


class Skill(CareerFact, Base):
    __tablename__ = "skills"


class Project(CareerFact, Base):
    __tablename__ = "projects"


class Certification(CareerFact, Base):
    __tablename__ = "certifications"


class Language(CareerFact, Base):
    __tablename__ = "languages"


class Identity(CareerFact, Base):
    __tablename__ = "identity_facts"


class Rule(CareerFact, Base):
    __tablename__ = "profile_rules"


FACTS = {"experience": Experience, "education": Education, "skills": Skill, "projects": Project,
         "certifications": Certification, "languages": Language, "identity": Identity, "rules": Rule}


class Preferences(Record, Base):
    __tablename__ = "preferences"
    candidate_id: Mapped[str] = mapped_column(ForeignKey("candidates.id"), unique=True)
    data: Mapped[dict] = mapped_column(JSON, default=dict)


class Employer(Record, Base):
    __tablename__ = "employers"
    name: Mapped[str] = mapped_column(String(240))
    website: Mapped[str] = mapped_column(String(2048), default="")
    careers_page: Mapped[str] = mapped_column(String(2048), default="")
    sector: Mapped[str] = mapped_column(String(240), default="")
    size: Mapped[str] = mapped_column(String(120), default="")
    countries: Mapped[list] = mapped_column(JSON, default=list)
    contacts: Mapped[list] = mapped_column(JSON, default=list)
    public_feed: Mapped[str] = mapped_column(String(240), default="")
    research_notes: Mapped[str] = mapped_column(Text, default="")


class Vacancy(Record, Base):
    __tablename__ = "vacancies"
    employer_id: Mapped[str] = mapped_column(ForeignKey("employers.id"), index=True)
    title: Mapped[str] = mapped_column(String(240))
    country: Mapped[str] = mapped_column(String(80), default="")
    location: Mapped[str] = mapped_column(String(240), default="")
    url: Mapped[str] = mapped_column(String(2048), default="")
    description: Mapped[str] = mapped_column(Text, default="")
    source: Mapped[str] = mapped_column(String(100), default="Manual capture")
    salary: Mapped[str] = mapped_column(String(240), default="Not published")
    salary_min: Mapped[float | None] = mapped_column(Float, nullable=True)
    salary_max: Mapped[float | None] = mapped_column(Float, nullable=True)
    salary_currency: Mapped[str] = mapped_column(String(3), default="")
    salary_period: Mapped[str] = mapped_column(String(10), default="")
    closing_date: Mapped[str] = mapped_column(String(80), default="")
    verification: Mapped[str] = mapped_column(String(20), default="unverified")
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False)
    fingerprint: Mapped[str] = mapped_column(String(64), index=True)


STAGES = ["Discovered", "Under Review", "Shortlisted", "Draft Ready", "Approved", "Submitted", "Interview", "Offer", "Rejected", "Withdrawn"]


class Application(Record, Base):
    __tablename__ = "applications"
    candidate_id: Mapped[str] = mapped_column(ForeignKey("candidates.id"))
    vacancy_id: Mapped[str] = mapped_column(ForeignKey("vacancies.id"), unique=True)
    stage: Mapped[str] = mapped_column(String(30), default="Discovered")
    version: Mapped[int] = mapped_column(Integer, default=1)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    evidence: Mapped[str] = mapped_column(Text, default="")
    __mapper_args__ = {"version_id_col": version}
    __table_args__ = (CheckConstraint("stage IN (" + ",".join(repr(s) for s in STAGES) + ")"),)


class Document(Record, Base):
    __tablename__ = "documents"
    application_id: Mapped[str] = mapped_column(ForeignKey("applications.id"), index=True)
    kind: Mapped[str] = mapped_column(String(30))
    country_template: Mapped[str] = mapped_column(String(80))
    content: Mapped[str] = mapped_column(Text)
    claims: Mapped[list] = mapped_column(JSON)
    checks: Mapped[dict] = mapped_column(JSON)
    conversion: Mapped[str] = mapped_column(String(120))
    status: Mapped[str] = mapped_column(String(30), default="generated")
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class Note(Record, Base):
    __tablename__ = "notes"
    application_id: Mapped[str] = mapped_column(ForeignKey("applications.id"), index=True)
    kind: Mapped[str] = mapped_column(String(30), default="note")
    body: Mapped[str] = mapped_column(Text)


class Activity(Record, Base):
    __tablename__ = "activity_logs"
    application_id: Mapped[str | None] = mapped_column(ForeignKey("applications.id"), nullable=True)
    action: Mapped[str] = mapped_column(String(80))
    message: Mapped[str] = mapped_column(Text)


class Feed(Record, Base):
    __tablename__ = "employer_feeds"
    employer: Mapped[str] = mapped_column(String(240))
    provider: Mapped[str] = mapped_column(String(30))
    slug: Mapped[str] = mapped_column(String(160))
    enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error: Mapped[str] = mapped_column(Text, default="")


class SavedSearch(Record, Base):
    __tablename__ = "saved_searches"
    name: Mapped[str] = mapped_column(String(160))
    titles: Mapped[list] = mapped_column(JSON)
    countries: Mapped[list] = mapped_column(JSON)
    sources: Mapped[list] = mapped_column(JSON)
    last_run: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    result: Mapped[dict] = mapped_column(JSON, default=dict)


class Reminder(Record, Base):
    __tablename__ = "reminders"
    application_id: Mapped[str] = mapped_column(ForeignKey("applications.id"))
    title: Mapped[str] = mapped_column(String(240))
    due_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    completed: Mapped[bool] = mapped_column(Boolean, default=False)


class Evidence(Record, Base):
    __tablename__ = "submission_evidence"
    application_id: Mapped[str] = mapped_column(ForeignKey("applications.id"))
    filename: Mapped[str] = mapped_column(String(240))
    storage_key: Mapped[str] = mapped_column(String(36))
