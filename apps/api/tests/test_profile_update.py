import copy

import pytest
from careerpilot.models import Application, Document, Preferences, Skill
from careerpilot.profile_update import apply_update
from careerpilot.schemas import CandidateInput, FactInput
from sqlalchemy import select


def payload(client):
    profile = client.get("/api/profile").json()
    return {
        "candidate": {k: profile["candidate"][k] for k in CandidateInput.model_fields},
        **{
            k: [{f: row[f] for f in FactInput.model_fields} for row in profile[k]]
            for k in [
                "experience",
                "education",
                "skills",
                "projects",
                "certifications",
                "languages",
                "identity",
                "rules",
            ]
        },
        "preferences": client.get("/api/preferences").json(),
    }


def test_correction_retains_fact_ids_and_saved_jobs(person, job, db):
    value = payload(person)
    old = {s.title: s.id for s in db.scalars(select(Skill))}
    value["skills"][0]["details"] = "Corrected owner-supplied skill scope."
    value["skills"].append({"title": "Fictional new research skill", "status": "confirmed"})
    country = value["preferences"]["countries"][0]
    country["authorization"] = "authorised"
    country["authorization_note"] = "Owner confirms a permit; type and conditions unspecified."
    result = apply_update(db, value)
    db.commit()
    assert result["added"] == 1 and result["changed"] == 1
    assert all(db.get(Skill, id).title == title for title, id in old.items())
    assert db.get(Application, job["id"]).vacancy_id == job["vacancy_id"]
    assert db.scalar(select(Preferences)).data["countries"][0]["authorization"] == "authorised"


def test_correction_supersedes_unsent_drafts(person, job, db):
    d = person.post(
        "/api/applications/" + job["id"] + "/documents",
        json={"kind": "resume", "country": "Canada"},
    ).json()
    a = db.get(Application, job["id"])
    a.stage = "Approved"
    db.commit()
    result = apply_update(db, payload(person))
    db.commit()
    assert result["drafts_superseded"] == 1
    assert db.get(Document, d["id"]).status == "superseded"
    assert a.stage == "Under Review" and a.approved_at is None


def test_correction_preserves_completed_submission_history(person, job, db):
    from careerpilot.models import now

    d = person.post(
        "/api/applications/" + job["id"] + "/documents",
        json={"kind": "resume", "country": "Canada"},
    ).json()
    a = db.get(Application, job["id"])
    a.stage = "Submitted"
    a.submitted_at = now()
    a.evidence = "Fictional test confirmation."
    db.commit()
    apply_update(db, payload(person))
    db.commit()
    assert a.stage == "Submitted" and a.evidence == "Fictional test confirmation."
    assert db.get(Document, d["id"]).status == "generated"


def test_correction_retains_owner_salary_settings_and_is_repeatable(person, db):
    pref = db.scalar(select(Preferences))
    current = copy.deepcopy(pref.data)
    current["countries"][0]["min_salary"] = 65000
    current["exchange_rates"] = {"USD": 1.3}
    current["exchange_rate_date"] = "2026-11-03"
    pref.data = current
    db.commit()
    value = payload(person)
    value["preferences"]["countries"][0]["min_salary"] = None
    value["preferences"]["exchange_rates"] = {}
    apply_update(db, value)
    db.commit()
    count = len(list(db.scalars(select(Skill))))
    apply_update(db, value)
    db.commit()
    assert len(list(db.scalars(select(Skill)))) == count
    assert pref.data["countries"][0]["min_salary"] == 65000
    assert pref.data["exchange_rates"] == {"USD": 1.3}


def test_invalid_correction_does_not_change_profile(person, db):
    from careerpilot.models import Candidate

    value = payload(person)
    original = value["candidate"]["name"]
    value["candidate"]["name"] = "Unapplied fictional replacement"
    value["experience"][0]["start_date"] = "not-a-date"
    with pytest.raises(ValueError):
        apply_update(db, value)
    assert db.scalar(select(Candidate)).name == original
