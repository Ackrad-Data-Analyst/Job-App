import asyncio
import json

import httpx
import pytest
from careerpilot.catalog import BY_KEY, ats_board, check_batch
from careerpilot.locations import country_for, region_rank
from careerpilot.matching import links
from careerpilot.models import Feed, SourceVerification
from careerpilot.schemas import SearchInput
from careerpilot.sources import Providers, capture
from careerpilot.taxonomy import ALL_TITLES
from careerpilot.workday import decode_board, encode_board, public_board
from sqlalchemy import select


def run(value):
    return asyncio.run(value)


def smart_row(index, title=None, city="Regina", country="ca"):
    return {
        "id": str(744000000000000 + index),
        "name": title or "Junior Civil Engineer " + str(index),
        "location": {"city": city, "country": country},
    }


def test_employer_directory_is_not_a_list_of_vacancies(client):
    r = client.get("/api/sources/catalog")
    assert r.status_code == 200
    body = r.json()
    assert len(body["employers"]) >= 124 and len(body["role_titles"]) >= 143
    assert all(
        e["state"] == "unchecked" and "Unknown" in e["foreign_applicant_evidence"]
        for e in body["employers"]
    )
    assert client.get("/api/applications").json() == []
    assert all("indeed" not in json.dumps(e).lower() for e in body["employers"])
    assert all("first quantum" not in e["name"].lower() for e in body["employers"])
    assert any(e["key"] == "city-of-regina" for e in body["employers"])
    assert any(e["key"] == "etihad-rail" for e in body["employers"])
    assert len(set(ALL_TITLES)) == len(ALL_TITLES)


@pytest.mark.parametrize("country", ["Canada", "UAE", "USA"])
def test_no_indeed_or_disallowed_aggregator_links(country):
    result = links("Civil Engineer", country, "Regina")
    assert result and all("indeed" not in r["url"].lower() for r in result)
    assert all(
        "adzuna" not in r["url"].lower() and "remotive" not in r["url"].lower() for r in result
    )


@pytest.mark.parametrize(
    "location,explicit,expected",
    [
        ("Regina, SK", "", "Canada"),
        ("Calgary, AB", "", "Canada"),
        ("Toronto, Ontario", "", "Canada"),
        ("Dubai", "", "UAE"),
        ("Abu Dhabi", "", "UAE"),
        ("California", "", "USA"),
        ("Regina", "us", "USA"),
        ("Anywhere", "", ""),
        ("California", "", "USA"),
        ("Toronto, Ontario and Dubai", "", ""),
    ],
)
def test_conservative_location_normalisation(location, explicit, expected):
    assert country_for(location, explicit)[0] == expected


def test_location_preference_does_not_fabricate_commute_times():
    assert (
        region_rank("Regina, Saskatchewan", "Canada")[0]
        < region_rank("Calgary, Alberta", "Canada")[0]
    )
    assert (
        region_rank("Calgary, Alberta", "Canada")[0] < region_rank("Toronto, Ontario", "Canada")[0]
    )
    assert "commute" in region_rank("Regina", "Canada")[1]


def test_smartrecruiters_reads_following_pages(person, db):
    offsets = []

    def handler(r):
        assert r.url.host == "api.smartrecruiters.com"
        offset = int(r.url.params.get("offset", 0))
        offsets.append(offset)
        return httpx.Response(
            200,
            json={
                "content": [smart_row(i) for i in range(offset, min(offset + 100, 125))],
                "totalFound": 125,
            },
        )

    p = Providers(httpx.MockTransport(handler))
    rows = run(p.feed("smartrecruiters", "Fictional", "Fictional employer", "", "Canada"))
    assert len(rows) == 125 and offsets == [0, 100]
    db.add(
        Feed(
            employer="Fictional employer",
            provider="smartrecruiters",
            slug="Fictional",
            enabled=True,
        )
    )
    db.commit()
    first = run(p.search(db, SearchInput(title="Civil Engineer", country="Canada", limit=50)))
    second = run(
        p.search(db, SearchInput(title="Civil Engineer", country="Canada", limit=50, offset=50))
    )
    assert first["total"] == 125 and first["has_more"] and len(first["jobs"]) == 50
    assert second["offset"] == 50 and len(second["jobs"]) == 50
    assert not ({r["url"] for r in first["jobs"]} & {r["url"] for r in second["jobs"]})


