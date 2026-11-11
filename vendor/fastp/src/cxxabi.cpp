#ifdef _WIN32
#include "cxxabi.h"
#include <windows.h>
#include <dbghelp.h>
#include <cstring>
#include <cstdlib>
#include <cstdio>
#if defined(__MINGW32__)
#define strcpy_s(dst, size, src) snprintf((dst), (size), "%s", (src))
#endif

#pragma comment(lib, "dbghelp.lib")

#ifdef __cplusplus
extern "C" {
#endif

    char* __cxa_demangle(const char* mangled_name,
        char* output_buffer,
        size_t* length,
        int* status) {
        if (status) *status = 0;

        if (!mangled_name) {
            if (status) *status = -2;  // 无效参数
            return nullptr;
        }

        // 检查是否是合法的C++名称修饰格式
        if (mangled_name[0] != '?' && mangled_name[0] != '.') {
            // 不是MSVC的名称修饰格式，直接返回原名称
            size_t len = strlen(mangled_name);
            
            if (output_buffer && length && *length >= len + 1) {
                strcpy_s(output_buffer, *length, mangled_name);
                return output_buffer;
            }
            else if (!output_buffer) {
                char* result = static_cast<char*>(malloc(len + 1));
                if (result) {
                    strcpy_s(result, len + 1, mangled_name);
                    if (length) *length = len;
                } else {
                    if (status) *status = -3;  // 内存分配失败
                }
                return result;
            } else {
                if (status) *status = -1;
                return nullptr;
            }
        }

        char* result = nullptr;

        if (output_buffer && length) {
            DWORD ret = UnDecorateSymbolName(mangled_name, output_buffer, (DWORD)*length, UNDNAME_COMPLETE);
            if (ret > 0) {
                result = output_buffer;
            } else {
                // 如果UnDecorateSymbolName失败，返回原始名称
                size_t len = strlen(mangled_name);
                if (*length > len) {
                    strcpy_s(output_buffer, *length, mangled_name);
                    result = output_buffer;
                } else {
                    if (status) *status = -1;
                    result = nullptr;
                }
            }
        } else {
            // 计算所需缓冲区大小
            DWORD needed = UnDecorateSymbolName(mangled_name, nullptr, 0, UNDNAME_COMPLETE);
            if (needed > 0) {
                result = static_cast<char*>(malloc(needed + 1));
                if (result) {
                    DWORD ret = UnDecorateSymbolName(mangled_name, result, needed, UNDNAME_COMPLETE);
                    if (ret > 0) {
                        if (length) *length = needed;
                    } else {
                        // 如果UnDecorateSymbolName失败，使用原始名称
                        size_t len = strlen(mangled_name);
                        strcpy_s(result, len + 1, mangled_name);
                        if (length) *length = len;
                    }
                } else {
                    if (status) *status = -3;  // 内存分配失败
                }
            } else {
                // UnDecorateSymbolName无法处理此名称，返回原始名称
                size_t len = strlen(mangled_name);
                result = static_cast<char*>(malloc(len + 1));
                if (result) {
                    strcpy_s(result, len + 1, mangled_name);
                    if (length) *length = len;
                } else {
                    if (status) *status = -3;  // 内存分配失败
                }
            }
        }

        return result;
    }

#ifdef __cplusplus
}
#endif

#endif // _WIN32