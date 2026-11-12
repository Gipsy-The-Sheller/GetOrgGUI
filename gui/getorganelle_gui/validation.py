"""Inline validation for the run configuration.

Every message is written as *what happened / why / how to fix it*, so it can
be shown next to the offending control instead of a generic modal dialog.
"""
from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

from .command import protected_flags_in_extra, split_extra_args
from .preprocess import ADAPTER_MODES
from .models import (
    ANONYM,
    MODE_ASSEMBLY,
    MODE_DATABASE,
    MODE_READS,
    ORGANELLES,
    DATABASE_TYPES,
    DependencyReport,
    DatabaseStatus,
    RunConfig,
    ValidationIssue,
    slugify,
    split_organelles,
)
from .settings import Settings

FASTQ_SUFFIXES = (".fq", ".fastq", ".fq.gz", ".fastq.gz", ".fq.tar.gz", ".fastq.tar.gz")
GRAPH_SUFFIXES = (".gfa", ".fastg")
RESERVED_WINDOWS_NAMES = {
    "con",
    "prn",
    "aux",
    "nul",
    *(f"com{i}" for i in range(1, 10)),
    *(f"lpt{i}" for i in range(1, 10)),
}


def parse_kmers(text: str) -> Tuple[List[int], Optional[str]]:
    tokens = [token for token in re.split(r"[,\s]+", (text or "").strip()) if token]
    if not tokens:
        return [], "Enter at least one k-mer value."
    values: List[int] = []
    for token in tokens:
        if not re.fullmatch(r"\d+", token):
            return [], f"'{token}' is not an integer."
        value = int(token)
        if value < 21 or value > 127:
            return [], "SPAdes accepts k-mers from 21 to 127."
        if value % 2 == 0:
            return [], f"k-mer {value} is even; SPAdes requires odd k-mers."
        values.append(value)
    if len(set(values)) != len(values):
        return [], "Duplicate k-mer values."
    if values != sorted(values):
        return [], "k-mers must be listed in increasing order."
    return values, None


def _check_file(
    issues: List[ValidationIssue],
    field: str,
    label: str,
    value: str,
    suffix: Optional[Iterable[str]] = None,
    required: bool = True,
) -> None:
    text = (value or "").strip()
    if not text:
        if required:
            issues.append(
                ValidationIssue("error", field, f"{label} is required.", f"Choose a {label.lower()} file.")
            )
        return
    path = Path(text)
    if not path.is_file():
        issues.append(
            ValidationIssue(
                "error",
                field,
                f"{label} does not exist: {text}",
                "Pick the file again; if it is on a network drive, reconnect the drive.",
            )
        )
        return
    if suffix and not text.lower().endswith(tuple(suffix)):
        issues.append(
            ValidationIssue(
                "warning",
                field,
                f"{label} has an unexpected extension.",
                "GetOrganelle expects FASTQ for reads and GFA/FASTG for graphs.",
            )
        )


def _check_output_dir(issues: List[ValidationIssue], config: RunConfig) -> None:
    output_dir = config.output_dir
    try:
        if output_dir.exists() and not output_dir.is_dir():
            issues.append(
                ValidationIssue(
                    "error",
                    "run_name",
                    "The output path exists and is a file.",
                    "Choose another run name or remove that file.",
                )
            )
            return
        if output_dir.is_dir() and any(output_dir.iterdir()) and not config.overwrite:
            issues.append(
                ValidationIssue(
                    "error",
                    "overwrite",
                    f"Output directory already contains files: {output_dir}",
                    "Enable “Replace existing output” on the Inputs page, or use a new run name.",
                )
            )
        parent = output_dir.parent
        while not parent.exists() and parent != parent.parent:
            parent = parent.parent
        if not os.access(parent, os.W_OK):
            issues.append(
                ValidationIssue(
                    "error",
                    "output_root",
                    f"The output folder is not writable: {parent}",
                    "Choose a workspace under your user profile or another writable drive.",
                )
            )
    except OSError as exc:
        issues.append(
            ValidationIssue(
                "error",
                "output_root",
                f"Cannot inspect the output folder: {exc}",
                "Choose another workspace folder.",
            )
        )


def _check_extra_args(issues: List[ValidationIssue], config: RunConfig) -> None:
    if not config.extra_args.strip():
        return
    try:
        split_extra_args(config.extra_args)
    except ValueError as exc:
        issues.append(
            ValidationIssue(
                "error",
                "extra_args",
                f"Extra options cannot be parsed: {exc}",
                "Check quotation marks, for example: --bowtie2-options \"--very-fast -t\"",
            )
        )
        return
    protected = protected_flags_in_extra(config.extra_args)
    if protected:
        issues.append(
            ValidationIssue(
                "error",
                "extra_args",
                "Extra options must not set inputs, output, mode or database: "
                + ", ".join(sorted(set(protected))),
                "Use the dedicated controls above; keep only tool-specific options here.",
            )
        )


