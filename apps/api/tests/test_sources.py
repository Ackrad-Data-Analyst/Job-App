import asyncio

import httpx
import pytest
from careerpilot.models import Feed
from careerpilot.schemas import SearchInput
from careerpilot.sources import Providers, canonical, capture, plain, unique


def run(coro):
    return asyncio.run(coro)


@pytest.mark.parametrize(
    "provider,payload",
    [
        (
            "smartrecruiters",
            {
                "content": [
                    {
                        "id": "744000000000001",
                        "name": "Junior Civil Engineer",
                        "location": {"city": "Regina", "country": "ca"},
                    }
                ]
            },
        ),
        (
            "greenhouse",
            {
                "jobs": [
                    {
                        "title": "Civil Engineer",
                        "absolute_url": "https://example.invalid/jobs/1",
                        "location": {"name": "Regina, Canada"},
                        "content": "<p>Python and QGIS</p>",
                    }
                ]
            },
        ),
        (
            "lever",
            [
                {
                    "text": "Civil Engineer",
                    "hostedUrl": "https://example.invalid/jobs/1",
                    "categories": {"location": "Regina, Canada"},
                    "descriptionPlain": "Python and QGIS",
                }
            ],
        ),
        (
            "ashby",
            {
                "jobs": [
                    {
                        "title": "Civil Engineer",
                        "jobUrl": "https://example.invalid/jobs/1",
                        "location": "Regina, Canada",
                        "descriptionPlain": "Python and QGIS",
                    }
                ]
            },
        ),
    ],
)
def test_published_provider_schemas(provider, payload):
    calls = []

    def handler(r):
        calls.append(r)
        return httpx.Response(200, json=payload)

    p = Providers(httpx.MockTransport(handler))
    rows = run(p.feed(provider, "Example", "Fictional employer"))
    assert len(rows) == 1 and rows[0]["verification"] == "unverified"
    run(p.feed(provider, "Example", "Fictional employer"))
    assert len(calls) == 1
    assert "api." in calls[0].url.host or "boards-api." in calls[0].url.host


@pytest.mark.parametrize("status", [403, 404, 429, 500])
def test_source_failure_never_replaced(status):
    p = Providers(httpx.MockTransport(lambda r: httpx.Response(status, json={})))
    with pytest.raises(ValueError):
        run(p.feed("smartrecruiters", "Example", "Fictional"))


@pytest.mark.parametrize(
    "payload",
    [
        {"content": None},
        {"content": [{"id": "../x", "name": "Civil engineer"}]},
        {"content": "unexpected"},
    ],
)
def test_invalid_source_payload_rejected(payload):
    p = Providers(httpx.MockTransport(lambda r: httpx.Response(200, json=payload)))
    with pytest.raises(ValueError):
        run(p.feed("smartrecruiters", "Example", "Fictional"))


def test_filter_domain_and_country_and_fit(person, db):
    db.add(
        Feed(
            employer="Fictional employer", provider="smartrecruiters", slug="Example", enabled=True
        )
    )
    db.commit()
    rows = [
        {
            "id": "744000000000001",
            "name": "Junior Civil Engineer",
            "location": {"city": "Regina", "country": "ca"},
        },
        {
            "id": "744000000000002",
            "name": "Senior Civil Engineer",
            "location": {"city": "Regina", "country": "ca"},
        },
        {
            "id": "744000000000003",
            "name": "Software Engineer",
            "location": {"city": "Regina", "country": "ca"},
        },
    ]
    p = Providers(httpx.MockTransport(lambda r: httpx.Response(200, json={"content": rows})))
    result = run(p.search(db, SearchInput(title="Civil Engineer", country="Canada")))
    assert len(result["jobs"]) == 1 and result["jobs"][0]["fit"]["score"] >= 0
    assert result["jobs"][0]["country"] == "Canada" and result["links"]


def test_no_feeds_clear_failure(client):
    r = client.post(
        "/api/search", json={"title": "Civil Engineer", "country": "Canada", "source": "feeds"}
    )
    assert r.status_code == 200 and r.json()["jobs"] == [] and r.json()["errors"]


@pytest.mark.parametrize(
    "url",
    [
        "http://example.invalid/job",
        "https://linkedin.com/jobs/1",
        "https://127.0.0.1/job",
        "https://user:secret@example.invalid/job",
        "https://example.invalid:8443/job",
    ],
)
def test_capture_rejects_restricted_or_internal_urls(url):
    with pytest.raises((ValueError, OSError)):
        run(capture(url, True))


def test_capture_requires_owner_request():
    with pytest.raises(ValueError):
        run(capture("https://example.invalid/job", False))


def test_html_scripts_removed_and_dedup():
    assert "secret" not in plain("<script>secret</script><p>Civil engineer</p>")
    jobs = [
        {
            "title": "Civil Engineer",
            "employer": "Fictional",
            "url": "https://example.invalid/job?utm_source=x",
        },
        {
            "title": "Civil Engineer",
            "employer": "Fictional",
            "url": "https://example.invalid/job?utm_source=y",
        },
    ]
    assert len(unique(jobs)) == 1
    assert (
        canonical("https://example.invalid/job?utm_source=x#apply") == "https://example.invalid/job"
    )


def test_owner_feed_verification_failure_disabled(client, monkeypatch):
    import careerpilot.main as main

    async def fail(*args):
        raise ValueError("Source unavailable, no substitute jobs.")

    monkeypatch.setattr(main.providers, "feed", fail)
    f = client.post(
        "/api/sources/feeds",
        json={"employer": "Fictional", "provider": "smartrecruiters", "slug": "Example"},
    ).json()
    r = client.post("/api/sources/feeds/" + f["id"] + "/verify", json={})
    assert r.status_code == 200 and not r.json()["ok"] and not r.json()["feed"]["enabled"]
    assert client.get("/api/applications").json() == []


def test_capture_full_smartrecruiters_description_and_stated_pay():
    payload = {
        "name": "Junior Civil Engineer",
        "company": {"name": "Fictional employer"},
        "active": True,
        "location": {"city": "Regina", "country": "ca"},
        "jobAd": {
            "sections": {
                "jobDescription": {
                    "title": "Description",
                    "text": "<p>Full civil infrastructure duties.</p>",
                },
                "qualifications": {
                    "title": "Required qualifications",
                    "text": "<p>Python and QGIS.</p>",
                },
            }
        },
        "compensation": {"min": 60000, "max": 72000, "currency": "CAD", "period": "year"},
    }
    transport = httpx.MockTransport(lambda r: httpx.Response(200, json=payload))
    r = run(capture("https://jobs.smartrecruiters.com/Example/744000000000001", True, transport))
    assert r["country"] == "Canada" and r["salary_min"] == 60000 and r["salary_period"] == "year"
    assert "Required qualifications" in r["description"] and "<p>" not in r["description"]


def test_malformed_feed_root_is_a_clear_failure():
    p = Providers(httpx.MockTransport(lambda r: httpx.Response(200, json=[])))
    with pytest.raises(ValueError):
        run(p.feed("smartrecruiters", "Example", "Fictional"))


def test_demo_records_are_explicitly_fictional(client, db):
    from careerpilot.initialize import demo

    demo(db)
    demo(db)
    rows = client.get("/api/applications").json()
    assert len(rows) == 3 and all(
        x["job"]["is_demo"] and x["job"]["verification"] == "fictional" for x in rows
    )
    assert client.get("/api/profile").json()["candidate"]["name"] == "My profile"
