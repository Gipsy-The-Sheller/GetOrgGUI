"""Machine-readable plugin metadata for the GUI, CLI and agent surface.

The shape follows YR-MPE's plugin metadata and ``control_bindings()``
contract: every executable control declares its CLI flag, while GUI-only
controls say so explicitly.
"""
from __future__ import annotations

from pathlib import Path
from typing import Dict, List

from . import PLUGIN_SOURCE, __version__
from .models import ORGANELLES

CITATIONS: Dict[str, str] = {
    "jin2020getorganelle": (
        "@article{jin2020getorganelle,\n"
        "  title={GetOrganelle: a fast and versatile toolkit for accurate de novo assembly of organelle genomes},\n"
        "  author={Jin, Jian-Jun and Yu, Wen-Bin and Yang, Jun-Bo and Song, Yu and dePamphilis, Claude W. and Yi, Ting-Shuang and Li, De-Zhu},\n"
        "  journal={Genome Biology}, volume={21}, pages={241}, year={2020},\n"
        "  doi={10.1186/s13059-020-02154-5}\n}"
    ),
    "prjibelski2020spades": (
        "@article{prjibelski2020spades,\n"
        "  title={Using SPAdes de novo assembler}, author={Prjibelski, Andrey and Antipov, Dmitry and Meleshko, Dmitry and Lapidus, Alla and Korobeynikov, Anton},\n"
        "  journal={Current Protocols in Bioinformatics}, volume={70}, number={1}, pages={e102}, year={2020},\n"
        "  doi={10.1002/cpbi.102}\n}"
    ),
    "langmead2012bowtie2": (
        "@article{langmead2012bowtie2,\n"
        "  title={Fast gapped-read alignment with Bowtie 2}, author={Langmead, Ben and Salzberg, Steven L.},\n"
        "  journal={Nature Methods}, volume={9}, pages={357--359}, year={2012},\n"
        "  doi={10.1038/nmeth.1923}\n}"
    ),
    "camacho2009blast": (
        "@article{camacho2009blast,\n"
        "  title={BLAST+: architecture and applications}, author={Camacho, Christiam and Coulouris, George and Avagyan, Vahram and Ma, Ning and Papadopoulos, Jason and Bealer, Kevin and Madden, Thomas L.},\n"
        "  journal={BMC Bioinformatics}, volume={10}, pages={421}, year={2009},\n"
        "  doi={10.1186/1471-2105-10-421}\n}"
    ),
}


def plugin_info() -> dict:
    return {
        "name": "GetOrganelle Assembly",
        "tool": "GetOrganelle",
        "source": PLUGIN_SOURCE,
        "gui_version": __version__,
        "description": (
            "Assemble organelle genomes from genome-skimming reads or an existing "
            "assembly graph using the native GetOrganelle toolchain."
        ),
        "input_types": {
            "Paired FASTQ": ["fq", "fastq", "fq.gz", "fastq.gz", "tar.gz"],
            "Unpaired FASTQ": ["fq", "fastq", "fq.gz", "fastq.gz"],
            "Assembly graph": ["gfa", "fastg"],
        },
        "output_types": {
            "Organelle scaffolds": ["fasta"],
            "Assembly graph": ["gfa", "fastg"],
            "Table": ["csv"],
            "Log": ["log", "txt"],
        },
        "organelle_types": {
            key: {
                "label": meta["label"],
                "detail": meta["detail"],
                "default_rounds": meta["rounds"],
                "target_size": meta["target_size"],
            }
            for key, meta in ORGANELLES.items()
        },
        "preprocessing": "fastp 1.0.1 (optional adapter trimming / filtering)",
        "graph_analysis": (
            "Reference GenBank BLAST+ screening in the graph viewer "
            "(blastn full record or tblastn annotated CDS)"
        ),
        "citation_keys": list(CITATIONS),
        "skill": "skills/getorganelle.md",
        "result_schema": "yrmpe.result.v1",
        "host_entry_point": "getorganelle_gui.yrtools_entry:GetOrganelleEntry",
        "agent_surface": {
            "transport": "headless-cli",
            "commands": [
                "python -m getorganelle_gui.cli inspect --json",
                "python -m getorganelle_gui.cli check --json",
                "python -m getorganelle_gui.cli run ... --json",
            ],
            "in_process_bridge": False,
        },
    }


