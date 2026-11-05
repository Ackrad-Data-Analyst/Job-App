"""Conservative location normalisation and preference ranking; no commute estimates."""

import re

ALIASES = {
    "Canada": [
        "canada",
        "saskatchewan",
        "alberta",
        "ontario",
        "british columbia",
        "manitoba",
        "quebec",
        "nova scotia",
        "new brunswick",
        "newfoundland",
        "prince edward island",
        "yukon",
        "northwest territories",
        "nunavut",
        "regina",
        "saskatoon",
        "moose jaw",
        "calgary",
        "edmonton",
        "toronto",
        "ottawa",
        "winnipeg",
        "vancouver",
    ],
    "UAE": ["united arab emirates", "uae", "dubai", "abu dhabi", "sharjah", "ras al khaimah"],
    "USA": [
        "united states",
        "united states of america",
        "usa",
        "san francisco",
        "california",
        "new york",
        "texas",
        "washington dc",
    ],
    "Australia": ["australia"],
    "United Kingdom": ["united kingdom", "england", "scotland", "wales", "london, uk"],
    "Ireland": ["ireland"],
    "New Zealand": ["new zealand"],
    "Qatar": ["qatar", "doha"],
    "Italy": ["italy", "italia"],
    "Zambia": ["zambia"],
}
CODES = {
    "ca": "Canada",
    "ae": "UAE",
    "us": "USA",
    "au": "Australia",
    "gb": "United Kingdom",
    "ie": "Ireland",
    "nz": "New Zealand",
    "qa": "Qatar",
    "it": "Italy",
    "zm": "Zambia",
}


def has(text, term):
    return bool(re.search(r"(?<!\w)" + re.escape(term) + r"(?!\w)", text, re.I))


def country_for(location, explicit=""):
    if explicit:
        name = CODES.get(explicit.casefold(), explicit)
        if name in ALIASES:
            return name, "Structured source country"
    matches = [
        country for country, terms in ALIASES.items() if any(has(location, t) for t in terms)
    ]
    if len(matches) == 1:
        return matches[0], "Inferred from published city/province/country text; review the original"
    return "", "Country not established from published fields"


def region_rank(location, country, region="", priorities=None):
    if region and has(location, region):
        return 0, "Matches your requested city/province"
    if country == "Canada":
        tiers = [
            ("Regina", ["regina", "white city", "emerald park"]),
            ("Saskatchewan", ["saskatchewan", "saskatoon", "moose jaw", "regina"]),
            ("Alberta", ["alberta", "calgary", "edmonton"]),
            ("Ontario", ["ontario", "toronto", "ottawa", "mississauga", "hamilton"]),
        ]
        order = priorities or ["Regina", "Saskatchewan", "Alberta", "Ontario"]
        for i, label in enumerate(order):
            terms = next((terms for name, terms in tiers if name == label), [label])
            if any(has(location, t) for t in terms):
                return i + 1, label + " preference; commute/travel suitability still needs review"
        return len(order) + 1, "Other Canadian location; still included"
    if country == "UAE":
        if has(location, "dubai"):
            return 1, "Dubai preference"
        if has(location, "abu dhabi"):
            return 2, "Abu Dhabi preference"
    return 10, "Review location requirements"
