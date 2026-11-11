"""Plain data models shared by the GUI, CLI and tests.

This module must stay free of Qt imports so that the headless agent surface
and the unit tests can run without a display.
"""
from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

MODE_READS = "reads"
MODE_ASSEMBLY = "assembly"
MODE_DATABASE = "database"

MODE_LABELS = {
    MODE_READS: "Reads",
    MODE_ASSEMBLY: "Assembly graph",
    MODE_DATABASE: "Database",
}

ORGANELLES: Dict[str, Dict[str, Any]] = {
    "embplant_pt": {
        "label": "Embryophyta plastome",
        "detail": "Land-plant chloroplast genome; typically ~150 kb.",
        "rounds": 15,
        "target_size": "130000",
    },
    "embplant_mt": {
        "label": "Plant mitogenome",
        "detail": "Land-plant mitochondrial genome; typically 200–500 kb.",
        "rounds": 30,
        "target_size": "390000",
    },
    "embplant_nr": {
        "label": "Plant nrDNA",
        "detail": "Plant nuclear ribosomal RNA repeat; typically ~13 kb.",
        "rounds": 10,
        "target_size": "13000",
    },
    "other_pt": {
        "label": "Non-embryophyta plastome",
        "detail": "Algal and other non-land-plant plastid genomes.",
        "rounds": 30,
        "target_size": "39000",
    },
    "animal_mt": {
        "label": "Animal mitogenome",
        "detail": "Animal mitochondrial genome; typically ~16 kb.",
        "rounds": 10,
        "target_size": "13000",
    },
    "fungus_mt": {
        "label": "Fungal mitogenome",
        "detail": "Fungal mitochondrial genome; typically ~65 kb.",
        "rounds": 10,
        "target_size": "65000",
    },
    "fungus_nr": {
        "label": "Fungal nrDNA",
        "detail": "Fungal nuclear ribosomal RNA repeat; typically ~13 kb.",
        "rounds": 10,
        "target_size": "13000",
    },
    "anonym": {
        "label": "Unknown organelle",
        "detail": "Requires a custom seed file and gene database.",
        "rounds": 15,
        "target_size": "39000",
    },
}

ANONYM = "anonym"
DEFAULT_KMERS = "21,45,65,85,105"
STATUS_SUCCESS = "success"
STATUS_WARNING = "warning"
STATUS_ERROR = "error"
STATUS_CANCELLED = "cancelled"
STATUS_RUNNING = "running"
STATUS_IDLE = "idle"


def split_organelles(value: str) -> List[str]:
    """Parse a -F style list, preserving order but dropping duplicates."""
    parts = [part.strip() for part in (value or "").replace(";", ",").split(",")]
    seen = set()
    result = []
    for part in parts:
        if part and part not in seen:
            seen.add(part)
            result.append(part)
    return result


def organelle_label(value: str) -> str:
    types = split_organelles(value)
    if not types:
        return "No organelle selected"
    return " + ".join(ORGANELLES.get(item, {}).get("label", item) for item in types)


def organelle_slug(value: str) -> str:
    types = split_organelles(value)
    return "-".join(types) if types else "organelle"


def organelle_default_rounds(value: str) -> int:
    types = split_organelles(value)
    rounds = [ORGANELLES.get(item, {}).get("rounds", 15) for item in types]
    return max(rounds) if rounds else 15


def now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def slugify(value: str, fallback: str = "run") -> str:
    value = re.sub(r"[^A-Za-z0-9._-]+", "_", (value or "").strip())
    value = value.strip("._-")
    return value or fallback


@dataclass
class ValidationIssue:
    level: str
    field: str
    message: str
    hint: str = ""

    @property
    def is_error(self) -> bool:
        return self.level == "error"

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class RunConfig:
    mode: str = MODE_READS
    reads_1: str = ""
    reads_2: str = ""
    unpaired: str = ""
    graph: str = ""
    organelle: str = "embplant_pt"
    output_root: str = ""
    run_name: str = ""
    threads: int = 8
    rounds: int = 15
    kmer_mode: str = "auto"
    kmers: str = DEFAULT_KMERS
    max_reads: str = ""
    reduce_coverage: str = "500"
    max_extending_len: str = "inf"
    prefix: str = ""
    preset: str = "balanced"
    keep_temp: bool = False
    out_per_round: bool = False
    zip_files: bool = False
    overwrite: bool = False
    min_depth: str = "0"
    max_depth: str = "inf"
    no_slim: bool = False
    spades_out_dir: str = ""
    seed_file: str = ""
    genes_db: str = ""
    config_dir: str = ""
    extra_args: str = ""
    database_types: str = ""
    preprocess: bool = False
    adapter_mode: str = "auto"  # auto | none | custom
    adapter_sequence: str = ""
    adapter_sequence_r2: str = ""
    trim_front1: int = 0
    trim_tail1: int = 0
    trim_front2: int = 0
    trim_tail2: int = 0
    fastp_quality: int = 15
    fastp_unqualified_percent: int = 40
    fastp_min_length: int = 15
    fastp_dedup: bool = False
    fastp_extra_args: str = ""
    fastp_threads: int = 0

    def __post_init__(self) -> None:
        if not self.run_name:
            self.run_name = self.suggested_run_name()

    def suggested_run_name(self) -> str:
        if self.mode == MODE_ASSEMBLY:
            stem = Path(self.graph).stem if self.graph else "assembly"
        elif self.reads_1:
            stem = Path(self.reads_1).stem
            stem = re.sub(r"[_.-]?(R?1|forward|fwd|read1)$", "", stem, flags=re.I)
        else:
            stem = "sample"
        return slugify(f"{stem}_{organelle_slug(self.organelle)}")

    @property
    def output_dir(self) -> Path:
        return Path(self.output_root) / slugify(self.run_name)

    def to_dict(self) -> dict:
        data = asdict(self)
        data["output_dir"] = str(self.output_dir)
        return data

    @classmethod
    def from_dict(cls, data: dict) -> "RunConfig":
        known = {name for name in cls.__dataclass_fields__}
        return cls(**{key: value for key, value in (data or {}).items() if key in known})


