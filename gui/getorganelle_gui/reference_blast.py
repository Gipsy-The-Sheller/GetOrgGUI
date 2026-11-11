"""Reference GenBank BLAST screening for assembly graphs.

This module is deliberately Qt-free so the same code can be used by the GUI,
the headless CLI and tests.  It handles the two modes requested for organelle
contig screening:

``blastn``
    The complete GenBank record (or records) is the query against graph nodes.
``tblastn``
    Annotated CDS features are translated and used as protein queries against
    the six-frame translation of graph nodes.

BLAST hits are kept in memory so the highlight E-value and evidence filters
can be changed without rerunning the search.
"""
from __future__ import annotations

import gzip
import math
import os
import re
import shutil
import subprocess
import threading
import time
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Callable, Dict, Iterable, List, Optional, Sequence, Tuple

from .graph_model import AssemblyGraph

_CREATE_NO_WINDOW = 0x08000000 if os.name == "nt" else 0

BLAST_OUTFMT = (
    "6 qseqid sseqid pident length mismatch gapopen qstart qend "
    "sstart send evalue bitscore qlen slen"
)
DEFAULT_SEARCH_EVALUE = 1e-3
DEFAULT_HIGHLIGHT_EVALUE = 1e-10
MIN_GRAPH_SEQUENCE = 12

_FEATURE_RE = re.compile(r"^ {5}([A-Za-z0-9][A-Za-z0-9_'-]*)\s+(.*)$")
_QUALIFIER_RE = re.compile(r"^/([A-Za-z0-9_]+)(?:=(.*))?$")
_DNA_KEEP = re.compile(r"[^ACGTNRYSWKMBDHV]")

_CODON_TABLE = (
    "FFLLSSSSYY**CC*WLLLLPPPPHHQQRRRRIIIMTTTTNNKKSSRRVVVVAAAADDEEGGGG"
)
_COMPLEMENT = str.maketrans(
    "ACGTRYSWKMBDHVNacgtryswkmbdhvn",
    "TGCAYRSWMKVHDBNtgcayrswmkvhdbn",
)


# --------------------------------------------------------------------------- #
# GenBank parsing
# --------------------------------------------------------------------------- #
@dataclass
class GenBankFeature:
    key: str
    location: str
    qualifiers: Dict[str, str] = field(default_factory=dict)

    @property
    def gene(self) -> str:
        return clean_qualifier(self.qualifiers.get("gene", ""))

    @property
    def product(self) -> str:
        return clean_qualifier(self.qualifiers.get("product", ""))

    @property
    def label(self) -> str:
        gene = self.gene
        product = self.product
        if gene and product and gene.lower() != product.lower():
            return f"{gene} ({product})"
        return gene or product or self.key


@dataclass
class GenBankRecord:
    name: str
    accession: str = ""
    version: str = ""
    sequence: str = ""
    features: List[GenBankFeature] = field(default_factory=list)
    length: int = 0


@dataclass
class ReferenceQuery:
    query_id: str
    label: str
    sequence: str
    gene: str = ""
    feature: str = ""


def clean_qualifier(value: str) -> str:
    value = (value or "").strip()
    if len(value) >= 2 and value[0] == '"' and value[-1] == '"':
        value = value[1:-1]
    return value.replace('""', '"').strip()


def _read_text(path: str) -> str:
    target = Path(path)
    if target.suffix.lower() == ".gz":
        with gzip.open(target, "rt", encoding="utf-8", errors="replace") as handle:
            return handle.read()
    return target.read_text(encoding="utf-8", errors="replace")


