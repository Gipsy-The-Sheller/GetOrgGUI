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
│  └─ samtools/           samtools 1.25 + htslib 源码
├─ packaging/             最终用户发行包所需的启动器与说明
├─ scripts/               本地/CI 构建脚本
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
./scripts/build_all.sh     # SPAdes + Bowtie2 + samtools + BLAST+
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

详见 `packaging/README-Windows.md`。

## 已知限制

- Bowtie2 的 Windows 构建不支持 mmap / 共享内存，`--mm` 会被包装器移除。
- `--time-limit` 在 Windows 上不生效。
- 路径建议不含空格；Bandage 可视化可选。
- arm64 版 BLAST+ 依赖 Windows 11 的 x64 模拟；Biopython 在 arm64 上暂不安装。

## 许可证

- GetOrganelle：GPLv3
- SPAdes：GPLv2
- Bowtie2：GPLv3
- samtools / htslib：MIT / Expat
- NCBI BLAST+：见其 `LICENSE`

各组件原始许可证文件均保留在对应源码/安装目录中。
