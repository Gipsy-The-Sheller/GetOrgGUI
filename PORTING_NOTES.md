# GetOrganelle 原生 Windows 移植说明

本目录把 GetOrganelle 及其依赖迁移到原生 Windows（MinGW-w64），运行时不依赖 MSYS2 bash，也不依赖 `msys-2.0.dll`。

## 目录结构

```
E:\Codes\getorg_win\
├─ GetOrganelle\                  GetOrganelle 1.8.0.1（含 Windows 补丁）
│  └─ GetOrganelleDep\Windows\    GetOrganelle 自动查找依赖的位置
│     ├─ SPAdes\                  SPAdes 4.3.0，原生 MinGW-w64 构建
│     ├─ bowtie2\                 Bowtie2 2.5.5，原生 MinGW-w64 构建
│     ├─ ncbi-blast\              NCBI BLAST+ 2.17.0 官方 Windows 版
│     └─ samtools\bin\            samtools 1.25（静态链接；GetOrganelle 流程本身不用）
├─ venv\                          Python 3.12 虚拟环境（numpy / Biopython / gekko / requests）
├─ build\                         构建目录、日志、测试数据
├─ run_get_organelle_reads.bat
├─ run_get_organelle_assembly.bat
└─ run_get_organelle_config.bat
```

GetOrganelle 在运行时按 `GetOrganelleLib/../GetOrganelleDep/Windows` 查找依赖，因此依赖必须放在 `GetOrganelle\GetOrganelleDep\Windows` 下。

## 组件版本

| 组件 | 版本 | 来源 |
| --- | --- | --- |
| GetOrganelle | 1.8.0.1 | GitHub Kinggerm/GetOrganelle（含本目录补丁） |
| SPAdes | 4.3.0 | 源码 `vendor/spades`（v4.3.0 release + Windows 补丁），MinGW-w64 原生构建 |
| Bowtie2 | 2.5.5 | 源码构建，静态链接 |
| samtools / htslib | 1.25 | 源码构建，静态链接 |
| BLAST+ | 2.17.0 | NCBI 官方 `x64-win64` 构建 |
| Python | 3.12 | `venv\Scripts\python.exe` |

## SPAdes 原生 Windows 改动

核心目标：用 MinGW-w64 直接编译，生成的 `.exe` 只依赖 `libgcc/libstdc++/libgomp/libwinpthread`，不再需要 MSYS2 运行时。

新增 `src/common/utils/win32compat/`：
- `sys/mman.h` + `mmap/munmap/msync/madvise/getpagesize`（Win32 文件映射实现，处理 64K 对齐）
- `sys/resource.h`（`getrlimit/setrlimit/getrusage`，内存上限只记录不强制）
- `sys/wait.h`、`syslog.h`、`glob.h`、`sysexits.h`
- `mkstemp/mkdtemp/getline/strsep/ctime_r/localtime_r/srandom/sync` 等 POSIX 兼容函数
- `win32_types.h`：BSD `uint` typedef（全局 force-include）
- `easel_compat.h`：HMMER/easel 的 `mmap`、`getuid` 等
- BWA：`shm_open` 桩（SPAdes 不使用 `bwa shm`）、`*rand48`、`waitpid/kill`、禁用 POSIX pipe 打开方式

构建选项：
- `-D_FILE_OFFSET_BITS=64`（大于 2 GB 的 k-mer 索引）
- `-mno-ms-bitfields`（保持 Itanium ABI 位域布局，`Sequence::LongRep` 必须为 16 字节）
- 全局 force-include `win32_types.h`；链接 `dbghelp`、`psapi`

源码层面：
- 大量 `std::filesystem::path` → `std::string` 的显式 `.string()` 转换（Windows 下 `path::value_type` 是 `wchar_t`）
- 捆绑 LLVM Support：排除缺失的 Windows `*.inc` 实现，改写 `raw_ostream`/`YAMLTraits` 的 path 输出；
  新增 `ext/src/llvm/llvm_win_support.cpp` 提供 `sys::fs`、`sys::path`、`Process`、`Threading`、
  `Signals`、`Program` 的最小 Win32 实现
