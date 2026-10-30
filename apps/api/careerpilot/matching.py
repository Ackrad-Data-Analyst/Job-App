import re
from urllib.parse import urlencode

from sqlalchemy import select

from .models import FACTS, Candidate, Preferences
from .schemas import DENIED_ORG

BANNED = re.compile(
    r"\b(gpa|cgpa|mca|master\s+of\s+computer\s+applications|immigration|visa|relocat\w*|work authori[sz]\w*|authori[sz]ed to work|citizenship|permanent residen\w*|spearheaded|leveraged|proven track record|passionate|dynamic|results.driven|expert|eit|p\.?eng\.?|p\.?e\.?|fe exam candidate|primavera|revit|"
    + DENIED_ORG
    + r")\b|\u2014",
    re.I,
)
FAMILIES = [
    (
        "Construction and site",
        ["civil", "construction", "site", "quantity"],
        [
            "Graduate Civil Engineer",
            "Junior Civil Engineer",
            "EIT Civil",
            "Site Engineer (Civil)",
            "Field Engineer",
            "Project Engineer (junior)",
            "QA/QC Engineer (Civil)",
            "Technical Engineer",
        ],
    ),
    (
        "Cost and quantity surveying",
        ["quantity", "planswift", "cost", "tender"],
        [
            "Quantity Surveyor",
            "Assistant/Junior Quantity Surveyor",
            "Cost Estimator",
            "Estimating Engineer",
            "Cost Engineer",
        ],
    ),
    (
        "Project controls and planning",
        ["ms project", "scheduling", "progress", "excel"],
        ["Project Controls Analyst", "Planning Engineer (junior)", "Scheduler (junior)"],
    ),
    (
        "GIS and geospatial",
        ["qgis", "arcgis", "arcpy", "gis"],
        ["GIS Analyst", "GIS Technician", "Geospatial Analyst"],
    ),
    (
        "Water resources and stormwater",
        ["hec-ras", "hydrology", "drainage", "stormwater"],
        [
            "Water Resources EIT",
            "Stormwater/Drainage Engineer (graduate)",
            "Hydrology/Hydraulic Modeller (junior)",
        ],
    ),
    (
        "Transportation",
        ["road", "pavement", "transportation", "python"],
        ["Transportation Engineer (graduate)", "Transportation Data Analyst"],
    ),
    ("Environmental", ["environmental", "water", "civil"], ["Environmental Engineer (graduate)"]),
    (
        "Renewable energy",
        ["solar", "renewable", "gis", "hydrology"],
        ["Renewable Energy Civil Engineer (graduate)", "Solar/Wind Development Analyst"],
    ),
    (
        "Mining",
        ["geotechnical", "civil", "surveying"],
        ["Mining Engineer-in-Training (civil/geotechnical/tailings support)"],
    ),
    ("Surveying", ["gps", "total station", "surveying"], ["Survey Technician"]),
    (
        "Asset management",
        ["condition", "maintenance", "infrastructure", "analytics"],
        ["Asset Management Analyst"],
    ),
    (
        "Infrastructure data analytics",
        ["python", "sql", "analytics", "civil"],
        ["Infrastructure Data Analyst", "Construction Data Analyst"],
    ),
]
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
    ("Canada", "Saskatchewan (Regina first), Alberta, Other provinces", "CAD"),
    ("UAE", "Dubai, Abu Dhabi", "AED"),
    ("USA", "", "USD"),
    ("Australia", "", "AUD"),
    ("United Kingdom", "", "GBP"),
    ("Ireland", "", "EUR"),
    ("New Zealand", "", "NZD"),
    ("Qatar", "", "QAR"),
    ("Italy", "", "EUR"),
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
        "comparison_currency": "CAD",
        "exchange_rates": {},
        "exchange_rate_date": "",
        "earliest_start": "2027-01-01",
        "employment_type": "Full-time",
        "early_career_only": True,
        "languages_on_resume": False,
        "canadian_location": False,
    }


def prefs(db):
    return db.scalar(select(Preferences)).data


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
            "hydrolog",
            "asset management",
        ]
    ) or any(x in title.lower() for x in ["field engineer", "technical engineer", "scheduler"])


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
        result["minimum_status"] = "Currency/annual period not comparable."
        if native and job.get("salary_period") == "year":
            if hi is not None and hi * native < minimum:
                result["minimum_status"] = "Below country minimum."
            elif lo is not None and lo * native >= minimum:
                result["minimum_status"] = "Published lower bound meets minimum; verify offer."
            elif hi is None:
                result["minimum_status"] = "Upper bound unknown; cannot assess minimum."
            else:
                result["minimum_status"] = "Range overlaps minimum; lower pay is possible."
    return result


def fit(db, job):
    text = confirmed_text(db)
    learning = " ".join(fact_text(f) for f in facts(db, True) if f.learning)
    req, prefer = clauses(job.get("description", ""))
    p = prefs(db)
    country = next((c for c in p["countries"] if c["country"] == job.get("country")), {})
    auth = country.get("authorization", "unknown")

    def split(value):
        terms = [s for s in SKILLS if contains(value, s)]
        return {
            "confirmed": [s for s in terms if contains(text, s)],
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
    if p["earliest_start"] >= "2027-01-01" and re.search(
        r"\b(intern(?:ship)?|co-op|coop)\b", job["title"], re.I
    ):
        blockers.append("Intern/co-op is outside the January 2027 career target.")
    relevant = domain(job["title"], job.get("description", "")[:1000])
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
            + (45 * len(required["confirmed"]) / count if count else 0)
            + (10 if text and not senior else 0)
        ),
    )
    if not text:
        score = 0
    recommendation = (
        "Skip"
        if blockers or not relevant
        else "Apply"
        if score >= 65 and not senior and not required["missing"] and not required["learning"]
        else "Consider"
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
        "authorization_note": country.get("authorization_note", ""),
        "salary_comparison": salary_comparison(job, p, country),
        "method": "Local keyword rubric from confirmed resume-allowed facts. Learning never counts as has. This does not establish eligibility.",
    }


def links(title, country, region=""):
    where = ", ".join(x for x in [region, country] if x)
    sites = {
        "Canada": [("Job Bank", "jobbank.gc.ca")],
        "UAE": [
            ("Bayt", "bayt.com"),
            ("GulfTalent", "gulftalent.com"),
            ("Naukrigulf", "naukrigulf.com"),
        ],
        "Australia": [("Seek", "seek.com.au")],
        "New Zealand": [("Seek NZ", "seek.co.nz")],
        "United Kingdom": [("Reed", "reed.co.uk")],
        "Qatar": [("GulfTalent", "gulftalent.com")],
    }
    return [
        {
            "name": "LinkedIn",
            "url": "https://www.linkedin.com/jobs/search/?"
            + urlencode({"keywords": title, "location": where, "f_JT": "F"}),
        }
    ] + [
        {
            "name": name,
            "url": "https://www.google.com/search?"
            + urlencode({"q": f'site:{host} "{title}" {where}'}),
        }
        for name, host in [
            ("Indeed", "indeed.com"),
            *sites.get(country, []),
            ("Employer sites", "careers"),
        ]
    ]