def parse_genbank(path: str) -> List[GenBankRecord]:
    """Parse the LOCUS/FEATURES/ORIGIN subset used for reference screening."""
    text = _read_text(path)
    records: List[GenBankRecord] = []
    record: Optional[GenBankRecord] = None
    section = ""
    feature: Optional[GenBankFeature] = None
    qualifier_key: Optional[str] = None
    origin: List[str] = []

    def finish_feature() -> None:
        nonlocal feature, qualifier_key
        if record is not None and feature is not None and feature.location.strip():
            record.features.append(feature)
        feature = None
        qualifier_key = None

    def finish_record() -> None:
        nonlocal record, origin, section
        if record is None:
            return
        finish_feature()
        sequence = "".join(origin).upper()
        if sequence:
            record.sequence = sequence
            record.length = len(sequence)
        records.append(record)
        record = None
        origin = []
        section = ""

    for raw_line in text.splitlines():
        line = raw_line.rstrip("\r\n")
        if line.startswith("LOCUS"):
            finish_record()
            parts = line.split()
            name = parts[1] if len(parts) > 1 else f"record_{len(records) + 1}"
            record = GenBankRecord(name=name)
            section = "header"
            continue
        if record is None:
            continue
        if line.startswith("//"):
            finish_record()
            continue
        if line.startswith("ACCESSION"):
            parts = line.split()
            if len(parts) > 1:
                record.accession = parts[1]
            continue
        if line.startswith("VERSION"):
            parts = line.split()
            if len(parts) > 1:
                record.version = parts[1]
            continue
        if line.startswith("FEATURES"):
            section = "features"
            finish_feature()
            continue
        if line.startswith("ORIGIN"):
            section = "origin"
            finish_feature()
            continue
        if section == "origin":
            origin.append(re.sub(r"[^A-Za-z]", "", line))
            continue
        if section != "features" or not line.strip():
            continue
        match = _FEATURE_RE.match(line)
        if match:
            finish_feature()
            feature = GenBankFeature(key=match.group(1), location=match.group(2).strip())
            continue
        if feature is None:
            continue
        stripped = line.strip()
        if stripped.startswith("/"):
            qualifier_match = _QUALIFIER_RE.match(stripped)
            if not qualifier_match:
                continue
            qualifier_key = qualifier_match.group(1)
            feature.qualifiers[qualifier_key] = qualifier_match.group(2) or ""
            continue
        if qualifier_key is not None:
            previous = feature.qualifiers.get(qualifier_key, "")
            separator = "" if qualifier_key == "translation" else " "
            feature.qualifiers[qualifier_key] = previous + separator + stripped
        else:
            feature.location += stripped

    finish_record()
    if not records:
        raise ValueError("No GenBank LOCUS record found in the reference file.")
    return records


# --------------------------------------------------------------------------- #
# Locations and translation
# --------------------------------------------------------------------------- #
def reverse_complement(sequence: str) -> str:
    return sequence.translate(_COMPLEMENT)[::-1]


def _split_top_level(value: str) -> List[str]:
    parts: List[str] = []
    depth = 0
    start = 0
    for index, character in enumerate(value):
        if character == "(":
            depth += 1
        elif character == ")":
            depth -= 1
        elif character == "," and depth == 0:
            parts.append(value[start:index])
            start = index + 1
    parts.append(value[start:])
    return [part for part in parts if part.strip()]


def extract_location(sequence: str, location: str) -> str:
    """Extract a feature sequence, honouring join()/order()/complement()."""
    text = re.sub(r"\s+", "", location or "")
    if not text:
        return ""
    lowered = text.lower()
    if lowered.startswith("complement(") and text.endswith(")"):
        return reverse_complement(extract_location(sequence, text[len("complement(") : -1]))
    for prefix in ("join(", "order("):
        if lowered.startswith(prefix) and text.endswith(")"):
            inner = text[len(prefix) : -1]
            return "".join(
                extract_location(sequence, part) for part in _split_top_level(inner)
            )
    text = text.strip("<>")
    if "^" in text:
        left = text.split("^", 1)[0]
        start = int(re.sub(r"\D", "", left) or "1")
        return sequence[start - 1 : start]
    if ".." in text:
        left, right = text.split("..", 1)
        start = int(re.sub(r"\D", "", left) or "0")
        end = int(re.sub(r"\D", "", right) or "0")
        if start < 1 or end < start:
            raise ValueError(f"Invalid GenBank location: {location!r}")
        return sequence[start - 1 : end]
    old_style = re.match(r"^(\d+)\.(\d+)$", text)
    if old_style:
        start, end = int(old_style.group(1)), int(old_style.group(2))
        if start < 1 or end < start:
            raise ValueError(f"Invalid GenBank location: {location!r}")
        return sequence[start - 1 : end]
    if text.isdigit():
        position = int(text)
        return sequence[position - 1 : position]
    raise ValueError(f"Unsupported GenBank location: {location!r}")


def _codon_table(table_number: int) -> Dict[str, str]:
    table: Dict[str, str] = {}
    index = 0
    for first in "TCAG":
        for second in "TCAG":
            for third in "TCAG":
                table[first + second + third] = _CODON_TABLE[index]
                index += 1
    if table_number in (2, 11):
        table["TGA"] = "W"
    if table_number == 2:
        table["AGA"] = "*"
        table["AGG"] = "*"
        table["ATA"] = "M"
    return table


