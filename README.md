# GetOrganelle Native Cross-Platform Port

[中文](#中文)

Native builds of [GetOrganelle](https://github.com/Kinggerm/GetOrganelle) and
its toolchain for **Windows x86_64/arm64, Linux x86_64/arm64, and macOS
arm64**. The Windows packages run without MSYS2 or Cygwin; Linux and macOS use
their native toolchains.

The repository contains complete source snapshots, build scripts, and a GitHub
Actions matrix that produces:

| Target | Toolchain | Package |
| --- | --- | --- |
| Windows x86_64 | MSYS2 `MINGW64` (GCC) | `GetOrganelle-Windows-x64-*.zip` |
| Windows arm64 | MSYS2 `CLANGARM64` (Clang/LLD) | `GetOrganelle-Windows-arm64-*.zip` |
| Linux x86_64 | Ubuntu 22.04 (GCC) | `GetOrganelle-Linux-x64-*.tar.gz` |
| Linux arm64 | Ubuntu 22.04 arm64 (GCC) | `GetOrganelle-Linux-arm64-*.tar.gz` |
| macOS arm64 | Apple Clang + Homebrew libomp | `GetOrganelle-macOS-arm64-*.tar.gz` |

Bundled components: GetOrganelle 1.8.0.1, SPAdes 4.3.0, Bowtie2 2.5.5, fastp
1.0.1, samtools/htslib 1.25, NCBI BLAST+ 2.17.0, and the PyQt5 Workbench GUI
and headless CLI (version 0.3.0).

## Component versions

| Component | Version | Build |
| --- | --- | --- |
| GetOrganelle | 1.8.0.1 | Pure Python, with Windows patches |
| SPAdes | 4.3.0 | Native build (MinGW-w64, GCC, or Apple Clang) |
| Bowtie2 | 2.5.5 | Native build (MinGW-w64, GCC, or Apple Clang) |
| fastp | 1.0.1 | Native build; static on Windows, ISA-L shared on Linux, Homebrew static archives on macOS |
| samtools / htslib | 1.25 | Native build, static link |
| NCBI BLAST+ | 2.17.0 | Official Windows x64, Linux x64/arm64, and macOS arm64 binaries |
| Python | 3.10+ | numpy, gekko, requests |

## Architecture support

| Target | Toolchain | Notes |
| --- | --- | --- |
| Windows x86_64 | MSYS2 `MINGW64` (GCC) | All components built natively |
| Windows arm64 | MSYS2 `CLANGARM64` (Clang/LLVM) | SPAdes, Bowtie2, and samtools native arm64; BLAST+ uses the official x64 archive through Windows 11 x64 emulation |
| Ubuntu 22.04 x86_64 | GCC / CMake / Ninja | All components built natively; fastp's ISA-L shared library is bundled |
| Ubuntu 22.04 arm64 | GCC / CMake / Ninja | All components built natively for arm64; official aarch64 BLAST+ |
| macOS arm64 | Apple Clang + Homebrew libomp | All components built natively for arm64; system libraries are provided by macOS |

The Linux and macOS build scripts detect the platform and place dependencies in
`GetOrganelle/GetOrganelleDep/linux` or `.../macOS`, following GetOrganelle's
own naming.

## Repository layout

```text
.
├─ GetOrganelle/          GetOrganelle 1.8.0.1 source (with Windows patches)
├─ vendor/
│  ├─ spades/             Patched SPAdes source snapshot
│  ├─ bowtie2/            Bowtie2 2.5.5 source (with wrapper patches)
│  ├─ fastp/              fastp 1.0.1 source (with MinGW compatibility patches)
│  └─ samtools/           samtools 1.25 + htslib source
├─ gui/                   PyQt5 desktop GUI (YR-MPE style) and headless CLI
├─ packaging/             Launchers and notes for the end-user packages
├─ scripts/               Local and CI build scripts
├─ GetOrganelleGUI.bat    Windows GUI launcher
├─ GetOrganelleGUI.sh     Linux/macOS GUI launcher
├─ run_get_organelle_*.bat / *.sh
├─ .github/workflows/build.yml
├─ PORTING_NOTES.md       Porting record, patch list, and verification
└─ README.md
```

`GetOrganelle/GetOrganelleDep/`, `build/`, `stage/`, and `venv/` are runtime or
build products and are not committed.

## Local build

### Windows (MSYS2)

In an MSYS2 MINGW64 shell:

```bash
pacman -S --needed \
  mingw-w64-x86_64-toolchain mingw-w64-x86_64-cmake mingw-w64-x86_64-ninja \
  mingw-w64-x86_64-zlib mingw-w64-x86_64-bzip2 mingw-w64-x86_64-libdeflate \
  mingw-w64-x86_64-isa-l mingw-w64-x86_64-libsystre mingw-w64-x86_64-libtre \
  mingw-w64-x86_64-gettext-runtime mingw-w64-x86_64-libiconv \
  mingw-w64-x86_64-pkgconf zip

export TARGET_ARCH=x86_64
./scripts/build_all.sh     # SPAdes + fastp + Bowtie2 + samtools + BLAST+
./scripts/package.sh       # build/ci-x64/GetOrganelle-Windows-x64-*.zip
```

For arm64, use the MSYS2 `CLANGARM64` shell on Windows 11 ARM64, set
`TARGET_ARCH=arm64`, and run the same commands.

### Ubuntu 22.04 (x86_64 / arm64)

```bash
sudo apt-get install -y build-essential cmake ninja-build pkg-config \
  zlib1g-dev libbz2-dev libisal-dev libdeflate-dev perl curl zip
./scripts/build_all.sh x86_64    # use arm64 on an arm64 machine
./scripts/package.sh x86_64      # use arm64 on an arm64 machine
# build/ci-linux-x64/GetOrganelle-Linux-x64-*.tar.gz
# or build/ci-linux-arm64/GetOrganelle-Linux-arm64-*.tar.gz
```

### macOS (Apple Silicon)

```bash
brew install cmake ninja bzip2 libomp isa-l libdeflate pkg-config
./scripts/build_all.sh arm64
./scripts/package.sh arm64
# build/ci-macos-arm64/GetOrganelle-macOS-arm64-*.tar.gz
```

Build products are first written to `stage/<platform>-<arch>/`; final packages
are placed under `GetOrganelle/GetOrganelleDep/Windows|linux|macOS/` in the
release layout.

## CI/CD

`.github/workflows/build.yml` defines:

- pushes to `main`/`master`, pull requests, and manual runs: build Windows
  x86_64, Windows arm64, Linux x86_64, Linux arm64, and macOS arm64, and
  upload the archives plus SHA-256 checksums;
- version tags (for example `v0.3.0` or `0.3.0`): after a successful build,
  create a GitHub Release with the five archives.

> The arm64 jobs use GitHub-hosted `windows-11-arm` runners. They are free for
> public repositories. Private repositories should confirm that their plan
> includes arm64 runners or configure a self-hosted runner.

## Using the release packages

Windows:

1. Install Python 3.10+ and Perl (Strawberry Perl or the Perl bundled with Git
   for Windows).
2. Run `setup_venv.bat` to create the Python environment.
3. Run `run_get_organelle_config.bat -a embplant_pt,embplant_mt` to initialize
   the databases. `embplant_nr`, `fungus_mt`, `fungus_nr`, `animal_mt`, and
   `other_pt` can also be installed, or use `-a all` for every database. The
   GUI's **Manage databases…** page supports per-type install, update, and
   remove.
4. Run `run_get_organelle_reads.bat` or `run_get_organelle_assembly.bat`.

Linux / macOS:

1. Install Python 3.10+ (Linux also needs `python3-venv`) and Perl.
2. Run `./setup_venv.sh`.
3. Run `./run_get_organelle_config.sh -a embplant_pt,embplant_mt`.
4. Run `./run_get_organelle_reads.sh` or
   `./run_get_organelle_assembly.sh`; start the GUI with
   `./GetOrganelleGUI.sh`.

### Desktop GUI

Double-click `GetOrganelleGUI.bat` to start **GetOrganelle Workbench** (Inputs
→ Preprocess → Parameters → Run → Results). It follows the YR-MPE plugin
contract and UI audit: multiple organelle types, optional fastp adapter
trimming and quality/length filtering, a Gb-scale limit on primary reads (0.1 Gb
precision), Basic/Advanced parameter tiers, inline validation, non-modal
background jobs, a Job Center, result preview, `run.json` provenance, database
management, and light/dark themes. GFA/FASTG graphs can be explored in the
built-in Bandage-style viewer, which draws nodes as curved multi-segment
polylines proportional to length and supports coverage colouring, search,
dragging, zooming, and PNG export. The viewer can also run the bundled BLAST+
against a user-supplied GenBank record in full-record `blastn` or annotated-CDS
`tblastn` mode and highlight candidate chloroplast contigs by E-value,
identity, alignment length, and number of distinct annotated genes. See
`gui/README.md` and `gui/NOTE.md` (Windows-first; the Windows x64, Linux x64,
and macOS arm64 packages include the GUI; Windows arm64 and Linux arm64 are
CLI/headless only).

The same model provides a headless / agent interface:

```bat
set PYTHONPATH=%CD%\gui
venv\Scripts\python.exe -m getorganelle_gui.cli inspect --json
venv\Scripts\python.exe -m getorganelle_gui.cli run --mode reads --reads1 R1.fq.gz --reads2 R2.fq.gz --organelle embplant_pt --workspace runs --run-name sample --json
```

```bash
export PYTHONPATH="$PWD/gui"
venv/bin/python -m getorganelle_gui.cli inspect --json
venv/bin/python -m getorganelle_gui.cli run --mode reads --reads1 R1.fq.gz --reads2 R2.fq.gz --organelle embplant_pt --workspace runs --run-name sample --json
```

The output is a `yrmpe.result.v1` ResultSpec.

The GUI can be embedded as a YRTools `polypyplug` tab via
`gui/settings.json` (entry point
`getorganelle_gui.yrtools_entry:GetOrganelleEntry`; `MainWindow.run()` returns
`self`). On the agent side, the stable boundaries are the headless CLI,
`control_bindings()`, and the skill documentation; there is no in-process
`AgentBridge`. See `gui/README.md`.

See `packaging/README-Windows.md` for package details.

## Documentation

- `gui/README.md` — GUI, headless CLI, and embedding.
- `gui/NOTE.md` — Windows-first UI notes and audit.
- `packaging/README-Windows.md` — Windows package usage.
- `PORTING_NOTES.md` — porting record, patches, and verification.
- `case_study/arabidopsis_col0_SRR30886772/` — worked 5 Gb Col-0 example.
- `manuscript/` — ODE Methods paper and LaTeX source.

## Known limitations

- Bowtie2's Windows build does not support mmap or shared memory; `--mm` is
  removed by the wrapper.
- `--time-limit` has no effect on Windows.
- Paths should not contain spaces; Bandage visualization is optional.
- The built-in graph viewer's reference BLAST uses local BLAST+ and does not
  contact NCBI; the per-file limit is 80 MB. Use Bandage or Bandage-NG for
  larger graphs.
- E-values alone cannot exclude NUMT/NUPT; confirm candidates with multiple
  annotated genes, node coverage, and read support.
- The Windows arm64 BLAST+ build uses x64 emulation on Windows 11; Biopython is
  not installed on Windows arm64.
- Linux packages are built on Ubuntu 22.04 and target glibc 2.35+; macOS
  packages are built on the `macos-15` runner and target macOS 15+ on Apple
  Silicon. The `libomp.dylib` required by SPAdes is bundled.

## License

- **GetOrganelle Workbench original code** (GUI, CLI, tests, build scripts, CI,
  documentation): **AGPL-3.0-only**; see `LICENSE` and `NOTICE.md`.
- GetOrganelle: GPLv3.
- SPAdes: GPLv2.
- Bowtie2: GPLv3.
- fastp: MIT.
- samtools / htslib: MIT / Expat.
- NCBI BLAST+: public domain; see its `LICENSE`.
- PyQt5: GPLv3 or a commercial license (GUI dependency; not distributed with
  the source repository).

AGPL covers only the original code in this repository and does not relicense
vendored third-party sources. Original license files remain in each component's
source or installation directory; release packages also include `NOTICE.md` and
`SOURCE_MANIFEST.md`. Corresponding source:
<https://github.com/Gipsy-The-Sheller/GetOrgGUI>.

## 中文


把 [GetOrganelle](https://github.com/Kinggerm/GetOrganelle) 及其依赖移植到
多个原生平台：Windows 版本不需要 MSYS2 / Cygwin bash，所有可执行文件都不依赖
`msys-2.0.dll`；Linux 与 macOS（Apple Silicon）版本直接用系统工具链构建。

仓库自带完整源码、构建脚本和 GitHub Actions 工作流，可自动构建并打包
Windows x86_64、Windows arm64、Linux x86_64、Linux arm64 与 macOS arm64
五个版本。

### 组件版本

| 组件 | 版本 | 构建方式 |
| --- | --- | --- |
| GetOrganelle | 1.8.0.1 | 纯 Python（含 Windows 补丁） |
| SPAdes | 4.3.0 | 原生构建（MinGW-w64 / GCC / Apple Clang） |
| Bowtie2 | 2.5.5 | 原生构建（MinGW-w64 / GCC / Apple Clang） |
| fastp | 1.0.1 | 原生构建，静态链接（可选预处理） |
| samtools / htslib | 1.25 | 原生构建，静态链接 |
| NCBI BLAST+ | 2.17.0 | 官方 Windows x64 / Linux x64 / Linux arm64 / macOS arm64 二进制 |
| Python | 3.10+ | numpy / gekko / requests |

### 架构支持

| 目标 | 工具链 | 说明 |
| --- | --- | --- |
| Windows x86_64 | MSYS2 `MINGW64`（GCC） | 全部组件原生构建 |
| Windows arm64 | MSYS2 `CLANGARM64`（Clang/LLVM） | SPAdes / Bowtie2 / samtools 原生 arm64；BLAST+ 使用官方 x64 版本（Windows 11 x64 模拟） |
| Ubuntu 22.04 x86_64 | GCC / CMake / Ninja | 全部组件原生构建；fastp 的 ISA-L 动态库随包分发 |
| Ubuntu 22.04 arm64 | GCC / CMake / Ninja | 全部组件原生 arm64 构建；使用官方 aarch64 BLAST+ |
| macOS arm64 | Apple Clang + Homebrew libomp | 全部组件原生 arm64；需 glibc 之外的系统库由 macOS 提供 |

Linux 与 macOS 的构建脚本会自动识别平台，并把依赖放入
`GetOrganelle/GetOrganelleDep/linux` 或 `.../macOS`（GetOrganelle 自身的命名）。

### 仓库结构

```
.
├─ GetOrganelle/          GetOrganelle 1.8.0.1 源码（含 Windows 补丁）
├─ vendor/
│  ├─ spades/             已打补丁的 SPAdes 源代码快照
│  ├─ bowtie2/            Bowtie2 2.5.5 源码（含包装器补丁）
│  ├─ fastp/              fastp 1.0.1 源码（含 MinGW 兼容补丁）
│  └─ samtools/           samtools 1.25 + htslib 源码
├─ gui/                   PyQt5 桌面 GUI（YR-MPE 风格）与 headless CLI
├─ packaging/             最终用户发行包所需的启动器与说明
├─ scripts/               本地/CI 构建脚本
├─ GetOrganelleGUI.bat    Windows GUI 启动器
├─ GetOrganelleGUI.sh     Linux/macOS GUI 启动器
├─ run_get_organelle_*.bat / *.sh
├─ .github/workflows/build.yml
├─ PORTING_NOTES.md       移植过程、补丁清单与验证记录
└─ README.md
```

`GetOrganelle/GetOrganelleDep/`、`build/`、`stage/`、`venv/` 等运行/构建产物
不会提交到仓库。

### 本地构建

#### Windows（MSYS2）

在 MSYS2 的 MINGW64 shell 中：

```bash
pacman -S --needed \
  mingw-w64-x86_64-toolchain mingw-w64-x86_64-cmake mingw-w64-x86_64-ninja \
  mingw-w64-x86_64-zlib mingw-w64-x86_64-bzip2 mingw-w64-x86_64-libdeflate \
  mingw-w64-x86_64-isa-l mingw-w64-x86_64-libsystre mingw-w64-x86_64-libtre \
  mingw-w64-x86_64-gettext-runtime mingw-w64-x86_64-libiconv \
  mingw-w64-x86_64-pkgconf zip

export TARGET_ARCH=x86_64
./scripts/build_all.sh     # SPAdes + fastp + Bowtie2 + samtools + BLAST+
./scripts/package.sh       # 生成 build/ci-x64/GetOrganelle-Windows-x64-*.zip
```

arm64 构建在 Windows 11 ARM64 的 MSYS2 `CLANGARM64` shell 中进行，设置
`TARGET_ARCH=arm64` 后执行同样的命令。

#### Ubuntu 22.04（x86_64 / arm64）

```bash
sudo apt-get install -y build-essential cmake ninja-build pkg-config \
  zlib1g-dev libbz2-dev libisal-dev libdeflate-dev perl curl zip
./scripts/build_all.sh x86_64    # arm64 机器上改为 arm64
./scripts/package.sh x86_64      # arm64 机器上改为 arm64
# 生成 build/ci-linux-x64/GetOrganelle-Linux-x64-*.tar.gz
# 或   build/ci-linux-arm64/GetOrganelle-Linux-arm64-*.tar.gz
```

#### macOS（Apple Silicon）

```bash
brew install cmake ninja bzip2 libomp isa-l libdeflate pkg-config
./scripts/build_all.sh arm64
./scripts/package.sh arm64
# 生成 build/ci-macos-arm64/GetOrganelle-macOS-arm64-*.tar.gz
```

构建产物先写入 `stage/<platform>-<arch>/`，最终包会放到
`GetOrganelle/GetOrganelleDep/Windows|linux|macOS/` 并按发行包布局打包。

### CI/CD

`.github/workflows/build.yml` 定义：

- 推送到 `main` / `master`、Pull Request、手动触发：构建 Windows x86_64、
  Windows arm64、Linux x86_64、Linux arm64、macOS arm64，并上传对应压缩包及 SHA256。
- 推送版本标签（如 `v0.3.0` 或 `0.3.0`）：构建完成后自动创建 GitHub
  Release 并附带五个发行包。

> arm64 任务使用 GitHub 托管的 `windows-11-arm` 运行器。公开仓库可免费使用；
> 私有仓库请确认账户/计划是否包含 arm64 标准运行器，或配置自托管运行器。

### 发行包使用

Windows：

1. 安装 Python 3.10+ 与 Perl（Strawberry Perl 或 Git for Windows 自带的 Perl）。
2. 运行 `setup_venv.bat` 创建 Python 环境。
3. `run_get_organelle_config.bat -a embplant_pt,embplant_mt` 初始化数据库；
   也可安装 `embplant_nr`、`fungus_mt`、`fungus_nr`、`animal_mt`、`other_pt`，
   或用 `-a all` 安装全部。GUI 的 **Manage databases…** 支持逐类安装/更新/删除。
4. 用 `run_get_organelle_reads.bat` 或 `run_get_organelle_assembly.bat` 运行。

Linux / macOS：

1. 安装 Python 3.10+（Linux 还需 `python3-venv`）与 Perl。
2. 运行 `./setup_venv.sh`。
3. `./run_get_organelle_config.sh -a embplant_pt,embplant_mt` 初始化数据库。
4. `./run_get_organelle_reads.sh` 或 `./run_get_organelle_assembly.sh` 运行；
   GUI 用 `./GetOrganelleGUI.sh` 启动。

#### 桌面 GUI

双击 `GetOrganelleGUI.bat` 启动 **GetOrganelle Workbench**（Inputs →
Preprocess → Parameters → Run → Results）。它按 YR-MPE 的插件契约与 UI
审计实现：多细胞器类型、可选 fastp 接头裁剪/过滤与按 Gb 限制主 reads
数据量（0.1 Gb 精度），参数 Basic/Advanced
分层、内联校验、非模态后台任务、Job Center、结果预览、`run.json` 溯源、
数据库管理与浅/深色主题。GFA/FASTG 还可在内置的 Bandage 风格交互查看器中
按节点长度/弯曲多段折线绘制，支持覆盖度着色、搜索、拖动、缩放与 PNG 导出。
查看器还可用内置 BLAST+ 对用户提供的 GenBank 参考做 `blastn`（全量）或
`tblastn`（注释 CDS）筛选，并按 E 值/一致性/比对长度/不同基因数高亮候选
叶绿体 contig；详见 `gui/README.md` 与 `gui/NOTE.md`（Windows-first；
Windows x64、Linux x64、macOS arm64 发行包含 GUI，Windows arm64 与
Linux arm64 仅命令行/headless CLI）。

同一套模型还提供 headless / agent 接口：

```bat
set PYTHONPATH=%CD%\gui
venv\Scripts\python.exe -m getorganelle_gui.cli inspect --json
venv\Scripts\python.exe -m getorganelle_gui.cli run --mode reads --reads1 R1.fq.gz --reads2 R2.fq.gz --organelle embplant_pt --workspace runs --run-name sample --json
```

输出为 `yrmpe.result.v1` ResultSpec。

GUI 可通过 `gui/settings.json` 作为 YRTools `polypyplug` 插入宿主标签页
（入口 `getorganelle_gui.yrtools_entry:GetOrganelleEntry`，`MainWindow.run()`
返回 `self`）；agent 侧目前以 headless CLI 和 `control_bindings()`/skill
文档为稳定边界，不提供进程内 `AgentBridge`。详见 `gui/README.md`。

详见 `packaging/README-Windows.md`。

### 已知限制

- Bowtie2 的 Windows 构建不支持 mmap / 共享内存，`--mm` 会被包装器移除。
- `--time-limit` 在 Windows 上不生效。
- 路径建议不含空格；Bandage 可视化可选。
- 内置图查看器的参考 BLAST 使用本地 BLAST+，不连接 NCBI；单文件上限
  80 MB，重图请用 Bandage/Bandage-NG。
- E 值不能单独排除 NUMT/NUPT；请结合多个注释基因、节点覆盖度与 reads
  支持人工确认。
- Windows arm64 版 BLAST+ 依赖 Windows 11 的 x64 模拟；Biopython 在
  Windows arm64 上暂不安装。
- Linux 包在 Ubuntu 22.04 上构建，面向 glibc 2.35+；macOS 包在 `macos-15`
  runner 上构建，面向 macOS 15+ Apple Silicon，SPAdes 所需的 `libomp.dylib`
  已随包附带。

### 许可证

- **GetOrganelle Workbench 原创代码**（GUI、CLI、测试、构建脚本、CI、文档）：
  **AGPL-3.0-only**，见 `LICENSE` 与 `NOTICE.md`
- GetOrganelle：GPLv3
- SPAdes：GPLv2
- Bowtie2：GPLv3
- fastp：MIT
- samtools / htslib：MIT / Expat
- NCBI BLAST+：public domain，见其 `LICENSE`
- PyQt5：GPLv3 或商业许可（GUI 依赖，不随源码仓库分发）

AGPL 仅覆盖本仓库原创代码，不会重新许可 vendored 第三方源码。各组件原始
许可证文件均保留在对应源码/安装目录中；发行包还包含 `NOTICE.md` 与
`SOURCE_MANIFEST.md`。对应源码：
<https://github.com/Gipsy-The-Sheller/GetOrgGUI>。
