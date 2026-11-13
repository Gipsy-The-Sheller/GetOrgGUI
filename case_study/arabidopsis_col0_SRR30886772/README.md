# Arabidopsis thaliana Col-0 WGS case study (SRR30886772)

This case study runs the Windows Workbench on a public paired-end Col-0 WGS
run and compares the complete circular plastid assembly with the RefSeq
chloroplast genome NC_000932.1.

## Inputs

- SRA run: `SRR30886772`
- BioSample: `SAMN44061621`
- Ecotype: Col-0
- Tissue: rosette leaf; Tokyo, Japan; 2023
- Platform: Illumina NovaSeq 6000, paired-end, 151 bp
- Data: 18,193,303 pairs / 5.49 Gb
- Workbench cap: **5.0 Gb** (`--fastp-gbase 5.0`)
- Reference: `NC_000932.1` *Arabidopsis thaliana* chloroplast, complete genome
  (154,478 bp)

The SRA archive was downloaded as ENA FASTQ:

- `SRR30886772_1.fastq.gz`: 1,409,560,500 B, MD5
  `4651dc3628434d520ad1589dc1b20736`
- `SRR30886772_2.fastq.gz`: 1,475,332,301 B, MD5
  `6204bacae2f716a56cfd899674dc33d0`

The run was processed on the native Windows 11 build with the Workbench
headless CLI.

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
  --reads1 C:\Users\ASUS\arabidopsis_case\fastq\SRR30886772_1.fastq.gz ^
  --reads2 C:\Users\ASUS\arabidopsis_case\fastq\SRR30886772_2.fastq.gz ^
  --organelle embplant_pt ^
  --run-name arabidopsis_col0_SRR30886772_5gb ^
  --threads 12 ^
  --preprocess --fastp-gbase 5.0 --json
```

For the reference dot plot:

```bat
E:\Codes\getorg_win\GetOrganelle\GetOrganelleDep\Windows\ncbi-blast\blastn.exe ^
  -query assembly.graph1.1.fasta -subject cpDNA_NC_000932.1.fasta ^
  -task megablast -evalue 1e-10 -perc_identity 90 -dust no ^
  -outfmt "6 qseqid sseqid pident length mismatch gapopen qstart qend sstart send evalue bitscore" ^
  > hits.tsv

python dotplot.py hits.tsv assembly.graph1.1.fasta cpDNA_NC_000932.1.fasta dotplot.pdf ^
  --ylabel "Assembly path (bp)"
```

For the all-vs-all self-comparison:

```bat
E:\Codes\getorg_win\GetOrganelle\GetOrganelleDep\Windows\ncbi-blast\blastn.exe ^
  -query assembly.graph1.1.fasta -subject assembly.graph1.1.fasta ^
  -task megablast -evalue 1e-10 -perc_identity 90 -dust no ^
  -max_target_seqs 5000 ^
  -outfmt "6 qseqid sseqid pident length mismatch gapopen qstart qend sstart send evalue bitscore sstrand qlen slen" ^
  > self_hits.tsv

python self_dotplot.py self_hits.tsv assembly.graph1.1.fasta self_dotplot.pdf ^
  --title "Arabidopsis Col-0 circular assembly self-comparison"
```

## Result

fastp processed 16,556,291 pairs (4,999,999,882 bases, i.e. the 5.0 Gb cap);
after filtering, 16,379,603 pairs (4,939,836,560 bases) remained. Q30 rose
from 89.4% to 89.8%, duplication was 2.38%, and 153,210 reads (6,815,030 bp)
were adapter-trimmed. fastp took 97 s. GetOrganelle used 549,750 pairs for
seed extension, reduced this to 495,367 pairs at 500x, assembled with SPAdes
k-mers 21,55,85,115, and finished in 187.7 s (285.2 s including fastp). The
result was a single circular genome.

| Metric | Value |
| --- | --- |
| Assembly status | circular genome |
| Genome length | 154,479 bp |
| LSC / SSC / IR | 84,171 / 17,780 / 26,264 bp |
| Average base coverage | 396.7x |
| Reference coverage | 154,478 / 154,478 bp (100.0%) |
| BLAST identity | 99.999-100% |
| IR self-comparison | two 26,264 bp RC copies, 100% |
| Workbench wall time | 285.2 s |

The assembly is one base longer than the reference. Two path sequences are
written (`graph1.1` and `graph1.2`); they differ only in the orientation of
the SSC (`901-` vs `901+`), i.e. the two flip-flop configurations of the
quadripartite chloroplast genome. The representative path is:

```text
945-,943+,901-,943-(circular)
```

## GFA

The complete GFA has three segments and four links, forming one connected
circular component:

| Segment | Length | Role |
| --- | ---: | --- |
| `945` | 84,401 bp | LSC |
| `943` | 26,264 bp | IR |
| `901` | 18,010 bp | SSC |

Links (115 bp overlaps):

```text
901 - -> 943 -
901 + -> 943 -
943 - -> 945 +
943 - -> 945 -
```

The IR segment `943` is traversed twice, once in each orientation, which is
why the path is circular and why the self-comparison finds two 26,264 bp RC
copies.

## Self-comparison

The all-vs-all BLAST of the circular path returns two 26,264 bp
reverse-complement HSPs at 100% identity:

- 84,172-110,435 <-> 154,479-128,216
- 128,216-154,479 <-> 110,435-84,172

These are the two IR copies. The reference self-BLAST gives the same
26,264 bp RC hit as a control.

## Files

- `assembly.graph1.1.fasta` - representative circular path (the header was
  renamed for plotting; the original path name is
  `945-,943+,901-,943-(circular)`)
- `assembly.graph1.2.fasta` - the SSC flip-flop path (`901+`)
- `cpDNA_NC_000932.1.fasta` - reference
- `hits.tsv`, `hits_strand.tsv` - assembly-versus-reference BLAST
- `self_hits.tsv` - all-vs-all BLAST
- `ref_self_hits.tsv` - reference self-BLAST control
- `dotplot.pdf`, `dotplot.png` - reference dot plot
- `self_dotplot.pdf`, `self_dotplot.png` - self dot plot
- `dotplot.py`, `self_dotplot.py` - plotting scripts
- `figure1.pdf`, `figure1.png` - two-panel Figure 1 (A, reference; B, self-comparison)
- `figure1.py` - two-panel figure script
- `fastp.json`, `fastp.html` - fastp report
- `run.json` - GetOrganelle run provenance
- `workbench_result.json` - Workbench CLI result
- `embplant_pt.K115.complete.graph1.path_sequence.gfa` - complete GFA
- `embplant_pt.K115.graph.selected_graph.gfa` - selected graph GFA
- `run_case.bat` - Workbench command

The old broken DRR188012 case is retained in
[`../arabidopsis_DRR188012_broken/`](../arabidopsis_DRR188012_broken/).
