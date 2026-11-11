/*
 * Minimal native-Windows implementations of the LLVM Support entry points
 * that the bundled LLVM subset references but whose Windows .inc files were
 * not vendored.
 *
 * File handles are represented as CRT file descriptors encoded in the
 * llvm::sys::fs::file_t (void*) value.  Only this file interprets them;
 * all other LLVM code treats file_t opaquely.
 */

#ifdef _WIN32

#include "llvm/Support/FileSystem.h"
#include "llvm/Support/Path.h"
#include "llvm/Support/Process.h"
#include "llvm/Support/Program.h"
#include "llvm/Support/Signals.h"
#include "llvm/Support/Threading.h"
#include "llvm/ADT/SmallVector.h"
#include "llvm/Support/Error.h"

#ifndef WIN32_LEAN_AND_MEAN
#define WIN32_LEAN_AND_MEAN
#endif
#ifndef NOMINMAX
#define NOMINMAX
#endif
#include <windows.h>

#include <fcntl.h>
#include <io.h>
#include <sys/stat.h>
#include <sys/types.h>

#include <cerrno>
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <system_error>

namespace {

inline int to_fd(llvm::sys::fs::file_t F) {
    return static_cast<int>(reinterpret_cast<intptr_t>(F));
}

inline llvm::sys::fs::file_t to_file_t(int FD) {
    return reinterpret_cast<llvm::sys::fs::file_t>(static_cast<intptr_t>(FD));
}

inline std::error_code errno_code() {
    return std::error_code(errno, std::generic_category());
}

int open_impl(const llvm::Twine &Name,
              llvm::sys::fs::CreationDisposition Disp,
              llvm::sys::fs::FileAccess Access,
              llvm::sys::fs::OpenFlags Flags,
              unsigned Mode) {
    std::string name = Name.str();

    int oflags = _O_BINARY;
    const unsigned access = static_cast<unsigned>(Access);
    const bool want_read = (access & llvm::sys::fs::FA_Read) != 0;
    const bool want_write = (access & llvm::sys::fs::FA_Write) != 0;
    if (want_read && want_write)
        oflags |= _O_RDWR;
    else if (want_write)
        oflags |= _O_WRONLY;
    else
        oflags |= _O_RDONLY;

    switch (Disp) {
    case llvm::sys::fs::CD_CreateAlways:
        oflags |= _O_CREAT | _O_TRUNC;
        break;
    case llvm::sys::fs::CD_CreateNew:
        oflags |= _O_CREAT | _O_EXCL;
        break;
    case llvm::sys::fs::CD_OpenExisting:
        break;
    case llvm::sys::fs::CD_OpenAlways:
        oflags |= _O_CREAT;
        break;
    }

    if (static_cast<unsigned>(Flags) & llvm::sys::fs::OF_Append)
        oflags |= _O_APPEND;

    return _open(name.c_str(), oflags, Mode ? Mode : 0666);
}

} // namespace

