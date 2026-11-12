/*
 * Portable yield helper.
 *
 * Some MinGW-w64 toolchains (notably CLANGARM64) do not ship sched.h, and
 * winpthreads' pthread.h includes its own sched.h with quoted-include
 * semantics.  A wrapper avoids both the missing-header case and conflicts
 * with winpthreads' extern declaration.
 */
#pragma once
#ifndef SPADES_WIN32COMPAT_SCHED_COMPAT_HPP
#define SPADES_WIN32COMPAT_SCHED_COMPAT_HPP

#ifdef _WIN32

#include <windows.h>

namespace spades {
namespace win32 {

inline void sched_yield() {
    if (!SwitchToThread())
        Sleep(0);
}

}  // namespace win32
}  // namespace spades

#else

#include <sched.h>

namespace spades {
namespace win32 {

inline void sched_yield() {
    ::sched_yield();
}

}  // namespace win32
}  // namespace spades

#endif /* _WIN32 */

#endif /* SPADES_WIN32COMPAT_SCHED_COMPAT_HPP */
