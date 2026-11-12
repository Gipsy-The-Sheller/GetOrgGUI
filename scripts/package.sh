#!/usr/bin/env bash
#
# Assemble the portable GetOrganelle package and archive it.
#
# Windows packages are zip files; Linux/macOS packages are tar.gz files.
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

PKG_NAME="GetOrganelle-${PLATFORM_LABEL}-${ARCH_LABEL}-${PKG_VERSION}"
DEST="$BUILD_ROOT/$PKG_NAME"
DEPS="$DEST/GetOrganelle/GetOrganelleDep/$DEP_PLATFORM"

log "Packaging $PKG_NAME"
rm -rf "$DEST"
mkdir -p "$DEPS"

# GetOrganelle source (patched for Windows), without local runtime deps.
tar -C "$ROOT/GetOrganelle" \
  --exclude=GetOrganelleDep \
  --exclude=__pycache__ \
  --exclude='*.pyc' \
  -cf - . | tar -C "$DEST/GetOrganelle" -xf -

# Dependencies
mkdir -p "$DEPS/SPAdes" "$DEPS/samtools/bin"
cp -a "$STAGE/spades/bin" "$STAGE/spades/share" "$DEPS/SPAdes/"

if [[ "$HOST_OS" == windows ]]; then
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
fi

cp -a "$STAGE/bowtie2" "$DEPS/bowtie2"
if [[ -f "$ROOT/vendor/bowtie2/third_party/simde/COPYING" ]]; then
  cp -a "$ROOT/vendor/bowtie2/third_party/simde/COPYING" \
    "$DEPS/bowtie2/SIMDE-LICENSE"
fi
cp -a "$STAGE/fastp" "$DEPS/fastp"
if [[ "$HOST_OS" == linux ]]; then
  # fastp links ISA-L dynamically; ship the matching soname with an
  # $ORIGIN rpath so it does not need a system libisal package.
  ISAL_DIR=""
  if command -v pkg-config >/dev/null 2>&1; then
    ISAL_DIR="$(pkg-config --variable=libdir libisal 2>/dev/null || true)"
  fi
  if [[ -z "$ISAL_DIR" && -d /usr/lib/x86_64-linux-gnu ]]; then
    ISAL_DIR=/usr/lib/x86_64-linux-gnu
  fi
  if [[ -n "$ISAL_DIR" && -f "$ISAL_DIR/libisal.so.2" ]]; then
    # -L: libisal.so.2 is normally a symlink to libisal.so.2.0.31; the
    # package needs the real file, not a dangling symlink.
    cp -Lf "$ISAL_DIR/libisal.so.2" "$DEPS/fastp/libisal.so.2"
  fi
  if [[ -f /usr/share/doc/libisal-dev/copyright ]]; then
    cp -a /usr/share/doc/libisal-dev/copyright "$DEPS/fastp/ISA-L-LICENSE"
  fi
fi
cp -a "$STAGE/ncbi-blast" "$DEPS/ncbi-blast"
if [[ "$HOST_OS" == windows ]]; then
  cp -a "$STAGE/samtools/bin/samtools.exe" "$DEPS/samtools/bin/"
else
  cp -a "$STAGE/samtools/bin/samtools" "$DEPS/samtools/bin/"
fi
if [[ -f "$ROOT/vendor/samtools/COPYING" ]]; then
  cp -a "$ROOT/vendor/samtools/COPYING" "$DEPS/samtools/"
fi

# Launchers, GUI and setup files
if [[ "$HOST_OS" == windows ]]; then
  cp -a "$ROOT/run_get_organelle_reads.bat" \
        "$ROOT/run_get_organelle_assembly.bat" \
        "$ROOT/run_get_organelle_config.bat" \
        "$ROOT/GetOrganelleGUI.bat" \
        "$ROOT/packaging/setup_venv.bat" \
        "$ROOT/packaging/requirements.txt" \
        "$ROOT/packaging/README-Windows.md" \
        "$DEST/"