namespace llvm {
namespace sys {
namespace fs {

Expected<file_t> openNativeFile(const Twine &Name, CreationDisposition Disp,
                                FileAccess Access, OpenFlags Flags,
                                unsigned Mode) {
    int fd = open_impl(Name, Disp, Access, Flags, Mode);
    if (fd < 0)
        return errorCodeToError(errno_code());
    return to_file_t(fd);
}

std::error_code openFile(const Twine &Name, int &ResultFD,
                         CreationDisposition Disp, FileAccess Access,
                         OpenFlags Flags, unsigned Mode) {
    int fd = open_impl(Name, Disp, Access, Flags, Mode);
    if (fd < 0)
        return errno_code();
    ResultFD = fd;
    return std::error_code();
}

Expected<file_t> openNativeFileForRead(const Twine &Name, OpenFlags Flags,
                                       SmallVectorImpl<char> *RealPath) {
    int fd = open_impl(Name, CD_OpenExisting, FA_Read, Flags, 0666);
    if (fd < 0)
        return errorCodeToError(errno_code());
    if (RealPath) {
        std::string name = Name.str();
        RealPath->append(name.begin(), name.end());
    }
    return to_file_t(fd);
}

std::error_code closeFile(file_t &F) {
    if (!F)
        return std::error_code();
    int fd = to_fd(F);
    F = nullptr;
    if (_close(fd) != 0)
        return errno_code();
    return std::error_code();
}

Expected<size_t> readNativeFile(file_t FileHandle, MutableArrayRef<char> Buf) {
    int fd = to_fd(FileHandle);
    unsigned chunk = static_cast<unsigned>(
        Buf.size() > 0x7fffffffu ? 0x7fffffffu : Buf.size());
    int got = _read(fd, Buf.data(), chunk);
    if (got < 0)
        return errorCodeToError(errno_code());
    return static_cast<size_t>(got);
}

Expected<size_t> readNativeFileSlice(file_t FileHandle,
                                     MutableArrayRef<char> Buf,
                                     uint64_t Offset) {
    int fd = to_fd(FileHandle);
    if (_lseeki64(fd, static_cast<__int64>(Offset), SEEK_SET) == -1)
        return errorCodeToError(errno_code());
    return readNativeFile(FileHandle, Buf);
}

std::error_code status(file_t FD, file_status &Result) {
    struct _stat64 st;
    if (_fstat64(to_fd(FD), &st) != 0)
        return errno_code();

    file_type Type = file_type::regular_file;
    if ((st.st_mode & _S_IFDIR) != 0)
        Type = file_type::directory_file;
    else if ((st.st_mode & _S_IFREG) == 0)
        Type = file_type::type_unknown;

    perms Perms = static_cast<perms>(st.st_mode & 0777);
    Result = file_status(Type, Perms,
                         static_cast<dev_t>(st.st_dev),
                         static_cast<nlink_t>(st.st_nlink),
                         static_cast<ino_t>(st.st_ino),
                         static_cast<time_t>(st.st_atime), 0,
                         static_cast<time_t>(st.st_mtime), 0,
                         static_cast<uid_t>(0), static_cast<gid_t>(0),
                         static_cast<off_t>(st.st_size));
    return std::error_code();
}

file_t getStdinHandle() { return to_file_t(0); }
file_t getStdoutHandle() { return to_file_t(1); }

/* ------------------------------------------------------------------ */
/* mapped_file_region                                                  */
/* ------------------------------------------------------------------ */

mapped_file_region::mapped_file_region(file_t FD, mapmode Mode_,
                                       size_t Length, uint64_t Offset,
                                       std::error_code &ec)
    : Size(Length), Mapping(nullptr), FileHandle(nullptr), Mode(Mode_) {
    HANDLE file = reinterpret_cast<HANDLE>(_get_osfhandle(to_fd(FD)));
    if (file == INVALID_HANDLE_VALUE) {
        ec = errno_code();
        return;
    }

    DWORD protect = (Mode_ == readonly) ? PAGE_READONLY : PAGE_READWRITE;
    HANDLE map = CreateFileMappingA(file, nullptr, protect, 0, 0, nullptr);
    if (!map) {
        ec = std::error_code(static_cast<int>(GetLastError()),
                             std::system_category());
        return;
    }

    SYSTEM_INFO si;
    GetSystemInfo(&si);
    const uint64_t granularity = si.dwAllocationGranularity;
    const uint64_t aligned = Offset & ~(granularity - 1);
    const uint64_t delta = Offset - aligned;

    DWORD access = (Mode_ == readonly) ? FILE_MAP_READ : FILE_MAP_WRITE;
    void *base = MapViewOfFile(
        map, access, static_cast<DWORD>(aligned >> 32),
        static_cast<DWORD>(aligned & 0xffffffffu),
        static_cast<SIZE_T>(Length + delta));
    CloseHandle(map);

    if (!base) {
        ec = std::error_code(static_cast<int>(GetLastError()),
                             std::system_category());
        return;
    }

    FileHandle = reinterpret_cast<file_t>(base);
    Mapping = static_cast<char *>(base) + delta;
    ec.clear();
}

mapped_file_region::~mapped_file_region() {
    if (FileHandle)
        UnmapViewOfFile(reinterpret_cast<void *>(FileHandle));
}

size_t mapped_file_region::size() const { return Size; }

char *mapped_file_region::data() const {
    return const_cast<char *>(const_data());
}

const char *mapped_file_region::const_data() const {
    return static_cast<const char *>(Mapping);
}

int mapped_file_region::alignment() {
    SYSTEM_INFO si;
    GetSystemInfo(&si);
    return static_cast<int>(si.dwAllocationGranularity);
}

} // namespace fs
} // namespace sys
} // namespace llvm