def _check_named_run(issues: List[ValidationIssue], config: RunConfig) -> None:
    name = config.run_name.strip()
    if not name:
        issues.append(
            ValidationIssue("error", "run_name", "Run name is required.", "Use a short sample name.")
        )
        return
    if name != slugify(name):
        issues.append(
            ValidationIssue(
                "error",
                "run_name",
                "Run name contains characters that are unsafe in a folder name.",
                "Use letters, digits, dots, dashes or underscores.",
            )
        )
    if name.lower() in RESERVED_WINDOWS_NAMES:
        issues.append(
            ValidationIssue(
                "error",
                "run_name",
                "Run name is reserved by Windows.",
                "Choose a different name (CON, PRN, AUX, NUL, COM1-9 and LPT1-9 are reserved).",
            )
        )
    if name.endswith(".") or name.endswith(" "):
        issues.append(
            ValidationIssue(
                "error",
                "run_name",
                "Run name must not end with a dot or a space.",
                "Remove the trailing character.",
            )
        )
    if len(name) > 80:
        issues.append(
            ValidationIssue("warning", "run_name", "Run name is long.", "Short names are easier to manage.")
        )
    prefix = config.prefix.strip()
    if prefix:
        if re.search(r'[\\/:*?"<>|]', prefix):
            issues.append(
                ValidationIssue(
                    "error",
                    "prefix",
                    "Prefix must not contain path separators or reserved characters.",
                    "Use letters, digits, dots, dashes or underscores.",
                )
            )
        elif " " in prefix:
            issues.append(
                ValidationIssue(
                    "warning",
                    "prefix",
                    "Prefix contains spaces.",
                    "GetOrganelle builds some internal commands as text; spaces can be fragile.",
                )
            )


def _check_numeric(issues: List[ValidationIssue], config: RunConfig) -> None:
    if not 1 <= config.threads <= 256:
        issues.append(
            ValidationIssue(
                "error",
                "threads",
                "Threads must be between 1 and 256.",
                "Use the number of physical cores available on this machine.",
            )
        )
    if config.mode == MODE_READS:
        if not 1 <= config.rounds <= 1_000_000:
            issues.append(
                ValidationIssue(
                    "error",
                    "rounds",
                    "Rounds must be between 1 and 1,000,000.",
                    "Use 15 for plastomes, 30 for mitogenomes, or a larger value for difficult data.",
                )
            )
        if config.kmer_mode == "custom":
            _, error = parse_kmers(config.kmers)
            if error:
                issues.append(
                    ValidationIssue(
                        "error",
                        "kmers",
                        error,
                        "Example: 21,45,65,85,105 (odd, increasing, 21–127).",
                    )
                )
        if config.max_reads.strip():
            try:
                if float(config.max_reads) <= 0:
                    raise ValueError
            except ValueError:
                issues.append(
                    ValidationIssue(
                        "error",
                        "max_reads",
                        "Max reads must be a positive number (scientific notation is allowed).",
                        "Example: 1.5E7, or leave it empty to use the GetOrganelle default.",
                    )
                )
        coverage = config.reduce_coverage.strip().lower()
        if coverage:
            if coverage != "inf":
                try:
                    if float(coverage) < 10:
                        raise ValueError
                except ValueError:
                    issues.append(
                        ValidationIssue(
                            "error",
                            "reduce_coverage",
                            "Coverage limit must be ≥ 10 or “inf”.",
                            "500 is the GetOrganelle default; use inf to disable reduction.",
                        )
                    )
        max_ext = config.max_extending_len.strip().lower()
        if max_ext:
            tokens = [token.strip() for token in max_ext.split(",") if token.strip()]
            type_count = len(split_organelles(config.organelle)) or 1
            if len(tokens) not in (1, type_count):
                issues.append(
                    ValidationIssue(
                        "error",
                        "max_extending_len",
                        f"{type_count} organelle types need one value or {type_count} comma-separated values.",
                        "Use a single value (applied to every type) or one value per type, e.g. inf,inf.",
                    )
                )
            for token in tokens:
                if token in ("inf", "auto"):
                    continue
                try:
                    if float(token) < 0:
                        raise ValueError
                except ValueError:
                    issues.append(
                        ValidationIssue(
                            "error",
                            "max_extending_len",
                            "Maximum extending length must be a non-negative number, “inf” or “auto”.",
                            "Use inf for seed loci that do not cover the whole genome.",
                        )
                    )
                    break
    else:
        min_depth = config.min_depth.strip().lower() or "0"
        max_depth = config.max_depth.strip().lower() or "inf"
        try:
            min_value = float(min_depth)
            if min_value < 0:
                raise ValueError
        except ValueError:
            issues.append(
                ValidationIssue("error", "min_depth", "Minimum depth must be ≥ 0.", "Example: 0")
            )
            min_value = 0.0
        try:
            max_value = float(max_depth) if max_depth != "inf" else float("inf")
            if max_value < 0:
                raise ValueError
        except ValueError:
            issues.append(
                ValidationIssue(
                    "error", "max_depth", "Maximum depth must be ≥ 0 or “inf”.", "Example: inf"
                )
            )
            max_value = float("inf")
        if max_value < min_value:
            issues.append(
                ValidationIssue(
                    "error",
                    "max_depth",
                    "Maximum depth is smaller than minimum depth.",
                    "Raise the maximum or lower the minimum.",
                )
            )


