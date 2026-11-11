#ifdef _WIN32

#include <string.h>
#include <sys/resource.h>

/*
 * BWA only uses getrusage() for reporting CPU time.  Keep this in a separate
 * archive member: spades-bwa needs it, while spades-core gets the strong
 * definition from common/utils and must not pull a duplicate.
 */
int getrusage(int who, struct rusage *usage) {
    (void)who;
    if (usage)
        memset(usage, 0, sizeof(*usage));
    return 0;
}

#endif /* _WIN32 */
