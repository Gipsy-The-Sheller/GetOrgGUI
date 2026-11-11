"""Optional fastp preprocessing stage.

fastp runs before GetOrganelle and writes trimmed reads and its JSON/HTML
reports under ``<workspace>/_workbench/preprocess/<run_id>/``.  The GetOrganelle
command is then built with the trimmed paths instead of the raw reads.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import List

from .command import CommandPlan, display_command, split_extra_args
from .models import MODE_READS, RunConfig
from .paths import dependency_environment
from .settings import Settings

ADAPTER_MODES = {
    "auto": "Auto-detect adapters",
    "none": "Disable adapter trimming",
    "custom": "Custom adapter sequence",
}


@dataclass
class PreprocessPlan:
    commands: List[CommandPlan] = field(default_factory=list)
    labels: List[str] = field(default_factory=list)
    reads_1: str = ""
    reads_2: str = ""
    unpaired: str = ""
    artifacts: List[str] = field(default_factory=list)
    report_json: str = ""
    report_html: str = ""
    report_jsons: List[str] = field(default_factory=list)
    description: str = ""

    @property
    def enabled(self) -> bool:
        return bool(self.commands)


def fastp_path(settings: Settings) -> Path:
    return Path(settings.dep_root) / "fastp" / "fastp.exe"


def _common_fastp_args(config: RunConfig) -> List[str]:
    args = [
        "--qualified_quality_phred",
        str(config.fastp_quality),
        "--unqualified_percent_limit",
        str(config.fastp_unqualified_percent),
        "--length_required",
        str(config.fastp_min_length),
    ]
    if config.trim_front1 > 0:
        args.extend(["--trim_front1", str(config.trim_front1)])
    if config.trim_tail1 > 0:
        args.extend(["--trim_tail1", str(config.trim_tail1)])
    if config.trim_front2 > 0:
        args.extend(["--trim_front2", str(config.trim_front2)])
    if config.trim_tail2 > 0:
        args.extend(["--trim_tail2", str(config.trim_tail2)])
    if config.fastp_dedup:
        args.append("--dedup")
    return args


def _adapter_args(config: RunConfig, paired: bool) -> List[str]:
    mode = (config.adapter_mode or "auto").lower()
    if mode == "none":
        return ["--disable_adapter_trimming"]
    if mode == "custom":
        args = ["--adapter_sequence", config.adapter_sequence.strip()]
        if paired and config.adapter_sequence_r2.strip():
            args.extend(["--adapter_sequence_r2", config.adapter_sequence_r2.strip()])
        return args
    if paired:
        return ["--detect_adapter_for_pe"]
    return []


def build_preprocess_plan(
    config: RunConfig, settings: Settings, base_dir: Path
) -> PreprocessPlan:
    """Build one or more fastp commands and the rewritten read paths."""
    plan = PreprocessPlan()
    if not config.preprocess or config.mode != MODE_READS:
        return plan
    settings.normalize()
    fastp = fastp_path(settings)
    base_dir = Path(base_dir)
    common = _common_fastp_args(config)
    threads = config.fastp_threads or config.threads
    extra = split_extra_args(config.fastp_extra_args)

    def make_command(inputs: List[str], outputs: List[str], label: str, stem: str):
        args = [str(fastp)]
        if len(inputs) == 2:
            args.extend(["-i", inputs[0], "-I", inputs[1], "-o", outputs[0], "-O", outputs[1]])
        else:
            args.extend(["-i", inputs[0], "-o", outputs[0]])
        args.extend(["--thread", str(threads)])
        args.extend(_adapter_args(config, paired=len(inputs) == 2))
        args.extend(common)
        report_json = str(base_dir / f"{stem}.json")
        report_html = str(base_dir / f"{stem}.html")
        args.extend(
            [
                "--json",
                report_json,
                "--html",
                report_html,
                "--report_title",
                f"fastp - {config.run_name}",
            ]
        )
        args.extend(extra)
        command = CommandPlan(
            argv=args,
            cwd=str(base_dir),
            env=dependency_environment(settings),
            display=display_command(args),
        )
        plan.commands.append(command)
        plan.labels.append(label)
        plan.artifacts.extend(outputs)
        plan.artifacts.extend([report_json, report_html])
        plan.report_jsons.append(report_json)
        if not plan.report_json:
            plan.report_json = report_json
            plan.report_html = report_html

    has_unpaired = bool(config.unpaired.strip())
    if config.reads_1.strip():
        if config.reads_2.strip():
            out1 = str(base_dir / "trimmed_R1.fq.gz")
            out2 = str(base_dir / "trimmed_R2.fq.gz")
            make_command(
                [config.reads_1.strip(), config.reads_2.strip()],
                [out1, out2],
                "fastp: paired reads",
                "fastp",
            )
            plan.reads_1, plan.reads_2 = out1, out2
        else:
            out1 = str(base_dir / "trimmed_R1.fq.gz")
            make_command(
                [config.reads_1.strip()],
                [out1],
                "fastp: reads",
                "fastp",
            )
            plan.reads_1 = out1
    if has_unpaired:
        trimmed = []
        for index, item in enumerate(
            [part.strip() for part in config.unpaired.split(",") if part.strip()], start=1
        ):
            out = str(base_dir / f"unpaired_{index}.fq.gz")
            make_command(
                [item],
                [out],
                f"fastp: unpaired file {index}",
                f"fastp_unpaired_{index}",
            )
            trimmed.append(out)
        plan.unpaired = ",".join(trimmed)
    if plan.commands:
        parts = []
        if plan.reads_1:
            parts.append("paired" if plan.reads_2 else "single-end")
        if plan.unpaired:
            parts.append("unpaired")
        plan.description = "fastp · " + " + ".join(parts)
    return plan


def _extract_json_summary(text: str) -> dict:
    """Read only the ``summary`` object from a fastp JSON report.

    fastp 1.0.1 writes its ``command`` string without JSON-escaping Windows
    backslashes, so the document is not valid JSON as a whole.  The summary
    object contains only numbers and safe keys, so extract it by brace
    balancing instead of rejecting the report.
    """
    import json

    try:
        payload = json.loads(text)
        return payload.get("summary", {})
    except ValueError:
        pass
    marker = '"summary"'
    start = text.find(marker)
    if start < 0:
        return {}
    brace = text.find("{", start)
    if brace < 0:
        return {}
    depth = 0
    in_string = False
    escaped = False
    for index in range(brace, len(text)):
        char = text[index]
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue
        if char == '"':
            in_string = True
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                try:
                    return json.loads(text[brace : index + 1])
                except ValueError:
                    return {}
    return {}


def summarize_fastp(report_paths: List[str]) -> dict:
    """Aggregate the machine-readable part of one or more fastp JSON reports."""

    before_reads = after_reads = 0
    before_bases = after_bases = 0
    reports = []
    for path in report_paths:
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as handle:
                text = handle.read()
        except OSError:
            continue
        summary = _extract_json_summary(text)
        if summary is None:
            continue
        before = summary.get("before_filtering", {})
        after = summary.get("after_filtering", {})
        before_reads += int(before.get("total_reads", 0) or 0)
        after_reads += int(after.get("total_reads", 0) or 0)
        before_bases += int(before.get("total_bases", 0) or 0)
        after_bases += int(after.get("total_bases", 0) or 0)
        reports.append(path)
    if not reports:
        return {}
    return {
        "reports": reports,
        "before_reads": before_reads,
        "after_reads": after_reads,
        "before_bases": before_bases,
        "after_bases": after_bases,
    }
