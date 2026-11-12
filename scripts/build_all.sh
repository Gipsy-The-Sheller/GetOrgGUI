#!/usr/bin/env bash
#
# Build every dependency used by GetOrganelle for the current platform.
#
set -euo pipefail

# Optional first argument overrides TARGET_ARCH (used by CI, where the
# environment may not survive every shell boundary).
if [[ $# -ge 1 && -n "${1:-}" ]]; then
  export TARGET_ARCH="$1"
fi

source "$(dirname "${BASH_SOURCE[0]}")/common.sh"

"$ROOT/scripts/build_spades.sh"
"$ROOT/scripts/build_fastp.sh"
"$ROOT/scripts/build_bowtie2.sh"
"$ROOT/scripts/build_samtools.sh"
"$ROOT/scripts/fetch_blast.sh"

log "All components built for $PLATFORM_LABEL $ARCH_LABEL ($TARGET_ARCH)"
