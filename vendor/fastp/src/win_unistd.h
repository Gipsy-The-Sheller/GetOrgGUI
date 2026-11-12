#ifndef COMPAT_UNISTD_H
#define COMPAT_UNISTD_H

#ifdef _WIN32
#include <io.h>
#include <direct.h>
#include <process.h>
#include <windows.h>
#include <fcntl.h>
#include <sys/stat.h>

// POSIX 
#define R_OK 4
#define W_OK 2
#define X_OK 1
#define F_OK 0

#define STDIN_FILENO 0
#define STDOUT_FILENO 1
#define STDERR_FILENO 2

// Ͷ
#ifdef _MSC_VER
typedef int ssize_t;
typedef long off_t;
typedef int pid_t;
typedef int uid_t;
typedef int gid_t;
typedef unsigned int useconds_t;
#endif


// Windows下stat结构的兼容定义
#ifdef _MSC_VER
    #define stat _stat
    #define fstat _fstat
    #define S_IFDIR _S_IFDIR
    #define S_IFMT _S_IFMT
#endif

#ifdef __cplusplus
extern "C" {
#endif

	// Windows Ѷĺֱʹ
#define win_access _access
#define win_close _close
#define win_getpid _getpid
#define win_isatty _isatty
#define win_getcwd _getcwd
#define win_chdir _chdir
#define win_rmdir _rmdir
#define win_unlink _unlink
#define win_dup _dup
#define win_dup2 _dup2
#define win_fsync _commit
#define win_fdatasync _commit
#define win_ftruncate _chsize
#define win_pipe _pipe
#define win_lseek _lseek
#define win_read _read
#define win_write _write

// Զʵֵĺ
	unsigned int win_sleep(unsigned int seconds);
	int win_usleep(unsigned int usec);
	int win_pread(int fd, void* buf, unsigned int count, long offset);
	int win_pwrite(int fd, const void* buf, unsigned int count, long offset);

	// ʵ֣ش
	int win_getppid(void);
	int win_getuid(void);
	int win_getgid(void);
	int win_fork(void);
	int win_execvp(const char* file, char* const argv[]);
	int win_execv(const char* path, char* const argv[]);
	int win_execlp(const char* file, const char* arg, ...);
	int win_execl(const char* path, const char* arg, ...);
	char* win_ttyname(int fd);

#ifdef __cplusplus
}
#endif

#else
// Use the toolchain's real unistd.h, skipping this compatibility header.
#include <unistd.h>
#endif

#endif // COMPAT_UNISTD_H