/*
 * The bundled LLVM headers are configured with LLVM_ON_UNIX, so they expect
 * a few POSIX typedefs that native MinGW does not provide.  This header is
 * force-included only when compiling the bundled llvm-support library.
 */
#pragma once
#ifndef SPADES_WIN32COMPAT_LLVM_POSIX_TYPES_H
#define SPADES_WIN32COMPAT_LLVM_POSIX_TYPES_H

#include <sys/types.h>

#ifndef _UID_T_DEFINED_
typedef unsigned int uid_t;
#define _UID_T_DEFINED_
#endif

#ifndef _GID_T_DEFINED_
typedef unsigned int gid_t;
#define _GID_T_DEFINED_
#endif

#ifndef _NLINK_T_DEFINED_
typedef unsigned short nlink_t;
#define _NLINK_T_DEFINED_
#endif

#endif /* SPADES_WIN32COMPAT_LLVM_POSIX_TYPES_H */
