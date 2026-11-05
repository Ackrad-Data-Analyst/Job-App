"""Published JSON APIs and guarded owner-requested single-page reads. No submissions."""

import asyncio
import hashlib
import html
import ipaddress
import json
import math
import os
import re
import socket
import time
from html.parser import HTMLParser
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from urllib.robotparser import RobotFileParser

import httpx
from sqlalchemy import select

from .config import settings
from .locations import country_for, has, region_rank
from .matching import SENIOR, analytics_domain, domain, fit, links, prefs
from .models import Feed
from .schemas import DENIED_ORG, safe_url
from .screening import discovery_screen
from .source_policy import is_indeed
from .taxonomy import family_terms

CODES = {
    "Canada": "ca",
    "UAE": "ae",
    "USA": "us",
    "Australia": "au",
    "United Kingdom": "gb",
    "Ireland": "ie",
    "New Zealand": "nz",
    "Qatar": "qa",
    "Italy": "it",
    "Zambia": "zm",
}
PUBLIC = {
    "workday": ("", "https://www.workday.com/en-us/products/talent-management/recruiting.html"),
    "smartrecruiters": (
        "https://api.smartrecruiters.com/v1/companies/{slug}/postings",
        "https://developers.smartrecruiters.com/docs/posting-api",
    ),
    "greenhouse": (
        "https://boards-api.greenhouse.io/v1/boards/{slug}/jobs?content=true",
        "https://developers.greenhouse.io/job-board.html",
    ),
    "lever": (
        "https://api.lever.co/v0/postings/{slug}?mode=json",
        "https://github.com/lever/postings-api",
    ),
    "ashby": (
        "https://api.ashbyhq.com/posting-api/job-board/{slug}?includeCompensation=true",
        "https://developers.ashbyhq.com/docs/public-job-posting-api",
    ),
}
BLOCKED = {
    "linkedin.com",
    "indeed.com",
    "bayt.com",
    "gulftalent.com",
    "naukrigulf.com",
    "jobbank.gc.ca",
    "seek.com.au",
    "seek.co.nz",
    "reed.co.uk",
}


