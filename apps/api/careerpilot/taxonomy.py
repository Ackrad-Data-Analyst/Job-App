"""Career directions, not claims of qualifications or current vacancies."""

import json
import re
from pathlib import Path

DATA = Path(__file__).with_name("reference")
ROLE_TITLES = json.loads((DATA / "role_titles.json").read_text())
WORDS = [
    ["civil", "municipal", "infrastructure", "land development", "site"],
    [
        "water",
        "hydrology",
        "hydraulic",
        "hec-ras",
        "drainage",
        "stormwater",
        "flood",
        "irrigation",
        "wastewater",
    ],
    ["environmental", "sustainability", "compliance", "water", "assessment"],
    ["geotechnical", "mining", "tailings", "hydrogeology", "groundwater", "materials"],
    ["transportation", "highway", "road", "traffic", "rail", "airport", "pavement"],
    [
        "gis",
        "geospatial",
        "qgis",
        "arcgis",
        "arcpy",
        "survey",
        "geomatics",
        "remote sensing",
        "gps",
    ],
    [
        "quantity",
        "planswift",
        "cost",
        "estimating",
        "construction",
        "field",
        "concrete",
        "materials",
    ],
    [
        "data",
        "business analyst",
        "operations analyst",
        "hospital",
        "project controls",
        "cost",
        "risk",
        "analytics",
        "sql",
        "python",
        "excel",
        "scheduling",
        "ms project",
        "asset",
    ],
    ["renewable", "solar", "wind", "energy", "hydropower", "civil", "gis"],
    ["planning", "land development", "municipal", "gis", "infrastructure"],
    ["bridge", "structural", "dam", "concrete", "inspection"],
    ["marine", "coastal", "port", "dredging", "civil"],
    ["transit", "rail", "track", "transportation", "asset"],
]
FAMILIES = [(name, WORDS[i], titles) for i, (name, titles) in enumerate(ROLE_TITLES.items())]
ALL_TITLES = list(dict.fromkeys(t for _, _, titles in FAMILIES for t in titles))


def family_terms(title):
    query = title.casefold()
    exact = next(
        (words for _, words, titles in FAMILIES if any(t.casefold() == query for t in titles)), None
    )
    if exact:
        return exact
    tokens = set(re.findall(r"[a-z]{3,}", query)) - {
        "junior",
        "graduate",
        "engineer",
        "training",
        "early",
        "career",
    }
    found = []
    for _, words, titles in FAMILIES:
        if any(word in query for word in words) or any(
            tokens & set(re.findall(r"[a-z]{3,}", t.casefold())) for t in titles
        ):
            found += words
    return list(dict.fromkeys(found)) or list(tokens)


EDUCATION_PATHWAYS = [
    {
        "title": "Construction, estimating and project controls",
        "bridge": "Civil-engineering fundamentals plus Excel, data handling and optimisation can support take-offs, cost checks, schedules and project reporting.",
        "titles": [
            "Construction Field Coordinator",
            "Junior Civil Estimator",
            "Project Controls Analyst",
            "Capital Projects Analyst",
        ],
        "check": "Verify actual project duties, estimating tools and scheduling proficiency. Do not claim Primavera P6 from coursework.",
    },
    {
        "title": "GIS and infrastructure analytics",
        "bridge": "Civil-domain knowledge plus SQL, Python/R and visualisation can support spatial, infrastructure and asset-data roles.",
        "titles": [
            "GIS Analyst",
            "Infrastructure Data Analyst",
            "Transportation Data Analyst",
            "Infrastructure Asset Management Analyst",
        ],
        "check": "Actual GIS, coding, database and dashboard work must be evidenced separately from degree names.",
    },
    {
        "title": "Water, transportation and energy",
        "bridge": "Hydrology, water resources, surveying and civil coursework can provide academic context; analytics can support modelling and engineering decisions.",
        "titles": [
            "Hydrology Analyst",
            "Junior Hydraulic Modeller",
            "Transportation Planning Analyst",
            "Renewable Energy GIS Analyst",
        ],
        "check": "Check technical requirements, local engineering registration and specialist software for each posting.",
    },
    {
        "title": "Specialist and regulated pathways",
        "bridge": "Bridges, structural work, dams, marine, geotechnical and mining are relevant civil-engineering directions to explore.",
        "titles": [
            "Bridge Engineer-in-Training",
            "Junior Tailings Engineer",
            "Graduate Marine Civil Engineer",
            "Dam Safety Analyst",
        ],
        "check": "A civil degree alone does not establish specialist experience, professional registration or eligibility. Treat these as stretch directions until the posting and your evidence support them.",
    },
]
CURRICULUM_SOURCES = [
    {
        "institution": "Northeastern University",
        "programme": "Business Analytics MS",
        "url": "https://catalog.northeastern.edu/graduate/business/business-analytics-ms/",
        "status": "Official curriculum reference, not independently verified in this release. Programme requirements do not prove individual course completion.",
    },
    {
        "institution": "Jain (Deemed-to-be University)",
        "programme": "Civil Engineering BTech",
        "url": "https://set.jainuniversity.ac.in/",
        "status": "Official school website candidate. Exact cohort curriculum needs the official programme page or transcript; it is not independently verified in this release.",
    },
]