/* ------------------------------------------------------------------ */
/* Process                                                             */
/* ------------------------------------------------------------------ */

namespace llvm {
namespace sys {

Process::Pid Process::getProcessId() {
    return static_cast<Pid>(GetCurrentProcessId());
}

Expected<unsigned> Process::getPageSize() {
    SYSTEM_INFO si;
    GetSystemInfo(&si);
    return static_cast<unsigned>(si.dwPageSize);
}

std::error_code Process::SafelyCloseFileDescriptor(int FD) {
    if (FD < 0)
        return std::error_code();
    if (_close(FD) != 0)
        return errno_code();
    return std::error_code();
}

bool Process::FileDescriptorIsDisplayed(int fd) {
    return _isatty(fd) != 0;
}

bool Process::FileDescriptorHasColors(int fd) {
    (void)fd;
    return false;
}

bool Process::ColorNeedsFlush() { return false; }

const char *Process::OutputColor(char c, bool bold, bool bg) {
    (void)c;
    (void)bold;
    (void)bg;
    return "";
}

const char *Process::OutputBold(bool bg) {
    (void)bg;
    return "";
}

const char *Process::OutputReverse() { return ""; }
const char *Process::ResetColor() { return ""; }

} // namespace sys
} // namespace llvm

/* ------------------------------------------------------------------ */
/* Threading                                                           */
/* ------------------------------------------------------------------ */

namespace llvm {

uint64_t get_threadid() {
    return static_cast<uint64_t>(GetCurrentThreadId());
}

void get_thread_name(SmallVectorImpl<char> &Name) {
    char buffer[64];
    std::snprintf(buffer, sizeof(buffer), "thread-%lu",
                  static_cast<unsigned long>(GetCurrentThreadId()));
    Name.append(buffer, buffer + std::strlen(buffer));
}

bool llvm_is_multithreaded() { return true; }

uint32_t get_max_thread_name_length() { return 0; }

void set_thread_name(const Twine &Name) { (void)Name; }

unsigned get_cpus() {
    SYSTEM_INFO si;
    GetSystemInfo(&si);
    return static_cast<unsigned>(si.dwNumberOfProcessors);
}

} // namespace llvm

/* ------------------------------------------------------------------ */
/* Signals / Program                                                   */
/* ------------------------------------------------------------------ */

namespace llvm {
namespace sys {

void RunInterruptHandlers() {}

std::error_code ChangeStdinToBinary() {
    _setmode(_fileno(stdin), _O_BINARY);
    return std::error_code();
}

std::error_code ChangeStdoutToBinary() {
    _setmode(_fileno(stdout), _O_BINARY);
    return std::error_code();
}

} // namespace sys
} // namespace llvm

/* ------------------------------------------------------------------ */
/* sys::path                                                           */
/* ------------------------------------------------------------------ */

namespace llvm {
namespace sys {
namespace path {

StringRef get_separator(Style style) {
    return (style == Style::windows) ? "\\" : "/";
}

StringRef filename(StringRef path, Style style) {
    if (path.empty())
        return path;

    size_t n = path.size();
    while (n > 0) {
        char c = path[n - 1];
        bool is_sep = (style == Style::windows) ? (c == '\\' || c == '/')
                                                : (c == '/');
        if (!is_sep)
            break;
        --n;
    }

    size_t start = n;
    while (start > 0) {
        char c = path[start - 1];
        bool is_sep = (style == Style::windows) ? (c == '\\' || c == '/')
                                                : (c == '/');
        if (is_sep)
            break;
        --start;
    }
    return path.substr(start, n - start);
}

} // namespace path
} // namespace sys
} // namespace llvm

#endif /* _WIN32 */
