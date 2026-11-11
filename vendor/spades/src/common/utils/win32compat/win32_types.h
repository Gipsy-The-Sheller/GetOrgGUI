/*
 * Force-included for all SPAdes targets on native Windows.
 * Linux's <sys/types.h> provides the BSD-style `uint` typedef; MinGW does not.
 */
#pragma once
#ifndef SPADES_WIN32COMPAT_WIN32_TYPES_H
#define SPADES_WIN32COMPAT_WIN32_TYPES_H

#include <sys/types.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>

#ifndef SPADES_WIN32_UINT_DEFINED
typedef unsigned int uint;
#define SPADES_WIN32_UINT_DEFINED
#endif

/* POSIX functions missing from MinGW's CRT, used by bundled HMMER/easel. */
#ifndef SPADES_WIN32_SYNC_DEFINED
#define SPADES_WIN32_SYNC_DEFINED
static inline void sync(void) {
    /* No portable Windows equivalent; data is flushed by the OS. */
}
static inline void srandom(unsigned int seed) {
    srand(seed);
}
#endif

#ifndef SPADES_WIN32_CTIME_R_DEFINED
#define SPADES_WIN32_CTIME_R_DEFINED
static inline char *ctime_r(const time_t *timep, char *buffer) {
    struct tm *tm_info = localtime(timep);
    if (!tm_info)
        return NULL;
    char *result = asctime(tm_info);
    if (!result)
        return NULL;
    memcpy(buffer, result, 26); /* asctime always writes 26 bytes */
    return buffer;
}

static inline struct tm *localtime_r(const time_t *timep, struct tm *result) {
    struct tm *tm_info = localtime(timep);
    if (!tm_info)
        return NULL;
    *result = *tm_info;
    return result;
}

static inline char *strsep(char **stringp, const char *delim) {
    char *start = *stringp;
    if (!start)
        return NULL;
    char *end = strpbrk(start, delim);
    if (end) {
        *end = '\0';
        *stringp = end + 1;
    } else {
        *stringp = NULL;
    }
    return start;
}

static inline ssize_t getline(char **lineptr, size_t *n, FILE *stream) {
    if (!lineptr || !n || !stream)
        return -1;
    if (!*lineptr || *n == 0) {
        *n = 128;
        *lineptr = (char *)malloc(*n);
        if (!*lineptr)
            return -1;
    }
    size_t len = 0;
    int c = EOF;
    while ((c = fgetc(stream)) != EOF) {
        if (len + 1 >= *n) {
            size_t new_n = *n * 2;
            char *new_ptr = (char *)realloc(*lineptr, new_n);
            if (!new_ptr)
                return -1;
            *lineptr = new_ptr;
            *n = new_n;
        }
        (*lineptr)[len++] = (char)c;
        if (c == '\n')
            break;
    }
    if (len == 0 && c == EOF)
        return -1;
    (*lineptr)[len] = '\0';
    return (ssize_t)len;
}
#endif

#endif /* SPADES_WIN32COMPAT_WIN32_TYPES_H */
