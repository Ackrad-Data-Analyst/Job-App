"""Owner's discovery-source exclusions, independent of employer demographics."""

from urllib.parse import urlsplit


def is_indeed(url):
    try:
        host = (urlsplit(url).hostname or "").casefold()
        return any(part in {"indeed", "indeedjobs"} for part in host.split("."))
    except ValueError:
        return False