def _check_inputs(issues: List[ValidationIssue], config: RunConfig) -> None:
    if config.mode == MODE_READS:
        _check_file(issues, "reads_1", "Forward reads", config.reads_1, FASTQ_SUFFIXES)
        if config.reads_2.strip():
            _check_file(issues, "reads_2", "Reverse reads", config.reads_2, FASTQ_SUFFIXES)
            if not config.reads_1.strip():
                issues.append(
                    ValidationIssue(
                        "error",
                        "reads_1",
                        "Reverse reads were selected without forward reads.",
                        "Add the R1 file or clear R2.",
                    )
                )
        for index, part in enumerate(
            [part.strip() for part in config.unpaired.split(",") if part.strip()], start=1
        ):
            _check_file(
                issues,
                "unpaired",
                f"Unpaired reads file {index}",
                part,
                FASTQ_SUFFIXES,
            )
    elif config.mode == MODE_ASSEMBLY:
        _check_file(issues, "graph", "Assembly graph", config.graph, GRAPH_SUFFIXES)
    elif config.mode == MODE_DATABASE:
        action = config.database_action or "install"
        if action not in ("install", "update", "remove"):
            issues.append(
                ValidationIssue(
                    "error",
                    "database_action",
                    f"Unknown database action: {action}.",
                    "Use install, update or remove.",
                )
            )
        if action != "update":
            if not config.database_types.strip() and not config.organelle.strip():
                issues.append(
                    ValidationIssue(
                        "error",
                        "database_types",
                        "No database type was selected.",
                        "Choose at least one organelle type.",
                    )
                )
            else:
                types = [
                    part.strip()
                    for part in (config.database_types or config.organelle).split(",")
                    if part.strip()
                ]
                valid = set(DATABASE_TYPES) | {"all"}
                unknown = [item for item in types if item not in valid]
                if unknown:
                    note = ""
                    if "anonym" in unknown:
                        note = (
                            " “Unknown organelle” uses a custom seed and gene FASTA, "
                            "not a downloadable database."
                        )
                    issues.append(
                        ValidationIssue(
                            "error",
                            "database_types",
                            "Unknown database type: " + ", ".join(unknown) + ".",
                            "Use one of: " + ", ".join(DATABASE_TYPES)
                            + ", or all." + note,
                        )
                    )


def _split_values(value: str) -> List[str]:
    return [part.strip() for part in (value or "").split(",") if part.strip()]


def _check_optional_files(issues: List[ValidationIssue], config: RunConfig) -> None:
    seed_parts = _split_values(config.seed_file)
    gene_parts = _split_values(config.genes_db)
    for index, part in enumerate(seed_parts, start=1):
        label = "Seed file" if len(seed_parts) == 1 else f"Seed file {index}"
        _check_file(issues, "seed_file", label, part)
    for index, part in enumerate(gene_parts, start=1):
        label = "Gene database" if len(gene_parts) == 1 else f"Gene database {index}"
        _check_file(issues, "genes_db", label, part)
    if ANONYM in split_organelles(config.organelle) and config.mode != MODE_DATABASE:
        if not config.seed_file.strip():
            issues.append(
                ValidationIssue(
                    "error",
                    "seed_file",
                    "“Unknown organelle” requires a custom seed sequence.",
                    "Choose a FASTA seed under Advanced options (it is passed as -s).",
                )
            )
        if not config.genes_db.strip():
            issues.append(
                ValidationIssue(
                    "error",
                    "genes_db",
                    "“Unknown organelle” requires a custom gene database.",
                    "Choose a gene FASTA/database under Advanced options (it is passed as --genes).",
                )
            )
    if config.mode == MODE_ASSEMBLY and config.spades_out_dir.strip():
        directory = Path(config.spades_out_dir)
        if not directory.is_dir():
            issues.append(
                ValidationIssue(
                    "error",
                    "spades_out_dir",
                    "SPAdes output folder does not exist.",
                    "Choose the folder that contains scaffolds.fasta and scaffolds.paths.",
                )
            )
        elif not (directory / "scaffolds.fasta").is_file():
            issues.append(
                ValidationIssue(
                    "warning",
                    "spades_out_dir",
                    "scaffolds.fasta was not found in the SPAdes folder.",
                    "Gap filling will be skipped if scaffolds.paths is also missing.",
                )
            )


