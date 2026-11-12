#!/usr/bin/env bash
#
# Shared configuration for the native builds.
#
# Supported hosts:
#   Windows (MSYS2 MINGW64 / CLANGARM64)
#   Linux   (GCC)
#   macOS   (Apple Clang, arm64 or x86_64)
#
# Source this file from every build script (it is idempotent).
#
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export ROOT

case "$(uname -s)" in
  MINGW*|MSYS*|CYGWIN*) HOST_OS=windows ;;
  Linux*)               HOST_OS=linux ;;
  Darwin*)              HOST_OS=macos ;;
  *)
    echo "Unsupported host OS: $(uname -s)" >&2
    exit 2
    ;;
esac
export HOST_OS

if [[ -z "${TARGET_ARCH:-}" ]]; then
  case "$HOST_OS" in
    windows) TARGET_ARCH=x86_64 ;;
    *)
      case "$(uname -m)" in
        x86_64|amd64)  TARGET_ARCH=x86_64 ;;
        arm64|aarch64) TARGET_ARCH=arm64 ;;
        *)
          echo "Unsupported host architecture: $(uname -m)" >&2
          exit 2
          ;;
      esac
      ;;
  esac
fi

case "$TARGET_ARCH" in
  x86_64|amd64|x64) TARGET_ARCH=x86_64;  ARCH_LABEL=x64 ;;
  arm64|aarch64)    TARGET_ARCH=aarch64; ARCH_LABEL=arm64 ;;
  *)
    echo "Unsupported TARGET_ARCH: $TARGET_ARCH (use x86_64 or arm64)" >&2
    exit 2
    ;;
esac
export TARGET_ARCH ARCH_LABEL

# Names used by GetOrganelle for GetOrganelleDep/<name>.
case "$HOST_OS" in
  windows) PLATFORM_LABEL=Windows; DEP_PLATFORM=Windows ;;
  linux)   PLATFORM_LABEL=Linux;   DEP_PLATFORM=linux ;;
  macos)   PLATFORM_LABEL=macOS;   DEP_PLATFORM=macOS ;;
esac
export PLATFORM_LABEL DEP_PLATFORM

: "${PKG_VERSION:=1.8.0.1-dev}"
export PKG_VERSION

if [[ -z "${JOBS:-}" ]]; then
  JOBS="$(getconf _NPROCESSORS_ONLN 2>/dev/null || nproc 2>/dev/null || sysctl -n hw.ncpu 2>/dev/null || echo 4)"
fi
export JOBS

if [[ "$HOST_OS" == macos ]]; then
  : "${BREW_PREFIX:=$(brew --prefix 2>/dev/null || echo /usr/local)}"
  export BREW_PREFIX
fi

# Toolchain selection.  MSYS2 exposes the environment through MSYSTEM:
#   MINGW64    -> GCC, produces native x86_64 binaries
#   CLANGARM64 -> Clang/LLVM, produces native arm64 binaries
if [[ "$HOST_OS" == windows ]]; then
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
else
  if [[ "$HOST_OS" == macos ]]; then
    CC=${CC:-clang}
    CXX=${CXX:-clang++}
  else
    CC=${CC:-gcc}
    CXX=${CXX:-g++}
  fi
  AR=${AR:-ar}
  RANLIB=${RANLIB:-ranlib}
  STRIP=${STRIP:-strip}
  RC=""
  : "${POPCNT_CAPABILITY:=$([[ "$TARGET_ARCH" == x86_64 ]] && echo 1 || echo 0)}"
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
    if [[ "$HOST_OS" == windows ]]; then
      echo "Hint: run inside the MSYS2 MINGW64 (or CLANGARM64) shell." >&2
    fi
    return 1
  fi
  if [[ "$HOST_OS" == windows ]]; then
    # Native Windows tools need the .exe suffix and a Windows path when
    # they are handed to CMake/configure; cygpath -m produces D:/msys64/... .
    if [[ "$found" != *.exe && -x "${found}.exe" ]]; then
      found="${found}.exe"
    fi
    if command -v cygpath >/dev/null 2>&1; then
      found="$(cygpath -m "$found")"
    fi
  fi
  printf '%s\n' "$found"
}
CC="$(resolve_tool "$CC")"
CXX="$(resolve_tool "$CXX")"
AR="$(resolve_tool "$AR")"
RANLIB="$(resolve_tool "$RANLIB")"
STRIP="$(resolve_tool "$STRIP")"
if [[ -n "$RC" ]]; then
  if ! RC="$(resolve_tool "$RC" 2>/dev/null)"; then
    # windres is only needed for optional Windows resource files.
    RC=""
  fi
fi
export CC CXX AR RANLIB STRIP RC POPCNT_CAPABILITY

# Use mingw32-make when available (MSYS make can lose TMPDIR through the
# native/msys boundary), and give native make a Windows path to bash so
# that $(shell uname), backticks, etc. work.
if [[ "$HOST_OS" == windows ]]; then
  if [[ -z "${MAKE:-}" ]]; then
    if command -v mingw32-make >/dev/null 2>&1; then
      MAKE=mingw32-make
    else
      MAKE=make
    fi
  fi
  SHELL_WIN="$(cygpath -w "$(command -v bash)" 2>/dev/null || command -v bash)"
  export SHELL_WIN
else
  MAKE=${MAKE:-make}
fi
export MAKE

if [[ "$HOST_OS" == windows ]]; then
  STAGE="$ROOT/stage/$ARCH_LABEL"
  BUILD_ROOT="$ROOT/build/ci-$ARCH_LABEL"
else
  STAGE="$ROOT/stage/$HOST_OS-$ARCH_LABEL"
  BUILD_ROOT="$ROOT/build/ci-$HOST_OS-$ARCH_LABEL"
fi
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
      if [[ "$HOST_OS" == windows ]]; then
        echo "Hint: run inside the MSYS2 MINGW64 (or CLANGARM64) shell." >&2
      else
        echo "Hint: install the build prerequisites for $PLATFORM_LABEL." >&2
      fi
      exit 1
    fi
  done
}

sha256_file() {
  if command -v sha256sum >/dev/null 2>&1; then
    sha256sum "$1" | awk '{print $1}'
  else
    shasum -a 256 "$1" | awk '{print $1}'
  fi
}
