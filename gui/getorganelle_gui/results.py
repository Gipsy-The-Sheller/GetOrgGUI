"""Scan a GetOrganelle output directory and build result/provenance objects."""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

from .models import (
    MODE_DATABASE,
    MODE_READS,
    STATUS_CANCELLED,
    STATUS_ERROR,
    STATUS_SUCCESS,
    STATUS_WARNING,
    OutputItem,
    RunConfig,
    RunResult,
)
from .resultspec import (
    DatasetItemSpec,
    DatasetSpec,
    ITEM_TYPE_SEQUENCE,
    ITEM_TYPE_TABLE,
    ResultSpec,
    RunSpec,
)

FASTA_SUFFIXES = (".fasta", ".fa", ".fna", ".fas")
GRAPH_SUFFIXES = (".gfa", ".fastg")
TABLE_SUFFIXES = (".csv", ".tsv")
LOG_SUFFIXES = (".log", ".txt")


def fasta_stats(path: Path) -> Dict[str, float]:
    records = 0
    total = 0
    longest = 0
    gc = 0
    current = 0
    try:
        with path.open("r", encoding="utf-8", errors="replace") as handle:
            for line in handle:
                if line.startswith(">"):
                    records += 1
                    if current:
                        total += current
                        longest = max(longest, current)
                        current = 0
                else:
                    sequence = line.strip()
                    if not sequence:
                        continue
                    sequence = sequence.upper()
                    current += len(sequence)
                    gc += sequence.count("G") + sequence.count("C")
            if current:
                total += current
                longest = max(longest, current)
    except OSError:
        return {"sequences": 0, "total_bp": 0, "max_len": 0, "gc_percent": 0.0}
    gc_percent = (100.0 * gc / total) if total else 0.0
    return {
        "sequences": records,
        "total_bp": total,
        "max_len": longest,
        "gc_percent": round(gc_percent, 2),
    }


def _kind_for(path: Path) -> Optional[str]:
    name = path.name.lower()
    suffix = path.suffix.lower()
    if suffix in FASTA_SUFFIXES:
        if "scaffold" in name or "path_sequence" in name or "contig" in name:
            return "scaffolds"
        return "sequence"
    if suffix in GRAPH_SUFFIXES:
        return "graph"
    if suffix in TABLE_SUFFIXES:
        return "table"
    if suffix in LOG_SUFFIXES:
        return "log"
    return None


def scan_outputs(output_dir: Path) -> Tuple[List[OutputItem], List[str]]:
    items: List[OutputItem] = []
    artifacts: List[str] = []
    if not output_dir.is_dir():
        return items, artifacts

    def add(path: Path) -> None:
        kind = _kind_for(path)
        if kind is None:
            return
        detail = ""
        stats = {"sequences": 0, "total_bp": 0, "max_len": 0, "gc_percent": 0.0}
        if kind in ("scaffolds", "sequence"):
            stats = fasta_stats(path)
            detail = f"{stats['sequences']} sequences"
        elif kind == "graph":
            detail = "Assembly graph"
        elif kind == "table":
            detail = "Table"
        elif kind == "log":
            detail = "Log file"
        try:
            size = path.stat().st_size
        except OSError:
            size = 0
        items.append(
            OutputItem(
                kind=kind,
                path=str(path),
                size=size,
                sequences=int(stats["sequences"]),
                total_bp=int(stats["total_bp"]),
                max_len=int(stats["max_len"]),
                gc_percent=float(stats["gc_percent"]),
                detail=detail,
            )
        )
        artifacts.append(str(path))

    for entry in sorted(output_dir.iterdir()):
        if entry.is_file():
            add(entry)

    if not any(item.kind in ("scaffolds", "sequence") for item in items):
        for entry in sorted(output_dir.rglob("*path_sequence.fasta")):
            if entry.is_file() and entry.parent != output_dir:
                add(entry)
                if sum(1 for item in items if item.kind in ("scaffolds", "sequence")) >= 3:
                    break
    return items, artifacts


