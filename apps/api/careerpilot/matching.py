import re
from urllib.parse import urlencode

from sqlalchemy import select

from .models import FACTS, Candidate, Preferences
from .schemas import DENIED_ORG, PreferencesInput
from .taxonomy import FAMILIES

BANNED = re.compile(
    r"\b(gpa|cgpa|mca|master\s+of\s+computer\s+applications|immigration|visa|relocat\w*|work authori[sz]\w*|authori[sz]ed to work|citizenship|permanent residen\w*|spearheaded|leveraged|proven track record|passionate|dynamic|results.driven|expert|eit|p\.?eng\.?|p\.?e\.?|fe exam candidate|primavera|revit|"
    + DENIED_ORG
    + r")\b|\u2014",
    re.I,
)

SKILLS = [
    "QGIS",
    "ArcGIS Pro",
    "ArcGIS",
    "ArcPy",
    "GeoPandas",
    "Shapely",
    "PostGIS",
    "AutoCAD",
    "Civil 3D",
    "HEC-RAS",
    "PlanSwift",
    "MS Project",
    "Primavera P6",
    "Revit",
    "Bluebeam",
    "Python",
    "R",
    "SQL",
    "Excel",
    "Power BI",
    "Tableau",
    "quantity take-off",
    "cost estimation",
    "surveying",
    "total station",
    "GPS",
    "hydrology",
    "drainage",
    "concrete",
    "French",
    "Arabic",
]
SENIOR = re.compile(r"\b(senior|sr\.?|principal|director|chief|lead|head|manager)\b", re.I)
COUNTRIES = [
    ("USA", "", "USD"),
    ("UAE", "Dubai, Abu Dhabi", "AED"),
]


def defaults():
    return {
        "countries": [
            {
                "country": c,
                "regions": r,
                "currency": cur,
                "min_salary": None,
                "authorization": "unknown",
                "authorization_note": "",
                "enabled": True,
                "template": c,
            }
            for c, r, cur in COUNTRIES
        ],
        "target_titles": [t for _, _, ts in FAMILIES for t in ts],
        "interests": ["civil engineering", "GIS", "infrastructure analytics"],
        "excluded_employers": ["First Quantum Minerals"],
        "excluded_terms": ["MEP", "facade", "façade", "finishes"],
        "comparison_currency": "USD",
        "exchange_rates": {},
        "exchange_rate_date": "",
        "earliest_start": "2027-01-01",
        "employment_type": "Full-time",
        "early_career_only": True,
        "languages_on_resume": False,
        "canadian_location": False,
    }


def prefs(db):
    return PreferencesInput.model_validate(db.scalar(select(Preferences)).data).model_dump()


def contains(text, term):
    return bool(re.search(r"(?<!\w)" + re.escape(term) + r"(?!\w)", text, re.I))


def fact_text(f):
    return " ".join([f.title, f.organization, f.details, f.start_date, f.end_date])


def usable(f):
    return f.status == "confirmed" and f.allowed_on_resume and not BANNED.search(fact_text(f))


def facts(db, include_learning=False):
    return [
        f
        for k, m in FACTS.items()
        if k not in {"identity", "rules"}
        for f in db.scalars(select(m))
        if usable(f) and (include_learning or not f.learning)
    ]


def confirmed_text(db):
    p = db.scalar(select(Candidate))
    extra = (
        (p.headline + " " + p.summary)
        if p.status == "confirmed"
        and p.allowed_on_resume
        and not BANNED.search(p.headline + " " + p.summary)
        else ""
    )
    return (" ".join(fact_text(f) for f in facts(db)) + " " + extra).lower()


def roles(db):
    text = confirmed_text(db)
    records = facts(db)
    return sorted(
        [
            {
                "title": t,
                "family": family,
                "supported": len([w for w in terms if contains(text, w)]) >= 2,
                "evidence": [w for w in terms if contains(text, w)],
                "facts": [
                    {"id": f.id, "title": f.title, "organization": f.organization}
                    for f in records
                    if any(contains(fact_text(f), w) for w in terms)
                ][:6],
                "gaps": [
                    "Check degree, experience and specialist training requirements.",
                    "Verify local registration, required software and work authorisation.",
                ],
            }
            for family, terms, titles in FAMILIES
            for t in titles
        ],
        key=lambda r: -len(r["evidence"]),
    )


