from datetime import UTC, datetime, timedelta

import pytest
from careerpilot.matching import analytics_domain, fit, salary_comparison
from careerpilot.models import Preferences
from careerpilot.screening import competition, discovery_screen, posting_age
from sqlalchemy import select

NOW = datetime(2026, 11, 5, 12, tzinfo=UTC)
PREFS = {
    "max_job_age_days": 5,
    "max_applicant_count": 100,
    "older_job_applicant_threshold": 20,
    "include_unknown_applicant_count": True,
    "include_unknown_posted_date": False,
    "use_apply_clicks_as_proxy": False,
}


def job(age, count=None, metric="applications", relation="exact"):
    return {
        "published_at": (NOW - timedelta(days=age)).isoformat(),
        "published_at_kind": "posted",
        "applicant_count": count,
        "applicant_metric": metric,
        "applicant_count_relation": relation,
    }


@pytest.mark.parametrize(
    "age,count,allowed",
    [
        (0, 0, True),
        (5, 100, True),
        (5.1, None, False),
        (1, 101, False),
        (6, 19, True),
        (60, 0, True),
        (6, 20, False),
        (6, None, False),
        (1, None, True),
        (5, 19, True),
    ],
)
def test_exact_owner_freshness_competition_rule(age, count, allowed):
    assert discovery_screen(job(age, count), PREFS, NOW)["allowed"] == allowed


def test_unknown_is_never_zero_and_clicks_are_not_applications():
    assert competition({}, PREFS)[:2] == (None, None)
    result = discovery_screen(job(30, 10, "apply clicks"), PREFS, NOW)
    assert not result["allowed"] and "not a completed-application" in result["count_note"]
    assert (
        discovery_screen(
            job(1, 10, "apply clicks"), {**PREFS, "include_unknown_applicant_count": False}, NOW
        )["allowed"]
        is False
    )
    assert (
        discovery_screen(
            job(30, 10, "apply clicks"), {**PREFS, "use_apply_clicks_as_proxy": True}, NOW
        )["allowed"]
        is True
    )


@pytest.mark.parametrize(
    "count,relation,allowed",
    [
        (100, "more than", False),
        (100, "at least", False),
        (20, "less than", True),
        (19, "at least", False),
        (19, "more than", False),
    ],
)
def test_qualified_counts_do_not_become_exact_counts(count, relation, allowed):
    assert discovery_screen(job(30, count, relation=relation), PREFS, NOW)["allowed"] == allowed


def test_updated_dates_do_not_masquerade_as_new_postings():
    data = job(0, None)
    data["published_at_kind"] = "updated"
    assert posting_age(data, NOW)[0] is None
    assert not discovery_screen(data, PREFS, NOW)["allowed"]
    assert discovery_screen({**data, "applicant_count": 5}, PREFS, NOW)["allowed"]


@pytest.mark.parametrize(
    "text,age",
    [
        ("Posted Today", 0),
        ("Posted Yesterday", 1),
        ("Posted 5 Days Ago", 5),
        ("Posted 30+ Days Ago", 30),
    ],
)
def test_relative_employer_posting_dates(text, age):
    assert posting_age({"published_at": text, "published_at_kind": "posted"}, NOW)[0] == age


def test_monthly_floors_compare_with_published_annual_rates(client):
    pref = client.get("/api/preferences").json()
    country = pref["countries"][0]
    country.update(min_salary=4000, min_salary_period="month", currency="CAD")
    j = {
        "salary_min": 48000,
        "salary_max": 60000,
        "salary_currency": "CAD",
        "salary_period": "year",
    }
    result = salary_comparison(j, pref, country)
    assert (
        result["country_comparison"]["min"] == 4000 and result["country_comparison"]["max"] == 5000
    )
    assert result["minimum_status"].startswith("Published lower bound meets")
    j.update(salary_min=40000, salary_max=45000)
    assert salary_comparison(j, pref, country)["minimum_status"] == "Below country minimum."
    j.update(salary_period="hour")
    assert (
        salary_comparison(j, pref, country)["minimum_status"]
        == "Currency/pay period not comparable."
    )