def test_more_than_twenty_employer_feeds_are_attempted_in_parallel(person, db):
    async def exercise():
        active = 0
        maximum = 0
        calls = []

        async def handler(r):
            nonlocal active, maximum
            active += 1
            maximum = max(maximum, active)
            calls.append(r.url.path)
            await asyncio.sleep(0.01)
            active -= 1
            return httpx.Response(200, json={"content": [smart_row(1)]})

        p = Providers(httpx.MockTransport(handler))
        for i in range(23):
            db.add(
                Feed(
                    employer="Fictional employer " + str(i),
                    provider="smartrecruiters",
                    slug="Example" + str(i),
                    enabled=True,
                )
            )
        db.commit()
        result = await p.search(db, SearchInput(title="Civil Engineer", country="Canada"))
        assert len(result["source_checks"]) == 23 and len(calls) == 23 and maximum > 1
        assert result["total"] == 23

    run(exercise())


def test_related_titles_and_preferred_region_keep_broader_canada(person, db):
    rows = [
        smart_row(1, "Municipal Engineering EIT", "Regina"),
        smart_row(2, "Infrastructure Engineer-in-Training", "Calgary"),
        smart_row(3, "Junior Civil Engineer", "Toronto"),
        smart_row(4, "Senior Civil Engineer", "Regina"),
        smart_row(5, "Software Engineer", "Regina"),
        smart_row(6, "Civil Engineer", "California", "us"),
    ]
    p = Providers(httpx.MockTransport(lambda r: httpx.Response(200, json={"content": rows})))
    db.add(
        Feed(
            employer="Fictional employer", provider="smartrecruiters", slug="Example", enabled=True
        )
    )
    db.commit()
    r = run(
        p.search(db, SearchInput(title="Junior Civil Engineer", country="Canada", region="Regina"))
    )
    assert r["total"] == 3 and r["jobs"][0]["location"].startswith("Regina")
    assert r["filtered"]["seniority"] == 1 and r["filtered"]["different_country"] == 1
    only = run(
        p.search(
            db,
            SearchInput(
                title="Junior Civil Engineer", country="Canada", region="Regina", region_mode="only"
            ),
        )
    )
    assert only["total"] == 1


def test_unknown_country_remains_unknown_until_owner_selects_it(person, db):
    payload = {
        "jobs": [
            {
                "title": "Civil Engineer",
                "absolute_url": "https://example.invalid/1",
                "location": {"name": "Location not supplied"},
                "content": "Civil infrastructure. Required qualifications: Python.",
            }
        ]
    }
    p = Providers(httpx.MockTransport(lambda r: httpx.Response(200, json=payload)))
    db.add(Feed(employer="Fictional employer", provider="greenhouse", slug="Example", enabled=True))
    db.commit()
    assert run(p.search(db, SearchInput(title="Civil Engineer", country="Canada")))["total"] == 0
    r = run(
        p.search(
            db, SearchInput(title="Civil Engineer", country="Canada", include_unknown_country=True)
        )
    )
    assert r["total"] == 1 and r["jobs"][0]["country"] == ""
    assert any("Country could not be established" in s for s in r["jobs"][0]["fit"]["warnings"])


@pytest.mark.parametrize("source", ["adzuna", "remotive"])
def test_aggregator_sources_fail_closed_without_network(client, source):
    r = client.post(
        "/api/search", json={"title": "Civil Engineer", "country": "Canada", "source": source}
    )
    assert r.status_code == 200 and r.json()["jobs"] == []
    assert "disabled" in r.json()["errors"][0]


def test_failed_sources_keep_directory_targets_separate_from_jobs(person, db):
    db.add(
        Feed(
            employer="Fictional employer", provider="smartrecruiters", slug="Example", enabled=True
        )
    )
    db.commit()
    p = Providers(httpx.MockTransport(lambda r: httpx.Response(403)))
    r = run(p.search(db, SearchInput(title="Civil Engineer", country="Canada")))
    assert r["jobs"] == [] and r["total"] == 0 and r["errors"] and r["target_count"] > 50
    assert r["employer_targets"] and r["source_checks"][0]["status"] == "failed"


@pytest.mark.parametrize(
    "url,expected",
    [
        ("https://jobs.smartrecruiters.com/Example", "smartrecruiters"),
        ("https://boards.greenhouse.io/Example", "greenhouse"),
        ("https://jobs.lever.co/Example", "lever"),
        ("https://jobs.ashbyhq.com/Example", "ashby"),
        ("https://example.wd3.myworkdayjobs.com/en-US/External", "workday"),
        ("https://jobs.smartrecruiters.com.evil.invalid/Example", None),
        ("http://jobs.lever.co/Example", None),
    ],
)
def test_discovered_board_requires_recognised_public_host(url, expected):
    value = ats_board(url)
    assert (value[0] if value else None) == expected