def control_bindings() -> List[dict]:
    """Map every executable GUI control to its command-line flag."""
    return [
        {"id": "mode", "widget": "mode_buttons", "label": "Run mode", "kind": "choice",
         "choices": {"Reads": "reads", "Assembly graph": "assembly"},
         "cli": [], "notes": "Selects get_organelle_from_reads.py or get_organelle_from_assembly.py."},
        {"id": "reads_1", "widget": "r1_input", "label": "Forward reads", "kind": "path",
         "cli": ["-1", "{value}"], "notes": "Reads mode only."},
        {"id": "reads_2", "widget": "r2_input", "label": "Reverse reads", "kind": "path",
         "cli": ["-2", "{value}"], "notes": "Optional."},
        {"id": "unpaired", "widget": "unpaired_input", "label": "Unpaired reads", "kind": "text",
         "cli": ["-u", "{value}"], "notes": "Comma-separated list accepted by GetOrganelle."},
        {"id": "graph", "widget": "graph_input", "label": "Assembly graph", "kind": "path",
         "cli": ["-g", "{value}"], "notes": "Assembly mode only; .gfa or .fastg."},
        {"id": "organelle", "widget": "organelle_checks", "label": "Organelle types", "kind": "choice",
         "choices": {meta["label"]: key for key, meta in ORGANELLES.items()},
         "cli": ["-F", "{value}"],
         "notes": "Multi-select; the value is a comma-separated list such as embplant_pt,embplant_mt."},
        {"id": "output_root", "widget": "workspace_input", "label": "Workspace", "kind": "path",
         "cli": [], "notes": "GUI-only; the run folder is <workspace>/<run_name>."},
        {"id": "run_name", "widget": "run_name_edit", "label": "Run name", "kind": "text",
         "cli": [], "notes": "GUI-only folder name."},
        {"id": "threads", "widget": "threads_spin", "label": "CPU threads", "kind": "int",
         "cli": ["-t", "{value}"]},
        {"id": "rounds", "widget": "rounds_spin", "label": "Extending rounds", "kind": "int",
         "cli": ["-R", "{value}"], "notes": "Reads mode only."},
        {"id": "kmers", "widget": "kmer_edit", "label": "SPAdes k-mers", "kind": "text",
         "cli": ["-k", "{value}"], "notes": "Only when k-mer mode is Custom; Auto lets GetOrganelle choose."},
        {"id": "max_reads", "widget": "max_reads_edit", "label": "Maximum reads", "kind": "text",
         "cli": ["--max-reads", "{value}"], "notes": "Empty uses the GetOrganelle default."},
        {"id": "reduce_coverage", "widget": "reduce_cov_edit", "label": "Coverage limit", "kind": "text",
         "cli": ["--reduce-reads-for-coverage", "{value}"]},
        {"id": "max_extending_len", "widget": "max_ext_edit", "label": "Max extending length", "kind": "text",
         "cli": ["--max-extending-len", "{value}"]},
        {"id": "prefix", "widget": "prefix_edit", "label": "Result prefix", "kind": "text",
         "cli": ["--prefix", "{value}"]},
        {"id": "preset", "widget": "preset_combo", "label": "Preset", "kind": "choice",
         "choices": {"Balanced": [], "Fast": ["--fast"], "Memory-saving": ["--memory-save"]},
         "cli": ["{value}"], "notes": "Choice maps to zero or one flag."},
        {"id": "keep_temp", "widget": "keep_temp_check", "label": "Keep temporary files", "kind": "bool",
         "cli": ["--keep-temp"]},
        {"id": "out_per_round", "widget": "out_per_round_check", "label": "Output per round", "kind": "bool",
         "cli": ["--out-per-round"]},
        {"id": "zip_files", "widget": "zip_files_check", "label": "Compress intermediates", "kind": "bool",
         "cli": ["--zip-files"]},
        {"id": "overwrite", "widget": "overwrite_check", "label": "Replace existing output", "kind": "bool",
         "cli": ["--overwrite"]},
        {"id": "min_depth", "widget": "min_depth_edit", "label": "Minimum depth", "kind": "text",
         "cli": ["--min-depth", "{value}"], "notes": "Assembly mode only."},
        {"id": "max_depth", "widget": "max_depth_edit", "label": "Maximum depth", "kind": "text",
         "cli": ["--max-depth", "{value}"], "notes": "Assembly mode only."},
        {"id": "no_slim", "widget": "no_slim_check", "label": "Skip slimming", "kind": "bool",
         "cli": ["--no-slim"], "notes": "Assembly mode only."},
        {"id": "spades_out_dir", "widget": "spades_out_input", "label": "SPAdes scaffolds", "kind": "path",
         "cli": ["--spades-out-dir", "{value}"], "notes": "Assembly mode only; optional."},
        {"id": "seed_file", "widget": "seed_input", "label": "Seed sequence", "kind": "path",
         "cli": ["-s", "{value}"]},
        {"id": "genes_db", "widget": "genes_input", "label": "Gene database", "kind": "path",
         "cli": ["--genes", "{value}"]},
        {"id": "config_dir", "widget": "settings.config_dir", "label": "GetOrganelle config folder", "kind": "path",
         "cli": ["--config-dir", "{value}"], "notes": "Set in Settings."},
        {"id": "extra_args", "widget": "extra_edit", "label": "Extra options", "kind": "text",
         "cli": ["{value}"], "notes": "Split shell-style; protected flags are rejected."},
        {"id": "preprocess", "widget": "enable_check", "label": "fastp preprocessing", "kind": "bool",
         "cli": ["--preprocess"], "notes": "Runs fastp before GetOrganelle; reads mode only."},
        {"id": "adapter_mode", "widget": "adapter_combo", "label": "Adapter handling", "kind": "choice",
         "choices": {"Auto-detect adapters": "auto", "Disable adapter trimming": "none",
                     "Custom adapter sequence": "custom"},
         "cli": ["--adapter-mode", "{value}"]},
        {"id": "adapter_sequence", "widget": "adapter_edit", "label": "R1 adapter", "kind": "text",
         "cli": ["--adapter-sequence", "{value}"], "notes": "Only with adapter_mode=custom."},
        {"id": "adapter_sequence_r2", "widget": "adapter_r2_edit", "label": "R2 adapter", "kind": "text",
         "cli": ["--adapter-sequence-r2", "{value}"], "notes": "Optional; defaults to the R1 adapter."},
        {"id": "fastp_quality", "widget": "quality_spin", "label": "Qualified quality", "kind": "int",
         "cli": ["--fastp-quality", "{value}"]},
        {"id": "fastp_unqualified_percent", "widget": "unqualified_spin",
         "label": "Unqualified percent", "kind": "int",
         "cli": ["--fastp-unqualified-percent", "{value}"]},
        {"id": "fastp_min_length", "widget": "min_length_spin", "label": "Minimum length", "kind": "int",
         "cli": ["--fastp-min-length", "{value}"]},
        {"id": "fastp_dedup", "widget": "dedup_check", "label": "Deduplicate", "kind": "bool",
         "cli": ["--fastp-dedup"]},
        {"id": "fastp_extra_args", "widget": "extra_edit", "label": "fastp extra options", "kind": "text",
         "cli": ["--fastp-extra", "{value}"], "notes": "Protected input/output/report/thread flags are rejected."},
        {"id": "graph_blast_reference", "widget": "blast.reference_input",
         "label": "Reference GenBank", "kind": "path", "cli": [],
         "notes": "GUI-only post-analysis; .gb/.gbk/.gbff is parsed locally, not passed to GetOrganelle."},
        {"id": "graph_blast_mode", "widget": "blast.mode_combo", "label": "BLAST mode",
         "kind": "choice", "choices": {"Full reference": "blastn", "Annotated CDS": "tblastn"},
         "cli": [], "notes": "GUI-only; runs bundled BLAST+ directly against graph node sequences."},
        {"id": "graph_blast_search_evalue", "widget": "blast.search_combo",
         "label": "BLAST search E-value", "kind": "text", "cli": [],
         "notes": "GUI-only; changing the highlight E-value does not rerun BLAST."},
        {"id": "graph_blast_highlight_filters", "widget": "blast.filters",
         "label": "BLAST highlight filters", "kind": "group", "cli": [],
         "notes": "GUI-only: E-value, identity, alignment length, query coverage and distinct genes."},
    ]


def agent_actions() -> List[dict]:
    return [
        {"id": "getorganelle.inspect", "description": "Return plugin metadata, control bindings and dependency status."},
        {"id": "getorganelle.check", "description": "Start every configured tool and report versions."},
        {"id": "getorganelle.run", "description": "Run a headless assembly and emit a yrmpe.result.v1 JSON result."},
    ]


def skill_path() -> str:
    return str(Path(__file__).resolve().parent.parent / "skills" / "getorganelle.md")