def domain(title, description=""):
    if re.search(
        r"\b(mep|facade|façade|finishes|payroll|accounting|software engineer|it analyst|financial analyst|finance analyst)\b",
        title,
        re.I,
    ):
        return False
    return any(
        x in (title + " " + description).lower()
        for x in [
            "civil",
            "construction",
            "water",
            "stormwater",
            "geotechnical",
            "structural",
            "transport",
            "renewable",
            "solar",
            "wind",
            "gis",
            "geospatial",
            "survey",
            "mining",
            "infrastructure",
            "quantity",
            "estimat",
            "project control",
            "planning engineer",
            "drainage",
            "bridge",
            "dam ",
            "marine",
            "coastal",
            "port infrastructure",
            "rail",
            "transit",
            "airport",
            "geomatics",
            "hydrogeolog",
            "tailings",
            "materials technician",
            "municipal",
            "urban planner",
            "planning technician",
            "land development",
            "project coordinator",
            "field coordinator",
            "capital projects",
            "cost control",
            "hydrolog",
            "asset management",
        ]
    ) or any(x in title.lower() for x in ["field engineer", "technical engineer", "scheduler"])


def analytics_domain(title, description=""):
    if re.search(
        r"\b(nurse|nursing|physician|surgeon|dentist|therapist|software engineer|financial analyst|finance analyst|payroll|accounting)\b",
        title,
        re.I,
    ):
        return False
    return bool(
        re.search(
            r"data analyst|business analyst|operations analyst|analytics|business intelligence|operations research|performance analyst|process improvement|supply chain analyst",
            title,
            re.I,
        )
    )


def clauses(description):
    required = []
    preferred = []
    mode = "required"
    for line in re.split(r"[\n;]|(?<=[.!?])\s+", description):
        if re.search(r"preferred qualifications|nice.to.have|desirable skills", line, re.I):
            mode = "preferred"
        elif re.search(
            r"required qualifications|minimum requirements|essential skills", line, re.I
        ):
            mode = "required"
        if re.search(
            r"not required|not essential|preferred|desirable|advantage|bonus|asset|optional",
            line,
            re.I,
        ) and not re.search(r"\b(must|mandatory)\b", line, re.I):
            preferred.append(line)
        else:
            (required if mode == "required" else preferred).append(line)
    return "\n".join(required), "\n".join(preferred)


def salary_comparison(job, p, c):
    lo, hi = job.get("salary_min"), job.get("salary_max")
    src = job.get("salary_currency", "")
    target = p["comparison_currency"]
    rates = p["exchange_rates"]
    dated = p["exchange_rate_date"]

    def rate(a, b):
        if a == b:
            return 1
        x = 1 if a == target else rates.get(a)
        y = 1 if b == target else rates.get(b)
        return x / y if dated and x and y else None

    r = rate(src, target)
    native = rate(src, c.get("currency", ""))
    result = {
        "label": "No comparable source-stated numeric salary.",
        "minimum_status": "Minimum not set; no salary filter applied.",
    }
    if (lo is not None or hi is not None) and r:
        result.update(
            min=round(lo * r, 2) if lo is not None else None,
            max=round(hi * r, 2) if hi is not None else None,
            currency=target,
            period=job.get("salary_period", ""),
            label="Source currency; no conversion."
            if src == target
            else "Converted using your dated rate; indicative only.",
            rate_date=dated,
        )
    minimum = c.get("min_salary")
    if minimum is not None:
        target_period = c.get("min_salary_period", "year")
        source_period = job.get("salary_period", "")
        factor = (
            1
            if target_period == source_period
            else (
                1 / 12
                if source_period == "year" and target_period == "month"
                else 12
                if source_period == "month" and target_period == "year"
                else None
            )
        )
        result["minimum_status"] = "Currency/pay period not comparable."
        result["country_minimum"] = {
            "value": minimum,
            "currency": c.get("currency", ""),
            "period": target_period,
        }
        if native and factor:
            low = lo * native * factor if lo is not None else None
            high = hi * native * factor if hi is not None else None
            result["country_comparison"] = {
                "min": round(low, 2) if low is not None else None,
                "max": round(high, 2) if high is not None else None,
                "currency": c.get("currency", ""),
                "period": target_period,
                "method": "Monthly/yearly rates compared with 12 calendar months only; hours, bonuses and take-home pay are not inferred.",
            }
            if high is not None and high < minimum:
                result["minimum_status"] = "Below country minimum."
            elif low is not None and low >= minimum:
                result["minimum_status"] = "Published lower bound meets minimum; verify offer."
            elif hi is None:
                result["minimum_status"] = "Upper bound unknown; cannot assess minimum."
            else:
                result["minimum_status"] = "Range overlaps minimum; lower pay is possible."
    return result


