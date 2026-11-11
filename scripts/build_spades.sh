#!/usr/bin/env bash
#
# Build the patched SPAdes (native MinGW-w64, no MSYS/Cygwin runtime).
#
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/common.sh"

require_tool cmake ninja

SRC="$ROOT/vendor/spades/src"
BUILD="$BUILD_ROOT/spades"
PREFIX="$STAGE/spades"

log "Building SPAdes ($TARGET_ARCH) with $CXX"
rm -rf "$BUILD" "$PREFIX"
mkdir -p "$BUILD" "$PREFIX"

cmake -S "$SRC" -B "$BUILD" -G Ninja \
  -DCMAKE_BUILD_TYPE=RelWithDebInfo \
  -DCMAKE_INSTALL_PREFIX="$PREFIX" \
  -DCMAKE_C_COMPILER="$CC" \
  -DCMAKE_CXX_COMPILER="$CXX" \
  -DCMAKE_AR="$AR" \
  -DCMAKE_RANLIB="$RANLIB" \
  -DSPADES_USE_JEMALLOC=OFF \
  -DSPADES_USE_MIMALLOC=OFF

cmake --build "$BUILD" -j "$JOBS"
cmake --install "$BUILD"

log "SPAdes installed to $PREFIX"
