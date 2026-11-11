#pragma once
#ifndef BWA_WIN_COMPAT_H
#define BWA_WIN_COMPAT_H

#ifdef _WIN32

#include <sys/types.h>

#ifdef __cplusplus
extern "C" {
#endif

/* MinGW's string.h has no BSD index() alias. */
#include <string.h>
#ifndef index
#define index strchr
#endif

/* MinGW's CRT has no *rand48() family. */
void srand48(long seed);
double drand48(void);

/* POSIX process helpers used by BWA's pipe opener. */
pid_t waitpid(pid_t pid, int *status, int options);
int kill(pid_t pid, int sig);

#ifdef __cplusplus
}
#endif

#endif /* _WIN32 */

#endif /* BWA_WIN_COMPAT_H */
