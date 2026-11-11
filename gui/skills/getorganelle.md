# GetOrganelle Assembly

## Purpose

Assemble organelle genomes (plastomes, mitogenomes, nrDNA) from genome-skimming
reads, or extract them from an existing GFA/FASTG assembly graph. The plugin
wraps the native Windows GetOrganelle 1.8.0.1 toolchain (SPAdes 4.3.0-dev,
Bowtie2 2.5.5, BLAST+ 2.17.0).

It does **not** annotate genes, build phylogenetic trees, or choose a
biologically correct organelle type for you.

## Inputs

| Object | Formats | Notes |
| --- | --- | --- |
| Paired reads | FASTQ / FASTQ.GZ / TAR.GZ | R1 required; R2 optional. |
| Unpaired reads | FASTQ / FASTQ.GZ | Comma-separated list accepted. |
| Assembly graph | .gfa or .fastg | Reads mode is skipped. |
| Seed FASTA | .fa / .fasta / .fna | Only for `anonym` or a custom seed. |
| Gene database | FASTA or BLAST DB basename | Only for `anonym` or `--genes`. |
| fastp | bundled fastp 1.0.1 | Optional preprocessing stage for adapter trimming/filtering. |

Select one or more organelle types; the GUI writes a comma-separated `-F`
value. Plastome and mitogenome databases are installed as a pair. A seed/label
database must be installed for every non-`anonym` organelle type.
Check it with `Manage databases…` in the GUI or `getorganelle_config.py --list`.

## GUI workflow

1. **Inputs** — choose `Reads` or `Assembly graph`, add files, tick one or
   more organelle types, and confirm the run folder.
2. **Preprocess** — optionally enable fastp for adapter auto-detection/custom
   adapters, quality and length filtering. Trimmed reads and fastp JSON/HTML
   reports are written under `<workspace>/_workbench/preprocess/<run_id>/`.
3. **Parameters** — keep Auto k-mers and the default rounds for a first run;
   open Advanced only when the data need it.
4. **Run** — fix any inline validation message, then press `F5` / Run. The job
   is non-modal; Cancel stops the whole process tree (fastp and GetOrganelle).
5. **Results** — inspect sequence and graph files, the fastp before/after read
   counts, warnings, and provenance (`run.json`). GFA/FASTG files open in a
   length-aware graph viewer with an interactive **BLAST ref…** screen.

## Reference BLAST screening

The graph viewer can compare graph nodes with a user-supplied GenBank file
using the bundled BLAST+ 2.17.0. This is a GUI post-analysis step; it does not
change the GetOrganelle run or its `run.json`.

- **Full reference (blastn)** — the complete GenBank record is the query.
- **Annotated CDS (tblastn)** — CDS features are translated (using
  `/translation`, otherwise `/transl_table`, `/codon_start` and the ORIGIN
  sequence) and searched against the six-frame translation of graph nodes.
- **Live highlight filter** — the highlight E-value can be tightened without
  rerunning BLAST. Additional filters require minimum identity, alignment
  length, query coverage and, for tblastn, a minimum number of distinct
  annotated genes. Passing nodes get a magenta outline and a BLAST badge;
  non-passing nodes are dimmed.
- **Export** — double-click a row to focus the node; copy node IDs, export a
  node-level TSV, or export the passing node sequences as FASTA. BLAST files
  and logs stay under `<workspace>/_workbench/blast/<timestamp>_<graph>/`.

E-value alone cannot distinguish a true organelle contig from a NUPT/NUMT-like
nuclear insertion, which can match a reference almost perfectly. Treat the
screen as evidence: prefer tblastn with ≥ 2 annotated genes, high identity and
alignment length, and verify candidates against node coverage, read support
and the assembly context. This viewer is not a Bandage replacement and does
not perform BLAST database searches against NCBI.

## Agent notes

Every executable control is described by `control_bindings()` and can be
inspected without a display:

```bash
python -m getorganelle_gui.cli inspect --json
python -m getorganelle_gui.cli check --json
```

A headless run emits a `yrmpe.result.v1` document on stdout:

```bash
python -m getorganelle_gui.cli run \
  --mode reads --reads1 R1.fq.gz --reads2 R2.fq.gz \
  --organelle embplant_pt --workspace runs --run-name sample --json
```

- `source` is `getorganelle`; item type is `sequence` for assembled FASTA.
- With `--preprocess`, `runs` contains a `fastp-preprocess` run before the
  `getorganelle-reads` run; `summary.preprocess` has before/after read and base
  counts; trimmed reads and reports are listed in `artifacts`.
- `artifacts` contains the graph, table and log paths.
- `summary` contains mode, organelle, threads, rounds, k-mers, contig count,
  total bp and exit code.
- `runs[0].command` is the exact argument list; the same command is in
  `<output>/run.json`.
- Failures return a non-zero exit code and include the console tail; they are
  never reported as an empty successful result.
- The GUI writes `workbench_run.log` next to `run.json`; GetOrganelle's own log
  is `get_org.log.txt`.

Stable action ids: `getorganelle.inspect`, `getorganelle.check`,
`getorganelle.run`.

## Interpretation

- A successful run produces at least one `*path_sequence.fasta`. For circular
  genomes GetOrganelle usually emits several paths/scaffolds; inspect the graph
  before treating one path as the final molecule.
- `Completed with warnings` / exit code 0 without a FASTA means the graph was
  built but no organelle sequence could be exported. Check coverage, the
  organelle type, the seed database and the graph.
- The number of rounds (`-R`) limits extension. Increase it only after reading
  the log; more rounds do not repair a wrong seed or contaminated library.
- Base coverage is estimated from organelle-hitting reads; very high coverage
  is reduced by `--reduce-reads-for-coverage` (default 500).

## Citation

- fastp: Chen et al. 2018, *Bioinformatics* 34:884–890, doi:10.1093/bioinformatics/btx659
- GetOrganelle: Jin et al. 2020, *Genome Biology* 21:241,
  doi:10.1186/s13059-020-02154-5
- SPAdes: Prjibelski et al. 2020, *Current Protocols in Bioinformatics* 70:e102
- Bowtie2: Langmead & Salzberg 2012, *Nature Methods* 9:357–359
- BLAST+: Camacho et al. 2009, *BMC Bioinformatics* 10:421
