# GetOrganelle for Windows（原生移植版）

本发行包把 GetOrganelle 及其依赖编译为**原生 Windows 程序**，运行时不需要
MSYS2 / Cygwin，也不需要 `msys-2.0.dll`。

## 包含内容

```
GetOrganelle\                     GetOrganelle 1.8.0.1（含 Windows 补丁）
GetOrganelleDep\Windows\
  SPAdes\                         SPAdes 4.3.0（原生构建）
  bowtie2\                        Bowtie2 2.5.5（原生构建）
  fastp\                          fastp 1.0.1（可选预处理，原生静态构建）
  ncbi-blast\                     NCBI BLAST+ 2.17.0（blastn / tblastn / makeblastdb）
  samtools\bin\samtools.exe       samtools 1.25（可选）
run_get_organelle_reads.bat
run_get_organelle_assembly.bat
run_get_organelle_config.bat
GetOrganelleGUI.bat             桌面 GUI（YR-MPE 风格工作台）
gui\                            GUI 源码、测试与 headless CLI
setup_venv.bat
requirements.txt
```

## 系统要求

- Windows 10/11 x86_64，或 Windows 11 ARM64（arm64 包）
- Python 3.10+（64 位）
- Perl（Bowtie2 的 `bowtie2` 驱动脚本需要；可安装
  [Strawberry Perl](https://strawberryperl.com/) 或使用 Git for Windows 自带的 Perl）
- BLAST+ 需要 Microsoft Visual C++ 运行库（绝大多数系统已具备）

> arm64 发行包中 SPAdes / Bowtie2 / samtools 为原生 arm64；NCBI 未提供
> Windows arm64 版 BLAST+，因此使用官方 x64 版本，由 Windows 11 的 x64
> 模拟运行。GenBank 注释工具所需的 Biopython 暂无 arm64 轮子，已自动跳过。

## 快速开始

1. 安装 Python 3.10+，确认命令行可以运行 `python`（或 `py -3`）。
2. 双击或在命令行运行 `setup_venv.bat`，创建 `venv` 并安装依赖（x64 会同时安装 PyQt5）。
3. 初始化数据库（首次使用，二者需一起安装）：

```bat
run_get_organelle_config.bat -a embplant_pt,embplant_mt
rem 也可安装其他 GetOrganelleDB 类型，例如：
rem run_get_organelle_config.bat -a fungus_mt,animal_mt
rem 安装全部：run_get_organelle_config.bat -a all
```

4. 从 reads 组装：

```bat
run_get_organelle_reads.bat -1 R1.fq -2 R2.fq -F embplant_pt -o out -R 15 -k 21,45,65,85,105 -t 8
```

5. 从组装图组装：

```bat
run_get_organelle_assembly.bat -g assembly_graph.gfa -F embplant_pt -o out -t 8
```

三个 `.bat` 会自动把 `venv\Scripts` 与各依赖目录加入 `PATH`。

## 桌面 GUI

双击 `GetOrganelleGUI.bat` 启动 **GetOrganelle Workbench**（Windows-first）。
工作流为 Inputs → Preprocess → Parameters → Run → Results，包含：

- 多选细胞器类型（如 `embplant_pt,embplant_mt`）；
- 可选 fastp 预处理：接头自动检测/自定义、质量与长度过滤、JSON/HTML 报告；
- 参数 Basic / Advanced 分层、内联校验与命令预览；
- 非模态后台任务、实时日志、单一 Cancel、完成后的结果横幅；
- 结果表、FASTA/图文件预览、警告与 `run.json` 溯源；
- 数据库状态检查与一键安装（plastome/mitogenome 成对校验）；
- 浅色 / 深色主题，状态同时用图标、文字和颜色表达；
- 快捷键：F5 运行、Esc 取消、Ctrl+, 设置、Ctrl+Shift+O 打开输出。

无界面 / agent 用法：

```bat
venv\Scripts\python.exe -m getorganelle_gui.cli inspect --json
venv\Scripts\python.exe -m getorganelle_gui.cli run --mode reads --reads1 R1.fq.gz --reads2 R2.fq.gz --organelle embplant_pt --workspace runs --run-name sample --json
```

运行前请把 `gui` 目录加入 `PYTHONPATH`，或在 GUI 目录中执行：

```bat
set PYTHONPATH=%ROOT%gui
```

> GUI 使用 PyQt5（与 YR-MPE 一致）。PyQt5 没有 Windows arm64 轮子，因此
> arm64 发行包仅提供命令行流程；如需 GUI，请使用 x64 版本的 Python
> （Windows 11 ARM64 可通过 x64 模拟运行）。

`gui/settings.json` 是 YRTools `polypyplug` 清单（入口
`getorganelle_gui.yrtools_entry:GetOrganelleEntry`）；将 `gui` 目录放入
`YRTools/plugins/` 即可作为标签页加载。`MainWindow.run()` 返回 `self`，
嵌入模式不会覆盖宿主的全局样式表。

## 已知限制

- Bowtie2 的 Windows 构建不支持 mmap / 共享内存，`--mm` 会被包装器自动移除。
- `--time-limit` 在 Windows 上不生效。
- 输入/输出路径建议不要包含空格（GetOrganelle 内部命令拼接未全面加引号）。
- GUI 自带 GFA/FASTG 图查看器（长度感知布局、弯曲节点、覆盖度着色），
  并可用内置 BLAST+ 对 GenBank 参考做 `blastn`/`tblastn` 筛选；BLAST 只
  搜索本地图库，不连接 NCBI。重图请用 Bandage/Bandage-NG。
- E 值不能单独排除 NUMT/NUPT；建议要求多个注释基因命中并结合覆盖度判断。
- Bandage 仍可作为 GetOrganelle 主流程的外部可视化工具；未安装时自动跳过。
- samtools 不参与 GetOrganelle 主流程。
- GUI 目前仅支持 x64（PyQt5 无 arm64 轮子）；arm64 包提供完整命令行工具与 headless CLI。

## 许可证

GetOrganelle（GPLv3）、SPAdes（GPLv2）、Bowtie2（GPLv3）、samtools/htslib
（MIT/Expat）均按其原始许可证分发；各目录内附有对应 LICENSE 文件。
NCBI BLAST+ 的使用条款见 `ncbi-blast\LICENSE`。
