# GetOrganelle 原生跨平台移植（Windows / Linux / macOS）

把 [GetOrganelle](https://github.com/Kinggerm/GetOrganelle) 及其依赖移植到
多个原生平台：Windows 版本不需要 MSYS2 / Cygwin bash，所有可执行文件都不依赖
`msys-2.0.dll`；Linux 与 macOS（Apple Silicon）版本直接用系统工具链构建。

仓库自带完整源码、构建脚本和 GitHub Actions 工作流，可自动构建并打包
Windows x86_64、Windows arm64、Linux x86_64 与 macOS arm64 四个版本。

## 组件版本

| 组件 | 版本 | 构建方式 |
| --- | --- | --- |
| GetOrganelle | 1.8.0.1 | 纯 Python（含 Windows 补丁） |
| SPAdes | 4.3.0 | MinGW-w64 原生构建 |
| Bowtie2 | 2.5.5 | MinGW-w64 原生构建，静态运行时 |
| fastp | 1.0.1 | MinGW-w64 原生构建，静态链接（可选预处理） |
| samtools / htslib | 1.25 | MinGW-w64 原生构建，静态链接 |
| NCBI BLAST+ | 2.17.0 | 官方 Windows x64 二进制 |
| Python | 3.10+ | numpy / gekko / requests |

## 架构支持

| 目标 | 工具链 | 说明 |
| --- | --- | --- |
| Windows x86_64 | MSYS2 `MINGW64`（GCC） | 全部组件原生构建 |
| Windows arm64 | MSYS2 `CLANGARM64`（Clang/LLVM） | SPAdes / Bowtie2 / samtools 原生 arm64；BLAST+ 使用官方 x64 版本（Windows 11 x64 模拟） |
| Ubuntu 22.04 x86_64 | GCC / CMake / Ninja | 全部组件原生构建；fastp 的 ISA-L 动态库随包分发 |
| macOS arm64 | Apple Clang + Homebrew libomp | 全部组件原生 arm64；需 glibc 之外的系统库由 macOS 提供 |

Linux 与 macOS 的构建脚本会自动识别平台，并把依赖放入
`GetOrganelle/GetOrganelleDep/linux` 或 `.../macOS`（GetOrganelle 自身的命名）。

## 仓库结构

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

## 本地构建

### Windows（MSYS2）

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

### Ubuntu 22.04

```bash
sudo apt-get install -y build-essential cmake ninja-build pkg-config \
  zlib1g-dev libbz2-dev libisal-dev libdeflate-dev perl curl zip
./scripts/build_all.sh x86_64
./scripts/package.sh x86_64
# 生成 build/ci-linux-x64/GetOrganelle-Linux-x64-*.tar.gz
```

### macOS（Apple Silicon）

```bash
brew install cmake ninja bzip2 libomp isa-l libdeflate pkg-config
./scripts/build_all.sh arm64
./scripts/package.sh arm64
# 生成 build/ci-macos-arm64/GetOrganelle-macOS-arm64-*.tar.gz
```

构建产物先写入 `stage/<platform>-<arch>/`，最终包会放到
`GetOrganelle/GetOrganelleDep/Windows|linux|macOS/` 并按发行包布局打包。

## CI/CD

`.github/workflows/build.yml` 定义：

- 推送到 `main` / `master`、Pull Request、手动触发：构建 Windows x86_64、
  Windows arm64、Linux x86_64、macOS arm64，并上传对应压缩包及 SHA256。
- 推送 `v*` 标签：构建完成后自动创建 GitHub Release 并附带四个发行包。

> arm64 任务使用 GitHub 托管的 `windows-11-arm` 运行器。公开仓库可免费使用；
> 私有仓库请确认账户/计划是否包含 arm64 标准运行器，或配置自托管运行器。

## 发行包使用

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

### 桌面 GUI

双击 `GetOrganelleGUI.bat` 启动 **GetOrganelle Workbench**（Inputs →
Preprocess → Parameters → Run → Results）。它按 YR-MPE 的插件契约与 UI
审计实现：多细胞器类型、可选 fastp 接头裁剪/过滤、参数 Basic/Advanced
分层、内联校验、非模态后台任务、Job Center、结果预览、`run.json` 溯源、
数据库管理与浅/深色主题。GFA/FASTG 还可在内置的 Bandage 风格交互查看器中
按节点长度/弯曲多段折线绘制，支持覆盖度着色、搜索、拖动、缩放与 PNG 导出。
查看器还可用内置 BLAST+ 对用户提供的 GenBank 参考做 `blastn`（全量）或
`tblastn`（注释 CDS）筛选，并按 E 值/一致性/比对长度/不同基因数高亮候选
叶绿体 contig；详见 `gui/README.md` 与 `gui/NOTE.md`（Windows-first，但
Linux/macOS 发行包也包含 GUI）。

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

## 已知限制

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

## 许可证

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
