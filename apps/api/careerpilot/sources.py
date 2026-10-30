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
from .matching import SENIOR, domain, fit, links, prefs
from .models import Feed
from .schemas import DENIED_ORG, safe_url

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
        self.lock = asyncio.Lock()

    async def feed(self, provider, slug, employer, title="", country=""):
        if provider not in PUBLIC or not re.fullmatch(r"[A-Za-z0-9_-]{1,160}", slug):
            raise ValueError("Unsupported public feed or invalid slug")
        key = (provider, slug, title, country)
        async with self.lock:
            cached = self.cache.get(key)
            if cached and time.monotonic() - cached[0] < 300:
                return cached[1]
            url = PUBLIC[provider][0].format(slug=slug)
            params = (
                {"limit": 100, "q": title, "country": CODES.get(country, "")}
                if provider == "smartrecruiters"
                else None
            )
            try:
                async with httpx.AsyncClient(
                    timeout=20,
                    follow_redirects=False,
                    transport=self.transport,
                    headers={"User-Agent": "CareerPilot/0.3"},
                ) as client:
                    body = json.loads(await read(client, url, params))
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
                jobs = []
                for row in rows[:1000]:
                    if not isinstance(row, dict):
                        continue
                    loc = row.get("location") if isinstance(row.get("location"), dict) else {}
                    cat = row.get("categories") if isinstance(row.get("categories"), dict) else {}
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
                                    row.get("lists") if isinstance(row.get("lists"), list) else []
                                )
                                if isinstance(x, dict)
                            )
                        )
                    else:
                        jobtitle = row.get("title")
                        url = row.get("jobUrl", "")
                        location = str(row.get("location", ""))
                        description = row.get("descriptionPlain") or row.get("descriptionHtml", "")
                    if not isinstance(jobtitle, str) or not safe_url(url):
                        continue
                    jobs.append(
                        {
                            "title": plain(jobtitle)[:240],
                            "employer": employer,
                            "url": url,
                            "location": plain(location)[:240],
                            "country": name if provider == "smartrecruiters" else "",
                            "description": plain(description),
                            "salary": "Not supplied in listing fields",
                            "source": provider + " public feed: " + employer,
                            "verification": "unverified",
                        }
                    )
                if rows and not jobs:
                    raise ValueError("No valid published listings in feed schema")
            except (httpx.HTTPError, TypeError, KeyError, json.JSONDecodeError):
                raise ValueError(
                    "Public feed unavailable or returned unsupported data. Check the published slug."
                ) from None
            self.cache[key] = (time.monotonic(), jobs)
            if len(self.cache) > 100:
                self.cache.pop(next(iter(self.cache)))
            return jobs

    async def search(self, db, body):
        p = prefs(db)
        jobs = []
        errors = []
        coverage = ""
        cfg = settings()
        if body.source == "feeds":
            enabled = list(db.scalars(select(Feed).where(Feed.enabled.is_(True))))
            if not enabled:
                errors.append(
                    "No enabled verified employer feeds. Add and verify a board in Job sources."
                )
            for feed in enabled[:20]:
                try:
                    rows = await self.feed(
                        feed.provider, feed.slug, feed.employer, body.title, body.country
                    )
                    aliases = [
                        body.country.lower(),
                        *(
                            [CODES.get(body.country, "")]
                            if feed.provider == "smartrecruiters"
                            else []
                        ),
                        *(
                            {
                                "UAE": ["united arab emirates"],
                                "USA": ["united states"],
                                "United Kingdom": ["united kingdom"],
                            }.get(body.country, [])
                        ),
                    ]
                    terms = [
                        t
                        for t in re.findall("[a-z]{3,}", body.title.lower())
                        if t not in {"junior", "graduate", "engineer"}
                    ]
                    for j in rows:
                        if j.get("country") and j["country"] != body.country:
                            continue
                        if not any(
                            re.search(r"\b" + re.escape(a) + r"\b", j["location"], re.I)
                            for a in aliases
                            if a
                        ):
                            continue
                        if body.region and body.region.lower() not in j["location"].lower():
                            continue
                        if terms and not any(t in j["title"].lower() for t in terms):
                            continue
                        jobs.append({**j, "country": body.country})
                except ValueError as e:
                    errors.append(feed.employer + ": " + str(e))
            coverage = "Verified employer boards only. SmartRecruiters: first 100 per title/country query. Other boards: first 1,000. Listings may omit full requirements; check the original."
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
                                *(
                                    [CODES.get(body.country, "")]
                                    if feed.provider == "smartrecruiters"
                                    else []
                                ),
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
    if not permitted or not safe_url(url) or urlsplit(url).scheme != "https":
        raise ValueError(
            "Confirm the employer permits a one-time public read, or paste the text instead. Use HTTPS without credentials."
        )
    parsed = urlsplit(url)
    if parsed.port not in {None, 443}:
        raise ValueError("Only standard public HTTPS URLs are supported.")
    if any(parsed.hostname == h or parsed.hostname.endswith("." + h) for h in BLOCKED):
        raise ValueError("This site is browser-only. Open it yourself and paste the job text.")
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
