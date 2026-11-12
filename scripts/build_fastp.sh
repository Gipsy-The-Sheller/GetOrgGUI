#!/usr/bin/env bash
#
# Build fastp (adapter trimming / read filtering).
#
# Windows uses a static MinGW build.  Linux prefers a fully static binary
# where the ISA-L and libdeflate static archives are available; macOS links
# the Homebrew static archives (a fully static Mach-O executable is not
# supported by the platform).
#
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/common.sh"

require_tool "$MAKE"

SRC="$BUILD_ROOT/fastp-src"
PREFIX="$STAGE/fastp"

log "Building fastp ($PLATFORM_LABEL $TARGET_ARCH) with $CXX"
rm -rf "$SRC" "$PREFIX"
cp -a "$ROOT/vendor/fastp" "$SRC"
mkdir -p "$PREFIX"
cd "$SRC"

"$MAKE" clean >/dev/null 2>&1 || true

if [[ "$HOST_OS" == windows ]]; then
  # LLD (CLANGARM64) rejects GNU ld's --no-as-needed; a static link does
  # not need it.
  "$MAKE" -j"$JOBS" \
    SHELL="$SHELL_WIN" \
    CXX="$CXX" \
    CXXFLAGS="-std=c++11 -pthread -g -O2 -I./src" \
    LIBS="-lisal -ldeflate -lpthread -ldbghelp -lws2_32 -lpsapi" \
    STATIC_FLAGS="-static -pthread" \
    static
  cp -a fastp.exe "$PREFIX/"
elif [[ "$HOST_OS" == macos ]]; then
  ISAL_PREFIX="${ISAL_PREFIX:-$(brew --prefix isa-l 2>/dev/null || true)}"
  DEFLATE_PREFIX="${DEFLATE_PREFIX:-$(brew --prefix libdeflate 2>/dev/null || true)}"
  if [[ -z "$ISAL_PREFIX" || -z "$DEFLATE_PREFIX" ]]; then
    echo "Homebrew isa-l/libdeflate not found; install with: brew install isa-l libdeflate" >&2
    exit 1
  fi
  if [[ -f "$ISAL_PREFIX/lib/libisal.a" && -f "$DEFLATE_PREFIX/lib/libdeflate.a" ]]; then
    LIBS="$ISAL_PREFIX/lib/libisal.a $DEFLATE_PREFIX/lib/libdeflate.a -lpthread"
  else
    LIBS="-L$ISAL_PREFIX/lib -L$DEFLATE_PREFIX/lib -lisal -ldeflate -lpthread"
  fi
  "$MAKE" -j"$JOBS" \
    CXX="$CXX" \
    CXXFLAGS="-std=c++11 -pthread -g -O2 -I./src" \
    LIBS="$LIBS" \
    fastp
  cp -a fastp "$PREFIX/"
else
  # Linux: libdeflate ships a static archive, but Debian/Ubuntu's libisal-dev
  # only provides a shared library.  Link ISA-L dynamically with an $ORIGIN
  # rpath; package.sh copies the matching libisal.so.2 next to fastp.
  DEFLATE_LIB=""
  if command -v pkg-config >/dev/null 2>&1; then
    DEFLATE_LIBDIR="$(pkg-config --variable=libdir libdeflate 2>/dev/null || true)"
    if [[ -n "$DEFLATE_LIBDIR" && -f "$DEFLATE_LIBDIR/libdeflate.a" ]]; then
      DEFLATE_LIB="$DEFLATE_LIBDIR/libdeflate.a"
    fi
  fi
  if [[ -z "$DEFLATE_LIB" ]]; then
    DEFLATE_LIB="-ldeflate"
  fi
  "$MAKE" -j"$JOBS" \
    CXX="$CXX" \
    CXXFLAGS="-std=c++11 -pthread -g -O2 -I./src" \
    LIBS="-lisal -lpthread" \
    LD_FLAGS="$DEFLATE_LIB -lisal -lpthread -Wl,-rpath,'\$\$ORIGIN'" \
    fastp
  cp -a fastp "$PREFIX/"
fi

log "fastp installed to $PREFIX"
