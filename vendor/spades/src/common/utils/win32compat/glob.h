/*
 * Minimal glob()/globfree() compatibility for native MinGW-w64 builds.
 * Supports wildcards in the last path component, which is what SPAdes uses.
 */
#pragma once
#ifndef SPADES_WIN32COMPAT_GLOB_H
#define SPADES_WIN32COMPAT_GLOB_H

#include <stddef.h>

#ifdef __cplusplus
extern "C" {
#endif

typedef struct {
    size_t gl_pathc;
    char **gl_pathv;
    size_t gl_offs;
} glob_t;

#define GLOB_ERR      0x0001
#define GLOB_MARK     0x0002
#define GLOB_NOSORT   0x0004
#define GLOB_NOESCAPE 0x0008

#define GLOB_NOSPACE 1
#define GLOB_ABORTED 2
#define GLOB_NOMATCH 3

int glob(const char *pattern, int flags,
         int (*errfunc)(const char *epath, int eerrno), glob_t *pglob);
void globfree(glob_t *pglob);

#ifdef __cplusplus
}
#endif

#endif /* SPADES_WIN32COMPAT_GLOB_H */
