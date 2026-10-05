#!/usr/bin/env bash
set -e
cd "$(dirname "$0")"
echo "=== IRA Review installer ==="
PY=$(command -v python3.12 || command -v python3.11 || command -v python3 || true)
if [ -z "$PY" ] || ! "$PY" -c 'import sys; sys.exit(0 if sys.version_info >= (3,11) else 1)'; then
  echo "Python 3.11+ is required (https://www.python.org/downloads/)."; exit 1
fi
[ -d .venv ] || "$PY" -m venv .venv
.venv/bin/python -m pip install -q --upgrade pip
.venv/bin/python -m pip install -r requirements.txt
mkdir -p user
echo "Fetching live market data..."
PYTHONPATH=src .venv/bin/python -m irasim.live || echo "(live data refresh failed; you can retry from the app: Data and Updates)"
echo; echo "Done. Start the app with bash run.sh"