def _warning_lines(log_lines: Iterable[str], limit: int = 20) -> List[str]:
    warnings: List[str] = []
    seen = set()
    for line in log_lines:
        text = line.strip()
        if not text:
            continue
        if re.search(r"\b(WARNING|ERROR)\b", text) or "Traceback" in text:
            key = re.sub(r"^\d{4}-\d{2}-\d{2}[^ ]* - ", "", text)
            if key in seen:
                continue
            seen.add(key)
            warnings.append(text)
            if len(warnings) >= limit:
                break
    return warnings


def _error_message(exit_code: int, lines: List[str]) -> str:
    tail = [line.strip() for line in lines[-16:] if line.strip()]
    detail = "\n".join(tail[-8:])
    message = f"GetOrganelle exited with code {exit_code}."
    if detail:
        message += "\n\nLast output:\n" + detail
    return message


def build_run_result(
    config: RunConfig,
    *,
    run_id: str,
    exit_code: int,
    log_lines: List[str],
    started_at: str,
    finished_at: str,
    elapsed_s: float,
    cancelled: bool = False,
) -> RunResult:
    output_dir = config.output_dir
    if config.mode == MODE_DATABASE:
        status = STATUS_SUCCESS if exit_code == 0 and not cancelled else (
            STATUS_CANCELLED if cancelled else STATUS_ERROR
        )
        artifacts: List[str] = []
        summary = {
            "mode": MODE_DATABASE,
            "database_types": config.database_types or config.organelle,
        }
        error_message = "" if status == STATUS_SUCCESS else (
            "Database initialisation was cancelled."
            if status == STATUS_CANCELLED
            else _error_message(exit_code, log_lines)
        )
        return RunResult(
            run_id=run_id,
            status=status,
            mode=config.mode,
            organelle=config.organelle,
            run_name=config.run_name,
            output_dir=str(output_dir),
            exit_code=exit_code,
            started_at=started_at,
            finished_at=finished_at,
            elapsed_s=elapsed_s,
            artifacts=artifacts,
            warnings=_warning_lines(log_lines),
            log_tail=log_lines[-60:],
            summary=summary,
            error_message=error_message,
        )

    items, artifacts = scan_outputs(output_dir)
    sequence_items = [item for item in items if item.kind in ("scaffolds", "sequence")]
    log_text = "\n".join(log_lines)
    internal_error = "Traceback (most recent call last)" in log_text
    if cancelled:
        status = STATUS_CANCELLED
    elif exit_code != 0:
        status = STATUS_ERROR
    elif sequence_items:
        status = STATUS_SUCCESS
    elif internal_error:
        status = STATUS_ERROR
    else:
        status = STATUS_WARNING
    error_message = ""
    if status == STATUS_ERROR:
        error_message = _error_message(exit_code, log_lines)
        if exit_code == 0 and internal_error:
            error_message = "GetOrganelle reported an internal exception.\n\n" + "\n".join(
                [line for line in log_lines if line.strip()][-8:]
            )
    elif status == STATUS_CANCELLED:
        error_message = "Run cancelled by the user."
    summary = {
        "mode": config.mode,
        "organelle": config.organelle,
        "threads": config.threads,
        "rounds": config.rounds if config.mode == MODE_READS else None,
        "kmers": (
            config.kmers if config.kmer_mode == "custom" else "auto"
        )
        if config.mode == MODE_READS
        else None,
        "exit_code": exit_code,
        "sequence_files": len(sequence_items),
        "contigs": sum(item.sequences for item in sequence_items),
        "total_bp": sum(item.total_bp for item in sequence_items),
        "elapsed_s": round(elapsed_s, 1),
    }
    return RunResult(
        run_id=run_id,
        status=status,
        mode=config.mode,
        organelle=config.organelle,
        run_name=config.run_name,
        output_dir=str(output_dir),
        exit_code=exit_code,
        started_at=started_at,
        finished_at=finished_at,
        elapsed_s=elapsed_s,
        items=items,
        artifacts=artifacts,
        warnings=_warning_lines(log_lines),
        log_tail=log_lines[-60:],
        summary=summary,
        error_message=error_message,
    )


