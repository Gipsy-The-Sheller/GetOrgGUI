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
cp -a "$STAGE/fastp" "$DEPS/fastp"
cp -a "$STAGE/ncbi-blast" "$DEPS/ncbi-blast"
cp -a "$STAGE/samtools/bin/samtools.exe" "$DEPS/samtools/bin/"
if [[ -f "$ROOT/vendor/samtools/COPYING" ]]; then
  cp -a "$ROOT/vendor/samtools/COPYING" "$DEPS/samtools/"
fi

# Launchers, GUI and setup files
cp -a "$ROOT/run_get_organelle_reads.bat" \
      "$ROOT/run_get_organelle_assembly.bat" \
      "$ROOT/run_get_organelle_config.bat" \
      "$ROOT/GetOrganelleGUI.bat" \
      "$ROOT/packaging/setup_venv.bat" \
      "$ROOT/packaging/requirements.txt" \
      "$ROOT/packaging/README-Windows.md" \
      "$DEST/"
cp -a "$ROOT/LICENSE" "$ROOT/NOTICE.md" "$ROOT/THIRD_PARTY_NOTICES.md" \
      "$ROOT/README.md" "$DEST/"
cp -a "$ROOT/gui" "$DEST/gui"

# MIT notices for the bundled fastp and samtools binaries.
cp -a "$ROOT/vendor/fastp/LICENSE" "$DEPS/fastp/LICENSE"
cp -a "$ROOT/vendor/samtools/LICENSE" "$DEPS/samtools/LICENSE"
if [[ -f "$ROOT/vendor/samtools/htslib-1.25/LICENSE" ]]; then
  cp -a "$ROOT/vendor/samtools/htslib-1.25/LICENSE" "$DEPS/samtools/htslib-LICENSE"
fi

# Corresponding-source manifest (GPL/AGPL compliance for this release).
GIT_COMMIT="$(git -C "$ROOT" rev-parse HEAD 2>/dev/null || echo unknown)"
cat > "$DEST/SOURCE_MANIFEST.md" <<EOF
# Source manifest

This package was built from GetOrgGUI commit \`${GIT_COMMIT}\`.

- Repository: https://github.com/Gipsy-The-Sheller/GetOrgGUI
- Source archive: https://github.com/Gipsy-The-Sheller/GetOrgGUI/archive/${GIT_COMMIT}.zip

## Components

| Component | Version | Source |
| --- | --- | --- |
| GetOrganelle Workbench (original code) | 0.2.0 | this repository (AGPL-3.0-only) |
| GetOrganelle | 1.8.0.1 | included under \`GetOrganelle/\`; upstream https://github.com/Kinggerm/GetOrganelle |
| SPAdes | 4.3.0 | \`vendor/spades\`; upstream https://github.com/ablab/spades/tree/v4.3.0 |
| Bowtie2 | 2.5.5 | \`vendor/bowtie2\`; upstream https://github.com/BenLangmead/bowtie2 |
| fastp | 1.0.1 | \`vendor/fastp\`; upstream https://github.com/OpenGene/fastp |
| samtools / htslib | 1.25 | \`vendor/samtools\`; upstream https://github.com/samtools/samtools |
| NCBI BLAST+ | 2.17.0 | official x64-win64 binary; https://ftp.ncbi.nlm.nih.gov/blast/executables/blast+/2.17.0/ |
| PyQt5 | 5.15.11 | installed by setup_venv.bat; GPLv3 or commercial |

The vendored trees include the exact upstream snapshots and Windows patches
used for this build. The source archive for this commit contains the build
scripts and CI workflow.
EOF

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
