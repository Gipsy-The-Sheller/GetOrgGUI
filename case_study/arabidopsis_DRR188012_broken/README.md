# DRR188012 negative example: broken IR junction

> **Negative example.** This directory documents a DRR188012 assembly whose
> graph is split into two components at the IR junction (see below). The clean
> Col-0 case used in the manuscript is in
> [`../arabidopsis_col0_SRR30886772/`](../arabidopsis_col0_SRR30886772/).

This directory records the original Windows Workbench run on a public
paired-end *Arabidopsis thaliana* WGS run and the analysis that exposed the
broken IR junction.

## Inputs

- SRA run: `DRR188012`
- Sample: *Arabidopsis* M6 plant, chronic gamma 2-4 µGy/h-3
- Organism: *Arabidopsis thaliana*
- Layout: paired-end
- Submitted bases: 5.58 Gb
- Workbench cap: **5.0 Gb** (`--fastp-gbase 5.0`)
- Reference: `NC_000932.1` *Arabidopsis thaliana* chloroplast, complete genome
  (154,478 bp), fetched from NCBI EFetch/RefSeq.

The public SRA archive was downloaded from the SRA Open Data Platform and
converted on Windows with `fasterq-dump --split-files`. The internal run label
used during development was `arabidopsis_col0_5gb`; the analysed sample is
DRR188012 (`Arabidopsis M6 plant chronic gamma 2-4 µGy/h-3`), not a verified
Col-0 accession. The run is processed on the native Windows 11 build with the
Workbench headless CLI. fastp trims/filters the first ~5.0 Gb of the primary
reads; the trimmed reads are passed to GetOrganelle 1.8.0.1 with the
`embplant_pt` database.

## Path-sequence FASTA

`assembly.fasta` is the GetOrganelle path sequence exported as
`embplant_pt.K115.scaffolds.graph1.1.path_sequence.fasta`
(md5 `556b2a6407efa6313f070baba8f359db`), not the raw assembly-graph contigs.
Both the reference BLAST and the self-comparison below use this file. The
three records are GetOrganelle path names (`scaffold_1--...`,
`scaffold_2--...`, `scaffold_3--...`). Re-running the all-vs-all BLAST
directly on the original export produces an identical `self_hits.tsv`.

## GFA path

`embplant_pt.K115.contigs.graph1.path_sequence.gfa` is the original exported
graph for the path FASTA. It contains five segments and four links (115 bp
overlaps) but no `P` records. `embplant_pt.K115.paths.gfa` is a copy with
explicit `P` records added for the three scaffolds; the P-line lengths match
the FASTA exactly:

```text
P	scaffold_1	445-,553_763+	115M
P	scaffold_2	535_757-,765+,535_757+	115M,115M
P	scaffold_3	727-,445+	115M
```

The segments are:

| Segment | Length | Reference role |
| --- | ---: | --- |
| `445` | 15,266 bp | IR block B copy |
| `727` | 17,168 bp | LSC |
| `765` | 18,010 bp | SSC |
| `553_763` | 67,349 bp | LSC |
| `535_757` | 11,095 bp | IR block A |

The path names in the FASTA decode as:

- scaffold_1: `445-` + `553_763+` = 15,266 + 67,349 - 115 = 82,500 bp
- scaffold_2: `535_757-` + `765+` + `535_757+` = 11,095 + 18,010 + 11,095 - 230 = 39,970 bp
- scaffold_3: `727-` + `445+` = 17,168 + 15,266 - 115 = 32,319 bp

The two outgoing links from `445-` (to `727+` or `553_763+`) are the IR
junction that splits the path into scaffold_1 and scaffold_3.

## Commands

```bat
set PYTHONPATH=E:\Codes\getorg_win\gui
E:\Codes\getorg_win\venv\Scripts\python.exe -m getorganelle_gui.cli run ^
  --getorganelle-root E:\Codes\getorg_win\GetOrganelle ^
  --dep-root E:\Codes\getorg_win\GetOrganelle\GetOrganelleDep\Windows ^
  --python E:\Codes\getorg_win\venv\Scripts\python.exe ^
  --config-dir C:\Users\ASUS\.GetOrganelle ^
  --workspace C:\Users\ASUS\arabidopsis_case\runs ^
  --mode reads ^
  --reads1 C:\Users\ASUS\arabidopsis_case\fastq_plain\DRR188012_1.fastq ^
  --reads2 C:\Users\ASUS\arabidopsis_case\fastq_plain\DRR188012_2.fastq ^
  --organelle embplant_pt ^
  --run-name arabidopsis_5gb ^
  --threads 12 ^
  --preprocess --fastp-gbase 5.0 --json
```

For the reference dot plot:

```bat
E:\Codes\getorg_win\GetOrganelle\GetOrganelleDep\Windows\ncbi-blast\blastn.exe ^
  -query assembly.fasta -subject cpDNA_NC_000932.1.fasta ^
  -outfmt "6 qseqid sseqid pident length mismatch gapopen qstart qend sstart send evalue bitscore" ^
  -evalue 1e-10 -perc_identity 90 -num_threads 8 > hits.tsv

python dotplot.py hits.tsv assembly.fasta cpDNA_NC_000932.1.fasta dotplot.pdf
```

For the all-vs-all self-comparison (the extra `sstrand`, `qlen`, and `slen`
fields are required by `self_dotplot.py`):