def translate_nt(sequence: str, table_number: int = 11) -> str:
    table = _codon_table(table_number)
    sequence = sequence.upper()
    return "".join(
        table.get(sequence[index : index + 3], "X")
        for index in range(0, len(sequence) - 2, 3)
    )


def _int_qualifier(feature: GenBankFeature, key: str, default: int) -> int:
    try:
        return int(clean_qualifier(feature.qualifiers.get(key, "")) or default)
    except ValueError:
        return default


def feature_protein(feature: GenBankFeature, sequence: str) -> str:
    """Return a usable protein query for a GenBank feature, or an empty string."""
    raw_translation = feature.qualifiers.get("translation", "")
    if raw_translation:
        protein = re.sub(r"[^A-Za-z*]", "", raw_translation.replace('"', "")).upper()
    else:
        if feature.key.upper() != "CDS" or not sequence:
            return ""
        try:
            nucleotides = extract_location(sequence, feature.location)
        except ValueError:
            return ""
        codon_start = _int_qualifier(feature, "codon_start", 1)
        if codon_start not in (1, 2, 3):
            codon_start = 1
        table_number = _int_qualifier(feature, "transl_table", 11)
        nucleotides = nucleotides[codon_start - 1 :]
        nucleotides = nucleotides[: len(nucleotides) // 3 * 3]
        protein = translate_nt(nucleotides, table_number)
    protein = protein.rstrip("*").replace("*", "X")
    if len(protein) < 10:
        return ""
    return protein


def build_reference_queries(
    records: Sequence[GenBankRecord], mode: str
) -> List[ReferenceQuery]:
    queries: List[ReferenceQuery] = []
    if mode == "blastn":
        for index, record in enumerate(records, start=1):
            sequence = re.sub(r"[^A-Za-z]", "", record.sequence or "").upper()
            if len(sequence) < 20:
                continue
            label = record.name
            if record.version:
                label += f" {record.version}"
            label += f" ({len(sequence)} bp)"
            queries.append(
                ReferenceQuery(
                    query_id=f"ref_{index:03d}",
                    label=label,
                    sequence=sequence,
                    feature="genome",
                )
            )
    elif mode == "tblastn":
        for record in records:
            for feature in record.features:
                protein = feature_protein(feature, record.sequence)
                if not protein:
                    continue
                query_id = f"prot_{len(queries) + 1:04d}"
                label = feature.label
                if not (feature.gene or feature.product):
                    label = f"{feature.key} {query_id}"
                if len(records) > 1:
                    label += f" [{record.name}]"
                queries.append(
                    ReferenceQuery(
                        query_id=query_id,
                        label=label,
                        sequence=protein,
                        gene=feature.gene or feature.product,
                        feature=feature.label,
                    )
                )
    else:
        raise ValueError(f"Unsupported BLAST mode: {mode}")
    if not queries:
        if mode == "blastn":
            raise ValueError(
                "The GenBank record has no ORIGIN sequence for a blastn query."
            )
        raise ValueError(
            "No translatable CDS features were found. tblastn mode needs CDS "
            "features with /translation or a coding ORIGIN sequence."
        )
    return queries


# --------------------------------------------------------------------------- #
# FASTA preparation and BLAST execution
# --------------------------------------------------------------------------- #
@dataclass
class BlastRunConfig:
    reference_path: str
    mode: str
    evalue: float
    threads: int
    work_dir: str
    blastn: str
    tblastn: str
    makeblastdb: str
    max_target_seqs: int = 5000
    max_hsps: int = 5


@dataclass
class BlastHit:
    query_id: str
    query_label: str
    gene: str
    node_id: str
    pident: float
    length: int
    mismatch: int
    gapopen: int
    qstart: int
    qend: int
    sstart: int
    send: int
    evalue: float
    bitscore: float
    qlen: int
    slen: int
    query_coverage: float
    subject_coverage: float
    mode: str

    @property
    def strand(self) -> str:
        return "+" if self.sstart <= self.send else "-"


@dataclass
class NodeBlastSummary:
    node_id: str
    hits: List[BlastHit]

    @property
    def best_hit(self) -> BlastHit:
        return min(self.hits, key=lambda hit: (hit.evalue, -hit.bitscore))


@dataclass
class BlastResult:
    mode: str
    evalue: float
    reference_path: str
    work_dir: str
    query_count: int
    subject_count: int
    total_nodes: int
    skipped_nodes: int
    hits: List[BlastHit]
    nodes: Dict[str, NodeBlastSummary]
    commands: List[List[str]] = field(default_factory=list)
    started_at: str = ""
    finished_at: str = ""


@dataclass
class BlastFilters:
    evalue: float = DEFAULT_HIGHLIGHT_EVALUE
    min_identity: float = 0.0
    min_alignment: int = 0
    min_query_coverage: float = 0.0
    min_distinct_genes: int = 1


@dataclass
class NodeHitView:
    node_id: str
    best_hit: BlastHit
    hit_count: int
    distinct_genes: int
    max_query_coverage: float
    max_subject_coverage: float


class BlastCancelled(Exception):
    pass


def _clean_dna(sequence: str) -> str:
    return _DNA_KEEP.sub("N", (sequence or "").upper().replace("U", "T"))


def write_fasta(
    path: Path, records: Iterable[Tuple[str, str]], width: int = 70
) -> None:
    with path.open("w", encoding="ascii", newline="\n") as handle:
        for identifier, sequence in records:
            handle.write(f">{identifier}\n")
            for start in range(0, len(sequence), width):
                handle.write(sequence[start : start + width] + "\n")


def write_graph_fasta(
    graph: AssemblyGraph, path: Path, min_length: int = MIN_GRAPH_SEQUENCE
) -> Tuple[Dict[str, str], int]:
    """Write graph nodes and return (subject id -> node id, skipped count)."""
    mapping: Dict[str, str] = {}
    entries: List[Tuple[str, str]] = []
    skipped = 0
    for index, node in enumerate(graph.nodes.values(), start=1):
        sequence = _clean_dna(node.sequence)
        if len(sequence) < min_length:
            skipped += 1
            continue
        subject_id = f"node_{index:06d}"
        mapping[subject_id] = node.id
        entries.append((subject_id, sequence))
    if not entries:
        raise ValueError(
            "The graph has no segment sequences to search. GFA nodes with '*' "
            "and empty FASTG records cannot be BLASTed."
        )
    write_fasta(path, entries)
    return mapping, skipped


def _resolve_key(identifier: str, mapping: Dict[str, str]) -> Optional[str]:
    if identifier in mapping:
        return identifier
    for candidate in (identifier.split("|")[-1], identifier.split("|")[0]):
        if candidate in mapping:
            return candidate
    return None


def parse_blast_tabular(
    text: str,
    subject_map: Dict[str, str],
    queries: Sequence[ReferenceQuery],
    mode: str,
) -> List[BlastHit]:
    query_map = {
        query.query_id: query for query in queries
    }
    hits: List[BlastHit] = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        fields = line.split("\t")
        if len(fields) < 14:
            continue
        try:
            (
                qseqid,
                sseqid,
                pident,
                length,
                mismatch,
                gapopen,
                qstart,
                qend,
                sstart,
                send,
                evalue,
                bitscore,
                qlen,
                slen,
            ) = fields[:14]
            query_key = _resolve_key(qseqid, query_map)
            subject_key = _resolve_key(sseqid, subject_map)
            if query_key is None or subject_key is None:
                continue
            query = query_map[query_key]
            node_id = subject_map[subject_key]
            alignment_length = int(length)
            query_length = max(1, int(qlen))
            subject_length = max(1, int(slen))
            query_coverage = min(1.0, alignment_length / query_length)
            if mode == "tblastn":
                subject_coverage = min(1.0, (alignment_length * 3.0) / subject_length)
            else:
                subject_coverage = min(1.0, alignment_length / subject_length)
            hits.append(
                BlastHit(
                    query_id=query_key,
                    query_label=query.label,
                    gene=query.gene,
                    node_id=node_id,
                    pident=float(pident),
                    length=alignment_length,
                    mismatch=int(mismatch),
                    gapopen=int(gapopen),
                    qstart=int(qstart),
                    qend=int(qend),
                    sstart=int(sstart),
                    send=int(send),
                    evalue=float(evalue),
                    bitscore=float(bitscore),
                    qlen=query_length,
                    slen=subject_length,
                    query_coverage=query_coverage,
                    subject_coverage=subject_coverage,
                    mode=mode,
                )
            )
        except (TypeError, ValueError):
            continue
    return hits


def build_result(
    graph: AssemblyGraph,
    config: BlastRunConfig,
    queries: Sequence[ReferenceQuery],
    subject_map: Dict[str, str],
    skipped_nodes: int,
    hits: List[BlastHit],
    commands: List[List[str]],
    started_at: str,
    finished_at: str,
) -> BlastResult:
    by_node: Dict[str, List[BlastHit]] = defaultdict(list)
    for hit in hits:
        by_node[hit.node_id].append(hit)
    summaries = {
        node_id: NodeBlastSummary(
            node_id=node_id,
            hits=sorted(node_hits, key=lambda hit: (hit.evalue, -hit.bitscore)),
        )
        for node_id, node_hits in by_node.items()
    }
    return BlastResult(
        mode=config.mode,
        evalue=config.evalue,
        reference_path=config.reference_path,
        work_dir=config.work_dir,
        query_count=len(queries),
        subject_count=len(subject_map),
        total_nodes=len(graph.nodes),
        skipped_nodes=skipped_nodes,
        hits=hits,
        nodes=summaries,
        commands=commands,
        started_at=started_at,
        finished_at=finished_at,
    )


class ReferenceBlastRunner:
    """Blocking BLAST runner with a thread-safe cancel hook."""

    def __init__(self, graph: AssemblyGraph, config: BlastRunConfig):
        self.graph = graph
        self.config = config
        self._process: Optional[subprocess.Popen] = None
        self._cancel = threading.Event()

    def cancel(self) -> None:
        self._cancel.set()
        process = self._process
        if process is not None and process.poll() is None:
            try:
                process.terminate()
            except OSError:
                pass

    def _check_cancelled(self) -> None:
        if self._cancel.is_set():
            raise BlastCancelled("BLAST was cancelled.")

    def _run_command(
        self, argv: Sequence[str], work_dir: Path, log_name: str, label: str
    ) -> None:
        self._check_cancelled()
        log_path = work_dir / log_name
        with log_path.open("w", encoding="utf-8", errors="replace") as log:
            process = subprocess.Popen(
                list(argv),
                cwd=str(work_dir),
                stdout=log,
                stderr=subprocess.STDOUT,
                creationflags=_CREATE_NO_WINDOW,
            )
            self._process = process
            while process.poll() is None:
                if self._cancel.is_set():
                    try:
                        process.terminate()
                    except OSError:
                        pass
                    try:
                        process.wait(timeout=3)
                    except subprocess.TimeoutExpired:
                        process.kill()
                    raise BlastCancelled("BLAST was cancelled.")
                time.sleep(0.2)
            returncode = process.returncode
        self._process = None
        if returncode != 0:
            detail = _tail(log_path)
            raise RuntimeError(f"{label} failed (exit {returncode}). {detail}")

    def run(self, status: Optional[Callable[[str], None]] = None) -> BlastResult:
        config = self.config
        mode = config.mode
        if mode not in ("blastn", "tblastn"):
            raise ValueError(f"Unsupported BLAST mode: {mode}")
        work_dir = Path(config.work_dir)
        work_dir.mkdir(parents=True, exist_ok=True)
        started_at = datetime.now().isoformat(timespec="seconds")
        emit = status or (lambda _message: None)

        emit("Reading GenBank annotations…")
        records = parse_genbank(config.reference_path)
        queries = build_reference_queries(records, mode)
        reference_fasta = work_dir / "reference.fasta"
        write_fasta(reference_fasta, ((query.query_id, query.sequence) for query in queries))

        emit(f"Preparing {len(self.graph.nodes)} graph nodes…")
        graph_fasta = work_dir / "graph_nodes.fasta"
        subject_map, skipped_nodes = write_graph_fasta(self.graph, graph_fasta)

        commands: List[List[str]] = []
        database = work_dir / "graph_db"
        makeblastdb_argv = [
            config.makeblastdb,
            "-in",
            graph_fasta.name,
            "-dbtype",
            "nucl",
            "-out",
            database.name,
            "-title",
            "GetOrganelle assembly graph",
            "-logfile",
            "makeblastdb.log",
        ]
        commands.append(makeblastdb_argv)
        emit("Building graph BLAST database…")
        self._run_command(makeblastdb_argv, work_dir, "makeblastdb_stdio.log", "makeblastdb")

        program = config.blastn if mode == "blastn" else config.tblastn
        hits_path = work_dir / "hits.tsv"
        blast_argv = [
            program,
            "-query",
            reference_fasta.name,
            "-db",
            database.name,
            "-out",
            hits_path.name,
            "-outfmt",
            BLAST_OUTFMT,
            "-evalue",
            f"{config.evalue:g}",
            "-max_target_seqs",
            str(max(1, config.max_target_seqs)),
            "-max_hsps",
            str(max(1, config.max_hsps)),
            "-num_threads",
            str(max(1, config.threads)),
        ]
        if mode == "blastn":
            blast_argv.extend(["-task", "blastn"])
        commands.append(blast_argv)
        emit(
            f"Running {mode} ({len(queries)} queries against "
            f"{len(subject_map)} node sequences)…"
        )
        self._run_command(blast_argv, work_dir, "blast_stdio.log", mode)
        if not hits_path.is_file():
            raise RuntimeError(f"{mode} did not produce a tabular output file.")

        emit("Parsing BLAST hits…")
        hits = parse_blast_tabular(
            hits_path.read_text(encoding="utf-8", errors="replace"),
            subject_map,
            queries,
            mode,
        )
        finished_at = datetime.now().isoformat(timespec="seconds")
        return build_result(
            self.graph,
            config,
            queries,
            subject_map,
            skipped_nodes,
            hits,
            commands,
            started_at,
            finished_at,
        )


def _tail(path: Path, limit: int = 1200) -> str:
    try:
        text = path.read_text(encoding="utf-8", errors="replace").strip()
    except OSError:
        return ""
    return text[-limit:]


def resolve_blast_tools(settings=None) -> Dict[str, str]:
    """Locate BLAST+ from the packaged dependency directory or PATH."""
    folders: List[Path] = []
    dep_root = getattr(settings, "dep_root", "") if settings is not None else ""
    if dep_root:
        folders.append(Path(dep_root) / "ncbi-blast")
    repository = Path(__file__).resolve().parents[2]
    folders.append(repository / "GetOrganelle" / "GetOrganelleDep" / "Windows" / "ncbi-blast")
    names = ("blastn", "tblastn", "makeblastdb")
    tools: Dict[str, str] = {}
    missing: List[str] = []
    for name in names:
        executable_names = [name + ".exe", name] if os.name == "nt" else [name]
        found = ""
        for folder in folders:
            for executable_name in executable_names:
                candidate = folder / executable_name
                if candidate.is_file():
                    found = str(candidate)
                    break
            if found:
                break
        if not found:
            found = shutil.which(name) or shutil.which(name + ".exe") or ""
        if found:
            tools[name] = found
        else:
            missing.append(name)
    if missing:
        raise FileNotFoundError(
            "NCBI BLAST+ tools were not found: " + ", ".join(missing)
        )
    return tools


def parse_evalue(text: str) -> float:
    try:
        value = float(str(text).strip())
    except (TypeError, ValueError):
        raise ValueError("Use a positive E-value, for example 1e-10.")
    if not math.isfinite(value) or value <= 0:
        raise ValueError("Use a positive E-value, for example 1e-10.")
    return value


def format_evalue(value: float) -> str:
    if value == 0:
        return "0"
    if value < 1e-3 or value >= 1e4:
        return f"{value:.1e}"
    return f"{value:.3g}"


def filter_node_hits(
    result: BlastResult, filters: BlastFilters
) -> List[NodeHitView]:
    """Apply the live highlight filters and return one view per passing node."""
    views: List[NodeHitView] = []
    for summary in result.nodes.values():
        passing = [
            hit
            for hit in summary.hits
            if hit.evalue <= filters.evalue
            and hit.pident >= filters.min_identity
            and hit.length >= filters.min_alignment
            and hit.query_coverage * 100.0 >= filters.min_query_coverage
        ]
        if not passing:
            continue
        genes = {hit.gene or hit.query_id for hit in passing}
        if len(genes) < max(1, filters.min_distinct_genes):
            continue
        best = min(passing, key=lambda hit: (hit.evalue, -hit.bitscore))
        views.append(
            NodeHitView(
                node_id=summary.node_id,
                best_hit=best,
                hit_count=len(passing),
                distinct_genes=len(genes),
                max_query_coverage=max(hit.query_coverage for hit in passing),
                max_subject_coverage=max(hit.subject_coverage for hit in passing),
            )
        )
    views.sort(key=lambda view: (view.best_hit.evalue, -view.best_hit.bitscore, view.node_id))
    return views