else
  cp -a "$ROOT/run_get_organelle_reads.sh" \
        "$ROOT/run_get_organelle_assembly.sh" \
        "$ROOT/run_get_organelle_config.sh" \
        "$ROOT/GetOrganelleGUI.sh" \
        "$ROOT/packaging/setup_venv.sh" \
        "$ROOT/packaging/requirements.txt" \
        "$ROOT/packaging/README-${PLATFORM_LABEL}.md" \
        "$DEST/"
  chmod +x "$DEST"/*.sh
fi
cp -a "$ROOT/LICENSE" "$ROOT/NOTICE.md" "$ROOT/THIRD_PARTY_NOTICES.md" \
      "$ROOT/README.md" "$DEST/"
mkdir -p "$DEST/gui"
tar -C "$ROOT/gui" \
  --exclude=__pycache__ \
  --exclude='*.pyc' \
  -cf - . | tar -C "$DEST/gui" -xf -

# MIT notices for the bundled fastp and samtools binaries.
cp -a "$ROOT/vendor/fastp/LICENSE" "$DEPS/fastp/LICENSE"
cp -a "$ROOT/vendor/samtools/LICENSE" "$DEPS/samtools/LICENSE"
if [[ -f "$ROOT/vendor/samtools/htslib-1.25/LICENSE" ]]; then
  cp -a "$ROOT/vendor/samtools/htslib-1.25/LICENSE" "$DEPS/samtools/htslib-LICENSE"
fi

# macOS: replace Homebrew absolute dylib paths with paths next to the
# executables, so the package does not depend on the builder's Homebrew tree.
if [[ "$HOST_OS" == macos ]]; then
  relocate_macos_dylibs() {
    find "$DEPS" -type f -print0 | while IFS= read -r -d '' f; do
      if ! file -b "$f" | grep -q 'Mach-O'; then
        continue
      fi
      while IFS= read -r dep; do
        case "$dep" in
          /opt/homebrew/*|/usr/local/*)
            base="$(basename "$dep")"
            if [[ ! -f "$(dirname "$f")/$base" ]]; then
              cp -f "$dep" "$(dirname "$f")/$base"
            fi
            install_name_tool -change "$dep" "@loader_path/$base" "$f"
            ;;
        esac
      done < <(otool -L "$f" | tail -n +2 | awk '{print $1}')
    done
  }
  relocate_macos_dylibs

  # Re-run over newly copied dylibs, then restore ad-hoc signatures.
  relocate_macos_dylibs
  find "$DEPS" -type f -print0 | while IFS= read -r -d '' f; do
    if file -b "$f" | grep -q 'Mach-O'; then
      codesign --force --sign - "$f" >/dev/null
    fi
  done
fi

# Corresponding-source manifest (GPL/AGPL compliance for this release).
GIT_COMMIT="$(git -C "$ROOT" rev-parse HEAD 2>/dev/null || echo unknown)"
case "$HOST_OS" in
  windows) BLAST_DESC="x64-win64 (x64 emulation on Windows arm64)" ;;
  linux)   BLAST_DESC="x64-linux" ;;
  macos)   BLAST_DESC="aarch64-macosx" ;;
esac
cat > "$DEST/SOURCE_MANIFEST.md" <<EOF
# Source manifest

This package was built from GetOrgGUI commit \`${GIT_COMMIT}\` for
**${PLATFORM_LABEL} ${ARCH_LABEL}**.

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
| NCBI BLAST+ | 2.17.0 | official ${BLAST_DESC} binary; https://ftp.ncbi.nlm.nih.gov/blast/executables/blast+/2.17.0/ |
| PyQt5 | 5.15.11 | installed by setup_venv; GPLv3 or commercial |

The vendored trees include the exact upstream snapshots and platform patches
used for this build. The source archive for this commit contains the build
scripts and CI workflow.
EOF

# Shrink binaries (keep debug info out of the distribution).
if [[ "$HOST_OS" == windows ]]; then
  log "Stripping binaries with $STRIP"
  find "$DEST" \( -name '*.exe' -o -name '*.dll' \) -print0 \
    | xargs -0 -r "$STRIP" --strip-unneeded
elif [[ "$HOST_OS" == linux ]]; then
  log "Stripping binaries with $STRIP"
  find "$DEST" -type f -print0 | while IFS= read -r -d '' f; do
    if file -b "$f" | grep -q 'ELF'; then
      "$STRIP" --strip-unneeded "$f" 2>/dev/null || true
    fi
  done
fi

cd "$BUILD_ROOT"
rm -f "$PKG_NAME.zip" "$PKG_NAME.zip.sha256" \
      "$PKG_NAME.tar.gz" "$PKG_NAME.tar.gz.sha256"
if [[ "$HOST_OS" == windows ]]; then
  zip -qr "$PKG_NAME.zip" "$PKG_NAME"
  ARCHIVE="$PKG_NAME.zip"
else
  tar -czf "$PKG_NAME.tar.gz" "$PKG_NAME"
  ARCHIVE="$PKG_NAME.tar.gz"
fi
HASH="$(sha256_file "$ARCHIVE")"
printf '%s  %s\n' "$HASH" "$ARCHIVE" > "$ARCHIVE.sha256"

log "Created $BUILD_ROOT/$ARCHIVE"
du -h "$BUILD_ROOT/$ARCHIVE"
