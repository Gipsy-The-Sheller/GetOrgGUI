/*
 * Minimal POSIX mmap() compatibility layer for native MinGW-w64 builds.
 * Implemented on top of the Win32 file-mapping API in win32compat.cpp.
 */
#pragma once
#ifndef SPADES_WIN32COMPAT_SYS_MMAN_H
#define SPADES_WIN32COMPAT_SYS_MMAN_H

#include <stddef.h>
#include <sys/types.h>

#ifdef __cplusplus
extern "C" {
#endif

#define PROT_NONE  0x0
#define PROT_READ  0x1
#define PROT_WRITE 0x2

#define MAP_SHARED  0x01
#define MAP_PRIVATE 0x02
#define MAP_FILE    0x00
#define MAP_FAILED  ((void *)-1)

void *mmap(void *addr, size_t length, int prot, int flags, int fd, off_t offset);
int munmap(void *addr, size_t length);
int msync(void *addr, size_t length, int flags);
int madvise(void *addr, size_t length, int advice);
int getpagesize(void);

#ifdef __cplusplus
}
#endif

#endif /* SPADES_WIN32COMPAT_SYS_MMAN_H */
