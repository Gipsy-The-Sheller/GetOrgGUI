#!/usr/bin/env bash
#
# Shared configuration for the Windows native build.
# Source this file from every build script (it is idempotent).
#
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export ROOT

: "${JOBS:=$(nproc 2>/dev/null || echo 4)}"
export JOBS

# Target architecture: x86_64 (default) or arm64.
: "${TARGET_ARCH:=x86_64}"
case "$TARGET_ARCH" in
  x86_64|amd64|x64) TARGET_ARCH=x86_64;  ARCH_LABEL=x64 ;;
  arm64|aarch64)    TARGET_ARCH=aarch64; ARCH_LABEL=arm64 ;;
  *)
    echo "Unsupported TARGET_ARCH: $TARGET_ARCH (use x86_64 or arm64)" >&2
    exit 2
    ;;
esac
export TARGET_ARCH ARCH_LABEL

: "${PKG_VERSION:=1.8.0.1-dev}"
export PKG_VERSION

# Toolchain selection.  MSYS2 exposes the environment through MSYSTEM:
#   MINGW64    -> GCC, produces native x86_64 binaries
#   CLANGARM64 -> Clang/LLVM, produces native arm64 binaries
if [[ "${MSYSTEM:-}" == "CLANGARM64" ]]; then
  CC=${CC:-clang}
  CXX=${CXX:-clang++}
  AR=${AR:-llvm-ar}
  RANLIB=${RANLIB:-llvm-ranlib}
  STRIP=${STRIP:-llvm-strip}
  RC=${RC:-llvm-windres}
  : "${POPCNT_CAPABILITY:=0}"
else
  CC=${CC:-gcc}
  CXX=${CXX:-g++}
  AR=${AR:-ar}
  RANLIB=${RANLIB:-ranlib}
  STRIP=${STRIP:-strip}
  RC=${RC:-windres}
  : "${POPCNT_CAPABILITY:=1}"
fi

# Resolve to absolute paths so that sub-shells / CMake always use the
# intended toolchain even when PATH changes.
resolve_tool() {
  local name="$1" found=""
  if [[ "$name" == */* ]]; then
    found="$name"
  else
    found="$(command -v "$name" 2>/dev/null || true)"
  fi
  if [[ -z "$found" || ! -x "$found" ]]; then
    echo "Required tool not found: $name" >&2
    echo "Hint: run inside the MSYS2 MINGW64 (or CLANGARM64) shell." >&2
    return 1
  fi
  # Native Windows tools need the .exe suffix and a Windows path when they
  # are handed to CMake/configure; cygpath -m produces e.g. D:/msys64/... .
  if [[ "$found" != *.exe && -x "${found}.exe" ]]; then
    found="${found}.exe"
  fi
  if command -v cygpath >/dev/null 2>&1; then
    found="$(cygpath -m "$found")"
  fi
  printf '%s\n' "$found"
}
CC="$(resolve_tool "$CC")"
CXX="$(resolve_tool "$CXX")"
AR="$(resolve_tool "$AR")"
RANLIB="$(resolve_tool "$RANLIB")"
STRIP="$(resolve_tool "$STRIP")"
RC="$(resolve_tool "$RC")"
export CC CXX AR RANLIB STRIP RC POPCNT_CAPABILITY

# Use mingw32-make when available (MSYS make can lose TMPDIR through the
# native/msys boundary), and give native make a Windows path to bash so
# that $(shell uname), backticks, etc. work.
if [[ -z "${MAKE:-}" ]]; then
  if command -v mingw32-make >/dev/null 2>&1; then
    MAKE=mingw32-make
  else
    MAKE=make
  fi
fi
SHELL_WIN="$(cygpath -w "$(command -v bash)" 2>/dev/null || command -v bash)"
export MAKE SHELL_WIN

STAGE="$ROOT/stage/$ARCH_LABEL"
BUILD_ROOT="$ROOT/build/ci-$ARCH_LABEL"
export STAGE BUILD_ROOT
mkdir -p "$STAGE" "$BUILD_ROOT"

log() {
  printf '\n==> %s\n' "$*"
}

require_tool() {
  local tool
  for tool in "$@"; do
    if ! command -v "$tool" >/dev/null 2>&1; then
      echo "Required tool not found in PATH: $tool" >&2
      echo "Hint: run inside the MSYS2 MINGW64 (or CLANGARM64) shell." >&2
      exit 1
    fi
  done
}
