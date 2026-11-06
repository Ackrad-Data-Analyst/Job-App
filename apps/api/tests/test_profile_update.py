import copy

import pytest
from sqlalchemy import select

from careerpilot.models import Application, Document, Preferences, Skill
from careerpilot.profile_update import apply_update
from careerpilot.schemas import CandidateInput, FactInput


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


def test_market_update_removes_cancelled_plan_without_replacing_career_edits(person, job, db):
    from careerpilot.models import Candidate, Identity, Rule

    candidate = db.scalar(select(Candidate))
    candidate.summary = "Owner-edited current summary; retain it."
    db.add(Identity(candidate_id=candidate.id, title="Canada location", details="Regina"))
    db.add(Rule(candidate_id=candidate.id, title="Canada work route", details="Cancelled plan"))
    db.add(
        Rule(candidate_id=candidate.id, title="Private mobility context", details="Cancelled move")
    )
    db.add(Rule(candidate_id=candidate.id, title="Keep this private rule", details="Owner's rule"))
    pref = db.scalar(select(Preferences))
    before = copy.deepcopy(pref.data)
    before["countries"][0].update(
        min_salary=7100,
        min_salary_period="month",
        authorization="authorised",
        authorization_route="Owner-edited route",
    )
    before["countries"].insert(
        0, {"country": "Canada", "currency": "CAD", "authorization": "authorised"}
    )
    before.update(
        home_base="Regina",
        planned_move_date="2027-01-05",
        comparison_currency="CAD",
        exchange_rates={"CAD": 1.4, "AED": 3.67},
    )
    pref.data = before
    db.commit()
    value = payload(person)
    value["update_scope"] = "markets"
    value["candidate"]["summary"] = "Old export must not overwrite current edits."
    value["skills"][0]["details"] = "Old export must not overwrite a skill."
    incoming = value["preferences"]
    incoming["countries"] = [c for c in incoming["countries"] if c["country"] in {"USA", "UAE"}]
    incoming.update(
        home_base="San Francisco, CA",
        location_priorities=[],
        planned_move_date="",
        mobility_notes="USA and UAE only",
        comparison_currency="USD",
        canadian_location=False,
    )
    apply_update(db, value)
    db.commit()
    assert candidate.summary == "Owner-edited current summary; retain it."
    assert all(
        s.details != "Old export must not overwrite a skill." for s in db.scalars(select(Skill))
    )
    assert [c["country"] for c in pref.data["countries"]] == ["USA", "UAE"]
    assert pref.data["countries"][0]["min_salary"] == 7100
    assert pref.data["countries"][0]["authorization_route"] == "Owner-edited route"
    assert pref.data["home_base"] == "San Francisco, CA" and not pref.data["planned_move_date"]
    assert pref.data["comparison_currency"] == "USD" and pref.data["exchange_rates"] == {
        "AED": 3.67
    }
    assert not list(db.scalars(select(Identity).where(Identity.title == "Canada location")))
    assert {r.title for r in db.scalars(select(Rule))} == {"Keep this private rule"}
    assert db.get(Application, job["id"]).vacancy_id == job["vacancy_id"]
    apply_update(db, value)
    db.commit()
    assert {r.title for r in db.scalars(select(Rule))} == {"Keep this private rule"}


def test_market_update_rejects_other_countries_before_mutation(person, db):
    from careerpilot.models import Candidate

    value = payload(person)
    value["update_scope"] = "markets"
    value["preferences"]["countries"] = [{"country": "Canada"}]
    original = db.scalar(select(Candidate)).name
    value["candidate"]["name"] = "Must not be applied"
    with pytest.raises(ValueError, match="USA and UAE only"):
        apply_update(db, value)
    assert db.scalar(select(Candidate)).name == original


def test_market_update_clears_retired_saved_searches(person, db):
    from careerpilot.models import SavedSearch

    retired = SavedSearch(
        name="Regina search", titles=["Civil Engineer"], countries=["Canada"], sources=["feeds"]
    )
    mixed = SavedSearch(
        name="USA and Canada",
        titles=["GIS Analyst"],
        countries=["USA", "Canada"],
        sources=["feeds"],
        result={"old": "summary"},
    )
    kept = SavedSearch(
        name="My Dubai shortlist", titles=["Estimator"], countries=["UAE"], sources=["feeds"]
    )
    db.add_all([retired, mixed, kept])
    db.commit()
    retired_id = retired.id
    value = payload(person)
    value["update_scope"] = "markets"
    apply_update(db, value)
    db.commit()
    assert db.get(SavedSearch, retired_id) is None
    assert mixed.countries == ["USA"] and mixed.result == {} and "Canada" not in mixed.name
    assert kept.name == "My Dubai shortlist" and kept.countries == ["UAE"]