```bat
E:\Codes\getorg_win\GetOrganelle\GetOrganelleDep\Windows\ncbi-blast\blastn.exe ^
  -query assembly.fasta -subject assembly.fasta ^
  -task megablast -evalue 1e-10 -perc_identity 90 -dust no ^
  -max_target_seqs 5000 ^
  -outfmt "6 qseqid sseqid pident length mismatch gapopen qstart qend sstart send evalue bitscore sstrand qlen slen" ^
  > self_hits.tsv

python self_dotplot.py self_hits.tsv assembly.fasta self_dotplot.pdf ^
  --title "Arabidopsis plastid assembly self-comparison"
```

The same BLAST command with `cpDNA_NC_000932.1.fasta` as both query and subject
produces the reference control in `ref_self_hits.tsv`. The assembly-versus-
reference table with strand information, used to map the IR blocks onto
`NC_000932.1`, is `hits_strand.tsv`.

The dot-plot script `dotplot.py` stacks path-sequence scaffolds on the y-axis
and plots BLAST HSPs against the 154,478 bp reference on the x-axis; colour
encodes percent identity. `self_dotplot.py` lays the scaffolds out head-to-tail
on both axes: direct hits follow the main diagonal, while reverse-complement
hits form anti-diagonal blocks.

## Result

The Workbench run used 12 threads on Windows 11 (10.0.26200). fastp processed
17,364,608 read pairs (4,984,282,663 bases, i.e. the 5.0 Gb cap); after
filtering, 16,511,657 pairs (4,703,340,924 bases) remained, with Q30 rising
from 85.9% to 88.2%. GetOrganelle used 2,886,257 reads for seed extension and
finished in 312.9 s (413.9 s including fastp).

| Metric | Value |
| --- | --- |
| Assembled scaffolds | 3 |
| Total assembly length | 154,789 bp |
| Reference length | 154,478 bp |
| BLAST hits (>= 200 bp, >= 90% identity) | 8 HSPs |
| Reference covered | 154,477 bp (100.0%) |
| BLAST identity | 99.964-100% |
| Workbench wall time | 413.9 s |

The path-sequence FASTA is collinear with `NC_000932.1` over its full length.
The three scaffolds are not a simple LSC/IR/SSC partition: each inverted-repeat
copy is split at the same point, with 15,210 bp of each copy on
scaffold_1/scaffold_3 and 11,095 bp on scaffold_2. The assembly is 311 bp
longer than the reference, consistent with small path-sequence extensions and
indel/assembly differences; no attempt was made to polish it.

## Self-comparison and the inverted repeat

The all-vs-all BLAST of the path-sequence FASTA returns four reverse-complement
HSPs, forming two distinct blocks (reciprocal hits are reported in both
directions):

| Block | Query | Subject | Length | Identity |
| --- | --- | --- | --- | --- |
| IR block A | scaffold_2 1-11,095 | scaffold_2 28,876-39,970 (RC) | 11,095 bp | 100% |
| IR block B | scaffold_1 1-15,266 | scaffold_3 17,054-32,319 (RC) | 15,266 bp | 100% |

Block A is the IR segment adjacent to the SSC; block B is the segment adjacent
to the LSC. In reference coordinates the two blocks correspond to IRa
84,171-110,434 and IRb 128,215-154,478:

- scaffold_1 57-15,266 maps to IRa 84,171-99,380 (15,210 bp) and to IRb
  139,269-154,478 (15,210 bp);
- scaffold_2 1-11,095 maps to IRa 99,340-110,434, and scaffold_2
  28,876-39,970 maps to IRb 128,215-139,309.

The two reference-aligned IR segments overlap by 41 bp (99,340-99,380) and sum
to the 26,264 bp IR. The 15,266 bp self-hit is longer than the 15,210 bp
reference-aligned segment because 56 bp at one end of the block (scaffold_1
positions 1-56 and the corresponding scaffold_3 positions 32,264-32,319) do not
align to the reference in this HSP. The reference self-BLAST returns the
expected single 26,264 bp RC hit at 84,171-110,434 <-> 128,215-154,478, 100%
identity, as a control.

The self dot plot shows the two anti-diagonal IR blocks; the grey diagonal is
the trivial self match.

## Files

- `assembly.fasta` - GetOrganelle path-sequence FASTA (see provenance above)
- `hits.tsv` - assembly-versus-reference BLAST table (12 columns)
- `hits_strand.tsv` - assembly-versus-reference BLAST table with strand
- `self_hits.tsv` - assembly all-vs-all BLAST table
- `ref_self_hits.tsv` - NC_000932.1 all-vs-all BLAST control
- `dotplot.pdf` / `dotplot.png` - reference dot plot
- `self_dotplot.pdf` / `self_dotplot.png` - self dot plot
- `dotplot.py`, `self_dotplot.py` - plotting scripts
- `fastp.json` / `fastp.html` - fastp report
- `workbench_result.json`, `run.json` - Workbench provenance

Note: the original Workbench run was made before the Windows fastp
large-file/64-bit counter fixes, so its embedded fastp summary contains
overflowed counters. The `fastp.json`/`fastp.html` in this directory were
regenerated from the same 5.0 Gb subset with the fixed fastp build; the
trimmed reads and GetOrganelle assembly were unchanged.
