#!/usr/bin/env bash
#
# Assemble the portable GetOrganelle Windows package and zip it.
#
set -euo pipefail

# Usage: package.sh [arch] [version]   (both optional)
if [[ $# -ge 1 && -n "${1:-}" ]]; then
  export TARGET_ARCH="$1"
fi
if [[ $# -ge 2 && -n "${2:-}" ]]; then
  export PKG_VERSION="$2"
fi

source "$(dirname "${BASH_SOURCE[0]}")/common.sh"

PKG_NAME="GetOrganelle-Windows-${ARCH_LABEL}-${PKG_VERSION}"
DEST="$BUILD_ROOT/$PKG_NAME"
DEPS="$DEST/GetOrganelle/GetOrganelleDep/Windows"

log "Packaging $PKG_NAME"
rm -rf "$DEST"
mkdir -p "$DEPS"

# GetOrganelle source (patched for Windows), without local runtime deps.
tar -C "$ROOT/GetOrganelle" \
  --exclude=./GetOrganelleDep \
  --exclude=__pycache__ \
  --exclude='*.pyc' \
  -cf - . | tar -C "$DEST/GetOrganelle" -xf -

# Dependencies
mkdir -p "$DEPS/SPAdes" "$DEPS/samtools/bin"
cp -a "$STAGE/spades/bin" "$STAGE/spades/share" "$DEPS/SPAdes/"

# SPAdes links the compiler runtime dynamically (unlike Bowtie2/samtools,
# which are static).  Ship the matching DLLs next to the executables.
TOOLCHAIN_BIN="$(dirname "$CXX")"
if [[ "${MSYSTEM:-}" == "CLANGARM64" ]]; then
  RUNTIME_DLLS=(libc++.dll libc++abi.dll libunwind.dll libomp.dll libwinpthread-1.dll)
else
  RUNTIME_DLLS=(libgcc_s_seh-1.dll libstdc++-6.dll libgomp-1.dll libwinpthread-1.dll)
fi
for dll in "${RUNTIME_DLLS[@]}"; do
  if [[ -f "$TOOLCHAIN_BIN/$dll" ]]; then
    cp -a "$TOOLCHAIN_BIN/$dll" "$DEPS/SPAdes/bin/"
  else
    echo "Warning: runtime DLL not found: $TOOLCHAIN_BIN/$dll" >&2
  fi
done
cp -a "$STAGE/bowtie2" "$DEPS/bowtie2"
cp -a "$STAGE/ncbi-blast" "$DEPS/ncbi-blast"
cp -a "$STAGE/samtools/bin/samtools.exe" "$DEPS/samtools/bin/"
if [[ -f "$ROOT/vendor/samtools/COPYING" ]]; then
  cp -a "$ROOT/vendor/samtools/COPYING" "$DEPS/samtools/"
fi

# Launchers and setup files
cp -a "$ROOT/run_get_organelle_reads.bat" \
      "$ROOT/run_get_organelle_assembly.bat" \
      "$ROOT/run_get_organelle_config.bat" \
      "$ROOT/packaging/setup_venv.bat" \
      "$ROOT/packaging/requirements.txt" \
      "$ROOT/packaging/README-Windows.md" \
      "$DEST/"

# Shrink binaries (keep debug info out of the distribution).
log "Stripping binaries with $STRIP"
find "$DEST" \( -name '*.exe' -o -name '*.dll' \) -print0 \
  | xargs -0 -r "$STRIP" --strip-unneeded

cd "$BUILD_ROOT"
rm -f "$PKG_NAME.zip" "$PKG_NAME.zip.sha256"
zip -qr "$PKG_NAME.zip" "$PKG_NAME"
sha256sum "$PKG_NAME.zip" > "$PKG_NAME.zip.sha256"

log "Created $BUILD_ROOT/$PKG_NAME.zip"
du -h "$BUILD_ROOT/$PKG_NAME.zip"
