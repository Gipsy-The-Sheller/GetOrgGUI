# GetOrganelle for Windows（原生移植版）

本发行包把 GetOrganelle 及其依赖编译为**原生 Windows 程序**，运行时不需要
MSYS2 / Cygwin，也不需要 `msys-2.0.dll`。

## 包含内容

```
GetOrganelle\                     GetOrganelle 1.8.0.1（含 Windows 补丁）
GetOrganelleDep\Windows\
  SPAdes\                         SPAdes 4.3.0-dev（原生构建）
  bowtie2\                        Bowtie2 2.5.5（原生构建）
  ncbi-blast\                     NCBI BLAST+ 2.17.0（blastn / makeblastdb）
  samtools\bin\samtools.exe       samtools 1.25（可选）
run_get_organelle_reads.bat
run_get_organelle_assembly.bat
run_get_organelle_config.bat
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
2. 双击或在命令行运行 `setup_venv.bat`，创建 `venv` 并安装依赖。
3. 初始化数据库（首次使用，二者需一起安装）：

```bat
run_get_organelle_config.bat -a embplant_pt,embplant_mt
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

## 已知限制

- Bowtie2 的 Windows 构建不支持 mmap / 共享内存，`--mm` 会被包装器自动移除。
- `--time-limit` 在 Windows 上不生效。
- 输入/输出路径建议不要包含空格（GetOrganelle 内部命令拼接未全面加引号）。
- Bandage 可视化是可选的；未安装时自动跳过。
- samtools 不参与 GetOrganelle 主流程。

## 许可证

GetOrganelle（GPLv3）、SPAdes（GPLv2）、Bowtie2（GPLv3）、samtools/htslib
（MIT/Expat）均按其原始许可证分发；各目录内附有对应 LICENSE 文件。
NCBI BLAST+ 的使用条款见 `ncbi-blast\LICENSE`。
