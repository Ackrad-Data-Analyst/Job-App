#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
if ! command -v python3 >/dev/null; then
  echo 'Install Python 3.12+ from https://www.python.org/downloads/ and Node.js 24 LTS from https://nodejs.org/'
  exit 1
fi
exec python3 start.py "$@"
