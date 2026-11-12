#!/usr/bin/env bash
#
# Build the patched SPAdes.
#
# Windows: native MinGW-w64, no MSYS/Cygwin runtime.
# Linux:   native GCC.
# macOS:   Apple Clang with Homebrew libomp (SPAdes requires OpenMP).
#
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/common.sh"

require_tool cmake ninja

SRC="${SPADES_SRC:-$ROOT/vendor/spades/src}"
BUILD="${SPADES_BUILD_DIR:-$BUILD_ROOT/spades}"
PREFIX="${SPADES_PREFIX:-$STAGE/spades}"

log "Building SPAdes ($PLATFORM_LABEL $TARGET_ARCH) with $CXX"
rm -rf "$BUILD" "$PREFIX"
mkdir -p "$BUILD" "$PREFIX"

CMAKE_EXTRA=(-DSPADES_USE_JEMALLOC=OFF -DSPADES_USE_MIMALLOC=OFF)
if [[ "$HOST_OS" == macos ]]; then
  LIBOMP_PREFIX="${LIBOMP_PREFIX:-$(brew --prefix libomp 2>/dev/null || true)}"
  BZIP2_PREFIX="${BZIP2_PREFIX:-$(brew --prefix bzip2 2>/dev/null || true)}"
  if [[ -z "$LIBOMP_PREFIX" || ! -f "$LIBOMP_PREFIX/lib/libomp.dylib" ]]; then
    echo "Homebrew libomp not found; install it with: brew install libomp" >&2
    exit 1
  fi
  if [[ -z "$BZIP2_PREFIX" || ! -d "$BZIP2_PREFIX/include" ]]; then
    echo "Homebrew bzip2 not found; install it with: brew install bzip2" >&2
    exit 1
  fi
  BZIP2_LIB="$BZIP2_PREFIX/lib/libbz2.dylib"
  if [[ -f "$BZIP2_PREFIX/lib/libbz2.a" ]]; then
    BZIP2_LIB="$BZIP2_PREFIX/lib/libbz2.a"
  fi
  CMAKE_EXTRA+=(
    "-DCMAKE_PREFIX_PATH=$LIBOMP_PREFIX;$BZIP2_PREFIX"
    "-DOpenMP_CXX_FLAGS=-Xpreprocessor -fopenmp"
    "-DOpenMP_CXX_LIB_NAMES=omp"
    "-DOpenMP_omp_LIBRARY=$LIBOMP_PREFIX/lib/libomp.dylib"
    "-DCMAKE_C_FLAGS=-I$LIBOMP_PREFIX/include"
    "-DCMAKE_CXX_FLAGS=-I$LIBOMP_PREFIX/include"
    "-DCMAKE_EXE_LINKER_FLAGS=-L$LIBOMP_PREFIX/lib -lomp"
    "-DBZIP2_INCLUDE_DIR=$BZIP2_PREFIX/include"
    "-DBZIP2_LIBRARY_RELEASE=$BZIP2_LIB"
  )
fi

cmake -S "$SRC" -B "$BUILD" -G Ninja \
  -DCMAKE_BUILD_TYPE=RelWithDebInfo \
  -DCMAKE_INSTALL_PREFIX="$PREFIX" \
  -DCMAKE_C_COMPILER="$CC" \
  -DCMAKE_CXX_COMPILER="$CXX" \
  -DCMAKE_AR="$AR" \
  -DCMAKE_RANLIB="$RANLIB" \
  "${CMAKE_EXTRA[@]}"

cmake --build "$BUILD" -j "$JOBS"
cmake --install "$BUILD"

log "SPAdes installed to $PREFIX"