- 捆绑 HMMER：排除 `hmmd*` 守护进程代码；easel 的 mmap/getuid/syslog 兼容
- BamTools：MinGW 下不使用 `dllimport`（静态库），并链接 `ws2_32`
- BWA：`shm` 桩、`*rand48`、`waitpid/kill`、POSIX pipe 打开方式禁用；`getrusage` 放入独立的
  `win_getrusage.c`，避免 `spades-bwa` / `spades-core` 重复定义
- Blaze：MinGW 平台宏与 WIN32/WIN64 互斥判断修正；为 `size_t`/`ptrdiff_t` 启用 `Limits` 特化
- 32 位 `long` 兼容：
  - `LinkRecord` 的无效标记由 `-1ul` 改为 `~uint64_t(0)`
    （MinGW 的 `unsigned long` 是 32 位，MSYS/Cygwin 是 64 位；原写法会让“无效记录”被当成有效，
    多出顶点并生成非法短边，最终在 coverage filling 阶段断言失败）
  - `rtseq.hpp` 的 `MaskForLastBucket` 在“序列长度恰为 32 的倍数”时返回 `-1ul`（32 位全 1），
    会清掉最后一个 64 位字的高 32 位；改为 `~size_t(0)`
- `stacktrace.hpp` 使用 `CaptureStackBackTrace`/dbghelp（已有补丁保留）
- `std::is_pod` 在较新的 libc++ 中已被移除；`binary.hpp`、Blaze 的
  `IsPod` trait 和 hpcSPAdes MPI 辅助代码改用 `std::is_trivially_copyable`
  （对二进制序列化和 MPI 传递是合适的约束），恢复 arm64 Clang 构建
- sse2neon 在 Windows 上改用 `_aligned_malloc/_aligned_free` 实现
  `_mm_malloc/_mm_free`，避免依赖未声明的 POSIX `posix_memalign`
- `adt/pointer_iterator.hpp` 不再继承已废弃/移除的 `std::iterator`，
  直接声明迭代器所需的五个 typedef，兼容新版 libc++
- lexy 在 Clang 下加入 `-Wno-pragma-clang-attribute`：MSYS2 libc++ 的
  attribute pragma 会触发 `-Werror`，该警告与 lexy 代码本身无关
- 捆绑的 spoa 补齐 libc++ 不再间接包含的头文件：`alignment_engine.cpp` 增加
  `<cstdlib>`（`std::abs`），`graph.cpp` 增加 `<iterator>`（`std::inserter`）
- CLANGARM64 缺少 `sched.h`/`sched_yield`：新增
  `win32compat/sched_compat.hpp`（Windows 用 `SwitchToThread`/`Sleep(0)`，
  POSIX 转发到 `sched_yield`），并替换 `read_processor.hpp`、ionhammer
  `kmer_data.hpp` 中的直接调用。这样也避免与 winpthreads 自带的
  `sched.h`（quoted include）发生 extern/static 冲突

Python 层（SPAdes 流水线）：
- `spades_init.py` 识别 `spades-core.exe`（否则误判为开发目录）
- `support.process_readline` 使用 `errors="replace"`，避免 Windows 本地化输出非 UTF-8 导致崩溃
- `compress_all.py` 在无 `pigz/gzip` 时使用 Python `gzip` 模块
- 配置模板中的 `load_from`、`sewage_matrix`、`series_analysis` 路径统一转成正斜杠
  （Boost property_tree 会把反斜杠当转义符）

构建/安装目录：`build/ci-x64/spades` → `stage/x64/spades` → `deps/SPAdes` → 拷贝到
`GetOrganelle/GetOrganelleDep/Windows/SPAdes`。

> `vendor/spades` 是 SPAdes v4.3.0 release 源码快照（含本目录的 Windows 补丁）；构建脚本
> 使用 MSYS2 MINGW64 工具链。v4.3.0 新增 BZip2 构建依赖，CI 需要安装
> `mingw-w64-x86_64-bzip2`（arm64 对应 `mingw-w64-clang-aarch64-bzip2`）。

## Bowtie2 包装器改动

