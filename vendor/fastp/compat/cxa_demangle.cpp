#ifdef _WIN32
#include <windows.h>
#include <dbghelp.h>
#include <cstdlib>
#include <cstring>

#pragma comment(lib, "dbghelp.lib")

// 只提供一个实现，不使用命名空间包装
extern "C" char* __cxa_demangle(const char* mangled_name,
    char* output_buffer,
    size_t* length,
    int* status) {
    if (!mangled_name) {
        if (status) *status = -1;
        return nullptr;
    }

    char* result = nullptr;

    if (output_buffer && length) {
        DWORD ret = UnDecorateSymbolName(mangled_name, output_buffer, (DWORD)*length, UNDNAME_COMPLETE);
        if (ret > 0) {
            result = output_buffer;
            if (status) *status = 0;
        }
        else {
            if (status) *status = -1;
        }
    }
    else if (length) {
        DWORD needed = UnDecorateSymbolName(mangled_name, nullptr, 0, UNDNAME_COMPLETE);
        if (needed > 0) {
            result = static_cast<char*>(malloc(needed + 1));
            if (result) {
                DWORD ret = UnDecorateSymbolName(mangled_name, result, needed, UNDNAME_COMPLETE);
                if (ret > 0) {
                    *length = needed;
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
            // 如果UnDecorateSymbolName失败，返回原始名称
            size_t len = strlen(mangled_name);
            result = static_cast<char*>(malloc(len + 1));
            if (result) {
                strcpy_s(result, len + 1, mangled_name);
                *length = len;
                if (status) *status = 0;
            }
            else {
                if (status) *status = -1;
            }
        }
    }
    else {
        if (status) *status = -1;
    }

    return result;
}
#endif