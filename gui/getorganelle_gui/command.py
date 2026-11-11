"""Translate GUI state into GetOrganelle command lines.

All commands are argument lists; nothing is passed through a shell.
"""
from __future__ import annotations

import os
import shlex
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import List

from .models import MODE_ASSEMBLY, MODE_DATABASE, RunConfig
from .paths import dependency_environment
from .settings import Settings

PROTECTED_FLAGS = {
    "-1",
    "-2",
    "-u",
    "-g",
    "-F",
    "-o",
    "--output-base",
    "--config-dir",
}


@dataclass
class CommandPlan:
    argv: List[str]
    cwd: str
    env: dict
    display: str

    @property
    def program(self) -> str:
        return self.argv[0] if self.argv else ""

    @property
    def arguments(self) -> List[str]:
        return self.argv[1:] if self.argv else []


def split_extra_args(text: str) -> List[str]:
    """Split a Windows-friendly argument string without eating backslashes."""
    if not text or not text.strip():
        return []
    lexer = shlex.shlex(text, posix=False)
    lexer.whitespace_split = True
    lexer.commenters = ""
    tokens: List[str] = []
    for token in lexer:
        token = token.strip()
        if len(token) >= 2 and token[0] == token[-1] and token[0] in ("'", '"'):
            token = token[1:-1]
        if token:
            tokens.append(token)
    return tokens


def normalize_kmers(text: str) -> str:
    parts = [part.strip() for part in (text or "").replace(";", ",").split(",")]
    return ",".join(part for part in parts if part)


def display_command(argv: List[str]) -> str:
    if not argv:
        return ""
    if os.name == "nt":
        return subprocess.list2cmdline(argv)
    return " ".join(shlex.quote(part) for part in argv)


def build_plan(config: RunConfig, settings: Settings) -> CommandPlan:
    settings.normalize()
    root = Path(settings.getorganelle_root)
    python = settings.python_executable
    output_dir = str(config.output_dir)
    extra = split_extra_args(config.extra_args)

    if config.mode == MODE_DATABASE:
        script = root / "Utilities" / "get_organelle_config.py"
        database_types = config.database_types.strip() or config.organelle
        argv = [python, "-u", str(script), "-a", database_types]
        if config.config_dir.strip():
            argv.extend(["--config-dir", config.config_dir.strip()])
        argv.extend(extra)
        return CommandPlan(
            argv=argv,
            cwd=str(root),
            env=dependency_environment(settings),
            display=display_command(argv),
        )

    if config.mode == MODE_ASSEMBLY:
        script = root / "get_organelle_from_assembly.py"
        argv = [
            python,
            "-u",
            str(script),
            "-g",
            config.graph,
            "-F",
            config.organelle,
            "-o",
            output_dir,
            "-t",
            str(config.threads),
        ]
        if config.min_depth.strip():
            argv.extend(["--min-depth", config.min_depth.strip()])
        if config.max_depth.strip():
            argv.extend(["--max-depth", config.max_depth.strip()])
        if config.prefix.strip():
            argv.extend(["--prefix", config.prefix.strip()])
        if config.no_slim:
            argv.append("--no-slim")
        if config.spades_out_dir.strip():
            argv.extend(["--spades-out-dir", config.spades_out_dir.strip()])
        if config.genes_db.strip():
            argv.extend(["--genes", config.genes_db.strip()])
        if config.overwrite:
            argv.append("--overwrite")
        if config.config_dir.strip():
            argv.extend(["--config-dir", config.config_dir.strip()])
        argv.extend(extra)
        return CommandPlan(
            argv=argv,
            cwd=str(root),
            env=dependency_environment(settings),
            display=display_command(argv),
        )

    script = root / "get_organelle_from_reads.py"
    argv = [python, "-u", str(script), "-1", config.reads_1]
    if config.reads_2.strip():
        argv.extend(["-2", config.reads_2.strip()])
    if config.unpaired.strip():
        argv.extend(["-u", config.unpaired.strip()])
    argv.extend(
        [
            "-F",
            config.organelle,
            "-o",
            output_dir,
            "-R",
            str(config.rounds),
            "-t",
            str(config.threads),
        ]
    )
    if config.kmer_mode == "custom":
        argv.extend(["-k", normalize_kmers(config.kmers)])
    if config.max_reads.strip():
        argv.extend(["--max-reads", config.max_reads.strip()])
    if config.reduce_coverage.strip():
        argv.extend(["--reduce-reads-for-coverage", config.reduce_coverage.strip()])
    if config.max_extending_len.strip():
        argv.extend(["--max-extending-len", config.max_extending_len.strip()])
    if config.prefix.strip():
        argv.extend(["--prefix", config.prefix.strip()])
    if config.seed_file.strip():
        argv.extend(["-s", config.seed_file.strip()])
    if config.genes_db.strip():
        argv.extend(["--genes", config.genes_db.strip()])
    if config.preset == "fast":
        argv.append("--fast")
    elif config.preset == "memory_save":
        argv.append("--memory-save")
    if config.keep_temp:
        argv.append("--keep-temp")
    if config.out_per_round:
        argv.append("--out-per-round")
    if config.zip_files:
        argv.append("--zip-files")
    if config.overwrite:
        argv.append("--overwrite")
    if config.config_dir.strip():
        argv.extend(["--config-dir", config.config_dir.strip()])
    argv.extend(extra)
    return CommandPlan(
        argv=argv,
        cwd=str(root),
        env=dependency_environment(settings),
        display=display_command(argv),
    )


def protected_flags_in_extra(text: str) -> List[str]:
    found = []
    for token in split_extra_args(text):
        key = token.split("=", 1)[0]
        if key in PROTECTED_FLAGS:
            found.append(key)
    return found
