#ifdef _WIN32
#include <windows.h>
#include <dbghelp.h>
#include <cstdlib>
#include <cstring>
#include <memory>

#pragma comment(lib, "dbghelp.lib")

// Windows 版本的 __cxa_demangle
// 注意：这只是一个简化实现，实际可能需要更复杂的处理
extern "C" char* __cxa_demangle(const char* mangled_name,
    char* output_buffer,
    size_t* length,
    int* status) {
    if (!mangled_name) {
        if (status) *status = -1;
        return nullptr;
    }

    // 尝试使用 Windows 的 UnDecorateSymbolName
    char* result = nullptr;

    if (output_buffer) {
        // 使用调用者提供的缓冲区
        DWORD ret = UnDecorateSymbolName(mangled_name, output_buffer, (DWORD)*length, UNDNAME_COMPLETE);
        if (ret > 0) {
            result = output_buffer;
            if (status) *status = 0;
        }
        else {
            if (status) *status = -1;
        }
    }
    else {
        // 分配新缓冲区
        DWORD needed = UnDecorateSymbolName(mangled_name, nullptr, 0, UNDNAME_COMPLETE);
        if (needed > 0) {
            result = static_cast<char*>(malloc(needed + 1));
            if (result) {
                DWORD ret = UnDecorateSymbolName(mangled_name, result, needed, UNDNAME_COMPLETE);
                if (ret > 0) {
                    if (length) *length = needed;
                    if (status) *status = 0;
                }
                else {
                    free(result);
                    result = nullptr;
                    if (status) *status = -1;
                }
            }
            else {
                if (status) *status = -1;
            }
        }
        else {
            // 如果UnDecorateSymbolName失败，返回原始名称的副本
            size_t len = strlen(mangled_name);
            result = static_cast<char*>(malloc(len + 1));
            if (result) {
                strcpy_s(result, len + 1, mangled_name);
                if (length) *length = len;
                if (status) *status = 0;
            }
            else {
                if (status) *status = -1;
            }
        }
    }

    return result;
}

// 简单的abi命名空间包装
namespace abi {
    extern "C" char* __cxa_demangle(const char* mangled_name,
        char* output_buffer,
        size_t* length,
        int* status) {
        return ::__cxa_demangle(mangled_name, output_buffer, length, status);
    }
}
#endif