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
  with live database status. **Manage databases…** handles every
  GetOrganelleDB type — `embplant_pt`, `embplant_mt`, `embplant_nr`,
  `fungus_mt`, `fungus_nr`, `animal_mt` and `other_pt` — with per-type
  selection, “install missing”, update and remove actions. Plastome and
  mitogenome remain paired for land-plant runs; `anonym` uses a custom seed
  and gene FASTA instead of a downloadable database.
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
- **Results** — typed output table, FASTA/log preview, warnings, assembled
  size/GC, and `run.json` provenance. GFA/FASTG files open in a built-in
  interactive graph viewer (length-aware layout, curved node tubes,
  coverage/length/GC colouring, search, drag, zoom/pan, PNG export). The
  command and exit code are recorded next to the outputs.

The workbench never creates the GetOrganelle output directory before the run:
GetOrganelle's `--overwrite` removes that folder itself, and an open log file
inside it would make the removal fail on Windows. Workbench logs live under
`<workspace>/_workbench/logs/`.

## Assembly graph viewer

The Results page previews `.gfa` and `.fastg` files in a Bandage-inspired
canvas (`graph_model.py` + `graph_viewer.py`) and can open the same canvas in
a larger non-modal window.

- **Length is real.** Each segment is represented by its 5′ and 3′ endpoints;
  an internal spring has a rest length proportional to the sequence length.
  Connected components are laid out separately and packed into a grid, so a
  long isolated contig is not reduced to a dot beside a dense component.
- **Curved multi-segment nodes.** The path between endpoints is sampled into
  a bent polyline (quadratic bend away from the component centre). It is
  stroked with a `QLinearGradient` brush over a rounded-cap pen, with an
  outline, shadow, selection glow and a thin specular highlight. Coverage
  controls both colour and tube thickness.
- **Interaction.** Drag nodes or empty space, wheel zoom (cursor-anchored),
  search by node ID, switch coverage/length/GC colouring, show ID/length/
  coverage labels (collision-aware), and export PNG.
- **Reference BLAST.** The **BLAST ref…** button opens a non-modal dialog that
  screens graph nodes against a GenBank reference with the bundled BLAST+:
  full-record `blastn` or annotated-CDS `tblastn`. The highlight E-value and
  evidence filters (identity, alignment length, query coverage, distinct
  annotated genes) update the magenta node highlights from cached hits without
  rerunning BLAST. Passing node IDs, a node-level TSV and a filtered node
  FASTA can be exported.
- **Limits.** This is a viewer, not a Bandage replacement: no NCBI remote
  BLAST, no plugin layouts or graph editing, and the in-app reader caps graph
  files at 80 MB. Use Bandage/Bandage-NG for very large graphs or its BLAST
  integration.

### Screening organelle contigs

`blastn` is useful when the reference is the organelle genome itself.
`tblastn` is often more informative for a GenBank record because every
annotated CDS becomes an independent query; requiring hits to ≥ 2 distinct
genes is a simple guard against single-gene NUPT/NUMT-like insertions.

E-value alone is **not** proof of organelle origin: nuclear organelle-derived
insertions can match a reference nearly perfectly. Treat BLAST as one line of
evidence together with node coverage, read support and assembly context. The
dialog documents this limitation next to the filters.

