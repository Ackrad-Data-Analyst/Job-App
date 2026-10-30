#!/usr/bin/env python3
"""Reject staged private files and common credential formats before committing."""

import re
import subprocess
import sys
from pathlib import Path

BAD_PATHS = {
    "data",
    "node_modules",
    ".venv",
    ".launcher-venv",
    ".next",
    "test-results",
    ".git",
}
PATTERNS = [
    rb"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----",
    rb"\bsk-(?:proj-)?[A-Za-z0-9_-]{24,}",
    rb"\bgh[pousr]_[A-Za-z0-9]{30,}",
    rb'(?i)(?:API_TOKEN|SESSION_SECRET)\s*=\s*["\']?(?!fictional|test|development)[A-Za-z0-9_-]{32,}',
]


def check(paths, read):
    errors = []
    for name in paths:
        p = Path(name)
        if (
            set(p.parts) & BAD_PATHS
            or (p.name.startswith(".env") and p.name != ".env.example")
            or p.suffix.lower() in {".db", ".sqlite", ".docx", ".pdf", ".csv"}
            or p.name == "profile.seed.json"
        ):
            errors.append(name + ": private/generated path")
            continue
        data = read(name)
        if any(re.search(pattern, data) for pattern in PATTERNS):
            errors.append(name + ": possible credential")
    return errors


if __name__ == "__main__":
    paths = (
        subprocess.check_output(
            ["git", "diff", "--cached", "--name-only", "--diff-filter=ACMR", "-z"]
        )
        .decode()
        .strip("\0")
        .split("\0")
    )
    errors = check(
        [p for p in paths if p],
        lambda p: subprocess.check_output(["git", "show", ":" + p]),
    )
    if errors:
        print("\n".join(errors))
        sys.exit(1)
    print("Staged private-file and credential checks passed.")
