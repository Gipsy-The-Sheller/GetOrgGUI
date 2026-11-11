# GetOrganelle Workbench

**Windows-first.** A PyQt5 desktop front-end for the native Windows
GetOrganelle port, designed against the YR-MPE workbench standard (plugin
lifecycle, typed results, provenance, and the UI audit constraints). See
[NOTE.md](NOTE.md) for the concise Windows-first note.

```
Inputs → Preprocess → Parameters → Run → Results
```

## What it does

- **Inputs** — paired/unpaired FASTQ or an existing GFA/FASTG graph, one or
  more organelle types (multi-select → `-F a,b`), workspace and run folder,
  with live database status.
- **Preprocess** — optional fastp stage: adapter auto-detection/custom
  sequences, quality and length filtering, optional front/tail trimming and
  deduplication. Trimmed reads and fastp JSON/HTML reports live under
  `<workspace>/_workbench/preprocess/<run_id>/`; Results shows before→after
  read counts.
- **Parameters** — 3–5 basic controls; everything else is behind
  **Advanced options**. k-mers can be automatic or a validated custom list.
- **Run** — the exact command is shown before execution. The job is
  non-modal, logs stream into the page and the Job Center, and a single
  **Cancel** stops the whole process tree.
- **Results** — typed output table, FASTA/graph/log preview, warnings,
  assembled size/GC, and `run.json` provenance. The command and exit code are
  recorded next to the outputs.

The workbench never creates the GetOrganelle output directory before the run:
GetOrganelle's `--overwrite` removes that folder itself, and an open log file
inside it would make the removal fail on Windows. Workbench logs live under
`<workspace>/_workbench/logs/`.

## Running

From the repository or release package root:

```bat
GetOrganelleGUI.bat
```

or directly:

```bat
venv\Scripts\python.exe gui\launcher.pyw
```

`setup_venv.bat` installs `gui\requirements.txt` (PyQt5) automatically on x64.
PyQt5 has no Windows arm64 wheel; the arm64 package stays command-line only.

## Headless / agent surface

The same models power a display-free CLI:

```bat
set PYTHONPATH=%CD%\gui
venv\Scripts\python.exe -m getorganelle_gui.cli inspect --json
venv\Scripts\python.exe -m getorganelle_gui.cli check --json
venv\Scripts\python.exe -m getorganelle_gui.cli run --mode reads ^
  --reads1 R1.fq.gz --reads2 R2.fq.gz --organelle embplant_pt ^
  --workspace runs --run-name sample --json
```

`run --json` emits a `yrmpe.result.v1` ResultSpec on stdout; logs go to
stderr. The exact command, parameters and output paths are also written to
`<run>/run.json`.

## YR-MPE standard mapping

| YR-MPE requirement | Implementation |
| --- | --- |
| Plugin lifecycle: metadata, input/output types, citations | `getorganelle_gui/plugin_meta.py` |
| `control_bindings()` for every executable control | `plugin_meta.control_bindings()` |
| `ResultSpec` (`yrmpe.result.v1`) | `resultspec.py`, `results.build_result_spec()` |
| Hidden subprocess, argument lists, explicit cwd | `command.py`, `runner.py` (QProcess) |
| `progress`, `console_output`, `finished`, `error` | `JobRunner` signals |
| Cancel and process-tree cleanup | `JobRunner.cancel()` (`taskkill /T /F` on Windows) |
| Result paths in a machine-readable summary | `run.json`, ResultSpec `artifacts` |
| Skill document | `skills/getorganelle.md` |
| Non-modal long tasks, one Cancel, Job Center | `RunPage`, `JobCenter` |
| Basic/Advanced progressive disclosure | `ParametersPage` |
| Optional fastp preprocessing with reports | `PreprocessPage`, `preprocess.py` |
| Multi-organelle `-F` lists | `InputsPage` checkbox grid |
| Inline validation with what/why/how | `validation.py`, field error labels |
| Status = icon + text + colour | `Badge`, rail symbols |
| Empty states with a next action | `EmptyState` |
| Keyboard access, focus rings | QSS `:focus`, F5/Esc/Ctrl+O/Ctrl+,/Ctrl+Shift+O |
| Light/dark semantic tokens | `theme.py` |

## Code layout

```
gui/
├─ getorganelle_gui/
│  ├─ models.py          # RunConfig, RunResult, deps/DB models (no Qt)
│  ├─ command.py         # argv construction, env, control bindings helpers
│  ├─ validation.py      # inline field validation
│  ├─ results.py         # output scan, fasta stats, run.json, ResultSpec
│  ├─ resultspec.py      # yrmpe.result.v1 dataclasses (host-compatible)
│  ├─ runner.py          # non-modal QProcess job + streaming logs
│  ├─ theme.py           # semantic light/dark tokens and QSS
│  ├─ widgets.py         # Card, Badge, FileInput, LogView, EmptyState
│  ├─ preprocess.py      # fastp command builder and report summary
│  ├─ pages/             # Inputs, Preprocess, Parameters, Run, Results
│  ├─ main_window.py     # rail + pages + inspector + job center
│  ├─ settings_dialog.py # paths/runtime/theme/asynchronous dependency check
│  ├─ database_dialog.py # seed/label database status and installation
│  ├─ plugin_meta.py     # metadata, control bindings, agent actions
│  └─ cli.py             # headless inspect/check/run
├─ skills/getorganelle.md
├─ tests/                # unit tests + offscreen smoke/screenshots
├─ requirements.txt
└─ launcher.pyw
```

## Tests

```bat
venv\Scripts\python.exe -m unittest discover -s gui\tests -p "test_*.py" -v
set QT_QPA_PLATFORM=offscreen
venv\Scripts\python.exe gui\tests\gui_smoke.py
```

`gui_smoke.py` builds the full window and writes light/dark screenshots to
`build/`. `gui_run_smoke.py` runs a real GetOrganelle job through the GUI's
runner; `gui_preprocess_smoke.py` runs fastp → GetOrganelle
(requires the built dependencies and the synthetic test reads).

## Scaling note

The UI was tuned against raxmlGUI 2.0 on a 2560×1600 / 150 % display: body
13 px, captions 11 px, page titles 20 px, 3–5 px control padding, default
window 1280×800. If a future display needs different density, change the type
sizes and paddings only in `theme.py`; layouts use the 8 px grid.
