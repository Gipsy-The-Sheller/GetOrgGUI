#ifdef _WIN32

#include "win_compat.h"

/*
 * Small replacements for the POSIX *rand48() family, which MinGW lacks.
 * Deterministic LCG; the exact sequence does not matter to BWA, which only
 * needs reproducible pseudo-random choices.
 */

static unsigned long long bwa_rand48_state = 0x1234abcd330eULL;

void srand48(long seed) {
    bwa_rand48_state = (unsigned long long)(unsigned long)seed * 0x5DEECE66DULL + 0xB;
}

double drand48(void) {
    bwa_rand48_state = (bwa_rand48_state * 0x5DEECE66DULL + 0xB) & 0xFFFFFFFFFFFFULL;
    return (double)bwa_rand48_state / 281474976710656.0; /* 2^48 */
}

/* BWA only uses this to reap a popen() child; Windows has no equivalent. */
pid_t waitpid(pid_t pid, int *status, int options) {
    (void)pid;
    (void)options;
    if (status)
        *status = 0;
    return -1;
}

int kill(pid_t pid, int sig) {
    (void)pid;
    (void)sig;
    return -1;
}

#endif /* _WIN32 */
