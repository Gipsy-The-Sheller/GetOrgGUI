#!/usr/bin/env bash
#
# Build fastp (adapter trimming / read filtering) for native Windows.
#
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/common.sh"

require_tool "$MAKE"

SRC="$BUILD_ROOT/fastp-src"
PREFIX="$STAGE/fastp"

log "Building fastp ($TARGET_ARCH) with $CXX"
rm -rf "$SRC" "$PREFIX"
cp -a "$ROOT/vendor/fastp" "$SRC"
mkdir -p "$PREFIX"
cd "$SRC"

"$MAKE" clean >/dev/null 2>&1 || true
"$MAKE" -j"$JOBS" \
  SHELL="$SHELL_WIN" \
  CXX="$CXX" \
  CXXFLAGS="-std=c++11 -pthread -g -O2 -I./src" \
  LIBS="-lisal -ldeflate -lpthread -ldbghelp -lws2_32 -lpsapi" \
  static

cp -a fastp.exe "$PREFIX/"
log "fastp installed to $PREFIX"