def _check_preprocess(
    issues: List[ValidationIssue], config: RunConfig, deps: Optional[DependencyReport]
) -> None:
    if not config.preprocess:
        return
    if config.mode != MODE_READS:
        issues.append(
            ValidationIssue(
                "error",
                "preprocess",
                "Read preprocessing is only available in reads mode.",
                "Clear the fastp option or choose reads mode.",
            )
        )
        return
    if deps is not None:
        fastp = deps.tools.get("fastp")
        if fastp is None or not fastp.ok:
            issues.append(
                ValidationIssue(
                    "error",
                    "preprocess",
                    "fastp is not available in the bundled dependencies.",
                    "Rebuild the package with fastp, or disable preprocessing.",
                )
            )
    mode = (config.adapter_mode or "auto").lower()
    if mode not in ADAPTER_MODES:
        issues.append(
            ValidationIssue(
                "error",
                "adapter_mode",
                "Unknown adapter mode.",
                "Choose Auto-detect, Disable adapter trimming, or Custom sequence.",
            )
        )
    if mode == "custom":
        sequence = config.adapter_sequence.strip().upper()
        if not sequence:
            issues.append(
                ValidationIssue(
                    "error",
                    "adapter_sequence",
                    "A custom adapter sequence is required.",
                    "Paste the R1 adapter, or switch to Auto-detect.",
                )
            )
        elif len(sequence) < 5 or any(base not in "ACGTN" for base in sequence):
            issues.append(
                ValidationIssue(
                    "error",
                    "adapter_sequence",
                    "Adapter sequence must be at least 5 bases of A/C/G/T/N.",
                    "Paste the adapter in 5'→3' orientation as provided by the vendor.",
                )
            )
        r2_sequence = config.adapter_sequence_r2.strip().upper()
        if r2_sequence and any(base not in "ACGTN" for base in r2_sequence):
            issues.append(
                ValidationIssue(
                    "error",
                    "adapter_sequence_r2",
                    "R2 adapter sequence contains invalid characters.",
                    "Use only A/C/G/T/N, or leave it empty to reuse the R1 adapter.",
                )
            )
    for field_name, value, low, high, label in (
        ("fastp_quality", config.fastp_quality, 0, 40, "Qualified quality phred"),
        ("fastp_unqualified_percent", config.fastp_unqualified_percent, 0, 100, "Unqualified percent"),
        ("fastp_min_length", config.fastp_min_length, 0, 10000, "Minimum read length"),
        ("trim_front1", config.trim_front1, 0, 10000, "Trim front R1"),
        ("trim_tail1", config.trim_tail1, 0, 10000, "Trim tail R1"),
        ("trim_front2", config.trim_front2, 0, 10000, "Trim front R2"),
        ("trim_tail2", config.trim_tail2, 0, 10000, "Trim tail R2"),
        ("fastp_threads", config.fastp_threads, 0, 256, "fastp threads"),
    ):
        if not low <= int(value) <= high:
            issues.append(
                ValidationIssue(
                    "error",
                    field_name,
                    f"{label} must be between {low} and {high}.",
                    "Use the default unless you have a specific reason to change it.",
                )
            )
    tokens = split_extra_args(config.fastp_extra_args)
    fastp_protected = {"-i", "-I", "-o", "-O", "-j", "-h", "-w", "--thread", "--json", "--html"}
    fastp_conflicts = {
        token.split("=", 1)[0] for token in tokens if token.split("=", 1)[0] in fastp_protected
    }
    conflicts = sorted(fastp_conflicts | set(protected_flags_in_extra(config.fastp_extra_args)))
    if conflicts:
        issues.append(
            ValidationIssue(
                "error",
                "fastp_extra_args",
                "fastp extra options must not set inputs, outputs, reports or threads: "
                + ", ".join(conflicts),
                "Use the dedicated fastp controls above.",
            )
        )


