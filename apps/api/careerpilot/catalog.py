"""Candidate official employer directory with explicit, bounded live verification."""

import asyncio
import json
import re
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin, urlsplit, urlunsplit
from urllib.robotparser import RobotFileParser

import httpx
from sqlalchemy import select

from .locations import country_for, region_rank
from .models import Feed, SourceVerification, now
from .taxonomy import ALL_TITLES, CURRICULUM_SOURCES, EDUCATION_PATHWAYS

CATALOG = json.loads((Path(__file__).with_name("reference") / "employers.json").read_text())
BY_KEY = {c["key"]: c for c in CATALOG}
ATS_HOSTS = {
    "jobs.smartrecruiters.com",
    "careers.smartrecruiters.com",
    "boards.greenhouse.io",
    "job-boards.greenhouse.io",
    "jobs.lever.co",
    "jobs.eu.lever.co",
    "jobs.ashbyhq.com",
}


class Links(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []
        self.in_title = False
        self.title = []

    def handle_starttag(self, tag, attrs):
        if tag == "a":
            self.links += [v for k, v in attrs if k == "href" and v]
        if tag == "title":
            self.in_title = True

    def handle_endtag(self, tag):
        if tag == "title":
            self.in_title = False

    def handle_data(self, data):
        if self.in_title:
            self.title.append(data)


def ats_board(url):
    from .workday import encode_board

    workday = encode_board(url)
    if workday:
        return "workday", workday
    p = urlsplit(url)
    parts = [s for s in p.path.split("/") if s]
    host = (p.hostname or "").casefold()
    if p.scheme != "https" or p.username or p.password or p.port not in {None, 443}:
        return None
    if host == "jobs.smartrecruiters.com" and parts:
        return "smartrecruiters", parts[0]
    if host == "careers.smartrecruiters.com" and parts:
        return "smartrecruiters", parts[0]
    if host in {"boards.greenhouse.io", "job-boards.greenhouse.io"} and parts:
        return "greenhouse", parts[0]
    if host == "jobs.lever.co" and parts:
        return "lever", parts[0]
    # EU Lever requires a separate API endpoint; never silently substitute the US board.
    if host == "jobs.ashbyhq.com" and parts:
        return "ashby", parts[0]
    return None


def view_catalog(db, p):
    checked = {r.catalog_key: r for r in db.scalars(select(SourceVerification))}
    excluded = [s.casefold() for s in p.get("excluded_employers", [])]
    markets = [c["country"] for c in p.get("countries", []) if c.get("enabled", True)]
    output = []
    for c in CATALOG:
        if any(s in c["name"].casefold() for s in excluded):
            continue
        countries = [country for country in markets if country in c["countries"]]
        if p.get("countries") is not None and not countries:
            continue
        regions = [
            region
            for region in c["regions"]
            if not markets or country_for(region)[0] in {"", *markets}
        ]
        r = checked.get(c["key"])
        rank, label = region_rank(
            " ".join(regions),
            countries[0] if countries else "",
            priorities=p.get("location_priorities"),
        )
        output.append(
            {
                **c,
                "countries": countries if markets else c["countries"],
                "regions": regions,
                "location_rank": rank,
                "location_note": label,
                "state": r.state if r else "unchecked",
                "checked_at": r.checked_at if r else None,
                "final_url": r.final_url if r else "",
                "page_title": r.page_title if r else "",
                "message": r.message
                if r
                else "Candidate official link; not checked in this installation. No vacancies or foreign-applicant policy inferred.",
                "feed_ids": r.feed_ids if r else [],
            }
        )
    return {
        "markets": markets,
        "default_country": markets[0] if markets else "",
        "employers": sorted(output, key=lambda c: (c["priority"], c["name"])),
        "role_titles": ALL_TITLES,
        "education_pathways": EDUCATION_PATHWAYS,
        "curriculum_sources": CURRICULUM_SOURCES,
        "policy": "Employer career pages and documented public employer feeds first. A reachable careers page is not a current vacancy or proof of sponsorship. No Indeed results or aggregator substitutions.",
    }


async def bounded(client, url, allowed, limit=1600000):
    current = url
    for _ in range(5):
        p = urlsplit(current)
        if (
            p.scheme != "https"
            or (
                p.hostname not in allowed
                and not re.fullmatch(
                    r"[a-z0-9-]+\.wd\d+\.myworkdayjobs\.com", p.hostname or "", re.I
                )
            )
            or p.username
            or p.password
            or p.port not in {None, 443}
        ):
            raise ValueError(
                "Redirect destination is not an approved employer/ATS host. Open the original manually."
            )
        async with client.stream("GET", current) as r:
            if r.status_code in {301, 302, 303, 307, 308}:
                current = urljoin(current, r.headers.get("location", ""))
                continue
            if r.status_code == 404:
                return 404, current, b""
            if r.status_code != 200:
                raise ValueError(
                    f"Official page returned HTTP {r.status_code}; no vacancies inferred."
                )
            chunks = []
            size = 0
            async for chunk in r.aiter_bytes():
                size += len(chunk)
                if size > limit:
                    raise ValueError(
                        "Official page exceeded the bounded read size. Open it manually."
                    )
                chunks.append(chunk)
            return 200, current, b"".join(chunks)
    raise ValueError("Too many redirects. Open the employer page manually.")


async def verify_candidate(candidate, providers, transport=None):
    target = candidate["careers_url"]
    base = urlsplit(target)
    allowed = {base.hostname, urlsplit(candidate["website"]).hostname, *ATS_HOSTS}
    # Restrict redirects to this employer's known first-party domains and supported ATS hosts.
    for host in list(allowed):
        if host and not host.startswith("www.") and host.count(".") == 1:
            allowed.add("www." + host)
        elif host and host.startswith("www."):
            allowed.add(host[4:])
    result = {
        "state": "unavailable",
        "checked_at": now(),
        "final_url": "",
        "page_title": "",
        "message": "",
        "boards": [],
    }
    try:
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(12, connect=8),
            follow_redirects=False,
            transport=transport,
            headers={"User-Agent": "CareerPilot/0.4 (owner-requested careers page check)"},
        ) as client:
            robots_url = urlunsplit(("https", base.netloc, "/robots.txt", "", ""))
            status, _, raw = await bounded(client, robots_url, allowed, 200000)
            if status == 200:
                policy = RobotFileParser()
                policy.parse(raw.decode(errors="replace").splitlines())
                if not policy.can_fetch("CareerPilot", target):
                    raise ValueError(
                        "Robots policy disallows the requested page read. Browser access only; no bypass attempted."
                    )
            status, final, raw = await bounded(client, target, allowed)
            if status != 200:
                raise ValueError(
                    "Candidate careers link returned HTTP 404. Use the official homepage to locate its current careers page."
                )
            html = raw.decode(errors="replace")
            parser = Links()
            parser.feed(html)
            title = " ".join(parser.title).strip()[:300]
            if re.search(
                r"captcha|access denied|just a moment|verify you are human|sign in to continue",
                title,
                re.I,
            ):
                raise ValueError(
                    "Page presents an access check. Browser access only; no bypass attempted."
                )
            result.update(final_url=final, page_title=title)
            urls = [final, *[urljoin(final, a) for a in parser.links]]
            boards = list(
                dict.fromkeys(
                    board
                    for url in urls
                    if (board := ats_board(url)) and re.fullmatch("[A-Za-z0-9_-]{1,160}", board[1])
                )
            )[:4]
            for provider, slug in boards:
                try:
                    listings = await providers.feed(provider, slug, candidate["name"])
                    result["boards"].append(
                        {
                            "provider": provider,
                            "slug": slug,
                            "listings_checked": len(listings),
                            "provenance_url": final,
                        }
                    )
                except ValueError:
                    pass
            career_context = bool(
                re.search(
                    r"careers?|jobs|vacanc",
                    title + " " + urlsplit(final).path + " " + (urlsplit(final).hostname or ""),
                    re.I,
                )
            )
            result["state"] = "checked" if career_context else "website reachable"
            result["message"] = (
                (
                    "Careers page reachable. "
                    if career_context
                    else "Official website candidate reachable; exact careers page needs manual review. "
                )
                + f"{len(result['boards'])} documented employer feed(s) confirmed from published links. Foreign-applicant eligibility remains posting-specific."
            )
    except (httpx.HTTPError, ValueError, OSError) as e:
        result["state"] = (
            "blocked"
            if "403" in str(e) or "Robots" in str(e) or "access check" in str(e)
            else "unavailable"
        )
        result["message"] = (
            str(e)
            if isinstance(e, ValueError)
            else "Network/proxy/TLS request failed. Source remains unverified; use the employer site in your browser."
        )
    return result


