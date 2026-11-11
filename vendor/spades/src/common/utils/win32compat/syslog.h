/*
 * Minimal <syslog.h> for native MinGW builds (used by bundled HMMER/easel).
 * Messages are redirected to stderr.
 */
#pragma once
#ifndef SPADES_WIN32COMPAT_SYSLOG_H
#define SPADES_WIN32COMPAT_SYSLOG_H

#include <stdarg.h>
#include <stdio.h>

#define LOG_EMERG   0
#define LOG_ALERT   1
#define LOG_CRIT    2
#define LOG_ERR     3
#define LOG_WARNING 4
#define LOG_NOTICE  5
#define LOG_INFO    6
#define LOG_DEBUG   7

static inline void openlog(const char *ident, int option, int facility) {
    (void)ident; (void)option; (void)facility;
}

static inline void closelog(void) {}

static inline void vsyslog(int priority, const char *format, va_list ap) {
    (void)priority;
    vfprintf(stderr, format, ap);
    fputc('\n', stderr);
}

static inline void syslog(int priority, const char *format, ...) {
    va_list ap;
    va_start(ap, format);
    vsyslog(priority, format, ap);
    va_end(ap);
}

#endif /* SPADES_WIN32COMPAT_SYSLOG_H */
