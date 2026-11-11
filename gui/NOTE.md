# GetOrganelle Workbench — 说明

> **Windows-first.** 本 GUI 以 Windows 10/11 x64 为首要目标开发与测试：
> 原生 PyQt5、Windows 路径与进程树取消、`python.exe/pythonw.exe` 分离、
> fastp/GetOrganelle 子进程均在 Windows 上验证。Linux/macOS 理论上可运行
> `getorganelle_gui` 的核心模块，但未作为发布目标。

## 这是什么

GetOrganelle Workbench 是原生 Windows 版 GetOrganelle 的桌面前端，按
YR-MPE 的插件契约与 UI 审计标准设计：

```
Inputs → Preprocess → Parameters → Run → Results
```

- **Inputs**：双端/单端 FASTQ、GFA/FASTG；可同时勾选多个细胞器类型
  （输出 `-F embplant_pt,embplant_mt` 这类列表）。
- **Preprocess（fastp）**：可选接头自动检测/自定义接头、质量与长度过滤、
  `--dedup`、首尾裁剪；fastp 原始 JSON/HTML 报告与 trimmed reads 写入
  `<workspace>/_workbench/preprocess/<run_id>/`。
- **Parameters**：Basic 仅保留线程、轮数、k-mer、预设；其余在 Advanced。
- **Run**：非模态后台任务、实时日志、阶段进度、单一 Cancel（Windows 下
  `taskkill /T /F` 终止 fastp/GetOrganelle 整棵进程树）。
- **Results**：输出表、FASTA/图/日志预览、fastp before→after reads、
  warnings、`run.json` provenance；产物路径写入 `yrmpe.result.v1`。

## 缩放与外观

- 以 raxmlGUI 2.0 的控件密度为基准调试：正文 13 px、caption 11 px、
  page title 20 px；控件 padding 3–5 px；默认窗口 1280×800，最小 1024×640。
- 8 px 间距网格、浅/深色语义 tokens；状态一律“图标 + 文字 + 颜色”。
- 在 2560×1600 / 150% 缩放屏幕上验证；截图见 `build/gui_*.png`（不提交）。

## Windows 优先的具体处理

- 子进程使用参数列表而非 shell 字符串；显式 `cwd` 与 PATH。
- 运行日志放在输出目录之外，避免 GetOrganelle `--overwrite` 删除输出目录
  时因日志文件被占用而失败。
- 取消任务使用 `taskkill /PID <pid> /T /F`，覆盖 SPAdes/fastp 子进程。
- GetOrganelle 在 UTF-8 模式下解码本地化 cmd 输出会崩溃，已改为只检查
  子进程返回码（`pipe_control_func.executable`）。
- PyQt5 无 Windows arm64 轮子：GUI 面向 x64；arm64 包保留完整命令行与
  headless CLI。x64 Python 可在 Windows 11 ARM64 上通过模拟运行 GUI。

## 运行与测试

```bat
setup_venv.bat
GetOrganelleGUI.bat
```

```bat
venv\Scripts\python.exe -m unittest discover -s gui\tests -p "test_*.py" -v
set QT_QPA_PLATFORM=offscreen
venv\Scripts\python.exe gui\tests\gui_smoke.py
```

headless / agent：

```bat
set PYTHONPATH=%CD%\gui
venv\Scripts\python.exe -m getorganelle_gui.cli inspect --json
venv\Scripts\python.exe -m getorganelle_gui.cli run --mode reads ^
  --reads1 R1.fq.gz --reads2 R2.fq.gz --organelle embplant_pt,embplant_mt ^
  --preprocess --adapter-mode auto --workspace runs --run-name sample --json
```

## 已知限制

- GUI 仅 x64（PyQt5 无 arm64 wheel）。
- fastp 为静态链接的 Windows 构建；Linux/macOS 用户请使用各自平台的 fastp。
- 路径建议不要包含空格；GetOrganelle 内部仍有文本命令拼接。
- GUI 不是 YR-MPE 的宿主插件本体，但已实现 `ResultSpec`、
  `control_bindings()`、skill 文档与 provenance，可作为插件层接入。
