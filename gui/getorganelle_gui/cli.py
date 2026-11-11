"""Headless / agent-facing surface.

Examples
--------
    python -m getorganelle_gui.cli inspect --json
    python -m getorganelle_gui.cli check --json
    python -m getorganelle_gui.cli run --mode reads --reads1 R1.fq.gz --reads2 R2.fq.gz \
        --organelle embplant_pt --workspace runs --run-name sample --json
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

from . import __version__
from .command import build_plan
from .models import (
    MODE_ASSEMBLY,
    MODE_DATABASE,
    MODE_READS,
    RunConfig,
    now_iso,
)
from .paths import database_status, probe_dependencies
from .preprocess import build_preprocess_plan, summarize_fastp
from .plugin_meta import agent_actions, control_bindings, plugin_info, skill_path
from .results import build_result_spec, build_run_result, write_run_json
from .settings import Settings
from .validation import has_errors, validate_config

_CREATE_NO_WINDOW = 0x08000000 if os.name == "nt" else 0


def _settings_from_args(args) -> Settings:
    settings = Settings.load()
    if getattr(args, "getorganelle_root", ""):
        settings.getorganelle_root = args.getorganelle_root
    if getattr(args, "dep_root", ""):
        settings.dep_root = args.dep_root
    if getattr(args, "python", ""):
        settings.python_executable = args.python
    if getattr(args, "config_dir", ""):
        settings.config_dir = args.config_dir
    if getattr(args, "workspace", ""):
        settings.workspace_root = str(Path(args.workspace).expanduser().resolve())
    if settings.config_dir.strip():
        settings.config_dir = str(Path(settings.config_dir).expanduser().resolve())
    return settings.normalize()


def _absolute(value: str) -> str:
    return str(Path(value).expanduser().resolve()) if value else ""


def _config_from_args(args, settings: Settings) -> RunConfig:
    mode = args.mode
    organelle = args.organelle
    database_types = args.database_types
    if mode == MODE_DATABASE:
        organelle = database_types or organelle
    config = RunConfig(
        mode=mode,
        reads_1=_absolute(args.reads1),
        reads_2=_absolute(args.reads2),
        unpaired=_absolute(args.unpaired),
        graph=_absolute(args.graph),
        organelle=organelle,
        output_root=settings.workspace_root,
        run_name=args.run_name,
        threads=args.threads,
        rounds=args.rounds,
        kmer_mode="custom" if args.kmers else "auto",
        kmers=args.kmers or "",
        max_reads=args.max_reads,
        reduce_coverage=args.reduce_coverage,
        max_extending_len=args.max_extending_len,
        prefix=args.prefix,
        preset=args.preset,
        keep_temp=args.keep_temp,
        out_per_round=args.out_per_round,
        zip_files=args.zip_files,
        overwrite=args.overwrite,
        min_depth=args.min_depth,
        max_depth=args.max_depth,
        no_slim=args.no_slim,
        spades_out_dir=_absolute(args.spades_out_dir),
        seed_file=_absolute(args.seed),
        genes_db=_absolute(args.genes),
        config_dir=settings.config_dir,
        extra_args=args.extra,
        database_types=database_types,
        preprocess=args.preprocess,
        adapter_mode=args.adapter_mode,
        adapter_sequence=args.adapter_sequence,
        adapter_sequence_r2=args.adapter_sequence_r2,
        fastp_quality=args.fastp_quality,
        fastp_unqualified_percent=args.fastp_unqualified_percent,
        fastp_min_length=args.fastp_min_length,
        trim_front1=args.trim_front1,
        trim_tail1=args.trim_tail1,
        trim_front2=args.trim_front2,
        trim_tail2=args.trim_tail2,
        fastp_dedup=args.fastp_dedup,
        fastp_threads=args.fastp_threads,
        fastp_extra_args=args.fastp_extra,
    )
    if not config.run_name:
        config.run_name = config.suggested_run_name()
    return config


def _emit(payload, as_json: bool) -> None:
    if as_json:
        json.dump(payload, sys.stdout, indent=2, ensure_ascii=False)
        sys.stdout.write("\n")
    else:
        print(json.dumps(payload, indent=2, ensure_ascii=False))


def cmd_inspect(args) -> int:
    settings = _settings_from_args(args)
    report = probe_dependencies(settings, check_versions=args.deep)
    payload = {
        "plugin": plugin_info(),
        "version": __version__,
        "control_bindings": control_bindings(),
        "agent_actions": agent_actions(),
        "dependencies": report.to_dict(),
        "databases": {
            key: status.to_dict() for key, status in database_status(settings).items()
        },
        "skill_path": skill_path(),
    }
    _emit(payload, args.json)
    return 0


def cmd_check(args) -> int:
    settings = _settings_from_args(args)
    report = probe_dependencies(settings, check_versions=True)
    _emit(report.to_dict(), args.json)
    return 0 if report.ok else 1


def _run_process(plan, quiet: bool) -> tuple:
    lines = []
    started_at = now_iso()
    started = time.monotonic()
    if not quiet:
        print("cwd:", plan.cwd, file=sys.stderr)
        print("command:", plan.display, file=sys.stderr)
        sys.stderr.flush()
    process = subprocess.Popen(
        plan.argv,
        cwd=plan.cwd,
        env=plan.env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        bufsize=1,
        creationflags=_CREATE_NO_WINDOW,
    )
    assert process.stdout is not None
    for line in process.stdout:
        line = line.rstrip("\r\n")
        lines.append(line)
        if not quiet:
            print(line, file=sys.stderr)
    exit_code = process.wait()
    elapsed = time.monotonic() - started
    return exit_code, lines, started_at, now_iso(), elapsed


def cmd_run(args) -> int:
    settings = _settings_from_args(args)
    config = _config_from_args(args, settings)
    report = probe_dependencies(settings, check_versions=False)
    db_status = database_status(settings)
    issues = validate_config(config, settings, report, db_status)
    if has_errors(issues):
        for issue in issues:
            if issue.is_error:
                print(f"error [{issue.field}]: {issue.message}", file=sys.stderr)
                if issue.hint:
                    print(f"       {issue.hint}", file=sys.stderr)
        return 2
    Path(settings.workspace_root).mkdir(parents=True, exist_ok=True)
    run_id = datetime.now().strftime("%Y%m%d-%H%M%S") + "_" + config.run_name
    preprocess = None
    preprocess_dir = ""
    lines = []
    all_commands = []
    started_at = now_iso()
    start_clock = time.monotonic()
    exit_code = 0
    plan = None
    if config.preprocess and config.mode == MODE_READS:
        preprocess_dir = str(
            Path(settings.workspace_root) / "_workbench" / "preprocess" / run_id
        )
        Path(preprocess_dir).mkdir(parents=True, exist_ok=True)
        preprocess = build_preprocess_plan(config, settings, Path(preprocess_dir))
        for command in preprocess.commands:
            all_commands.append(command.argv)
            exit_code, stage_lines, stage_start, stage_end, stage_elapsed = _run_process(
                command, args.quiet
            )
            lines.extend(stage_lines)
            if exit_code != 0:
                break
        if exit_code == 0 and preprocess.enabled:
            effective = RunConfig.from_dict(config.to_dict())
            effective.preprocess = False
            effective.reads_1 = preprocess.reads_1
            effective.reads_2 = preprocess.reads_2
            effective.unpaired = preprocess.unpaired
            plan = build_plan(effective, settings)
            all_commands.append(plan.argv)
            code, run_lines, _, _, _ = _run_process(plan, args.quiet)
            lines.extend(run_lines)
            exit_code = code
    else:
        plan = build_plan(config, settings)
        all_commands.append(plan.argv)
        exit_code, lines, _, _, _ = _run_process(plan, args.quiet)
    finished_at = now_iso()
    elapsed = time.monotonic() - start_clock
    result = build_run_result(
        config,
        run_id=run_id,
        exit_code=exit_code,
        log_lines=lines,
        started_at=started_at,
        finished_at=finished_at,
        elapsed_s=elapsed,
    )
    result.summary["commands"] = all_commands
    if plan is not None:
        result.command = plan.argv
        result.summary["command"] = plan.argv
        result.summary["cwd"] = plan.cwd
    if preprocess is not None and preprocess.enabled:
        pre_summary = summarize_fastp(preprocess.report_jsons)
        pre_summary.update(
            {
                "description": preprocess.description,
                "output_dir": preprocess_dir,
                "commands": [item.argv for item in preprocess.commands],
                "report_html": preprocess.report_html,
            }
        )
        result.summary["preprocess"] = pre_summary
        for artifact in preprocess.artifacts:
            if artifact not in result.artifacts:
                result.artifacts.append(artifact)
        if not result.artifacts:
            result.command = preprocess.commands[0].argv if preprocess.commands else []
    try:
        run_json = write_run_json(result)
    except OSError:
        run_json = Path(result.output_dir) / "run.json"
    spec = build_result_spec(
        result,
        config,
        tool_version=report.getorganelle_version,
        log_path=str(run_json),
    )
    if args.json:
        sys.stdout.write(spec.to_json())
        sys.stdout.write("\n")
    else:
        print(
            json.dumps(
                {
                    "status": result.status,
                    "exit_code": exit_code,
                    "output_dir": result.output_dir,
                    "run_json": str(run_json),
                    "sequence_files": len(result.sequence_items),
                    "total_bp": result.total_bp,
                    "elapsed_s": round(elapsed, 1),
                },
                indent=2,
                ensure_ascii=False,
            )
        )
    return 0 if result.ok else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="getorganelle-workbench",
        description="Headless interface for the GetOrganelle Workbench (yrmpe.result.v1).",
    )
    parser.add_argument("--version", action="version", version=__version__)
    sub = parser.add_subparsers(dest="command", required=True)

    def common(subparser):
        subparser.add_argument("--getorganelle-root", default="")
        subparser.add_argument("--dep-root", default="")
        subparser.add_argument("--python", default="")
        subparser.add_argument("--config-dir", default="")
        subparser.add_argument("--workspace", default="")
        subparser.add_argument("--json", action="store_true")

    inspect = sub.add_parser("inspect", help="Show metadata, controls and database status.")
    common(inspect)
    inspect.add_argument("--deep", action="store_true", help="Start tools to read versions.")
    inspect.set_defaults(func=cmd_inspect)

    check = sub.add_parser("check", help="Check every configured dependency.")
    common(check)
    check.set_defaults(func=cmd_check)

    run = sub.add_parser("run", help="Run GetOrganelle without the GUI.")
    common(run)
    run.add_argument("--mode", choices=[MODE_READS, MODE_ASSEMBLY, MODE_DATABASE], default=MODE_READS)
    run.add_argument("--reads1", default="")
    run.add_argument("--reads2", default="")
    run.add_argument("--unpaired", default="")
    run.add_argument("--graph", default="")
    run.add_argument(
        "--organelle",
        default="embplant_pt",
        help="One type or a comma-separated list, e.g. embplant_pt,embplant_mt.",
    )
    run.add_argument("--database-types", default="embplant_pt,embplant_mt")
    run.add_argument("--run-name", default="")
    run.add_argument("--threads", type=int, default=0)
    run.add_argument("--rounds", type=int, default=15)
    run.add_argument("--kmers", default="", help="Custom k-mers; empty = automatic.")
    run.add_argument("--max-reads", default="")
    run.add_argument("--reduce-coverage", default="500")
    run.add_argument("--max-extending-len", default="inf")
    run.add_argument("--prefix", default="")
    run.add_argument("--preset", choices=["balanced", "fast", "memory_save"], default="balanced")
    run.add_argument("--keep-temp", action="store_true")
    run.add_argument("--out-per-round", action="store_true")
    run.add_argument("--zip-files", action="store_true")
    run.add_argument("--overwrite", action="store_true")
    run.add_argument("--min-depth", default="0")
    run.add_argument("--max-depth", default="inf")
    run.add_argument("--no-slim", action="store_true")
    run.add_argument("--spades-out-dir", default="")
    run.add_argument("--seed", default="")
    run.add_argument("--genes", default="")
    run.add_argument("--extra", default="")
    run.add_argument("--preprocess", action="store_true", help="Run fastp before GetOrganelle.")
    run.add_argument("--adapter-mode", choices=["auto", "none", "custom"], default="auto")
    run.add_argument("--adapter-sequence", default="")
    run.add_argument("--adapter-sequence-r2", default="")
    run.add_argument("--fastp-quality", type=int, default=15)
    run.add_argument("--fastp-unqualified-percent", type=int, default=40)
    run.add_argument("--fastp-min-length", type=int, default=15)
    run.add_argument("--trim-front1", type=int, default=0)
    run.add_argument("--trim-tail1", type=int, default=0)
    run.add_argument("--trim-front2", type=int, default=0)
    run.add_argument("--trim-tail2", type=int, default=0)
    run.add_argument("--fastp-dedup", action="store_true")
    run.add_argument("--fastp-threads", type=int, default=0)
    run.add_argument("--fastp-extra", default="")
    run.add_argument("--quiet", action="store_true")
    run.set_defaults(func=cmd_run)
    return parser


def main(argv=None) -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass
    parser = build_parser()
    args = parser.parse_args(argv)
    if getattr(args, "threads", 1) == 0:
        settings = _settings_from_args(args)
        args.threads = settings.threads
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