def test_opt_route_flags_degree_relationship_and_future_start(person, job, db):
    row = db.scalar(select(Preferences))
    data = dict(row.data)
    data["countries"] = [dict(c) for c in data["countries"]]
    usa = next(c for c in data["countries"] if c["country"] == "USA")
    usa.update(
        authorization="authorised",
        authorization_route="OPT - Business Analytics",
        work_start_not_before="2027-01-22",
        allow_internships=True,
    )
    row.data = data
    db.commit()
    civil = {
        **job["job"],
        "country": "USA",
        "title": "Civil Field Engineer",
        "description": "Construction site inspections and concrete supervision.",
    }
    f = fit(db, civil)
    assert (
        f["opt_alignment"]["status"] == "needs duties review"
        and f["work_start_not_before"] == "2027-01-22"
    )
    assert any("OPT degree relationship" in text for text in f["warnings"])
    analytics = {
        **civil,
        "title": "Infrastructure Data Analyst",
        "description": "Required qualifications: Python, SQL and data analysis.",
    }
    f = fit(db, analytics)
    assert f["opt_alignment"]["status"] == "potentially related"
    early = {**analytics, "description": analytics["description"] + " Start date: 2027-01-10."}
    assert any("earlier than" in text for text in fit(db, early)["blockers"])


def test_supervised_skill_is_not_independent_proficiency(person, job, db):
    r = person.post(
        "/api/profile/skills",
        json={
            "title": "HEC-RAS",
            "details": "Supporting use under supervision.",
            "status": "confirmed",
            "allowed_on_resume": True,
        },
    )
    assert r.status_code == 201
    f = fit(db, {**job["job"], "description": "Required qualifications: HEC-RAS, QGIS and Python."})
    assert "HEC-RAS" in f["required"]["supporting"] and "HEC-RAS" not in f["required"]["confirmed"]
    assert f["recommendation"] != "Apply"


def test_nonclinical_hospital_analytics_is_not_a_nursing_role(person, job, db):
    assert analytics_domain("Hospital Business Analyst")
    assert not analytics_domain("Nurse")
    f = fit(
        db,
        {
            **job["job"],
            "title": "Healthcare Data Analyst",
            "employer": "Fictional Hospital",
            "description": "Required qualifications: SQL and Python. Non-clinical performance reporting.",
        },
    )
    assert any("not blanket-excluded" in text for text in f["warnings"])
    assert not any("nursing" in text.lower() for text in f["blockers"])


@pytest.mark.parametrize(
    "url",
    [
        "https://www.indeed.com/viewjob?jk=1",
        "https://ca.indeed.com/viewjob?jk=1",
        "https://www.indeed.ca/viewjob",
        "https://company.indeedjobs.com/1",
    ],
)
def test_indeed_is_excluded_from_manual_capture_and_source_reads(client, url):
    assert (
        client.post(
            "/api/jobs",
            json={"title": "Civil engineer", "employer": "Fictional employer", "url": url},
        ).status_code
        == 422
    )
    response = client.post("/api/capture", json={"url": url, "permitted": True})
    assert response.status_code == 422 and "Indeed sources are excluded" in response.text


def test_usa_entry_level_pay_exception_and_intern_route(person, db):
    import asyncio

    import httpx
    from careerpilot.models import Feed
    from careerpilot.schemas import SearchInput
    from careerpilot.sources import Providers

    pref = db.scalar(select(Preferences))
    p = dict(pref.data)
    p["countries"] = [dict(c) for c in p["countries"]]
    usa = next(c for c in p["countries"] if c["country"] == "USA")
    usa.update(
        min_salary=5000,
        min_salary_period="month",
        currency="USD",
        allow_lower_for_early_career=True,
        allow_internships=True,
        authorization="authorised",
        authorization_route="OPT - Business Analytics",
        work_start_not_before="2027-01-22",
    )
    pref.data = p
    db.add(
        Feed(
            employer="Fictional employer", provider="smartrecruiters", slug="Example", enabled=True
        )
    )
    db.commit()
    rows = [
        {
            "id": "744000000000001",
            "name": "Infrastructure Data Analytics Intern",
            "location": {"city": "California", "country": "us"},
            "releasedDate": datetime.now(UTC).isoformat(),
            "typeOfEmployment": {"label": "Internship"},
        }
    ]
    provider = Providers(httpx.MockTransport(lambda r: httpx.Response(200, json={"content": rows})))
    result = asyncio.run(
        provider.search(
            db, SearchInput(title="Data Analyst", country="USA", scope="domain", track="analytics")
        )
    )
    assert result["total"] == 1
    assert not any("Intern/co-op is outside" in b for b in result["jobs"][0]["fit"]["blockers"])
