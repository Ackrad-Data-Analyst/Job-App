"""Apply an owner-supplied profile correction while retaining application history."""

import argparse
import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from .config import PRIVATE, engine
from .models import FACTS, Activity, Application, Candidate, Document, Preferences
from .schemas import CandidateInput, FactInput, PreferencesInput


def prepared(value):
    candidate = CandidateInput.model_validate(value["candidate"]).model_dump()
    facts = {
        kind: [FactInput.model_validate(f).model_dump() for f in value.get(kind, [])]
        for kind in FACTS
    }
    preferences = PreferencesInput.model_validate(value["preferences"]).model_dump()
    return candidate, facts, preferences


def apply_update(db, value):
    # Validate the complete input before changing any record.
    candidate, entries, incoming = prepared(value)
    person = db.scalar(select(Candidate))
    if person is None:
        raise ValueError("Start CareerPilot once to initialise the database first.")
    for key, val in candidate.items():
        setattr(person, key, val)
    added = changed = 0
    for kind, rows in entries.items():
        model = FACTS[kind]
        existing = list(db.scalars(select(model).where(model.candidate_id == person.id)))
        index = {}
        for row in existing:
            key = (row.title.casefold().strip(), row.organization.casefold().strip())
            index.setdefault(key, []).append(row)
        for row in rows:
            key = (row["title"].casefold().strip(), row["organization"].casefold().strip())
            matches = index.get(key, [])
            if len(matches) > 1:
                raise ValueError(
                    "Duplicate career facts need review before this correction can be applied."
                )
            item = matches[0] if matches else None
            if item is None:
                item = model(candidate_id=person.id, **row)
                db.add(item)
                index[key] = [item]
                added += 1
            elif any(getattr(item, k) != v for k, v in row.items()):
                for k, v in row.items():
                    setattr(item, k, v)
                changed += 1
    pref = db.scalar(select(Preferences).where(Preferences.candidate_id == person.id))
    if pref:
        current = pref.data
        # Retain owner-entered salary comparisons and optional document toggles.
        for key in [
            "comparison_currency",
            "exchange_rates",
            "exchange_rate_date",
            "languages_on_resume",
            "canadian_location",
        ]:
            if key in current:
                incoming[key] = current[key]
        for country in incoming["countries"]:
            old = next(
                (c for c in current.get("countries", []) if c["country"] == country["country"]), {}
            )
            if country["min_salary"] is None and old.get("min_salary") is not None:
                country["min_salary"] = old["min_salary"]
                country["currency"] = old.get("currency", country["currency"])
        pref.data = PreferencesInput.model_validate(incoming).model_dump()
    else:
        db.add(Preferences(candidate_id=person.id, data=incoming))
    # Retain completed submissions and their history. Unsent drafts need fresh review.
    superseded = 0
    for application in db.scalars(select(Application).where(Application.candidate_id == person.id)):
        if application.submitted_at is not None:
            continue
        for doc in db.scalars(
            select(Document).where(
                Document.application_id == application.id,
                Document.status.in_(["generated", "approved"]),
            )
        ):
            doc.status = "superseded"
            doc.approved_at = None
            superseded += 1
        if application.stage in {"Approved", "Draft Ready"}:
            application.stage = "Under Review"
            application.approved_at = None
    db.add(
        Activity(
            action="profile_corrected",
            message="Owner-supplied career profile correction applied. Unsent drafts require fresh review; saved jobs and submitted history retained.",
        )
    )
    db.flush()
    return {"added": added, "changed": changed, "drafts_superseded": superseded}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("file", type=Path)
    args = parser.parse_args()
    value = json.loads(args.file.read_text(encoding="utf-8-sig"))
    prepared(value)
    if (PRIVATE / "runner.lock").exists():
        raise ValueError("Stop CareerPilot using stop.bat before applying the profile correction.")
    db_engine = engine()
    if db_engine.dialect.name != "sqlite":
        raise ValueError(
            "This local correction tool requires SQLite. Back up a remote database separately first."
        )
    backups = PRIVATE / "backups"
    backups.mkdir(parents=True, exist_ok=True, mode=0o700)
    destination = backups / (
        "before-profile-correction-" + datetime.now(UTC).strftime("%Y%m%dT%H%M%S%f") + ".db"
    )
    connection = db_engine.raw_connection()
    try:
        with sqlite3.connect(destination) as copy:
            connection.driver_connection.backup(copy)
    finally:
        connection.close()
    destination.chmod(0o600)
    with Session(db_engine) as db:
        result = apply_update(db, value)
        db.commit()
    print(
        "Profile corrected. Added facts: {added}; updated facts: {changed}; superseded unsent drafts: {drafts_superseded}.".format(
            **result
        )
    )
    print(
        "A full private database backup was saved in data/private/backups. Saved applications and submitted history were retained."
    )
    print("Open start.bat to use the corrected profile.")


if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError) as error:
        raise SystemExit(str(error)) from None
