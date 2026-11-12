#!/usr/bin/env bash
#
# Build samtools/htslib 1.25.
#
# Windows uses static htslib and samtools binaries.  Linux/macOS use the
# normal POSIX build, with the same optional features disabled so that the
# build does not depend on network/client libraries.
#
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/common.sh"

require_tool "$MAKE"

SRC="$BUILD_ROOT/samtools-src"
HTS="$SRC/htslib-1.25"
PREFIX="$STAGE/samtools"

log "Building htslib ($PLATFORM_LABEL $TARGET_ARCH) with $CC"
rm -rf "$SRC" "$PREFIX"
cp -a "$ROOT/vendor/samtools" "$SRC"
# The vendored snapshot lost executable bits on its helper scripts.
chmod +x "$HTS/configure" "$HTS/version.sh" "$SRC/configure" "$SRC/version.sh"
cd "$HTS"

CONFIGURE_ARGS=(
  --prefix="$PREFIX"
  --disable-bz2
  --disable-lzma
  --disable-libcurl
  --disable-plugins
  --without-libdeflate
  --disable-gcs
  --disable-s3
  CC="$CC"
  AR="$AR"
  RANLIB="$RANLIB"
)

if [[ "$HOST_OS" == windows ]]; then
  CONFIGURE_ARGS+=(
    LDFLAGS="-static -static-libgcc"
    LIBS="-lgnurx -ltre -lintl -liconv -lpthread"
  )
fi

./configure "${CONFIGURE_ARGS[@]}"

if [[ "$HOST_OS" == windows ]]; then
  # htslib's configure records the POSIX regex/intl libraries in config.mk but
  # does not propagate them into the static link list used by downstream
  # projects.  htslib_static.mk is generated from htslib.pc.tmp, so patch the
  # latter and force regeneration.
  sed -i 's#^static_libs=.*#static_libs=-lpthread -lz -lm -lws2_32 -lgnurx -ltre -lintl -liconv#' \
    "$HTS/htslib.pc.tmp"
  rm -f "$HTS/htslib_static.mk"
fi

# Only the static library and samtools are shipped.  Building htslib's
# Windows shared DLL also builds an import library with gendef, which is no
# longer available from the current MSYS2 repositories.
if [[ "$HOST_OS" == windows ]]; then
  "$MAKE" -j"$JOBS" lib-static SHELL="$SHELL_WIN"
else
  "$MAKE" -j"$JOBS" lib-static
fi

log "Building samtools ($PLATFORM_LABEL $TARGET_ARCH) with $CC"
cd "$SRC"

SAMTOOLS_ARGS=(
  --prefix="$PREFIX"
  --without-curses
  --disable-configure-htslib
  CC="$CC"
  AR="$AR"
  RANLIB="$RANLIB"
)
if [[ "$HOST_OS" == windows ]]; then
  SAMTOOLS_ARGS+=(LDFLAGS="-static -static-libgcc")
fi
./configure "${SAMTOOLS_ARGS[@]}"

if [[ "$HOST_OS" == windows ]]; then
  "$MAKE" -j"$JOBS" SHELL="$SHELL_WIN"
  "$MAKE" install SHELL="$SHELL_WIN"
else
  "$MAKE" -j"$JOBS"
  "$MAKE" install
fi

log "samtools installed to $PREFIX"
