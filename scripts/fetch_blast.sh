#!/usr/bin/env bash
#
# Fetch the official NCBI BLAST+ Windows x64 binaries and keep only the
# tools GetOrganelle actually uses (blastn + makeblastdb).
#
# NCBI does not publish a Windows arm64 build.  The x64 binaries run on
# Windows 11 ARM64 through the built-in x64 emulation, so the same archive
# is used for both target architectures.
#
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/common.sh"

BLAST_VERSION="2.17.0"
BLAST_URL="https://ftp.ncbi.nlm.nih.gov/blast/executables/blast+/${BLAST_VERSION}/ncbi-blast-${BLAST_VERSION}+-x64-win64.tar.gz"
BLAST_SHA256="ccde8788641e8f4137536aaadedfeac2f3599dbbc6166e701b5d89d19fa79038"

ARCHIVE="$BUILD_ROOT/ncbi-blast-${BLAST_VERSION}-x64-win64.tar.gz"
EXTRACT="$BUILD_ROOT/ncbi-blast-extract"
PREFIX="$STAGE/ncbi-blast"
TOPDIR="ncbi-blast-${BLAST_VERSION}+"

require_tool curl tar sha256sum

log "Fetching NCBI BLAST+ ${BLAST_VERSION} (x64-win64)"
if [[ ! -f "$ARCHIVE" ]]; then
  curl -fL --retry 3 --retry-delay 2 -o "$ARCHIVE" "$BLAST_URL"
fi
echo "${BLAST_SHA256}  ${ARCHIVE}" | sha256sum -c -

rm -rf "$EXTRACT" "$PREFIX"
mkdir -p "$EXTRACT" "$PREFIX"
tar -xzf "$ARCHIVE" -C "$EXTRACT"

for f in blastn.exe makeblastdb.exe nghttp2.dll; do
  cp -a "$EXTRACT/$TOPDIR/bin/$f" "$PREFIX/"
done
for f in LICENSE README ChangeLog BLAST_PRIVACY; do
  if [[ -f "$EXTRACT/$TOPDIR/$f" ]]; then
    cp -a "$EXTRACT/$TOPDIR/$f" "$PREFIX/"
  fi
done

cat > "$PREFIX/ARCHITECTURE.txt" <<'EOF'
These are the official NCBI BLAST+ x64 Windows binaries.
On Windows 11 ARM64 they run through the built-in x64 emulation.
EOF

log "BLAST+ installed to $PREFIX"
