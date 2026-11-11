#!/usr/bin/env bash
#
# Build samtools/htslib 1.25 as native Windows binaries (static linking).
#
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/common.sh"

require_tool "$MAKE"

SRC="$BUILD_ROOT/samtools-src"
HTS="$SRC/htslib-1.25"
PREFIX="$STAGE/samtools"

log "Building htslib ($TARGET_ARCH) with $CC"
rm -rf "$SRC"
cp -a "$ROOT/vendor/samtools" "$SRC"
cd "$HTS"
./configure \
  --prefix="$PREFIX" \
  --disable-bz2 \
  --disable-lzma \
  --disable-libcurl \
  --disable-plugins \
  --without-libdeflate \
  --disable-gcs \
  --disable-s3 \
  CC="$CC" \
  AR="$AR" \
  RANLIB="$RANLIB" \
  LDFLAGS="-static -static-libgcc" \
  LIBS="-lgnurx -ltre -lintl -liconv -lpthread"

# htslib's configure records the POSIX regex/intl libraries in config.mk but
# does not propagate them into the static link list used by downstream
# projects.  htslib_static.mk is generated from htslib.pc.tmp, so patch the
# latter and force regeneration.
sed -i 's#^static_libs=.*#static_libs=-lpthread -lz -lm -lws2_32 -lgnurx -ltre -lintl -liconv#' \
  "$HTS/htslib.pc.tmp"
rm -f "$HTS/htslib_static.mk"

"$MAKE" -j"$JOBS" SHELL="$SHELL_WIN"
"$MAKE" install SHELL="$SHELL_WIN"

log "Building samtools ($TARGET_ARCH) with $CC"
cd "$SRC"
./configure \
  --prefix="$PREFIX" \
  --without-curses \
  --disable-configure-htslib \
  CC="$CC" \
  AR="$AR" \
  RANLIB="$RANLIB" \
  LDFLAGS="-static -static-libgcc"
"$MAKE" -j"$JOBS" SHELL="$SHELL_WIN"
"$MAKE" install SHELL="$SHELL_WIN"

log "samtools installed to $PREFIX"
