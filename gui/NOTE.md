# GetOrganelle Workbench — 说明

> **Windows-first.** 本 GUI 以 Windows 10/11 x64 为首要目标开发与测试：
> 原生 PyQt5、Windows 路径与进程树取消、`python.exe/pythonw.exe` 分离、
> fastp/GetOrganelle 子进程均在 Windows 上验证。Linux 与 macOS 发行包
> 也包含 GUI（依赖解析、`fastp` 可执行文件名与 GetOrganelleDep 目录已
> 按平台适配），但 Windows 仍是主要支持平台。

## 这是什么

GetOrganelle Workbench 是原生 GetOrganelle 的桌面前端，按 YR-MPE 的
插件契约与 UI 审计标准设计：

```
Inputs → Preprocess → Parameters → Run → Results
```

- **Inputs**：双端/单端 FASTQ、GFA/FASTG；可同时勾选多个细胞器类型
  （输出 `-F embplant_pt,embplant_mt` 这类列表）。**Manage databases…**
  可安装 GetOrganelleDB 的全部类型（embplant_pt/mt/nr、fungus_mt/nr、
  animal_mt、other_pt），支持勾选安装、安装全部缺失、更新和删除；
  `anonym` 使用自定义 seed/gene FASTA，不需要可下载数据库。
- **Preprocess（fastp）**：可选接头自动检测/自定义接头、质量与长度过滤、
  `--dedup`、首尾裁剪；fastp 原始 JSON/HTML 报告与 trimmed reads 写入
  `<workspace>/_workbench/preprocess/<run_id>/`。
- **Parameters**：Basic 仅保留线程、轮数、k-mer、预设；其余在 Advanced。
- **Run**：非模态后台任务、实时日志、阶段进度、单一 Cancel（Windows 下
  `taskkill /T /F` 终止 fastp/GetOrganelle 整棵进程树）。
- **Results**：输出表、FASTA/日志预览、fastp before→after reads、
  warnings、`run.json` provenance；产物路径写入 `yrmpe.result.v1`。
  GFA/FASTG 可在内置的 Bandage 风格查看器中打开（见下节）。

## 缩放与外观

- 以 raxmlGUI 2.0 的控件密度为基准调试：正文 13 px、caption 11 px、
  page title 20 px；控件 padding 3–5 px；默认窗口 1280×800，最小 1024×640。
- 8 px 间距网格、浅/深色语义 tokens；状态一律“图标 + 文字 + 颜色”。
- 在 2560×1600 / 150% 缩放屏幕上验证；截图见 `build/gui_*.png`（不提交）。

## 组装图查看器

Results 页的 **Graph** 标签与“Open graph viewer”使用纯 QPainter 实现的
交互式组装图查看器（`graph_model.py` + `graph_viewer.py`），参考
Bandage 的视觉语言：

- 每个节点用 5′/3′ 两端点表示，内部弹簧的自然长度与序列长度成正比；
  连通分量分别布局后再网格排布，避免孤立的长 contig 被压成一个点。
- 节点是沿端点采样的弯曲多段折线，用 `QLinearGradient` 自定义笔刷描边，
  带圆角端帽、描边、阴影、选中光晕与高光；覆盖度同时决定颜色和粗细。
- 支持拖动节点/平移、以光标为中心缩放、按节点 ID 搜索、覆盖度/长度/GC
  着色、ID/长度/覆盖度标签（自动避让），以及 PNG 导出。
- **参考 GenBank BLAST**：**BLAST ref…** 打开非模态对话框，用内置
  BLAST+ 对图节点做筛选。全量参考用 `blastn`；解析 CDS 注释、翻译后
  用 `tblastn`。高亮 E 值以及一致性、比对长度、query 覆盖度、不同基因
  数等证据过滤器可在缓存结果上实时调整，无需重跑 BLAST；通过的节点会
  加洋红色轮廓和 BLAST 徽标，其余节点变暗。可复制节点 ID、导出 TSV，
  或将通过的节点序列导出为 FASTA。
- 这是查看器而非 Bandage 替代品：没有 NCBI 远程 BLAST、插件布局或图
  编辑；单文件上限 80 MB。超大图请用 Bandage/Bandage-NG。