def test_career_page_check_discovers_real_linked_feed_only(client, db):
    def handler(r):
        if r.url.path == "/robots.txt":
            return httpx.Response(200, text="User-agent: *\nAllow: /")
        if r.url.host == "api.smartrecruiters.com":
            return httpx.Response(200, json={"content": [smart_row(1)]})
        return httpx.Response(
            200,
            text='<html><title>Clifton Careers</title><a href="https://jobs.smartrecruiters.com/Clifton">Jobs</a></html>',
        )

    transport = httpx.MockTransport(handler)
    p = Providers(transport)
    r = run(check_batch(db, ["clifton-engineering-group"], p, transport))
    assert r["results"][0]["state"] == "checked" and len(r["results"][0]["feed_ids"]) == 1
    feed = db.scalar(select(Feed))
    assert feed.provider == "smartrecruiters" and feed.slug == "Clifton" and feed.enabled
    run(check_batch(db, ["clifton-engineering-group"], p, transport))
    assert len(list(db.scalars(select(Feed)))) == 1
    assert len(list(db.scalars(select(SourceVerification)))) == 1


@pytest.mark.parametrize(
    "policy,status", [("User-agent: *\nDisallow: /", 200), ("", 403), ("", 404)]
)
def test_unavailable_or_disallowed_career_page_never_enables_a_feed(client, db, policy, status):
    def handler(r):
        if r.url.path == "/robots.txt":
            return httpx.Response(200, text=policy)
        return httpx.Response(status, text="Unavailable")

    transport = httpx.MockTransport(handler)
    r = run(check_batch(db, ["clifton-engineering-group"], Providers(transport), transport))
    assert not r["results"][0]["feed_ids"]
    assert list(db.scalars(select(Feed))) == []
    assert r["results"][0]["state"] in {"unavailable", "blocked"}


def test_catalog_check_api_is_authenticated_and_bounded(client):
    assert client.get("/api/sources/catalog", headers={"Authorization": ""}).status_code == 401
    assert (
        client.post("/api/sources/catalog/check", json={"keys": ["not-in-catalog"]}).status_code
        == 422
    )
    assert (
        client.post("/api/sources/catalog/check", json={"keys": list(BY_KEY)[:9]}).status_code
        == 422
    )


def test_workday_public_search_pages_and_full_description(person, db):
    calls = []

    def handler(r):
        calls.append(r)
        if r.url.path == "/robots.txt":
            return httpx.Response(404)
        if r.method == "POST":
            query = json.loads(r.content)
            offset = query["offset"]
            assert query["searchText"] == ""
            return httpx.Response(
                200,
                json={
                    "total": 25,
                    "jobPostings": [
                        {
                            "title": "Junior Civil Engineer " + str(i),
                            "externalPath": "/job/Regina/Civil_" + str(i),
                            "locationsText": "Regina, Saskatchewan",
                            "postedOn": "Posted Today",
                        }
                        for i in range(offset, min(offset + 20, 25))
                    ],
                },
            )
        return httpx.Response(
            200,
            json={
                "jobPostingInfo": {
                    "title": "Junior Civil Engineer",
                    "location": "Regina, Saskatchewan",
                    "jobDescription": "<p>Required qualifications: QGIS and Python.</p>",
                    "company": "Fictional employer",
                }
            },
        )

    transport = httpx.MockTransport(handler)
    slug = encode_board("https://example.wd3.myworkdayjobs.com/en-US/External")
    p = Providers(transport)
    jobs = run(p.feed("workday", slug, "Fictional employer", "", "Canada"))
    assert (
        len(jobs) == 25 and jobs[0]["country"] == "Canada" and not jobs[0]["description_complete"]
    )
    assert len([r for r in calls if r.method == "POST"]) == 2
    assert all("/wday/cxs/example/External/jobs" in r.url.path for r in calls if r.method == "POST")
    full = run(capture(jobs[0]["url"], True, transport))
    assert "Required qualifications" in full["description"] and full["country"] == "Canada"
    assert all("alex@example.invalid" not in r.content.decode() for r in calls)


def test_workday_robots_policy_stops_search_read():
    requests = []

    def handler(r):
        requests.append(r)
        return httpx.Response(200, text="User-agent: *\nDisallow: /wday/")

    p = Providers(httpx.MockTransport(handler))
    slug = encode_board("https://example.wd3.myworkdayjobs.com/External")
    with pytest.raises(ValueError):
        run(p.feed("workday", slug, "Fictional employer"))
    assert len(requests) == 1 and requests[0].method == "GET"


@pytest.mark.parametrize(
    "url",
    [
        "http://example.wd3.myworkdayjobs.com/External",
        "https://example.wd3.myworkdayjobs.com.evil.invalid/External",
        "https://user:secret@example.wd3.myworkdayjobs.com/External",
        "https://127.0.0.1/External",
    ],
)
def test_workday_rejects_non_public_or_spoofed_boards(url):
    assert public_board(url) is None
    with pytest.raises(ValueError):
        decode_board("not_a_board")