class HTML(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts = []
        self.skip = 0
        self.scripts = []
        self.script = None
        self.title = []
        self.in_title = False

    def handle_starttag(self, tag, attrs):
        if tag == "script":
            self.script = [] if dict(attrs).get("type") == "application/ld+json" else None
        if tag in {"script", "style", "noscript"}:
            self.skip += 1
        if tag in {"p", "li", "div", "br", "h1", "h2"}:
            self.parts.append("\n")
        if tag == "title":
            self.in_title = True

    def handle_endtag(self, tag):
        if tag == "script" and self.script is not None:
            self.scripts.append("".join(self.script))
            self.script = None
        if tag in {"script", "style", "noscript"}:
            self.skip = max(0, self.skip - 1)
        if tag == "title":
            self.in_title = False

    def handle_data(self, data):
        if self.script is not None:
            self.script.append(data)
        if not self.skip:
            self.parts.append(data)
        if self.in_title:
            self.title.append(data)


def plain(value):
    p = HTML()
    p.feed(str(value or "")[:200000])
    return html.unescape("\n".join(x.strip() for x in "".join(p.parts).splitlines() if x.strip()))[
        :50000
    ]


def number(v):
    return (
        v
        if isinstance(v, (float, int))
        and not isinstance(v, bool)
        and math.isfinite(v)
        and 0 < v <= 1000000000
        else None
    )


def canonical(url):
    p = urlsplit(url)
    return urlunsplit(
        (
            p.scheme.lower(),
            p.netloc.lower(),
            p.path.rstrip("/"),
            urlencode(
                sorted(
                    (k, v)
                    for k, v in parse_qsl(p.query)
                    if not k.lower().startswith("utm_")
                    and k.lower() not in {"source", "ref", "gh_src"}
                )
            ),
            "",
        )
    )


def fingerprint(job):
    return hashlib.sha256(
        "|".join(
            re.sub(r"\W+", " ", str(job.get(k, "")).casefold()).strip()
            for k in ["title", "employer", "country", "location", "description"]
        ).encode()
    ).hexdigest()


def unique(jobs):
    seen = set()
    result = []
    for j in jobs:
        keys = {"f:" + fingerprint(j)} | ({"u:" + canonical(j["url"])} if j.get("url") else set())
        if keys & seen:
            continue
        seen |= keys
        result.append(j)
    return result


async def read(client, url, params=None, headers=None, limit=8000000):
    async with client.stream("GET", url, params=params, headers=headers or {}) as r:
        if r.status_code != 200:
            raise ValueError(
                f"Source returned HTTP {r.status_code}; no fallback jobs were invented."
            )
        parts = []
        size = 0
        async for part in r.aiter_bytes():
            size += len(part)
            if size > limit:
                raise ValueError("Source exceeds the read limit.")
            parts.append(part)
        return b"".join(parts)


class Providers:
    def __init__(self, transport=None):
        self.transport = transport
        self.cache = {}

    async def feed(self, provider, slug, employer, title="", country=""):
        if provider not in PUBLIC or not re.fullmatch(r"[A-Za-z0-9_-]{1,160}", slug):
            raise ValueError("Unsupported public feed or invalid slug")
        key = (provider, slug, title, country)
        cached = self.cache.get(key)
        if cached and time.monotonic() - cached[0] < 300:
            return cached[1]
        if provider == "workday":
            from .workday import search_board

            jobs, meta = await search_board(slug, employer, title, self.transport)
            self.cache[key] = (time.monotonic(), jobs)
            if not hasattr(self, "feed_meta"):
                self.feed_meta = {}
            self.feed_meta[key] = meta
            if len(self.cache) > 100:
                stale = next(iter(self.cache))
                self.cache.pop(stale)
                self.feed_meta.pop(stale, None)
            return jobs
        api_url = PUBLIC[provider][0].format(slug=slug)
        jobs = []
        seen_pages = set()
        started = time.monotonic()
        truncated = False
        pages = 0
        try:
            async with httpx.AsyncClient(
                timeout=15,
                follow_redirects=False,
                transport=self.transport,
                headers={"User-Agent": "CareerPilot/0.4"},
            ) as client:
                for page in range(10 if provider in {"smartrecruiters", "lever"} else 1):
                    params = (
                        {
                            "limit": 100,
                            "offset": page * 100,
                            "q": title,
                            "country": CODES.get(country, ""),
                        }
                        if provider == "smartrecruiters"
                        else (
                            {"mode": "json", "limit": 100, "skip": page * 100}
                            if provider == "lever"
                            else None
                        )
                    )
                    body = json.loads(await read(client, api_url, params))
                    if provider != "lever" and not isinstance(body, dict):
                        raise ValueError("Unsupported feed schema")
                    rows = (
                        body
                        if provider == "lever"
                        else body.get(
                            {"smartrecruiters": "content", "greenhouse": "jobs", "ashby": "jobs"}[
                                provider
                            ]
                        )
                    )
                    if not isinstance(rows, list):
                        raise ValueError("Unsupported feed schema")
                    page_hash = hashlib.sha256(
                        json.dumps(rows, sort_keys=True).encode()
                    ).hexdigest()
                    if page_hash in seen_pages:
                        truncated = bool(rows)
                        break
                    seen_pages.add(page_hash)
                    pages += 1
                    if len(rows) > 5000:
                        truncated = True
                    rows = rows[:5000]
                    for row in rows:
                        if (
                            not isinstance(row, dict)
                            or row.get("active") is False
                            or row.get("isListed") is False
                        ):
                            continue
                        loc = row.get("location") if isinstance(row.get("location"), dict) else {}
                        cat = (
                            row.get("categories") if isinstance(row.get("categories"), dict) else {}
                        )
                        if provider == "smartrecruiters":
                            jobtitle = row.get("name")
                            identifier = str(row.get("id", ""))
                            if not re.fullmatch("[A-Za-z0-9-]{1,160}", identifier):
                                continue
                            url = f"https://jobs.smartrecruiters.com/{slug}/{identifier}"
                            code = str(loc.get("country", ""))
                            name = next((n for n, c in CODES.items() if c == code.lower()), code)
                            location = ", ".join(
                                dict.fromkeys(
                                    str(x) for x in [loc.get("city"), loc.get("region"), name] if x
                                )
                            )
                            description = (
                                "Open the original for full requirements. Public listing summary: "
                                + str(
                                    row.get("department", {}).get("label", "")
                                    if isinstance(row.get("department"), dict)
                                    else ""
                                )
                            )
                        elif provider == "greenhouse":
                            jobtitle = row.get("title")
                            url = row.get("absolute_url", "")
                            location = loc.get("name", "")
                            description = row.get("content", "")
                        elif provider == "lever":
                            jobtitle = row.get("text")
                            url = row.get("hostedUrl", "")
                            location = cat.get("location", "")
                            description = (
                                str(row.get("descriptionPlain") or row.get("description") or "")
                                + "\n"
                                + "\n".join(
                                    plain(x.get("content", ""))
                                    for x in (
                                        row.get("lists")
                                        if isinstance(row.get("lists"), list)
                                        else []
                                    )
                                    if isinstance(x, dict)
                                )
                            )
                        else:
                            jobtitle = row.get("title")
                            url = row.get("jobUrl", "")
                            location = str(row.get("location", ""))
                            description = row.get("descriptionPlain") or row.get(
                                "descriptionHtml", ""
                            )
                        if not isinstance(jobtitle, str) or not safe_url(url):
                            continue
                        explicit = (
                            name if provider == "smartrecruiters" else str(row.get("country", ""))
                        )
                        country_name, country_evidence = country_for(plain(location), explicit)
                        jobs.append(
                            {
                                "title": plain(jobtitle)[:240],
                                "employer": employer,
                                "url": url,
                                "location": plain(location)[:240],
                                "country": country_name,
                                "country_evidence": country_evidence,
                                "description_complete": provider != "smartrecruiters",
                                "employment_type": str(
                                    (row.get("typeOfEmployment") or {}).get("label", "")
                                )
                                if isinstance(row.get("typeOfEmployment"), dict)
                                else str(row.get("employmentType", cat.get("commitment", ""))),
                                "published_at": str(
                                    row.get("releasedDate")
                                    or row.get("publishedAt")
                                    or row.get("first_published_at")
                                    or row.get("updated_at")
                                    or ""
                                ),
                                "published_at_kind": "released"
                                if row.get("releasedDate")
                                else "posted"
                                if row.get("publishedAt") or row.get("first_published_at")
                                else "updated"
                                if row.get("updated_at")
                                else "unknown",
                                "published_at_evidence": "Provider releasedDate/publishedAt/first_published_at field; update-only dates remain classified as updates.",
                                "source_checked_at": time.time(),
                                "description": plain(description),
                                "salary": "Not supplied in listing fields",
                                "source": provider + " public feed: " + employer,
                                "verification": "unverified",
                            }
                        )
                    if rows and not jobs:
                        raise ValueError("No valid published listings in feed schema")
                    if provider not in {"smartrecruiters", "lever"} or len(rows) < 100:
                        break
                    total = body.get("totalFound") if isinstance(body, dict) else None
                    if isinstance(total, int) and (page + 1) * 100 >= total:
                        break
                    if page == 9 or time.monotonic() - started > 25:
                        truncated = True
                        break
        except (
            httpx.HTTPError,
            TypeError,
            KeyError,
            AttributeError,
            json.JSONDecodeError,
        ):
            if not jobs:
                raise ValueError(
                    "Public feed unavailable or returned unsupported data. Check the published slug."
                ) from None
            truncated = True
        self.cache[key] = (time.monotonic(), unique(jobs))
        if not hasattr(self, "feed_meta"):
            self.feed_meta = {}
        self.feed_meta[key] = {
            "pages": pages,
            "truncated": truncated,
            "fetched": len(jobs),
            "checked_at": time.time(),
        }
        if len(self.cache) > 100:
            stale = next(iter(self.cache))
            self.cache.pop(stale)
            self.feed_meta.pop(stale, None)
        return self.cache[key][1]

    async def employer_search(self, db, body, p):
        enabled = list(db.scalars(select(Feed).where(Feed.enabled.is_(True))))
        filtered = {
            k: 0
            for k in [
                "different_country",
                "unknown_country",
                "region",
                "title",
                "outside_domain",
                "seniority",
                "internship",
                "excluded",
                "employment_type",
                "salary",
                "untrusted_url",
                "freshness_competition",
            ]
        }
        checked = []
        rows = []
        errors = []
        semaphore = asyncio.Semaphore(5)
        screening_rejections = {}
        terms = family_terms(body.title)

        async def fetch(feed):
            async with semaphore:
                query = body.title if body.scope == "exact" else ""
                try:
                    cached_key = (feed.provider, feed.slug, query, body.country)
                    was_cached = (
                        cached_key in self.cache
                        and time.monotonic() - self.cache[cached_key][0] < 300
                    )
                    result = await self.feed(
                        feed.provider, feed.slug, feed.employer, query, body.country
                    )
                    meta = getattr(self, "feed_meta", {}).get(
                        (feed.provider, feed.slug, query, body.country), {}
                    )
                    return (
                        result,
                        {
                            "employer": feed.employer,
                            "status": "checked",
                            "cached": was_cached,
                            "returned": len(result),
                            **meta,
                        },
                        None,
                    )
                except ValueError as error:
                    return (
                        [],
                        {"employer": feed.employer, "status": "failed", "returned": 0},
                        feed.employer + ": " + str(error),
                    )

        tasks = {asyncio.create_task(fetch(f)): f for f in enabled}
        if tasks:
            done, pending = await asyncio.wait(tasks, timeout=48)
            for task in done:
                try:
                    found, info, error = task.result()
                    rows += found
                    checked.append(info)
                    if error:
                        errors.append(error)
                except Exception:
                    checked.append(
                        {"employer": tasks[task].employer, "status": "failed", "returned": 0}
                    )
                    errors.append(tasks[task].employer + ": source could not be processed.")
            for task in pending:
                checked.append(
                    {"employer": tasks[task].employer, "status": "time limit", "returned": 0}
                )
                task.cancel()
            if pending:
                await asyncio.gather(*pending, return_exceptions=True)
                errors.append(
                    "Some employer boards reached the search time limit. Partial results are retained; retry uses recent successful source caches."
                )
        else:
            errors.append(
                "No enabled verified employer feeds. Check employer career pages to discover supported feeds, or add a published board in Job sources."
            )
        output = []
        for job in unique(rows):
            if (
                is_indeed(job.get("url", ""))
                or not safe_url(job.get("url", ""))
                or any(
                    (urlsplit(job["url"]).hostname or "") == h
                    or (urlsplit(job["url"]).hostname or "").endswith("." + h)
                    for h in BLOCKED
                )
            ):
                filtered["untrusted_url"] += 1
                continue
            screening = discovery_screen(job, p)
            if not screening["allowed"]:
                screening_rejections[screening["reason"]] = (
                    screening_rejections.get(screening["reason"], 0) + 1
                )
                filtered["freshness_competition"] += 1
                continue
            job = {**job, "discovery_screen": screening}
            country, evidence = country_for(job.get("location", ""), job.get("country", ""))
            evidence = job.get("country_evidence") or evidence
            job = {**job, "country": country, "country_evidence": evidence}
            if country and country != body.country:
                filtered["different_country"] += 1
                continue
            if not country and not body.include_unknown_country:
                filtered["unknown_country"] += 1
                continue
            if (
                body.region
                and body.region_mode == "only"
                and not has(job.get("location", ""), body.region)
            ):
                filtered["region"] += 1
                continue
            title = job["title"]
            description = job.get("description", "")
            if body.scope == "exact" and body.title.casefold() not in title.casefold():
                filtered["title"] += 1
                continue
            if (
                body.scope == "related"
                and terms
                and not any(has(title + " " + description, t) for t in terms)
            ):
                filtered["title"] += 1
                continue
            civil_relevant = domain(title, description[:1500])
            analytics_relevant = analytics_domain(title, description[:1500])
            if not (
                civil_relevant
                if body.track == "civil"
                else analytics_relevant
                if body.track == "analytics"
                else civil_relevant or analytics_relevant
            ):
                filtered["outside_domain"] += 1
                continue
            if p["early_career_only"] and not body.include_stretch and SENIOR.search(title):
                filtered["seniority"] += 1
                continue
            if (
                p["earliest_start"] >= "2027-01-01"
                and not next(
                    (
                        c.get("allow_internships", False)
                        for c in p["countries"]
                        if c["country"] == body.country
                    ),
                    False,
                )
                and re.search(r"\b(intern(?:ship)?|co-op|coop)\b", title, re.I)
            ):
                filtered["internship"] += 1
                continue
            if (
                re.search(r"\b" + DENIED_ORG + r"\b", json.dumps(job), re.I)
                or any(x.casefold() in job["employer"].casefold() for x in p["excluded_employers"])
                or any(contains_term(title, x) for x in p["excluded_terms"])
            ):
                filtered["excluded"] += 1
                continue
            if (
                p["employment_type"] == "Full-time"
                and not (
                    next(
                        (
                            c.get("allow_internships", False)
                            for c in p["countries"]
                            if c["country"] == body.country
                        ),
                        False,
                    )
                    and re.search(r"intern|co.op", title + job.get("employment_type", ""), re.I)
                )
                and re.search("part.time|contract|intern", job.get("employment_type", ""), re.I)
            ):
                filtered["employment_type"] += 1
                continue
            assessment = fit(db, job)
            if not country:
                assessment["warnings"].append(
                    "Country could not be established from published location fields. Confirm geography before applying."
                )
            if not job.get("description_complete", True):
                assessment["warnings"].append(
                    "Listing summary only. Read and save the full employer description before deciding eligibility or drafting."
                )
            country_pref = next((c for c in p["countries"] if c["country"] == body.country), {})
            lower_exception = country_pref.get("allow_lower_for_early_career", False) and bool(
                re.search(
                    r"junior|graduate|entry.level|intern|co.op|trainee|early.career", title, re.I
                )
            )
            if (
                lower_exception
                and assessment["salary_comparison"]["minimum_status"] == "Below country minimum."
            ):
                assessment["warnings"].append(
                    "Below your preferred pay floor; retained under your early-career/internship exception. Progression or conversion is not established."
                )
            if (
                not lower_exception
                and assessment["salary_comparison"]["minimum_status"] == "Below country minimum."
            ):
                filtered["salary"] += 1
                continue
            rank, label = region_rank(
                job.get("location", ""), country, body.region, p.get("location_priorities")
            )
            output.append(
                {
                    **job,
                    **assessment,
                    "fit": assessment,
                    "location_rank": rank,
                    "location_note": label,
                    "career_track": "civil/infrastructure"
                    if civil_relevant
                    else "adjacent business/operations analytics",
                    "foreign_applicant_evidence": "Not established: review the original posting and your permit conditions.",
                }
            )
        output.sort(
            key=lambda j: (j["location_rank"], -j["score"], j["title"].casefold(), j["url"])
        )
        total = len(output)
        end = body.offset + body.limit
        from .catalog import view_catalog

        catalog = view_catalog(db, p)["employers"]
        targets = [c for c in catalog if body.country in c["countries"]]
        if body.region:
            targets.sort(
                key=lambda c: (
                    0 if any(has(r, body.region) for r in c["regions"]) else 1,
                    c["priority"],
                    c["name"],
                )
            )
        return {
            "jobs": output[body.offset : end],
            "total": total,
            "offset": body.offset,
            "limit": body.limit,
            "has_more": end < total,
            "next_offset": end if end < total else None,
            "errors": errors,
            "coverage": f"{len(checked)} enabled employer board(s) attempted; public employer-source results only. Up to 10 pages for SmartRecruiters/Lever, 400 public Workday search results and 5,000 rows for whole-board APIs. Career-page targets below are separate from live vacancies.",
            "links": links(body.title, body.country, body.region),
            "checked_at": time.time(),
            "cached": any(c.get("cached", False) for c in checked),
            "source_checks": sorted(checked, key=lambda x: x["employer"]),
            "filtered": filtered,
            "screening_rejections": screening_rejections,
            "retrieved": len(rows),
            "deduplicated": len(unique(rows)),
            "employer_targets": targets,
            "target_count": len(targets),
            "search_scope": body.scope,
        }

    async def search(self, db, body):
        p = prefs(db)
        jobs = []
        errors = []
        coverage = ""
        cfg = settings()
        if body.source == "feeds":
            return await self.employer_search(db, body, p)
        if body.source in {"remotive", "adzuna"}:
            return {
                "jobs": [],
                "errors": [
                    "Aggregator sources are disabled for this direct-employer search. Use employer career pages, verified employer feeds or the official government source."
                ],
                "coverage": "Direct employers and government sources only.",
                "links": links(body.title, body.country, body.region),
            }
        else:
            try:
                async with httpx.AsyncClient(
                    timeout=20,
                    follow_redirects=False,
                    transport=self.transport,
                    headers={"User-Agent": "CareerPilot/0.3"},
                ) as client:
                    if body.source == "remotive":
                        data = json.loads(
                            await read(
                                client,
                                "https://remotive.com/api/remote-jobs",
                                {"search": body.title, "limit": 100},
                            )
                        )
                        rows = data.get("jobs", [])
                        for r in rows:
                            loc = str(r.get("candidate_required_location", ""))
                            aliases = [
                                body.country,
                                CODES.get(body.country, ""),
                                {"UAE": "United Arab Emirates", "USA": "United States"}.get(
                                    body.country, ""
                                ),
                            ]
                            if not (
                                "worldwide" in loc.lower()
                                or any(
                                    a and re.search(r"\b" + re.escape(a) + r"\b", loc, re.I)
                                    for a in aliases
                                )
                            ):
                                continue
                            jobs.append(
                                {
                                    "title": plain(r.get("title", "")),
                                    "employer": plain(r.get("company_name", "")),
                                    "url": r.get("url", ""),
                                    "country": body.country,
                                    "location": "Remote: " + loc,
                                    "description": plain(r.get("description", "")),
                                    "salary": str(r.get("salary") or "Not published"),
                                    "source": "Remotive public API (provider-delayed)",
                                    "verification": "unverified",
                                    "employment_type": str(r.get("job_type", "unknown")),
                                }
                            )
                        coverage = "Remotive remote jobs only, provider-delayed; attribution retained. Location/authorisation restrictions still apply."
                    elif body.source == "adzuna":
                        code = CODES.get(body.country)
                        if code not in {"ca", "us", "au", "gb", "nz", "it"}:
                            raise ValueError(
                                "This Adzuna adapter covers Canada, USA, Australia, UK, NZ and Italy only."
                            )
                        if not cfg.adzuna_app_id or not cfg.adzuna_app_key:
                            raise ValueError(
                                "Add your Adzuna keys in data/private/.env and restart."
                            )
                        data = json.loads(
                            await read(
                                client,
                                f"https://api.adzuna.com/v1/api/jobs/{code}/search/1",
                                {
                                    "app_id": cfg.adzuna_app_id,
                                    "app_key": cfg.adzuna_app_key,
                                    "what": body.title,
                                    "where": body.region,
                                    "results_per_page": 50,
                                },
                            )
                        )
                        currencies = {
                            "ca": "CAD",
                            "us": "USD",
                            "au": "AUD",
                            "gb": "GBP",
                            "nz": "NZD",
                            "it": "EUR",
                        }
                        for r in data.get("results", []):
                            j = {
                                "title": plain(r.get("title", "")),
                                "employer": plain(r.get("company", {}).get("display_name", "")),
                                "url": r.get("redirect_url", ""),
                                "country": body.country,
                                "location": str(r.get("location", {}).get("display_name", "")),
                                "description": plain(r.get("description", "")),
                                "salary": "Not published (predictions discarded)",
                                "source": "Adzuna official API",
                                "verification": "unverified",
                            }
                            if r.get("salary_is_predicted") in {0, "0", False}:
                                lo, hi = number(r.get("salary_min")), number(r.get("salary_max"))
                                if (lo or hi) and (not lo or not hi or hi >= lo):
                                    j.update(
                                        salary_min=lo,
                                        salary_max=hi,
                                        salary_currency=currencies[code],
                                        salary_period="year",
                                        salary=f"{currencies[code]} {lo or '?'} to {hi or '?'} / year",
                                    )
                            jobs.append(j)
                        coverage = "Adzuna official developer API: first 50 results. Source-stated pay only; no salary predictions."
                    else:
                        if body.country != "USA":
                            raise ValueError("USAJOBS covers US federal jobs only.")
                        if not cfg.usajobs_api_key or not cfg.usajobs_email:
                            raise ValueError("USAJOBS key and registered email are not configured.")
                        data = json.loads(
                            await read(
                                client,
                                "https://data.usajobs.gov/api/search",
                                {
                                    "Keyword": body.title,
                                    "LocationName": body.region,
                                    "ResultsPerPage": 50,
                                },
                                {
                                    "Host": "data.usajobs.gov",
                                    "User-Agent": cfg.usajobs_email,
                                    "Authorization-Key": cfg.usajobs_api_key,
                                },
                            )
                        )
                        for r in data.get("SearchResult", {}).get("SearchResultItems", []):
                            r = r["MatchedObjectDescriptor"]
                            detail = r.get("UserArea", {}).get("Details", {})
                            jobs.append(
                                {
                                    "title": r["PositionTitle"],
                                    "employer": r.get("OrganizationName", "US federal employer"),
                                    "url": r.get("PositionURI", ""),
                                    "country": "USA",
                                    "location": r.get("PositionLocationDisplay", ""),
                                    "description": plain(
                                        "\n".join(
                                            str(detail.get(k, ""))
                                            for k in [
                                                "JobSummary",
                                                "MajorDuties",
                                                "Requirements",
                                                "Qualifications",
                                                "WhoMayApply",
                                            ]
                                        )
                                    ),
                                    "salary": "Review published announcement",
                                    "source": "USAJOBS official API",
                                    "verification": "unverified",
                                }
                            )
                        coverage = "US federal jobs only. Check every citizenship, clearance and eligibility restriction."
            except ValueError as e:
                errors.append(
                    str(e)
                    if not isinstance(e, json.JSONDecodeError)
                    else "Source returned invalid JSON."
                )
            except (httpx.HTTPError, KeyError, TypeError):
                errors.append(
                    "Source request failed. Check connectivity, provider access and key status; no substitute jobs were created."
                )
        output = []
        for job in unique(jobs):
            if not safe_url(job.get("url", "")) or not domain(
                job["title"], job.get("description", "")[:500]
            ):
                continue
            if re.search(r"\b" + DENIED_ORG + r"\b", json.dumps(job), re.I):
                continue
            if p["early_career_only"] and SENIOR.search(job["title"]):
                continue
            if p["earliest_start"] >= "2027-01-01" and re.search(
                r"\b(intern(?:ship)?|co-op|coop)\b", job["title"], re.I
            ):
                continue
            if any(x.lower() in job["employer"].lower() for x in p["excluded_employers"]) or any(
                contains_term(job["title"], x) for x in p["excluded_terms"]
            ):
                continue
            if p["employment_type"] == "Full-time" and re.search(
                "part.time|contract|intern", job.get("employment_type", ""), re.I
            ):
                continue
            assessment = fit(db, job)
            if assessment["salary_comparison"]["minimum_status"] == "Below country minimum.":
                continue
            output.append({**job, **assessment, "fit": assessment})
        return {
            "jobs": sorted(output, key=lambda x: -x["score"])[:100],
            "errors": errors,
            "coverage": coverage,
            "links": links(body.title, body.country, body.region),
            "checked_at": time.time(),
            "cached": False,
        }


def contains_term(text, term):
    return bool(re.search(r"\b" + re.escape(term) + r"\b", text, re.I))


async def capture(url, permitted, transport=None):
    if is_indeed(url):
        raise ValueError("Indeed sources are excluded. Use the original employer posting.")
    if not permitted or not safe_url(url) or urlsplit(url).scheme != "https":
        raise ValueError(
            "Confirm the employer permits a one-time public read, or paste the text instead. Use HTTPS without credentials."
        )
    parsed = urlsplit(url)
    if parsed.port not in {None, 443}:
        raise ValueError("Only standard public HTTPS URLs are supported.")
    if any(parsed.hostname == h or parsed.hostname.endswith("." + h) for h in BLOCKED):
        raise ValueError("This site is browser-only. Open it yourself and paste the job text.")
    from .workday import capture_posting, public_board

    if public_board(url) and "/job/" in parsed.path:
        return await capture_posting(url, transport)
    match = re.fullmatch(r"/([A-Za-z0-9_-]{1,160})/([0-9]{6,30})(?:-[^/]*)?/?", parsed.path)
    async with httpx.AsyncClient(timeout=15, follow_redirects=False, transport=transport) as client:
        if parsed.hostname == "jobs.smartrecruiters.com" and match:
            slug, identifier = match.groups()
            body = json.loads(
                await read(
                    client,
                    f"https://api.smartrecruiters.com/v1/companies/{slug}/postings/{identifier}",
                    limit=1500000,
                )
            )
            if not isinstance(body, dict):
                raise ValueError("Unsupported posting schema; paste the text.")
            if body.get("active") is False:
                raise ValueError("The posting is marked inactive. Check the original.")
            advertisement = body.get("jobAd")
            sections = advertisement.get("sections") if isinstance(advertisement, dict) else None
            if not isinstance(sections, dict):
                raise ValueError("Published sections are missing; paste the text.")
            description = "\n\n".join(
                str(v.get("title") or k) + "\n" + plain(v.get("text", ""))
                for k, v in sections.items()
                if isinstance(v, dict)
            )
            if not body.get("name") or not description:
                raise ValueError("Published fields incomplete; paste the original text.")
            loc = body.get("location") if isinstance(body.get("location"), dict) else {}
            code = str(loc.get("country", ""))
            country = next((n for n, c in CODES.items() if c == code.lower()), code)
            result = {
                "title": str(body["name"])[:240],
                "employer": str(body.get("company", {}).get("name", ""))[:240],
                "country": country,
                "location": ", ".join(
                    dict.fromkeys(str(loc.get(k)) for k in ["city", "region"] if loc.get(k))
                )[:240],
                "url": url,
                "description": description[:50000],
                "source": "SmartRecruiters public Posting API",
                "salary": "Structured salary not supplied; review original",
                "closing_date": "",
            }
            pay = body.get("compensation") if isinstance(body.get("compensation"), dict) else {}
            lo, hi = number(pay.get("min")), number(pay.get("max"))
            cur = str(pay.get("currency", ""))
            period = {"year": "year", "annual": "year", "month": "month", "hour": "hour"}.get(
                str(pay.get("period", "")).lower(), ""
            )
            if (lo or hi) and re.fullmatch("[A-Z]{3}", cur) and (not lo or not hi or hi >= lo):
                result.update(
                    salary_min=lo,
                    salary_max=hi,
                    salary_currency=cur,
                    salary_period=period,
                    salary=f"{cur} {lo or '?'} to {hi or '?'} / {period or 'period not stated'}",
                )
            return result
        if transport is None and any(
            os.environ.get(k)
            for k in [
                "HTTP_PROXY",
                "HTTPS_PROXY",
                "ALL_PROXY",
                "http_proxy",
                "https_proxy",
                "all_proxy",
            ]
        ):
            raise ValueError(
                "Generic page capture is unavailable behind this proxy. Paste the job text; network rules will not be bypassed."
            )

    def pin(value):
        p = urlsplit(value)
        try:
            addresses = socket.getaddrinfo(p.hostname, 443, type=socket.SOCK_STREAM)
        except OSError:
            raise ValueError("Employer hostname could not be resolved; paste the text.") from None
        if not addresses or any(not ipaddress.ip_address(a[4][0]).is_global for a in addresses):
            raise ValueError("Private/reserved network addresses are blocked.")
        return (
            httpx.URL(value).copy_with(host=addresses[0][4][0]),
            {"Host": p.hostname, "User-Agent": "CareerPilot/0.3"},
            {"sni_hostname": p.hostname},
        )

    async with httpx.AsyncClient(
        timeout=15, follow_redirects=False, trust_env=False, transport=transport
    ) as client:
        endpoint, headers, ext = pin("https://" + parsed.netloc + "/robots.txt")
        async with client.stream("GET", endpoint, headers=headers, extensions=ext) as robots:
            if robots.status_code == 200:
                chunks = []
                total = 0
                async for chunk in robots.aiter_bytes():
                    total += len(chunk)
                    if total > 200000:
                        raise ValueError("Robots policy too large; paste the text.")
                    chunks.append(chunk)
                raw = b"".join(chunks)
                policy = RobotFileParser()
                policy.parse(raw.decode(errors="replace").splitlines())
                if not policy.can_fetch("CareerPilot", url):
                    raise ValueError("Robots policy disallows reading this page; paste the text.")
            elif robots.status_code != 404:
                raise ValueError("Read permission could not be checked; paste the text.")
        endpoint, headers, ext = pin(url)
        async with client.stream("GET", endpoint, headers=headers, extensions=ext) as response:
            if response.status_code != 200 or "text/html" not in response.headers.get(
                "content-type", ""
            ):
                raise ValueError("Page is blocked or not HTML; paste the description.")
            raw = []
            size = 0
            async for part in response.aiter_bytes():
                size += len(part)
                if size > 1500000:
                    raise ValueError("Page too large; paste relevant text.")
                raw.append(part)
        parser = HTML()
        parser.feed(b"".join(raw).decode(errors="replace"))
        posting = None

        def find(v):
            if isinstance(v, list):
                return next((r for x in v if (r := find(x))), None)
            if isinstance(v, dict):
                return v if "JobPosting" in str(v.get("@type", "")) else find(v.get("@graph", []))
            return None

        for script in parser.scripts:
            try:
                posting = find(json.loads(script))
            except ValueError:
                pass
            if posting:
                break
        if posting:
            org = posting.get("hiringOrganization") or {}
            loc = posting.get("jobLocation") or {}
            loc = loc[0] if isinstance(loc, list) and loc else loc
            address = loc.get("address", {}) if isinstance(loc, dict) else {}
            return {
                "title": plain(posting.get("title", ""))[:240],
                "employer": str(org.get("name", ""))[:240],
                "country": str(address.get("addressCountry", "")),
                "location": ", ".join(
                    str(address.get(k))
                    for k in ["addressLocality", "addressRegion"]
                    if address.get(k)
                ),
                "url": url,
                "description": plain(posting.get("description", "")),
                "source": "Owner-requested one-time capture",
                "salary": "Review source-stated salary in original text",
                "closing_date": str(posting.get("validThrough", ""))[:80],
                "published_at": str(posting.get("datePosted", "")),
                "published_at_kind": "posted" if posting.get("datePosted") else "unknown",
                "published_at_evidence": "Employer JobPosting.datePosted field",
            }
        return {
            "title": "".join(parser.title)[:240],
            "employer": "",
            "country": "",
            "location": "",
            "url": url,
            "description": plain(b"".join(raw).decode(errors="replace")),
            "salary": "Not parsed; review original",
            "closing_date": "",
            "source": "Owner-requested one-time capture",
        }
