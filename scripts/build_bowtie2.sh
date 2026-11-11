#!/usr/bin/env bash
#
# Build Bowtie2 2.5.5 as a native Windows binary (static runtime, no mmap/shmem).
#
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/common.sh"

require_tool "$MAKE"

SRC="$BUILD_ROOT/bowtie2-src"
PREFIX="$STAGE/bowtie2"

log "Building Bowtie2 ($TARGET_ARCH) with $CXX"
rm -rf "$SRC"
cp -a "$ROOT/vendor/bowtie2" "$SRC"
cd "$SRC"

# Command-line variables override the Makefile's hard-coded
# x86_64-w64-mingw32-* tools, which are wrong for arm64 and for the
# MSYS2 toolchain layout.
"$MAKE" -j"$JOBS" \
  SHELL="$SHELL_WIN" \
  CXX="$CXX" \
  CC="$CC" \
  AR="$AR" \
  RC="$RC" \
  LD="${LD:-$CXX}" \
  STRIP="$STRIP" \
  WINDOWS=1 \
  MINGW=1 \
  BOWTIE_MM= \
  BOWTIE_SHARED_MEM= \
  ARCH="$TARGET_ARCH" \
  POPCNT_CAPABILITY="$POPCNT_CAPABILITY" \
  all

rm -rf "$PREFIX"
mkdir -p "$PREFIX"
cp -a \
  bowtie2 \
  bowtie2-align-s.exe \
  bowtie2-align-l.exe \
  bowtie2-build \
  bowtie2-build-s.exe \
  bowtie2-build-l.exe \
  bowtie2-inspect \
  bowtie2-inspect-s.exe \
  bowtie2-inspect-l.exe \
  "$PREFIX/"
cp -a "$ROOT/packaging/bowtie2/"*.bat "$PREFIX/"
if [[ -f LICENSE ]]; then
  cp -a LICENSE "$PREFIX/"
fi

log "Bowtie2 installed to $PREFIX"