**关于 NUMT/NUPT**：核基因组中的细胞器插入片段可能几乎完美匹配参考，
仅靠 E 值不能证明节点来自叶绿体。建议用 `tblastn` 并要求 ≥ 2 个不同
注释基因，同时结合节点覆盖度、reads 支持和组装上下文人工确认。

Bandage 引用：Wick RR, Schultz MB, Zobel J, Holt KE. *Bandage:
interactive visualization of de novo genome assemblies.* Bioinformatics
2015;31(20):3350–3352. doi:10.1093/bioinformatics/btv383。

## Windows 优先的具体处理

- 子进程使用参数列表而非 shell 字符串；显式 `cwd` 与 PATH。
- 运行日志放在输出目录之外，避免 GetOrganelle `--overwrite` 删除输出目录
  时因日志文件被占用而失败。
- 取消任务使用 `taskkill /PID <pid> /T /F`，覆盖 SPAdes/fastp 子进程。
- GetOrganelle 在 UTF-8 模式下解码本地化 cmd 输出会崩溃，已改为只检查
  子进程返回码（`pipe_control_func.executable`）。
- PyQt5 无 Windows arm64 轮子：GUI 面向 x64；Windows arm64 包保留完整
  命令行与 headless CLI。x64 Python 可在 Windows 11 ARM64 上通过模拟运行
  GUI。Linux x64 和 macOS arm64 有 PyQt5 轮子，发行包包含 GUI。

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

## YRTools 接入与 agent 边界

- `gui/settings.json` 提供 YRTools `polypyplug` 入口：
  `getorganelle_gui.yrtools_entry:GetOrganelleEntry`。把 `gui` 目录复制/链接到
  `YRTools/plugins/` 后，YRTools 会调用 `entry.run()`；该入口构造
  `MainWindow` 并返回 `MainWindow.run()`，后者返回 `self`，可直接插入
  YRTools 标签页。
- 嵌入模式下主题只作用于本 Widget 子树（`apply_global_theme=False`），不会
  覆盖 YRTools 的全局字体与样式；独立启动仍使用全局样式。
- 当前 agent 接入面是 **headless CLI + 元数据**：`cli inspect/check/run --json`、
  `control_bindings()`、`agent_actions()`、skill 文档和 `yrmpe.result.v1`/
  `run.json`。
- 当前**没有**在桌面 Widget 上实现 YR-MPE 的 `AgentBridge`、
  `agent_invoke`、`inspect_status`、`modify_options` 等实时控制面。考虑：
  GetOrganelle 是长任务且需要 Windows 进程树取消；现有 GUI 运行可能弹出
  覆盖确认等模态框；GUI 控制面还需要 action registry 与 token 保护。
  因此现阶段把稳定、无显示依赖的 CLI 作为 agent 边界，宿主嵌入和 agent
  控制保持解耦。
- `import_from/import_data` 目前只被入口接收，尚未映射到 Inputs 页；完整
  BasePlugin 风格 agent 面属于后续工作。

## 已知限制

- GUI 仅 x64（PyQt5 无 arm64 wheel）。
- fastp 为静态链接的 Windows 构建；Linux/macOS 用户请使用各自平台的 fastp。
- 路径建议不要包含空格；GetOrganelle 内部仍有文本命令拼接。
- 内置图查看器的 BLAST 只搜索本地自建图库，不连接 NCBI；重图请用
  Bandage/Bandage-NG。
- E 值不能单独排除 NUMT/NUPT；请结合多基因证据、覆盖度与 reads 支持。
- GUI 不是 YR-MPE 的宿主插件本体，但已实现 `ResultSpec`、
  `control_bindings()`、skill 文档与 provenance，可作为插件层接入。
- 原创代码采用 **AGPL-3.0-only**；vendored 的 GetOrganelle（GPLv3）、
  SPAdes（GPLv2）、Bowtie2（GPLv3）等保留各自许可证。GUI 通过 PyQt5
  的 GPLv3 选项使用，详见根目录 `LICENSE`、`NOTICE.md` 与
  `THIRD_PARTY_NOTICES.md`。
