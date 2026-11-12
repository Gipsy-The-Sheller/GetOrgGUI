#!/usr/bin/env bash
#
# Create the bundled Python environment for the Linux/macOS package.
#
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

PY="${PYTHON:-python3}"
if ! command -v "$PY" >/dev/null 2>&1; then
  echo "Python 3 was not found. Install Python 3.10+ and retry." >&2
  exit 1
fi

"$PY" -m venv "$ROOT/venv"
"$ROOT/venv/bin/python" -m pip install --upgrade pip
"$ROOT/venv/bin/python" -m pip install -r "$ROOT/requirements.txt"

if [[ -f "$ROOT/gui/requirements.txt" ]]; then
  if ! "$ROOT/venv/bin/python" -m pip install -r "$ROOT/gui/requirements.txt"; then
    echo
    echo "WARNING: GUI dependencies could not be installed."
    echo "The command-line package still works; the desktop GUI may not start."
  fi
fi

echo
echo "Python environment created at \"$ROOT/venv\"."
