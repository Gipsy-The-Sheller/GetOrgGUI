#ifdef _WIN32
#include "unistd.h"
#include <io.h>
#include <windows.h>

#ifdef __cplusplus
extern "C" {
#endif

    unsigned int win_sleep(unsigned int seconds) {
        Sleep(seconds * 1000);
        return 0;
    }

    int win_usleep(unsigned int usec) {
        Sleep(usec / 1000);
        return 0;
    }

    int win_pread(int fd, void* buf, unsigned int count, long offset) {
        long old_offset = _lseek(fd, 0, SEEK_CUR);
        if (old_offset == -1) return -1;

        if (_lseek(fd, offset, SEEK_SET) == -1) return -1;

        int result = _read(fd, buf, count);

        _lseek(fd, old_offset, SEEK_SET);
        return result;
    }

    int win_pwrite(int fd, const void* buf, unsigned int count, long offset) {
        long old_offset = _lseek(fd, 0, SEEK_CUR);
        if (old_offset == -1) return -1;

        if (_lseek(fd, offset, SEEK_SET) == -1) return -1;

        int result = _write(fd, buf, count);

        _lseek(fd, old_offset, SEEK_SET);
        return result;
    }

    int win_getppid(void) { return 0; }
    int win_getuid(void) { return 0; }
    int win_getgid(void) { return 0; }
    int win_fork(void) { return -1; }
    int win_execvp(const char* file, char* const argv[]) { return -1; }
    int win_execv(const char* path, char* const argv[]) { return -1; }
    int win_execlp(const char* file, const char* arg, ...) { return -1; }
    int win_execl(const char* path, const char* arg, ...) { return -1; }
    char* win_ttyname(int fd) { return _isatty(fd) ? (char*)"console" : NULL; }

#ifdef __cplusplus
}
#endif

#endif // _WIN32