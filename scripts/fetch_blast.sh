#!/usr/bin/env bash
#
# Fetch the official NCBI BLAST+ binaries and keep only the tools
# GetOrganelle and the graph viewer use (blastn + tblastn + makeblastdb).
#
# NCBI publishes native Linux x64, Linux arm64, macOS x64, macOS arm64,
# universal macOS, and Windows x64 builds.  Windows arm64 runs the x64
# binaries through the built-in x64 emulation, as NCBI has no win_arm64
# archive.
#
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/common.sh"

BLAST_VERSION="2.17.0"
TOPDIR="ncbi-blast-${BLAST_VERSION}+"

case "$HOST_OS/$TARGET_ARCH" in
  windows/x86_64)
    BLAST_PLATFORM="x64-win64"
    BLAST_SHA256="ccde8788641e8f4137536aaadedfeac2f3599dbbc6166e701b5d89d19fa79038"
    ;;
  linux/x86_64)
    BLAST_PLATFORM="x64-linux"
    BLAST_SHA256="3888112d8207831aa47371d93583c601f058f88b5db22dc782438b039a3a411b"
    ;;
  macos/aarch64)
    BLAST_PLATFORM="aarch64-macosx"
    BLAST_SHA256="8d6739fa133107bce91dbb6b143ec993c9983416244fe502f9c36d585850dc00"
    ;;
  *)
    echo "No pinned NCBI BLAST+ archive for $HOST_OS/$TARGET_ARCH." >&2
    echo "Add its URL and SHA-256 to scripts/fetch_blast.sh first." >&2
    exit 2
    ;;
esac

BLAST_URL="https://ftp.ncbi.nlm.nih.gov/blast/executables/blast+/${BLAST_VERSION}/ncbi-blast-${BLAST_VERSION}+-${BLAST_PLATFORM}.tar.gz"
ARCHIVE="$BUILD_ROOT/ncbi-blast-${BLAST_VERSION}-${BLAST_PLATFORM}.tar.gz"
EXTRACT="$BUILD_ROOT/ncbi-blast-extract"
PREFIX="$STAGE/ncbi-blast"

require_tool curl tar

log "Fetching NCBI BLAST+ ${BLAST_VERSION} (${BLAST_PLATFORM})"
if [[ ! -f "$ARCHIVE" ]]; then
  curl -fL --retry 3 --retry-delay 2 -o "$ARCHIVE" "$BLAST_URL"
fi
ACTUAL_SHA256="$(sha256_file "$ARCHIVE")"
if [[ "$ACTUAL_SHA256" != "$BLAST_SHA256" ]]; then
  echo "BLAST archive checksum mismatch for $ARCHIVE" >&2
  echo "  expected: $BLAST_SHA256" >&2
  echo "  actual:   $ACTUAL_SHA256" >&2
  exit 1
fi

rm -rf "$EXTRACT" "$PREFIX"
mkdir -p "$EXTRACT" "$PREFIX"
tar -xzf "$ARCHIVE" -C "$EXTRACT"

if [[ "$HOST_OS" == windows ]]; then
  BLAST_FILES=(blastn.exe tblastn.exe makeblastdb.exe nghttp2.dll)
else
  BLAST_FILES=(blastn tblastn makeblastdb)
fi
for f in "${BLAST_FILES[@]}"; do
  cp -a "$EXTRACT/$TOPDIR/bin/$f" "$PREFIX/"
done
for f in LICENSE README ChangeLog BLAST_PRIVACY; do
  if [[ -f "$EXTRACT/$TOPDIR/$f" ]]; then
    cp -a "$EXTRACT/$TOPDIR/$f" "$PREFIX/"
  fi
done

case "$HOST_OS" in
  windows)
    cat > "$PREFIX/ARCHITECTURE.txt" <<'EOF'
These are the official NCBI BLAST+ x64 Windows binaries.
On Windows 11 ARM64 they run through the built-in x64 emulation.
EOF
    ;;
  linux)
    cat > "$PREFIX/ARCHITECTURE.txt" <<'EOF'
These are the official NCBI BLAST+ Linux x64 binaries.
EOF
    ;;
  macos)
    cat > "$PREFIX/ARCHITECTURE.txt" <<'EOF'
These are the official NCBI BLAST+ macOS arm64 binaries.
EOF
    ;;
esac

log "BLAST+ installed to $PREFIX"
