/*
 * Minimal <sys/wait.h> for native MinGW builds (used by bundled BWA).
 */
#pragma once
#ifndef SPADES_WIN32COMPAT_SYS_WAIT_H
#define SPADES_WIN32COMPAT_SYS_WAIT_H

#include <sys/types.h>

#ifdef __cplusplus
extern "C" {
#endif

#define WNOHANG 1

#define WIFEXITED(status)   (((status) & 0x7f) == 0)
#define WEXITSTATUS(status) (((status) & 0xff00) >> 8)
#define WIFSIGNALED(status) (((status) & 0x7f) != 0 && ((status) & 0x7f) != 0x7f)
#define WTERMSIG(status)    ((status) & 0x7f)

pid_t waitpid(pid_t pid, int *status, int options);

#ifdef __cplusplus
}
#endif

#endif /* SPADES_WIN32COMPAT_SYS_WAIT_H */
