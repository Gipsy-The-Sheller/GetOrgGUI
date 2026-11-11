#ifndef COMPAT_CXXABI_H
#define COMPAT_CXXABI_H

#ifdef __cplusplus
extern "C" {
#endif

#ifdef _WIN32
    // Windows 下的改进版本
    #include <windows.h>
    #include <dbghelp.h>
    
    char* __cxa_demangle(const char* mangled_name,
        char* output_buffer,
        size_t* length,
        int* status);
#else
    // 非 Windows 平台使用标准 cxxabi
    #include <cxxabi.h>
#endif

#ifdef __cplusplus
}
#endif

// 提供 abi 命名空间支持
#ifdef __cplusplus
#ifdef _WIN32
namespace abi {
    inline char* __cxa_demangle(const char* mangled_name,
        char* output_buffer,
        size_t* length,
        int* status) {
        return ::__cxa_demangle(mangled_name, output_buffer, length, status);
    }
}
#endif
#endif

#endif // COMPAT_CXXABI_H