Bowtie2 的 `bowtie2` 是 Perl 脚本。Windows 下需要：
- `bowtie2.bat` 调用 `perl`（Strawberry Perl 或 Git 自带 MSYS Perl 均可）；
- 包装器已修补：
  - 识别 `$^O eq "msys"` 也按 Windows 处理；
  - `glob()` 对反斜杠路径做直接文件存在性回退；
  - 自动移除 `--mm`（Windows 构建未启用 `BOWTIE_MM`，否则 aligner 会直接异常退出）。

`bowtie2-build.bat` / `bowtie2-inspect.bat` 使用 `python`（启动器会把 venv 放到 PATH 前面）。

## GetOrganelle 改动摘要

- `platform.system() == "Windows"` → `SYSTEM_NAME = "Windows"`（主脚本、assembly、config 及 Utilities）
- `detect_bowtie2_path/detect_blast_path/detect_spades_path` 支持 `.exe` / `.bat`
- `spades.py`、`slim_graph.py` 通过 `sys.executable` 调用（Windows 不能直接执行 `.py`）
- `zip_file/unzip` 改为纯 Python（`gzip`/`tarfile`），不依赖 `tar/gunzip/head`
- `os.system("cp/head/ln/mv ...")` 改为 `shutil.copy` / `os.link` / Python 读写
- `os.rename` → `os.replace`（Windows 的 rename 不覆盖已存在文件）
- Bandage 检查加空路径保护；`&& mv` 拆成 Python 移动
- Windows 无 `SIGALRM`，`--time-limit` 装饰器退化为直接调用
- `Utilities/slim_graph.py`：Windows 下路径字符合法集加入 `:` 和 `\`（盘符/反斜杠），
  否则 `E:\...\K65` 会被判为“非法字符 `:`”
- `GetOrganelleLib/seq_parser.py`：`SequenceList(file, indexed=True)` 中 `read_fasta()`
  经 `append()` 已填好索引，原代码随后又断言“标签不在索引中”，必然触发 `AssertionError`；
  改为重建索引后再查重（该上游 bug 与平台无关，仅在“SPAdes scaffolds 补洞”路径触发）
- `GetOrganelleLib/pipe_control_func.py`：`executable()` 不再解码子进程输出。中文
  Windows 下 `cmd.exe` 的“找不到命令”是 GBK 编码；若 Python 处于 UTF-8 模式
  （`PYTHONUTF8=1`），`subprocess.getstatusoutput()` 用 UTF-8 解码会抛
  `UnicodeDecodeError`。改为只检查返回码，避免 GUI/agent 环境启用 UTF-8 模式时崩溃
- `download_file_with_progress()` 在下载失败/校验失败时先关闭临时文件句柄再删除；
  Windows 不允许删除仍打开的文件，旧逻辑会抛 `PermissionError` 并留下 `.Temp`

## 使用

初始化数据库（已执行过 `embplant_pt,embplant_mt`，位于 `C:\Users\<user>\.GetOrganelle`）：

```bat
run_get_organelle_config.bat -a embplant_pt,embplant_mt
```

运行 reads 流程：

```bat
run_get_organelle_reads.bat -1 R1.fq -2 R2.fq -F embplant_pt -o out -R 15 -k 21,45,65,85,105 -t 8
```

运行 assembly 流程：

```bat
run_get_organelle_assembly.bat -a assembly.fasta -F embplant_pt -o out -t 8
```

三个 `.bat` 会把 `venv\Scripts`、bowtie2、ncbi-blast、SPAdes\bin 放到 PATH 前面。

## 桌面 GUI（GetOrganelle Workbench）

`gui/` 提供按 YR-MPE 标准实现的 PyQt5 工作台（**Windows-first**，见
`gui/NOTE.md`）：

- 工作流 `Inputs → Preprocess → Parameters → Run → Results`，左侧 workflow
  rail、右侧 inspector、底部 Job Center；
- 细胞器类型支持多选，输出 `-F embplant_pt,embplant_mt`；plastome/mitogenome
  数据库按 GetOrganelle 规则成对校验；
- 可选 fastp 预处理：接头自动检测/自定义、质量/长度过滤、去重、首尾裁剪；
  fastp JSON/HTML 报告与 trimmed reads 写入 workspace 的 `_workbench` 目录；
- 界面密度以 raxmlGUI 2.0 为参考：正文 13 px、caption 11 px、默认 1280×800；
- 参数 Basic/Advanced 分层、内联校验、命令行预览；
- 非模态 QProcess 任务、实时日志、单一 Cancel（Windows 下 `taskkill /T /F`
  终止整棵进程树）、结果横幅与空状态；
- `ResultSpec`（`yrmpe.result.v1`）、`control_bindings()`、skill 文档与
  `run.json` 溯源，可按 YR-MPE 插件契约导出；
- headless CLI：`python -m getorganelle_gui.cli inspect|check|run --json`；
- 浅/深色语义色 tokens，状态均为“图标 + 文字 + 颜色”。

GUI 使用 PyQt5（与 YR-MPE 一致），因此只有 x64 轮子；arm64 包保留完整命令行
与 headless CLI。`setup_venv.bat` 会在 x64 上自动安装 `gui/requirements.txt`。

## 验证结果（2026-11-11）

| 测试 | 结果 |
| --- | --- |
| `spades.py --test`（native SPAdes 自检） | 通过（exit 0，产出 contigs） |
| K45 预组装，`more.fq`（80,000 reads） | 通过；de Bruijn 顶点数 29889，与 MSYS2 对照完全一致（修复前 29890 并崩溃） |
| 完整 GetOrganelle reads 流程（embplant_pt，`-k 21,45,65 -R 1`） | 通过（exit 0，日志 0 条 ERROR），输出 6 scaffolds |
| GetOrganelle assembly 流程（`-g` GFA 输入） | 通过（exit 0），输出 6 scaffolds |
| GUI 驱动完整 reads 流程（JobRunner/QProcess） | 通过（status success，6 scaffolds，12,695 bp，run.json 写入） |
| GUI 驱动 fastp → GetOrganelle 完整流水线 | 通过（fastp 40,000 → 40,000 reads，随后 6 scaffolds，exit 0） |
| GUI multi-organelle 选择（`embplant_pt,embplant_mt`） | 通过；`-F` 列表、默认 -R 30、数据库成对校验 |
| GUI headless CLI `inspect` / `check` / `run --json` | 通过；输出 `yrmpe.result.v1`；`--preprocess` 时含 `fastp-preprocess` + `getorganelle-reads` 两个 RunSpec |
| GUI 单元测试（command/validation/results）与离屏 smoke | 通过 |
| `spades-core.exe` DLL 依赖 | 仅 KERNEL32/dbghelp/msvcrt + 随附的 libgcc/libstdc++/libgomp/libwinpthread，**无 msys-2.0.dll** |
| `bowtie2-align-s.exe` / `samtools.exe` DLL 依赖 | 仅系统 DLL，**无 msys-2.0.dll** |

## fastp（预处理阶段）

- 源码来自 `E:/Codes/Fastp`，以 `vendor/fastp` 快照纳入仓库；版本 1.0.1。
- MinGW 兼容补丁：
  - `src/unistd.h`：`ssize_t/off_t/pid_t/uid_t/gid_t/useconds_t` 的 typedef 仅在
    `_MSC_VER` 下定义，避免与 mingw-w64 冲突；
  - `src/cxxabi.cpp`：MinGW 下用 `snprintf` 兼容 `strcpy_s`。
- `scripts/build_fastp.sh` 用 Makefile 静态链接 isa-l/libdeflate；产物仅依赖
  系统 DLL（无 msys-2.0.dll）。
- GetOrganelle 输出目录不会在运行前创建，日志写到
  `<workspace>/_workbench/logs/`；这避免 `--overwrite` 删除输出目录时被占用。

## 已知限制

- `bowtie2` 包装器需要 Perl；`bowtie2-build` 需要 PATH 中有 `python`（启动器已处理）。
- Windows 版 Bowtie2 不支持 mmap / shared memory；`--mm` 会被包装器静默移除。
- 输出/输入路径建议不要包含空格（GetOrganelle 内部命令拼接未全面加引号）。
- Bandage 可视化是可选的；未安装时自动跳过。
- `--time-limit` 在 Windows 上不生效。
- samtools 不参与 GetOrganelle 主流程，仅作为额外组件提供。
