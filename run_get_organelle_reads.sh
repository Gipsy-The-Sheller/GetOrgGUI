#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
case "$(uname -s)" in
  Linux*)  DEP=linux ;;
  Darwin*) DEP=macOS ;;
  *) echo "Unsupported platform: $(uname -s)" >&2; exit 1 ;;
esac
PY="$ROOT/venv/bin/python"
if [[ ! -x "$PY" ]]; then
  PY=python3
fi
export PATH="$ROOT/venv/bin:$ROOT/GetOrganelle/GetOrganelleDep/$DEP/bowtie2:$ROOT/GetOrganelle/GetOrganelleDep/$DEP/ncbi-blast:$ROOT/GetOrganelle/GetOrganelleDep/$DEP/SPAdes/bin:$PATH"
exec "$PY" "$ROOT/GetOrganelle/get_organelle_from_reads.py" "$@"
