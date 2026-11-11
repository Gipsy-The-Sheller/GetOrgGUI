/*
 * POSIX compatibility shims used by the native MinGW-w64 build of SPAdes.
 *
 * Covered here:
 *   - mkstemp() / mkdtemp()
 *   - mmap() / munmap() / msync() / madvise() on top of Win32 file mappings
 *   - glob() / globfree()
 *   - getrlimit() / setrlimit() / getrusage()
 *
 * Windows has no equivalent of RLIMIT_AS that user space can enforce, so the
 * memory limit is remembered and reported but not enforced by the kernel.
 */

#ifdef _WIN32

#ifndef WIN32_LEAN_AND_MEAN
#  define WIN32_LEAN_AND_MEAN
#endif
#ifndef NOMINMAX
#  define NOMINMAX
#endif

#include <windows.h>
#include <psapi.h>

#include <io.h>
#include <direct.h>
#include <fcntl.h>
#include <sys/stat.h>
#include <sys/types.h>

#include <cerrno>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <algorithm>
#include <mutex>
#include <string>
#include <unordered_map>
#include <vector>

#include "sys/mman.h"
#include "sys/resource.h"
#include "glob.h"

/* ------------------------------------------------------------------ */
/* mkstemp / mkdtemp                                                   */
/* ------------------------------------------------------------------ */

namespace {

char RandomChar(unsigned &state) {
    static const char kAlphabet[] =
        "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789";
    state = state * 1103515245u + 12345u;
    return kAlphabet[(state >> 16) % (sizeof(kAlphabet) - 1)];
}

bool FillTemplate(char *tmpl, unsigned &state) {
    size_t len = std::strlen(tmpl);
    if (len < 6)
        return false;
    char *suffix = tmpl + len - 6;
    for (size_t i = 0; i < 6; ++i)
        suffix[i] = RandomChar(state);
    return true;
}

} // namespace

