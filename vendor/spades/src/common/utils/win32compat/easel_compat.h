/*
 * Force-included into bundled HMMER/easel sources on native Windows.
 * Easel assumes POSIX: it uses mmap() and the uid/gid accessors without
 * pulling in the corresponding headers on non-POSIX platforms.
 */
#pragma once
#ifndef SPADES_WIN32COMPAT_EASEL_COMPAT_H
#define SPADES_WIN32COMPAT_EASEL_COMPAT_H

#ifdef _WIN32

#include <sys/types.h>
#include <sys/mman.h>

static inline int getuid(void)  { return 0; }
static inline int geteuid(void) { return 0; }
static inline int getgid(void)  { return 0; }
static inline int getegid(void) { return 0; }
static inline int getppid(void) { return 1; }

#endif /* _WIN32 */

#endif /* SPADES_WIN32COMPAT_EASEL_COMPAT_H */
