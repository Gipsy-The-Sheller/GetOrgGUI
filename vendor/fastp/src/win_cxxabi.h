#ifndef COMPAT_CXXABI_H
#define COMPAT_CXXABI_H

#include <stddef.h>

#ifdef _WIN32

#ifdef __cplusplus
extern "C" {
#endif

char* __cxa_demangle(const char* mangled_name,
    char* output_buffer,
    size_t* length,
    int* status);

#ifdef __cplusplus
}
#endif

#ifdef __cplusplus
namespace abi {
    inline char* __cxa_demangle(const char* mangled_name,
        char* output_buffer,
        size_t* length,
        int* status) {
        return ::__cxa_demangle(mangled_name, output_buffer, length, status);
    }
}
#endif

#else

// Skip this compatibility header and use the toolchain's real cxxabi.h.
#include <cxxabi.h>

#endif

#endif // COMPAT_CXXABI_H
