"""Owner-requested reads of an employer's public Workday careers search.

This uses the same public search data as the career page, not an application or
account endpoint. Robots restrictions, access challenges and failures stop reads.
"""

import base64
import json
import re
import time
from urllib.parse import urlsplit, urlunsplit
from urllib.robotparser import RobotFileParser

import httpx

from .locations import country_for


def public_board(url):
    p = urlsplit(url)
    if (
        p.scheme != "https"
        or not re.fullmatch(r"[a-z0-9-]+\.wd\d+\.myworkdayjobs\.com", p.hostname or "", re.I)
        or p.username
        or p.password
        or p.port not in {None, 443}
    ):
        return None
    parts = [s for s in p.path.split("/") if s]
    if parts and re.fullmatch("[a-z]{2}-[A-Z]{2}", parts[0]):
        parts = parts[1:]
    if not parts or not re.fullmatch("[A-Za-z0-9_-]{1,100}", parts[0]):
        return None
    site = parts[0]
    tenant = p.hostname.split(".")[0]
    path = urlsplit(url).path.split("/job/", 1)[0].rstrip("/")
    if "/job/" not in p.path:
        original = [s for s in p.path.split("/") if s]
        path = "/" + (
            "/".join(original[:2])
            if original and re.fullmatch("[a-z]{2}-[A-Z]{2}", original[0])
            else site
        )
    return {
        "base": urlunsplit(("https", p.netloc, path, "", "")),
        "host": p.hostname,
        "tenant": tenant,
        "site": site,
        "api": f"https://{p.netloc}/wday/cxs/{tenant}/{site}",
    }


def encode_board(url):
    board = public_board(url)
    return base64.urlsafe_b64encode(board["base"].encode()).decode().rstrip("=") if board else None


def decode_board(slug):
    try:
        url = base64.urlsafe_b64decode(slug + "=" * (-len(slug) % 4)).decode()
        board = public_board(url)
        if board:
            return board
    except (ValueError, UnicodeError):
        pass
    raise ValueError("Invalid public Workday employer board identifier.")


async def response_json(response, limit=4000000):
    if response.status_code != 200:
        raise ValueError(
            f"Employer careers search returned HTTP {response.status_code}; no bypass attempted."
        )
    parts = []
    total = 0
    async for part in response.aiter_bytes():
        total += len(part)
        if total > limit:
            raise ValueError("Employer response exceeded the bounded read limit.")
        parts.append(part)
    try:
        return json.loads(b"".join(parts))
    except ValueError:
        raise ValueError(
            "Employer careers endpoint did not return supported public JSON."
        ) from None


async def allowed(client, board):
    async with client.stream("GET", f"https://{board['host']}/robots.txt") as r:
        if r.status_code == 404:
            return
        if r.status_code != 200:
            raise ValueError(
                "Workday robots permission could not be checked. Use the employer website manually."
            )
        chunks = []
        size = 0
        async for chunk in r.aiter_bytes():
            size += len(chunk)
            if size > 200000:
                raise ValueError("Employer robots policy too large; use the website manually.")
            chunks.append(chunk)
        robot = RobotFileParser()
        robot.parse(b"".join(chunks).decode(errors="replace").splitlines())
        if not robot.can_fetch("CareerPilot", board["base"]) or not robot.can_fetch(
            "CareerPilot", board["api"] + "/jobs"
        ):
            raise ValueError(
                "Employer robots policy disallows this search read. Browser access only; no bypass attempted."
            )


