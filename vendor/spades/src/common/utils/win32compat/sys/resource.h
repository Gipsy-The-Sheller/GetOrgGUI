/*
 * Minimal getrlimit()/setrlimit()/getrusage() compatibility for native MinGW.
 *
 * Windows has no RLIMIT_AS equivalent that can be enforced from user space,
 * so setrlimit() only remembers the requested value. get_memory_limit() in
 * SPAdes will report total physical memory unless a limit was requested.
 */
#pragma once
#ifndef SPADES_WIN32COMPAT_SYS_RESOURCE_H
#define SPADES_WIN32COMPAT_SYS_RESOURCE_H

#include <sys/types.h>
#include <sys/time.h>
#include <io.h>

/* MinGW has no fsync(); _commit() is the equivalent. */
#ifndef fsync
#define fsync _commit
#endif

#ifdef __cplusplus
extern "C" {
#endif

typedef unsigned long long rlim_t;

struct rlimit {
    rlim_t rlim_cur;
    rlim_t rlim_max;
};

struct rusage {
    struct timeval ru_utime;
    struct timeval ru_stime;
    long ru_maxrss; /* peak working set in kilobytes */
};

#define RLIMIT_AS     9
#define RLIMIT_NOFILE 7
#define RUSAGE_SELF   0

int getrlimit(int resource, struct rlimit *rlim);
int setrlimit(int resource, const struct rlimit *rlim);
int getrusage(int who, struct rusage *usage);

#ifdef __cplusplus
}
#endif

#endif /* SPADES_WIN32COMPAT_SYS_RESOURCE_H */