def fit(db, job):
    text = confirmed_text(db)
    learning = " ".join(fact_text(f) for f in facts(db, True) if f.learning)
    supporting = " ".join(
        fact_text(f)
        for f in db.scalars(select(FACTS["skills"]))
        if usable(f) and re.search(r"supporting use|under supervision", f.details, re.I)
    )
    req, prefer = clauses(job.get("description", ""))
    p = prefs(db)
    country = next((c for c in p["countries"] if c["country"] == job.get("country")), {})
    auth = country.get("authorization", "unknown")

    def split(value):
        terms = [s for s in SKILLS if contains(value, s)]
        return {
            "confirmed": [s for s in terms if contains(text, s) and not contains(supporting, s)],
            "supporting": [s for s in terms if contains(text, s) and contains(supporting, s)],
            "learning": [s for s in terms if not contains(text, s) and contains(learning, s)],
            "missing": [s for s in terms if not contains(text, s) and not contains(learning, s)],
        }

    required, preferred = split(req), split(prefer)
    blockers = []
    warnings = []
    for pattern, label, proof in [
        (
            r"\bp\.?eng\b|professional engineer|chartered engineer|\bpe licen[cs]e",
            "Professional licence required; none confirmed.",
            r"licensed professional engineer",
        ),
        (
            r"security clearance",
            "Security clearance required; confirm eligibility.",
            r"active security clearance",
        ),
        (
            r"citizenship|citizen or permanent resident|permanent residen\w*|\bcitizens? only\b",
            "Citizenship/permanent residency restriction.",
            None,
        ),
        (
            r"\b(full|valid|unrestricted)\b.{0,30}\b(driv\w*|licen[cs]e)\b|driver.?s licen[cs]e",
            "Full driving licence required; none confirmed.",
            r"full driving licen[cs]e",
        ),
        (
            r"\barabic\b",
            "Arabic required; professional proficiency not confirmed.",
            r"arabic.{0,25}(fluent|native|professional)",
        ),
        (
            r"\bfrench\b",
            "French required; beginner/learning is insufficient.",
            r"french.{0,25}(fluent|native|professional)",
        ),
        (
            r"primavera|\bp6\b",
            "Primavera P6 is a must-have and is not a confirmed skill.",
            r"primavera p6",
        ),
    ]:
        if re.search(pattern, req, re.I) and not (proof and re.search(proof, text, re.I)):
            blockers.append(label)
    california = any(
        f.status == "confirmed"
        and f.allowed_on_resume
        and "california" in fact_text(f).lower()
        and re.search(r"driver.?s licen[cs]e|driving licen[cs]e", fact_text(f), re.I)
        for f in facts(db)
    )
    if california and any("Full driving licence" in b for b in blockers):
        blockers = [b for b in blockers if "Full driving licence" not in b]
        if job.get("country") == "USA":
            warnings.append(
                "California driver's licence is recorded. Confirm the required class and state recognition for this posting."
            )
        else:
            blockers.append(
                "California driver's licence recorded; required local licence/class and recognition are not confirmed."
            )
    senior = bool(SENIOR.search(job["title"])) or any(
        int(n) > 3 for n in re.findall(r"\b(\d{1,2})\s*\+?\s*(?:years|yrs)\b", req, re.I)
    )
    if senior:
        warnings.append(
            "Senior responsibilities or more than three years requested; check the experience gap."
        )
    if re.search(r"\beit\b|engineer.in.training", job["title"] + " " + req, re.I):
        warnings.append(
            "EIT registration is not opened. Possible after APEGS/APEGA registration; check the employer’s entry route."
        )
    if auth != "authorised":
        warnings.append("Work authorisation: " + auth + ". Do not claim current authorisation.")
    if any(x.lower() in job.get("employer", "").lower() for x in p["excluded_employers"]):
        blockers.append("Excluded employer in your settings.")
    if (
        p["earliest_start"] >= "2027-01-01"
        and not country.get("allow_internships", False)
        and re.search(r"\b(intern(?:ship)?|co-op|coop)\b", job["title"], re.I)
    ):
        blockers.append("Intern/co-op is outside the January 2027 career target.")
    opt_alignment = None
    availability = country.get("work_start_not_before") or p.get("earliest_start", "")
    if availability:
        warnings.append(
            "Recorded availability is not before "
            + availability
            + "; confirm the posting's actual start date."
        )
        explicit_start = re.search(
            r"(?:start date|starting|commencement)\s*[:=-]?\s*(\d{4}-\d{2}-\d{2})",
            job.get("description", ""),
            re.I,
        )
        if explicit_start and explicit_start[1] < availability:
            blockers.append("Published start date is earlier than your recorded availability.")
    if job.get("country") == "USA" and "opt" in country.get("authorization_route", "").casefold():
        terms = [
            t
            for t in [
                "analytics",
                "data analysis",
                "data analyst",
                "business analyst",
                "sql",
                "python",
                "forecast",
                "optimisation",
                "optimization",
                "dashboard",
                "business intelligence",
                "operations research",
            ]
            if contains(job["title"] + " " + job.get("description", ""), t)
        ]
        opt_alignment = {
            "status": "potentially related" if terms else "needs duties review",
            "evidence_terms": terms,
            "explanation": "OPT employment must relate to the Business Analytics programme supporting OPT. A prior civil-engineering degree alone does not establish that relationship. Work starts only within the actual authorised EAD dates; no approval or extension is inferred from an application.",
            "reference": "https://www.uscis.gov/working-in-the-united-states/students-and-exchange-visitors/optional-practical-training-opt-for-f-1-students",
        }
        warnings.append(
            "OPT degree relationship: "
            + opt_alignment["status"]
            + ". Check actual duties and the authorised dates with the designated school official."
        )
    if job.get("country") == "Canada" and re.search(
        r"hospital|healthcare|health care|health services",
        job["title"] + " " + job.get("employer", "") + " " + job.get("description", ""),
        re.I,
    ):
        warnings.append(
            "Hospital employment is not blanket-excluded. Check the actual occupation and duties against the exact health-service restriction on your permit; non-clinical analytics is assessed separately from nursing or patient care."
        )
    relevant = domain(job["title"], job.get("description", "")[:1000]) or analytics_domain(
        job["title"]
    )
    evidence = sorted(
        {
            w
            for _, words, _ in FAMILIES
            for w in words
            if contains(text, w) and contains(job["title"] + " " + job.get("description", ""), w)
        }
    )
    count = sum(len(v) for v in required.values())
    score = min(
        100,
        round(
            (25 if relevant and text else 0)
            + min(20, len(evidence) * 4)
            + (
                45 * (len(required["confirmed"]) + 0.5 * len(required["supporting"])) / count
                if count
                else 0
            )
            + (10 if text and not senior else 0)
        ),
    )
    if not text:
        score = 0
    recommendation = (
        "Skip"
        if blockers or not relevant
        else "Apply"
        if score >= 65
        and not senior
        and not required["missing"]
        and not required["learning"]
        and not required["supporting"]
        and not (opt_alignment and opt_alignment["status"] == "needs duties review")
        else "Stretch"
    )
    if not count:
        warnings.append(
            "No recognised technical requirements extracted. Read the complete description before deciding."
        )
    return {
        "score": score,
        "recommendation": recommendation,
        "required": required,
        "preferred": preferred,
        "blockers": blockers,
        "warnings": warnings,
        "evidence_terms": evidence,
        "authorization": auth,
        "authorization_route": country.get("authorization_route", ""),
        "work_start_not_before": availability,
        "opt_alignment": opt_alignment,
        "authorization_note": country.get("authorization_note", ""),
        "salary_comparison": salary_comparison(job, p, country),
        "method": "Local keyword rubric from confirmed resume-allowed facts. Learning never counts as has. This does not establish eligibility.",
    }


def links(title, country, region=""):
    where = ", ".join(x for x in [region, country] if x)
    sites = {
        "Canada": [
            (
                "Canada Job Bank (government)",
                "https://www.jobbank.gc.ca/jobsearch/jobsearch?"
                + urlencode({"searchstring": title, "locationstring": where}),
            )
        ],
        "USA": [
            (
                "USAJOBS (government)",
                "https://www.usajobs.gov/Search/Results?" + urlencode({"k": title, "l": where}),
            )
        ],
        "UAE": [("Dubai government jobs", "https://dubaicareers.ae/")],
    }
    return [
        {
            "name": "LinkedIn (optional browser search)",
            "url": "https://www.linkedin.com/jobs/search/?"
            + urlencode({"keywords": title, "location": where, "f_JT": "F", "f_TPR": "r432000"}),
        }
    ] + [{"name": name, "url": url} for name, url in sites.get(country, [])]