async def search_board(slug, employer, title="", transport=None):
    from .sources import plain

    board = decode_board(slug)
    jobs = []
    pages = 0
    partial = False
    started = time.monotonic()
    try:
        async with httpx.AsyncClient(
            timeout=15,
            follow_redirects=False,
            transport=transport,
            headers={"User-Agent": "CareerPilot/0.4 (owner-requested public employer search)"},
        ) as client:
            await allowed(client, board)
            previous = set()
            for offset in range(0, 400, 20):
                # This POST retrieves public search results; it does not submit an application.
                async with client.stream(
                    "POST",
                    board["api"] + "/jobs",
                    json={"appliedFacets": {}, "limit": 20, "offset": offset, "searchText": title},
                ) as r:
                    payload = await response_json(r)
                if not isinstance(payload, dict) or not isinstance(
                    payload.get("jobPostings"), list
                ):
                    raise ValueError("Unsupported Workday public job-search schema.")
                rows = payload["jobPostings"]
                signature = json.dumps(rows, sort_keys=True)
                if signature in previous:
                    partial = bool(rows)
                    break
                previous.add(signature)
                pages += 1
                for row in rows:
                    if not isinstance(row, dict) or not isinstance(row.get("title"), str):
                        continue
                    path = row.get("externalPath", "")
                    if (
                        not isinstance(path, str)
                        or not path.startswith("/job/")
                        or ".." in path
                        or "?" in path
                        or "#" in path
                    ):
                        continue
                    location = str(row.get("locationsText", ""))
                    country, evidence = country_for(location)
                    jobs.append(
                        {
                            "title": plain(row["title"])[:240],
                            "employer": employer,
                            "url": board["base"] + path,
                            "location": plain(location)[:240],
                            "country": country,
                            "country_evidence": evidence,
                            "description": "Employer listing summary only. Open the complete original posting for duties, registration, experience and work-authorisation requirements.",
                            "description_complete": False,
                            "source": "workday public employer careers: " + employer,
                            "verification": "unverified",
                            "salary": "Not supplied in listing fields",
                            "published_at": str(row.get("postedOn", "")),
                            "published_at_kind": "posted" if row.get("postedOn") else "unknown",
                            "published_at_evidence": "Employer Workday postedOn text",
                            "source_checked_at": time.time(),
                            "employment_type": "",
                        }
                    )
                total = payload.get("total")
                if len(rows) < 20 or isinstance(total, int) and offset + 20 >= total:
                    break
                if time.monotonic() - started > 25 or offset == 380:
                    partial = True
                    break
    except (httpx.HTTPError, ValueError) as e:
        if not jobs:
            raise ValueError(
                str(e)
                if isinstance(e, ValueError)
                else "Public Workday careers search unavailable; use the official employer page."
            ) from None
        partial = True
    return jobs, {
        "pages": pages,
        "truncated": partial,
        "fetched": len(jobs),
        "checked_at": time.time(),
    }


async def capture_posting(url, transport=None):
    from .sources import plain

    board = public_board(url)
    if not board or "/job/" not in urlsplit(url).path:
        raise ValueError("Unsupported public employer posting URL.")
    path = "/job/" + urlsplit(url).path.split("/job/", 1)[1]
    if ".." in path:
        raise ValueError("Invalid employer posting path.")
    async with httpx.AsyncClient(
        timeout=15,
        follow_redirects=False,
        transport=transport,
        headers={"User-Agent": "CareerPilot/0.4"},
    ) as client:
        await allowed(client, board)
        async with client.stream("GET", board["api"] + path) as r:
            body = await response_json(r)
    info = body.get("jobPostingInfo") if isinstance(body, dict) else None
    if not isinstance(info, dict) or not info.get("title") or not info.get("jobDescription"):
        raise ValueError(
            "Full employer posting fields unavailable; paste the original description."
        )
    location = str(info.get("location", ""))
    country, evidence = country_for(location)
    return {
        "title": plain(info["title"])[:240],
        "employer": (info.get("company", "")[:240] if isinstance(info.get("company"), str) else ""),
        "country": country,
        "location": plain(location)[:240],
        "url": url,
        "description": plain(info["jobDescription"]),
        "source": "Workday public employer posting",
        "salary": "Review original posting; no numeric salary inferred",
        "closing_date": str(info.get("endDate", "")),
        "published_at": str(info.get("postedOn", "")),
        "published_at_kind": "posted" if info.get("postedOn") else "unknown",
        "published_at_evidence": "Employer Workday postedOn text",
    }
