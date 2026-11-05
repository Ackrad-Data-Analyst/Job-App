"""Source-based freshness and competition checks. Unknown is never zero."""

import re
from datetime import UTC, datetime


def posting_age(job, checked_at=None):
    current = checked_at or datetime.now(UTC)
    if isinstance(current, (int, float)):
        current = datetime.fromtimestamp(current, UTC)
    raw = str(job.get("published_at") or "").strip()
    kind = job.get("published_at_kind", "unknown")
    if kind not in {"posted", "released", "owner reported"}:
        return (
            None,
            "Original posting date not reported; an update date is not treated as a new posting.",
        )
    relative = re.sub(r"\s+", " ", raw).casefold()
    observed = job.get("source_checked_at")
    elapsed = (
        max(0, (current.timestamp() - observed) / 86400)
        if isinstance(observed, (int, float))
        else 0
    )
    if re.fullmatch(r"(posted\s*)?(today|just posted)", relative):
        return int(elapsed), "Source says posted today."
    if re.fullmatch(r"(posted\s*)?yesterday", relative):
        return 1 + int(elapsed), "Source says posted yesterday."
    days = re.search(r"(\d+)\s*(\+)?\s*days?\s*ago", relative)
    if days:
        return int(days[1]) + int(elapsed), "Published relative age" + (
            " is a lower bound." if days[2] else "."
        )
    try:
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", raw):
            value = (current.date() - datetime.fromisoformat(raw).date()).days
        else:
            parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=UTC)
            value = int((current - parsed).total_seconds() // 86400)
        if value < 0:
            return None, "Source date is in the future; verify it."
        return value, "Published source date; reposting history is not established."
    except (ValueError, TypeError):
        return None, "Posting date could not be established from the published source."


def competition(job, prefs):
    value = job.get("applicant_count")
    metric = job.get("applicant_metric", "unknown")
    relation = job.get("applicant_count_relation", "exact")
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        return None, None, "Applicant count not reported."
    if metric == "apply clicks" and not prefs.get("use_apply_clicks_as_proxy", False):
        return (
            None,
            None,
            f"{value} apply clicks reported; this is not a completed-application count.",
        )
    if metric not in {"applications", "apply clicks"}:
        return None, None, "Reported count has unknown meaning; not used as an application count."
    lower = (
        value + 1 if relation == "more than" else value if relation in {"exact", "at least"} else 0
    )
    upper = value - 1 if relation == "less than" else value if relation == "exact" else None
    return (
        lower,
        upper,
        f"{relation} {value} "
        + (
            "applications"
            if metric == "applications"
            else "apply clicks (explicitly enabled proxy)"
        )
        + ".",
    )


def discovery_screen(job, prefs, checked_at=None):
    age, date_note = posting_age(job, checked_at)
    lower, upper, count_note = competition(job, prefs)
    limit = prefs.get("max_applicant_count", 100)
    age_limit = prefs.get("max_job_age_days", 5)
    older_threshold = prefs.get("older_job_applicant_threshold", 20)
    result = {
        "allowed": True,
        "age_days": age,
        "date_note": date_note,
        "count_note": count_note,
        "reason": "Freshness and competition rules passed.",
    }
    if lower is not None and (lower > limit or lower == limit and upper is None):
        result.update(
            allowed=False, reason="Published competition count exceeds or may exceed your maximum."
        )
        return result
    comparison_age = age
    raw = str(job.get("published_at") or "").strip()
    if age is not None and "T" in raw:
        try:
            stamp = datetime.fromisoformat(raw.replace("Z", "+00:00"))
            if stamp.tzinfo is None:
                stamp = stamp.replace(tzinfo=UTC)
            current = checked_at or datetime.now(UTC)
            if isinstance(current, (int, float)):
                current = datetime.fromtimestamp(current, UTC)
            comparison_age = (current - stamp).total_seconds() / 86400
        except (ValueError, TypeError):
            pass
    low_competition = upper is not None and upper < older_threshold
    if age is None:
        if low_competition:
            result["reason"] = (
                "Date unknown, but published count is below the older-job exception threshold."
            )
        elif not prefs.get("include_unknown_posted_date", False):
            result.update(
                allowed=False,
                reason="Posting date unknown; your freshness rule cannot be established.",
            )
    elif comparison_age > age_limit:
        if low_competition:
            result["reason"] = (
                "Older posting retained because its published count is below the exception threshold."
            )
        else:
            result.update(
                allowed=False,
                reason="Posting is older than your limit without a qualifying low published applicant count.",
            )
            return result
    if lower is None and not prefs.get("include_unknown_applicant_count", True):
        result.update(
            allowed=False, reason="Applicant count unknown; strict published-count mode is enabled."
        )
    return result
