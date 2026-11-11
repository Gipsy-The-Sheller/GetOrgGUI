#pragma once
#ifndef SPADES_WIN32COMPAT_HPP
#define SPADES_WIN32COMPAT_HPP

#ifdef _WIN32

#ifdef __cplusplus
extern "C" {
#endif

/* Declarations for functions implemented in win32compat.cpp. */
char *mkdtemp(char *tmpl);
int mkstemp(char *tmpl);

#ifdef __cplusplus
}
#endif

#endif /* _WIN32 */

#endif /* SPADES_WIN32COMPAT_HPP */