extern "C" {

int mkstemp(char *tmpl) {
    if (!tmpl)
        return -1;
    unsigned state = static_cast<unsigned>(GetTickCount()) ^
                     static_cast<unsigned>(GetCurrentProcessId() * 2654435761u);
    for (int attempt = 0; attempt < 256; ++attempt) {
        if (!FillTemplate(tmpl, state)) {
            errno = EINVAL;
            return -1;
        }
        int fd = _open(tmpl, _O_CREAT | _O_EXCL | _O_RDWR | _O_BINARY,
                       _S_IREAD | _S_IWRITE);
        if (fd >= 0)
            return fd;
        if (errno != EEXIST)
            return -1;
    }
    errno = EEXIST;
    return -1;
}

char *mkdtemp(char *tmpl) {
    if (!tmpl)
        return nullptr;
    unsigned state = static_cast<unsigned>(GetTickCount()) ^
                     static_cast<unsigned>(GetCurrentProcessId() * 2246822519u);
    for (int attempt = 0; attempt < 256; ++attempt) {
        if (!FillTemplate(tmpl, state)) {
            errno = EINVAL;
            return nullptr;
        }
        if (_mkdir(tmpl) == 0)
            return tmpl;
        if (errno != EEXIST)
            return nullptr;
    }
    errno = EEXIST;
    return nullptr;
}

/* ------------------------------------------------------------------ */
/* mmap family                                                         */
/* ------------------------------------------------------------------ */

namespace {
std::mutex g_mapping_mutex;
std::unordered_map<void *, void *> g_mappings; // user pointer -> mapped base
} // namespace

void *mmap(void *addr, size_t length, int prot, int flags, int fd, off_t offset) {
    (void)addr;
    (void)flags;

    if (length == 0) {
        errno = EINVAL;
        return MAP_FAILED;
    }

    intptr_t os_handle = _get_osfhandle(fd);
    if (os_handle == -1) {
        errno = EBADF;
        return MAP_FAILED;
    }

    SYSTEM_INFO si;
    GetSystemInfo(&si);
    const uint64_t granularity = si.dwAllocationGranularity;
    const uint64_t file_offset = static_cast<uint64_t>(offset);
    const uint64_t aligned_offset = file_offset & ~(granularity - 1);
    const uint64_t delta = file_offset - aligned_offset;

    DWORD page_protect = PAGE_READONLY;
    DWORD view_access = FILE_MAP_READ;
    if (prot & PROT_WRITE) {
        page_protect = PAGE_READWRITE;
        view_access = FILE_MAP_WRITE;
    }

    HANDLE map_handle = CreateFileMappingA(
        reinterpret_cast<HANDLE>(os_handle), nullptr, page_protect, 0, 0, nullptr);
    if (!map_handle) {
        errno = EINVAL;
        return MAP_FAILED;
    }

    void *base = MapViewOfFile(
        map_handle, view_access,
        static_cast<DWORD>(aligned_offset >> 32),
        static_cast<DWORD>(aligned_offset & 0xffffffffu),
        static_cast<SIZE_T>(length + delta));
    CloseHandle(map_handle);

    if (!base) {
        errno = EINVAL;
        return MAP_FAILED;
    }

    void *user_ptr = static_cast<char *>(base) + delta;
    {
        std::lock_guard<std::mutex> lock(g_mapping_mutex);
        g_mappings[user_ptr] = base;
    }
    return user_ptr;
}

int munmap(void *addr, size_t length) {
    (void)length;
    void *base = nullptr;
    {
        std::lock_guard<std::mutex> lock(g_mapping_mutex);
        auto it = g_mappings.find(addr);
        if (it == g_mappings.end()) {
            errno = EINVAL;
            return -1;
        }
        base = it->second;
        g_mappings.erase(it);
    }
    if (!UnmapViewOfFile(base)) {
        errno = EINVAL;
        return -1;
    }
    return 0;
}

int msync(void *addr, size_t length, int flags) {
    (void)flags;
    return FlushViewOfFile(addr, length) ? 0 : -1;
}

int madvise(void *addr, size_t length, int advice) {
    (void)addr;
    (void)length;
    (void)advice;
    return 0;
}

int getpagesize(void) {
    SYSTEM_INFO si;
    GetSystemInfo(&si);
    return static_cast<int>(si.dwPageSize);
}

/* ------------------------------------------------------------------ */
/* glob family                                                         */
/* ------------------------------------------------------------------ */

static bool HasWildcard(const char *s) {
    return std::strchr(s, '*') || std::strchr(s, '?');
}

static void AppendPath(glob_t *pglob, const std::string &path, bool is_dir, int flags) {
    std::string value = path;
    if ((flags & GLOB_MARK) && is_dir && !value.empty() &&
        value.back() != '/' && value.back() != '\\')
        value.push_back('/');

    char **new_pathv = static_cast<char **>(
        std::realloc(pglob->gl_pathv, (pglob->gl_pathc + 1) * sizeof(char *)));
    if (!new_pathv)
        return;
    pglob->gl_pathv = new_pathv;
    pglob->gl_pathv[pglob->gl_pathc] = _strdup(value.c_str());
    if (pglob->gl_pathv[pglob->gl_pathc])
        ++pglob->gl_pathc;
}

static int ComparePaths(const void *a, const void *b) {
    const char *pa = *static_cast<const char *const *>(a);
    const char *pb = *static_cast<const char *const *>(b);
    return std::strcmp(pa, pb);
}

int glob(const char *pattern, int flags,
         int (*errfunc)(const char *epath, int eerrno), glob_t *pglob) {
    if (!pattern || !pglob)
        return GLOB_NOSPACE;

    pglob->gl_pathc = 0;
    pglob->gl_pathv = nullptr;
    pglob->gl_offs = 0;

    std::string pattern_str(pattern);
    const size_t sep = pattern_str.find_last_of("/\\");
    const std::string dir = (sep == std::string::npos)
                                ? std::string()
                                : pattern_str.substr(0, sep + 1);
    const std::string mask = (sep == std::string::npos)
                                 ? pattern_str
                                 : pattern_str.substr(sep + 1);

    if (!HasWildcard(mask.c_str())) {
        DWORD attrs = GetFileAttributesA(pattern_str.c_str());
        if (attrs == INVALID_FILE_ATTRIBUTES)
            return GLOB_NOMATCH;
        AppendPath(pglob, pattern_str, (attrs & FILE_ATTRIBUTE_DIRECTORY) != 0, flags);
        return pglob->gl_pathc ? 0 : GLOB_NOSPACE;
    }

    WIN32_FIND_DATAA data;
    HANDLE find_handle = FindFirstFileA(pattern_str.c_str(), &data);
    if (find_handle == INVALID_HANDLE_VALUE) {
        DWORD err = GetLastError();
        if (err == ERROR_FILE_NOT_FOUND || err == ERROR_PATH_NOT_FOUND)
            return GLOB_NOMATCH;
        if (errfunc)
            errfunc(pattern_str.c_str(), static_cast<int>(err));
        return GLOB_ABORTED;
    }

    do {
        if (std::strcmp(data.cFileName, ".") == 0 ||
            std::strcmp(data.cFileName, "..") == 0)
            continue;
        AppendPath(pglob, dir + data.cFileName,
                   (data.dwFileAttributes & FILE_ATTRIBUTE_DIRECTORY) != 0, flags);
    } while (FindNextFileA(find_handle, &data));

    FindClose(find_handle);

    if (pglob->gl_pathc == 0)
        return GLOB_NOMATCH;

    if (!(flags & GLOB_NOSORT) && pglob->gl_pathc > 1)
        std::qsort(pglob->gl_pathv, pglob->gl_pathc, sizeof(char *), ComparePaths);

    return 0;
}

void globfree(glob_t *pglob) {
    if (!pglob || !pglob->gl_pathv)
        return;
    for (size_t i = 0; i < pglob->gl_pathc; ++i)
        std::free(pglob->gl_pathv[i]);
    std::free(pglob->gl_pathv);
    pglob->gl_pathv = nullptr;
    pglob->gl_pathc = 0;
}

/* ------------------------------------------------------------------ */
/* getrlimit / setrlimit / getrusage                                   */
/* ------------------------------------------------------------------ */

namespace {
rlim_t g_requested_memory_limit = 0;
}

int getrlimit(int resource, struct rlimit *rlim) {
    if (!rlim) {
        errno = EINVAL;
        return -1;
    }

    if (resource == RLIMIT_NOFILE) {
        /* MinGW's CRT inherits the ~8k handle limit; report a generous value. */
        rlim->rlim_cur = 65536;
        rlim->rlim_max = 65536;
        return 0;
    }

    if (resource != RLIMIT_AS) {
        errno = EINVAL;
        return -1;
    }

    rlim_t limit = g_requested_memory_limit;
    if (limit == 0) {
        MEMORYSTATUSEX status;
        status.dwLength = sizeof(status);
        if (GlobalMemoryStatusEx(&status))
            limit = static_cast<rlim_t>(status.ullTotalPhys);
    }

    rlim->rlim_cur = limit;
    rlim->rlim_max = limit;
    return 0;
}

int setrlimit(int resource, const struct rlimit *rlim) {
    if (!rlim) {
        errno = EINVAL;
        return -1;
    }

    if (resource == RLIMIT_NOFILE) {
        /* No per-process file limit is enforced on Windows. */
        return 0;
    }

    if (resource != RLIMIT_AS) {
        errno = EINVAL;
        return -1;
    }
    /*
     * Windows does not expose an RLIMIT_AS equivalent usable from user mode.
     * Remember the value for reporting purposes; actual enforcement would
     * require a Job Object around the whole process tree, which is the
     * responsibility of the SPAdes launcher.
     */
    g_requested_memory_limit = rlim->rlim_cur;
    return 0;
}

int getrusage(int who, struct rusage *usage) {
    if (!usage || who != RUSAGE_SELF) {
        errno = EINVAL;
        return -1;
    }
    std::memset(usage, 0, sizeof(*usage));
    PROCESS_MEMORY_COUNTERS counters;
    if (GetProcessMemoryInfo(GetCurrentProcess(), &counters, sizeof(counters)))
        usage->ru_maxrss = static_cast<long>(counters.WorkingSetSize / 1024);
    return 0;
}

} // extern "C"

#endif /* _WIN32 */
