#!/usr/bin/env bash
#
# Build Bowtie2 2.5.5.
#
# Windows: native binary, static runtime, no mmap/shmem.
# Linux/macOS: the normal POSIX build (mmap and shared memory enabled).
#
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/common.sh"

require_tool "$MAKE"

SRC="$BUILD_ROOT/bowtie2-src"
PREFIX="$STAGE/bowtie2"

log "Building Bowtie2 ($PLATFORM_LABEL $TARGET_ARCH) with $CXX"
rm -rf "$SRC"
cp -a "$ROOT/vendor/bowtie2" "$SRC"
cd "$SRC"

if [[ "$HOST_OS" == windows ]]; then
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
else
  "$MAKE" -j"$JOBS" \
    CXX="$CXX" \
    CC="$CC" \
    AR="$AR" \
    ARCH="$TARGET_ARCH" \
    POPCNT_CAPABILITY="$POPCNT_CAPABILITY" \
    all

  rm -rf "$PREFIX"
  mkdir -p "$PREFIX"
  cp -a \
    bowtie2 \
    bowtie2-align-s \
    bowtie2-align-l \
    bowtie2-build \
    bowtie2-build-s \
    bowtie2-build-l \
    bowtie2-inspect \
    bowtie2-inspect-s \
    bowtie2-inspect-l \
    "$PREFIX/"
fi

if [[ -f LICENSE ]]; then
  cp -a LICENSE "$PREFIX/"
fi

log "Bowtie2 installed to $PREFIX"