async def check_batch(db, keys, providers, transport=None):
    semaphore = asyncio.Semaphore(4)

    async def check(key):
        async with semaphore:
            try:
                return key, await asyncio.wait_for(
                    verify_candidate(BY_KEY[key], providers, transport), 35
                )
            except TimeoutError:
                return key, {
                    "state": "unavailable",
                    "checked_at": now(),
                    "final_url": "",
                    "page_title": "",
                    "message": "Time limit reached; open the official site manually.",
                    "boards": [],
                }

    results = await asyncio.gather(*(check(k) for k in keys))
    out = []
    for key, result in results:
        record = db.scalar(select(SourceVerification).where(SourceVerification.catalog_key == key))
        if not record:
            record = SourceVerification(catalog_key=key)
            db.add(record)
        for field in ["state", "checked_at", "final_url", "page_title", "message"]:
            setattr(record, field, result[field])
        ids = []
        for board in result["boards"]:
            feed = db.scalar(
                select(Feed).where(Feed.provider == board["provider"], Feed.slug == board["slug"])
            )
            if not feed:
                feed = Feed(
                    employer=BY_KEY[key]["name"], provider=board["provider"], slug=board["slug"]
                )
                db.add(feed)
                db.flush()
            feed.enabled = True
            feed.verified_at = now()
            feed.last_error = ""
            ids.append(feed.id)
        # A transient page failure does not erase previously verified feed ownership.
        record.feed_ids = list(dict.fromkeys([*(record.feed_ids or []), *ids]))
        out.append(
            {
                "key": key,
                **{
                    f: getattr(record, f)
                    for f in [
                        "state",
                        "checked_at",
                        "final_url",
                        "page_title",
                        "message",
                        "feed_ids",
                    ]
                },
            }
        )
    db.commit()
    return {"results": out}