Bandage citation: Wick RR, Schultz MB, Zobel J, Holt KE. *Bandage:
interactive visualization of de novo genome assemblies.* Bioinformatics
2015;31(20):3350–3352. doi:10.1093/bioinformatics/btv383. The active fork is
[Bandage-NG](https://github.com/asl/BandageNG).

## YRTools / host embedding

`gui/settings.json` declares a YRTools `polypyplug` entry point:

```
getorganelle_gui.yrtools_entry:GetOrganelleEntry
```

Copy or link the `gui` directory into `YRTools/plugins/` (YRTools adds the
plugin directory to `sys.path`). `GetOrganelleEntry.run()` constructs
`MainWindow` and returns `MainWindow.run()`, which returns `self` — the same
widget YRTools inserts into a tab. The embedded window applies its semantic
tokens to its own subtree instead of changing the application stylesheet, so
the host keeps ownership of fonts and global styling. Standalone startup is
unchanged and still applies the theme globally.

Data import from a YR-MPE workflow (`import_from`/`import_data`) is accepted
but not yet mapped into the Inputs page. The host can still open the plugin
and use its normal file pickers.

## Agent integration

The designed agent surface is the **headless CLI + machine-readable
metadata**, not an in-process GUI bridge:

- `python -m getorganelle_gui.cli inspect --json` returns plugin metadata,
  dependencies, databases, `control_bindings()` and `agent_actions()`.
- `check --json` starts every configured tool and reports versions.
- `run ... --json` runs the same command builder/runner path and emits a
  `yrmpe.result.v1` ResultSpec; `run.json` and the log remain beside the
  outputs.
- `skills/getorganelle.md` is the agent-facing skill document.

There is deliberately **no** `AgentBridge`, `agent_invoke`, `inspect_status`
or `modify_options` on the desktop widget yet. The reasons are practical:

- GetOrganelle runs are long and must be cancellable as a Windows process
  tree; the CLI already owns that lifecycle without a Qt event loop.
- GUI runs can raise modal overwrite confirmations; an agent path must avoid
  modal dialogs, and that policy is not implemented.
- The host-level YR-MPE bridge requires a registered action registry and a
  token-protected transport; exposing arbitrary widget actions without that
  contract would be less safe and less stable than the JSON CLI.
- Host embedding and agent control are separable: YRTools can embed the
  widget while an agent drives the CLI.

If full YR-MPE agent-plugin compliance is needed, the next step is to add the
BasePlugin-style status/console/options/action facade and route it through
the same handlers as the GUI; that is not claimed today.

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
│  ├─ graph_model.py     # GFA/FASTG parser, endpoint force layout (no Qt)
│  ├─ graph_viewer.py    # QPainter graph canvas, toolbar, large viewer
│  ├─ reference_blast.py # GenBank parser, BLAST+ runner, hit filters (no Qt)
│  ├─ blast_dialog.py    # non-modal reference BLAST dialog and hit table
│  ├─ pages/             # Inputs, Preprocess, Parameters, Run, Results
│  ├─ main_window.py     # rail + pages + inspector + job center
│  ├─ settings_dialog.py # paths/runtime/theme/asynchronous dependency check
│  ├─ database_dialog.py # seed/label database status and installation
│  ├─ plugin_meta.py     # metadata, control bindings, agent actions
│  ├─ yrtools_entry.py   # YRTools/YR-MPE host entry (run() returns MainWindow)
│  └─ cli.py             # headless inspect/check/run
├─ settings.json         # YRTools polypyplug manifest
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
`blast_smoke.py` runs an optional synthetic `blastn` + `tblastn` integration
test and skips when the bundled BLAST+ tools are absent. `yrtools_smoke.py`
constructs the YRTools entry, embeds the widget in a host tab, and checks that
`MainWindow.run()` returns `self` without overriding the host stylesheet.

## License

The Workbench original code (GUI, CLI, tests, build scripts and CI) is
**AGPL-3.0-only**; see the repository `LICENSE` and `NOTICE.md`. The GUI uses
PyQt5 under its GPLv3 option (or a commercial PyQt license). Vendored
GetOrganelle, SPAdes, Bowtie2, fastp and samtools sources keep their own
licenses; the release package includes the notices and a source manifest.

## Scaling note

The UI was tuned against raxmlGUI 2.0 on a 2560×1600 / 150 % display: body
13 px, captions 11 px, page titles 20 px, 3–5 px control padding, default
window 1280×800. If a future display needs different density, change the type
sizes and paddings only in `theme.py`; layouts use the 8 px grid.
