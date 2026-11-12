/*
 * Minimal <sched.h> replacement for MinGW-w64 toolchains (notably
 * CLANGARM64) whose winpthreads headers do not provide sched_yield().
 */
#pragma once
#ifndef SPADES_WIN32COMPAT_SCHED_H
#define SPADES_WIN32COMPAT_SCHED_H

#ifdef _WIN32

#include <windows.h>

static __inline int sched_yield(void) {
    if (!SwitchToThread())
        Sleep(0);
    return 0;
}

#endif /* _WIN32 */

#endif /* SPADES_WIN32COMPAT_SCHED_H */
