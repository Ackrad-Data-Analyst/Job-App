import argparse
import json
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from .config import PRIVATE, engine
from .matching import defaults
from .models import FACTS, Activity, Application, Candidate, Employer, Feed, Preferences, Vacancy
from .schemas import CandidateInput, FactInput, PreferencesInput

STARTERS = [
    ("AECOM", "AECOM2"),
    ("Turner & Townsend", "TurnerTownsend"),
    ("Ramboll", "Ramboll3"),
    ("Egis", "EgisGroup"),
    ("BESIX", "BESIX"),
]


def import_seed(db, value):
    person = db.scalar(select(Candidate))
    if person and (
        person.name != "My profile" or any(db.scalar(select(m.id)) for m in FACTS.values())
    ):
        return False
    candidate = CandidateInput.model_validate(value["candidate"])
    entries = {k: [FactInput.model_validate(f) for f in value.get(k, [])] for k in FACTS}
    preferences = PreferencesInput.model_validate(value.get("preferences", defaults())).model_dump()
    if not person:
        person = Candidate()
        db.add(person)
        db.flush()
    for k, v in candidate.model_dump().items():
        setattr(person, k, v)
    for kind, rows in entries.items():
        for row in rows:
            db.add(FACTS[kind](candidate_id=person.id, **row.model_dump()))
    pref = db.scalar(select(Preferences))
    if pref:
        pref.data = preferences
    else:
        db.add(Preferences(candidate_id=person.id, data=preferences))
    db.add(
        Activity(
            action="profile_imported",
            message="Private profile imported. Unverified and excluded facts remain restricted.",
        )
    )
    db.commit()
    return True


def initialize(db, starters=False):
    fresh = db.scalar(select(Candidate)) is None
    if fresh:
        person = Candidate()
        db.add(person)
        db.flush()
        db.add(Preferences(candidate_id=person.id, data=defaults()))
        if starters:
            # These boards were checked on 16 October 2026. No vacancies are preloaded.
            for name, slug in STARTERS:
                db.add(
                    Feed(
                        employer=name,
                        provider="smartrecruiters",
                        slug=slug,
                        enabled=True,
                        verified_at=datetime.fromisoformat("2026-10-16T01:34:00+00:00"),
                    )
                )
    db.commit()


def demo(db):
    if db.scalar(select(Vacancy).where(Vacancy.is_demo.is_(True))):
        return
    e = Employer(
        name="Fictional Northfield Infrastructure",
        sector="Fictional civil engineering consultancy",
        research_notes="Demonstration only. This employer and these vacancies are fictional.",
    )
    db.add(e)
    db.flush()
    for title, city, stage in [
        ("Junior Civil Engineer (fictional)", "Regina", "Discovered"),
        ("GIS Analyst (fictional)", "Calgary", "Under Review"),
        ("Graduate Drainage Engineer (fictional)", "Dubai", "Shortlisted"),
    ]:
        j = Vacancy(
            employer_id=e.id,
            title=title,
            country="UAE" if city == "Dubai" else "Canada",
            location=city,
            description="FICTIONAL DEMONSTRATION. This is not a genuine job opening. Example full-time role supporting civil infrastructure, GIS and drainage analysis. Example requirements: QGIS and Python.",
            source="Fictional demonstration",
            is_demo=True,
            verification="fictional",
            fingerprint="fictional-" + city,
        )
        db.add(j)
        db.flush()
        db.add(
            Application(candidate_id=db.scalar(select(Candidate)).id, vacancy_id=j.id, stage=stage)
        )
    db.add(
        Activity(
            action="demo_added",
            message="Clearly fictional examples added. They cannot be verified or submitted.",
        )
    )
    db.commit()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--no-starters", action="store_true")
    parser.add_argument("--demo", action="store_true")
    args = parser.parse_args()
    with Session(engine()) as db:
        initialize(db, not args.no_starters)
        path = PRIVATE / "profile.seed.json"
        if path.exists():
            import_seed(db, json.loads(path.read_text(encoding="utf-8")))
        if args.demo:
            demo(db)
    print("Database initialized. Existing records preserved; no career facts invented.")
