//***************************************************************************
//* Copyright (c) 2023-2024 SPAdes team
//* Copyright (c) 2015-2022 Saint Petersburg State University
//* Copyright (c) 2011-2014 Saint Petersburg Academic University
//* All Rights Reserved
//* See file LICENSE for details.
//***************************************************************************

/*
 * stacktrace.hpp
 *
 *  Created on: Feb 2, 2012
 *      Author: valery
 */

#pragma once
#include <iostream>

#if defined(_WIN32) && !defined(__MSYS__)
#ifndef WIN32_LEAN_AND_MEAN
#define WIN32_LEAN_AND_MEAN
#endif
#ifndef NOMINMAX
#define NOMINMAX
#endif
#include <windows.h>
#include <dbghelp.h>
#ifdef ERROR
#undef ERROR
#endif
#elif defined(__MSYS__)
// MSYS2 does not have execinfo.h, provide empty implementation
#else
#include <execinfo.h>
#endif

namespace utils {

inline void print_stacktrace() {
    std::cout << "=== Stack Trace ===" << std::endl;

#if defined(_WIN32) && !defined(__MSYS__)
    const size_t max_stack_size = 1000;
    void *stack_pointers[max_stack_size];
    unsigned short frames = CaptureStackBackTrace(0, max_stack_size, stack_pointers, NULL);

    HANDLE process = GetCurrentProcess();
    SymInitialize(process, NULL, TRUE);

    SYMBOL_INFO *symbol = (SYMBOL_INFO *)malloc(sizeof(SYMBOL_INFO) + 256 * sizeof(char));
    symbol->SizeOfStruct = sizeof(SYMBOL_INFO);
    symbol->MaxNameLen = 255;

    IMAGEHLP_LINE64 *line = (IMAGEHLP_LINE64 *)malloc(sizeof(IMAGEHLP_LINE64));
    line->SizeOfStruct = sizeof(IMAGEHLP_LINE64);

    for (unsigned short i = 0; i < frames; i++) {
        DWORD64 displacement64 = 0;
        if (SymFromAddr(process, (DWORD64)stack_pointers[i], &displacement64, symbol)) {
            DWORD displacement = 0;
            if (SymGetLineFromAddr64(process, (DWORD64)stack_pointers[i], &displacement, line)) {
                std::cerr << symbol->Name << " - " << line->FileName << ":" << line->LineNumber << std::endl;
            } else {
                std::cerr << symbol->Name << " - " << stack_pointers[i] << std::endl;
            }
        } else {
            std::cerr << "??? - " << stack_pointers[i] << std::endl;
        }
    }

    free(symbol);
    free(line);
    SymCleanup(process);
#elif defined(__MSYS__)
    // MSYS2 does not support stack tracing
    std::cerr << "Stack trace not available on MSYS2" << std::endl;
#else
    const size_t max_stack_size = 1000;

    void *stack_pointers[max_stack_size];
    int count = backtrace(stack_pointers, max_stack_size);

    char **func_names = backtrace_symbols(stack_pointers, count);

    // Print the stack trace
    for (int i = 0; i < count; ++i)
        std::cerr << func_names[i] << std::endl;

    // Free the string pointers
    free(func_names);
#endif
}

}