def write_run_json(result: RunResult, directory: Optional[Path] = None) -> Path:
    target_dir = Path(directory or result.output_dir)
    target_dir.mkdir(parents=True, exist_ok=True)
    path = target_dir / "run.json"
    with path.open("w", encoding="utf-8") as handle:
        json.dump(result.to_dict(), handle, indent=2, ensure_ascii=False)
        handle.write("\n")
    return path


def load_run_json(path: str) -> RunResult:
    with Path(path).open("r", encoding="utf-8") as handle:
        return RunResult.from_dict(json.load(handle))


def build_result_spec(
    result: RunResult,
    config: RunConfig,
    tool_version: str = "",
    log_path: str = "",
) -> ResultSpec:
    items = []
    for item in result.sequence_items:
        items.append(
            DatasetItemSpec(
                loci_name=Path(item.path).stem,
                item_type=ITEM_TYPE_SEQUENCE,
                file_path=item.path,
                format="fasta",
                length=item.max_len,
                sequence_count=item.sequences,
                metadata={
                    "organelle": result.organelle,
                    "kind": item.kind,
                    "total_bp": item.total_bp,
                    "gc_percent": item.gc_percent,
                },
            )
        )
    if not items:
        fallback = log_path
        if not fallback or not Path(fallback).is_file():
            fallback = str(Path(result.output_dir) / "run.json")
        items.append(
            DatasetItemSpec(
                loci_name="run log",
                item_type=ITEM_TYPE_TABLE,
                file_path=fallback,
                format="text",
                metadata={"kind": "log"},
            )
        )
    dataset = DatasetSpec(
        name=result.run_name,
        items=items,
        description=f"GetOrganelle {result.mode} result for {result.organelle}",
        source="getorganelle",
        summary=dict(result.summary),
        metadata={
            "mode": result.mode,
            "organelle": result.organelle,
            "output_dir": result.output_dir,
        },
    )
    run_spec = RunSpec(
        method=f"getorganelle-{result.mode}",
        tool="GetOrganelle",
        tool_version=tool_version,
        command=result.command,
        parameters=config.to_dict(),
        input_paths=[
            path
            for path in (config.reads_1, config.reads_2, config.unpaired, config.graph)
            if path
        ],
        output_paths=result.artifacts,
        status={
            STATUS_SUCCESS: "completed",
            STATUS_WARNING: "completed",
            STATUS_ERROR: "failed",
            STATUS_CANCELLED: "cancelled",
        }.get(result.status, result.status),
        cwd=str(Path(config.output_root)),
        log=log_path,
        metadata={"run_id": result.run_id, "exit_code": result.exit_code},
        started_at=result.started_at,
        completed_at=result.finished_at,
    )
    runs = [run_spec]
    preprocess = result.summary.get("preprocess") or {}
    if preprocess:
        fastp_commands = preprocess.get("commands") or []
        runs.insert(
            0,
            RunSpec(
                method="fastp-preprocess",
                tool="fastp",
                command=fastp_commands[0] if fastp_commands else [],
                parameters={
                    "adapter_mode": config.adapter_mode,
                    "quality": config.fastp_quality,
                    "unqualified_percent": config.fastp_unqualified_percent,
                    "min_length": config.fastp_min_length,
                    "dedup": config.fastp_dedup,
                },
                input_paths=[
                    path
                    for path in (config.reads_1, config.reads_2, config.unpaired)
                    if path
                ],
                output_paths=preprocess.get("reports", []),
                status="completed" if result.status != STATUS_ERROR else "failed",
                cwd=preprocess.get("output_dir", ""),
                metadata={
                    "before_reads": preprocess.get("before_reads", 0),
                    "after_reads": preprocess.get("after_reads", 0),
                    "description": preprocess.get("description", ""),
                },
                started_at=result.started_at,
                completed_at=result.finished_at,
            ),
        )
    return ResultSpec(
        source="getorganelle",
        datasets=[dataset],
        artifacts=result.artifacts,
        summary=dict(result.summary),
        warnings=result.warnings,
        tool="GetOrganelle",
        tool_version=tool_version,
        runs=runs,
    )