@dataclass
class OutputItem:
    kind: str
    path: str
    size: int = 0
    sequences: int = 0
    total_bp: int = 0
    max_len: int = 0
    gc_percent: float = 0.0
    detail: str = ""

    @property
    def name(self) -> str:
        return Path(self.path).name

    def to_dict(self) -> dict:
        data = asdict(self)
        data["name"] = self.name
        return data


@dataclass
class RunResult:
    run_id: str
    status: str
    mode: str
    organelle: str
    run_name: str
    output_dir: str
    command: List[str] = field(default_factory=list)
    exit_code: Optional[int] = None
    started_at: str = ""
    finished_at: str = ""
    elapsed_s: float = 0.0
    items: List[OutputItem] = field(default_factory=list)
    artifacts: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    log_tail: List[str] = field(default_factory=list)
    summary: Dict[str, Any] = field(default_factory=dict)
    schema: str = "getorganelle.run.v1"
    error_message: str = ""

    @property
    def sequence_items(self) -> List[OutputItem]:
        return [item for item in self.items if item.kind in ("scaffolds", "contigs", "sequence")]

    @property
    def total_bp(self) -> int:
        return sum(item.total_bp for item in self.sequence_items)

    @property
    def ok(self) -> bool:
        return self.status in (STATUS_SUCCESS, STATUS_WARNING)

    def to_dict(self) -> dict:
        data = asdict(self)
        data["items"] = [item.to_dict() for item in self.items]
        data["total_bp"] = self.total_bp
        return data

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False)

    @classmethod
    def from_dict(cls, data: dict) -> "RunResult":
        payload = dict(data or {})
        item_fields = set(OutputItem.__dataclass_fields__)
        payload["items"] = [
            OutputItem(**{key: value for key, value in item.items() if key in item_fields})
            for item in payload.get("items", [])
        ]
        known = {name for name in cls.__dataclass_fields__}
        return cls(**{key: value for key, value in payload.items() if key in known})


@dataclass
class ToolStatus:
    key: str
    label: str
    path: str = ""
    version: str = ""
    ok: bool = False
    detail: str = ""
    required: bool = True

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class DependencyReport:
    tools: Dict[str, ToolStatus] = field(default_factory=dict)
    modules: Dict[str, bool] = field(default_factory=dict)
    getorganelle_root: str = ""
    dep_root: str = ""
    getorganelle_version: str = ""
    python_executable: str = ""
    config_dir: str = ""
    checked_at: str = ""

    @property
    def missing_required(self) -> List[ToolStatus]:
        return [
            tool
            for tool in self.tools.values()
            if tool.required and not tool.ok
        ]

    @property
    def missing_modules(self) -> List[str]:
        return [name for name, ok in self.modules.items() if not ok]

    @property
    def ok(self) -> bool:
        return not self.missing_required and not self.missing_modules

    def summary_text(self) -> str:
        if self.ok:
            return "Toolchain ready"
        missing = [tool.label for tool in self.missing_required]
        missing.extend(self.missing_modules)
        if not missing:
            return "Toolchain needs attention"
        return "Missing: " + ", ".join(missing[:4]) + (
            "…" if len(missing) > 4 else ""
        )

    def to_dict(self) -> dict:
        return {
            "ok": self.ok,
            "summary": self.summary_text(),
            "getorganelle_root": self.getorganelle_root,
            "dep_root": self.dep_root,
            "getorganelle_version": self.getorganelle_version,
            "python_executable": self.python_executable,
            "config_dir": self.config_dir,
            "checked_at": self.checked_at,
            "tools": {key: tool.to_dict() for key, tool in self.tools.items()},
            "python_modules": dict(self.modules),
        }


@dataclass
class DatabaseStatus:
    organelle: str
    label: str
    seed: bool
    label_db: bool
    seed_path: str = ""
    label_path: str = ""

    @property
    def ready(self) -> bool:
        return self.seed and self.label_db

    def to_dict(self) -> dict:
        data = asdict(self)
        data["ready"] = self.ready
        return data
