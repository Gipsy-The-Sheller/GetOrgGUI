# GetOrganelle Windows 原生移植

把 [GetOrganelle](https://github.com/Kinggerm/GetOrganelle) 及其依赖移植到
**原生 Windows**：不需要 MSYS2 / Cygwin bash，所有可执行文件都不依赖
`msys-2.0.dll`。

仓库自带完整源码、构建脚本和 GitHub Actions 工作流，可自动构建并打包
Windows x86_64 与 Windows arm64 两个版本。

## 组件版本

| 组件 | 版本 | 构建方式 |
| --- | --- | --- |
| GetOrganelle | 1.8.0.1 | 纯 Python（含 Windows 补丁） |
| SPAdes | 4.3.0-dev | MinGW-w64 原生构建 |
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
├─ GetOrganelleGUI.bat    GUI 启动器
├─ run_get_organelle_*.bat
├─ .github/workflows/build.yml
├─ PORTING_NOTES.md       移植过程、补丁清单与验证记录
└─ README.md
```

`GetOrganelle/GetOrganelleDep/`、`build/`、`stage/`、`venv/` 等运行/构建产物
不会提交到仓库。

## 本地构建

在 MSYS2 的 MINGW64 shell 中：

```bash
pacman -S --needed \
  mingw-w64-x86_64-toolchain mingw-w64-x86_64-cmake mingw-w64-x86_64-ninja \
  mingw-w64-x86_64-zlib mingw-w64-x86_64-libgnurx mingw-w64-x86_64-libsystre \
  mingw-w64-x86_64-libtre mingw-w64-x86_64-gettext mingw-w64-x86_64-libiconv \
  mingw-w64-x86_64-pkgconf zip

export TARGET_ARCH=x86_64
./scripts/build_all.sh     # SPAdes + fastp + Bowtie2 + samtools + BLAST+
./scripts/package.sh       # 生成 build/ci-x64/GetOrganelle-Windows-x64-*.zip
```

arm64 构建在 Windows 11 ARM64 的 MSYS2 `CLANGARM64` shell 中进行，设置
`TARGET_ARCH=arm64` 后执行同样的命令。

构建产物先写入 `stage/<arch>/`，最终包会放到 `GetOrganelle/GetOrganelleDep/Windows/`
并按发行包布局打包。

## CI/CD

`.github/workflows/build.yml` 定义：

- 推送到 `main` / `master`、Pull Request、手动触发：分别构建 x86_64 与 arm64，
  上传 `GetOrganelle-Windows-x64.zip` / `GetOrganelle-Windows-arm64.zip` 及 SHA256。
- 推送 `v*` 标签：构建完成后自动创建 GitHub Release 并附带两个发行包。

> arm64 任务使用 GitHub 托管的 `windows-11-arm` 运行器。公开仓库可免费使用；
> 私有仓库请确认账户/计划是否包含 arm64 标准运行器，或配置自托管运行器。

## 发行包使用

1. 安装 Python 3.10+ 与 Perl（Strawberry Perl 或 Git for Windows 自带的 Perl）。
2. 运行 `setup_venv.bat` 创建 Python 环境。
3. `run_get_organelle_config.bat -a embplant_pt,embplant_mt` 初始化数据库。
4. 用 `run_get_organelle_reads.bat` 或 `run_get_organelle_assembly.bat` 运行。

### 桌面 GUI

双击 `GetOrganelleGUI.bat` 启动 **GetOrganelle Workbench**（Inputs →
Preprocess → Parameters → Run → Results）。它按 YR-MPE 的插件契约与 UI
审计实现：多细胞器类型、可选 fastp 接头裁剪/过滤、参数 Basic/Advanced
分层、内联校验、非模态后台任务、Job Center、结果预览、`run.json` 溯源、
数据库管理与浅/深色主题。GFA/FASTG 还可在内置的 Bandage 风格交互查看器中
按节点长度/弯曲多段折线绘制，支持覆盖度着色、搜索、拖动、缩放与 PNG 导出。
查看器还可用内置 BLAST+ 对用户提供的 GenBank 参考做 `blastn`（全量）或
`tblastn`（注释 CDS）筛选，并按 E 值/一致性/比对长度/不同基因数高亮候选
叶绿体 contig；详见 `gui/README.md` 与 `gui/NOTE.md`（Windows-first）。

同一套模型还提供 headless / agent 接口：

```bat
set PYTHONPATH=%CD%\gui
venv\Scripts\python.exe -m getorganelle_gui.cli inspect --json
venv\Scripts\python.exe -m getorganelle_gui.cli run --mode reads --reads1 R1.fq.gz --reads2 R2.fq.gz --organelle embplant_pt --workspace runs --run-name sample --json
```

输出为 `yrmpe.result.v1` ResultSpec。

详见 `packaging/README-Windows.md`。

## 已知限制

- Bowtie2 的 Windows 构建不支持 mmap / 共享内存，`--mm` 会被包装器移除。
- `--time-limit` 在 Windows 上不生效。
- 路径建议不含空格；Bandage 可视化可选。
- 内置图查看器的参考 BLAST 使用本地 BLAST+，不连接 NCBI；单文件上限
  80 MB，重图请用 Bandage/Bandage-NG。
- E 值不能单独排除 NUMT/NUPT；请结合多个注释基因、节点覆盖度与 reads
  支持人工确认。
- arm64 版 BLAST+ 依赖 Windows 11 的 x64 模拟；Biopython 在 arm64 上暂不安装。

## 许可证

- GetOrganelle：GPLv3
- SPAdes：GPLv2
- Bowtie2：GPLv3
- samtools / htslib：MIT / Expat
- NCBI BLAST+：见其 `LICENSE`

各组件原始许可证文件均保留在对应源码/安装目录中。