def _check_organelle_selection(issues: List[ValidationIssue], config: RunConfig) -> None:
    types = split_organelles(config.organelle)
    if not types:
        issues.append(
            ValidationIssue(
                "error",
                "organelle",
                "Select at least one organelle type.",
                "Use the checkbox list on the Inputs page.",
            )
        )
        return
    unknown = [item for item in types if item not in ORGANELLES]
    if unknown:
        issues.append(
            ValidationIssue(
                "error",
                "organelle",
                "Unknown organelle type: " + ", ".join(unknown),
                "Use one or more of: " + ", ".join(ORGANELLES) + ".",
            )
        )
        return
    if ANONYM in types and len(types) > 1:
        issues.append(
            ValidationIssue(
                "error",
                "organelle",
                "“Unknown organelle” must be run alone.",
                "Clear the other types, or choose a known organelle type instead.",
            )
        )
    if config.mode == MODE_DATABASE:
        return
    if len(types) > 1:
        seed_parts = _split_values(config.seed_file)
        if seed_parts and len(seed_parts) != len(types):
            issues.append(
                ValidationIssue(
                    "error",
                    "seed_file",
                    f"{len(types)} organelle types need {len(types)} comma-separated seed files.",
                    "Provide one FASTA per type in the same order as -F, or clear the field to use the default database.",
                )
            )
        gene_parts = _split_values(config.genes_db)
        if gene_parts and len(gene_parts) != len(types):
            issues.append(
                ValidationIssue(
                    "error",
                    "genes_db",
                    f"{len(types)} organelle types need {len(types)} comma-separated gene databases.",
                    "Provide one value per type in the same order as -F, or clear the field to use the default database.",
                )
            )


def validate_config(
    config: RunConfig,
    settings: Settings,
    deps: Optional[DependencyReport] = None,
    db_status: Optional[Dict[str, DatabaseStatus]] = None,
) -> List[ValidationIssue]:
    issues: List[ValidationIssue] = []
    if config.mode not in (MODE_READS, MODE_ASSEMBLY, MODE_DATABASE):
        issues.append(
            ValidationIssue("error", "mode", "Unknown run mode.", "Choose Reads or Assembly graph.")
        )
    _check_inputs(issues, config)
    _check_preprocess(issues, config, deps)
    if config.mode != MODE_DATABASE:
        _check_organelle_selection(issues, config)
        _check_named_run(issues, config)
        _check_output_dir(issues, config)
        _check_numeric(issues, config)
        _check_optional_files(issues, config)
        _check_extra_args(issues, config)

    if deps is not None:
        missing = deps.missing_required
        if missing:
            issues.append(
                ValidationIssue(
                    "error",
                    "dependencies",
                    "Required components are missing: "
                    + ", ".join(tool.label for tool in missing),
                    "Open Settings → Dependencies → Check now, then fix the paths.",
                )
            )
        if deps.missing_modules:
            issues.append(
                ValidationIssue(
                    "error",
                    "dependencies",
                    "Python packages are missing: " + ", ".join(deps.missing_modules),
                    "Open Settings → Paths and click “Use running Python” (the bundled venv), "
                    "or run setup_venv.bat / pip install numpy gekko requests for the configured interpreter.",
                )
            )

    if db_status is not None and config.mode != MODE_DATABASE:
        selected = split_organelles(config.organelle)
        required = {item for item in selected if item != ANONYM}
        pair_note = ""
        if "embplant_pt" in selected or "embplant_mt" in selected:
            required.update({"embplant_pt", "embplant_mt"})
            pair_note = " (plastome and mitogenome databases are installed as a pair)"
        missing = []
        for key in sorted(required):
            status = db_status.get(key)
            if status is None or not status.ready:
                missing.append(ORGANELLES.get(key, {}).get("label", key))
        if missing:
            issues.append(
                ValidationIssue(
                    "error",
                    "database",
                    "Missing seed/label database: " + ", ".join(missing) + pair_note,
                    "Open “Manage databases” on the Inputs page and install the selected organelle types.",
                )
            )
    return issues


def issues_by_field(issues: Iterable[ValidationIssue]) -> Dict[str, List[ValidationIssue]]:
    grouped: Dict[str, List[ValidationIssue]] = {}
    for issue in issues:
        grouped.setdefault(issue.field, []).append(issue)
    return grouped


def has_errors(issues: Iterable[ValidationIssue]) -> bool:
    return any(issue.is_error for issue in issues)
