"""Locate GetOrganelle, its bundled dependencies and user databases."""
from __future__ import annotations

import importlib.util
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Dict, Iterable, List, Optional

from .models import (
    DatabaseStatus,
    DependencyReport,
    ORGANELLES,
    ToolStatus,
    now_iso,
)
from .settings import Settings

_CREATE_NO_WINDOW = 0x08000000 if os.name == "nt" else 0
_EXE = ".exe" if os.name == "nt" else ""


def _capture(argv: List[str], cwd: Optional[str] = None, timeout: float = 10.0):
    try:
        completed = subprocess.run(
            argv,
            cwd=cwd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            creationflags=_CREATE_NO_WINDOW,
        )
        output = ((completed.stdout or "") + "\n" + (completed.stderr or "")).strip()
        return completed.returncode, output
    except (OSError, subprocess.SubprocessError) as exc:
        return -1, str(exc)


def read_getorganelle_version(root: Path) -> str:
    versions_file = root / "GetOrganelleLib" / "versions.py"
    try:
        text = versions_file.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""
    match = re.search(r'"number"\s*:\s*"([^"]+)"', text)
    return match.group(1) if match else ""


def read_spades_version(dep_root: Path) -> str:
    version_file = dep_root / "SPAdes" / "share" / "spades" / "VERSION"
    try:
        return version_file.read_text(encoding="utf-8", errors="replace").strip()
    except OSError:
        return ""


def config_directory(settings: Settings) -> Path:
    settings.normalize()
    if settings.config_dir.strip():
        return Path(settings.config_dir).expanduser()
    env_value = os.environ.get("GETORG_PATH", "").strip()
    if env_value:
        return Path(env_value).expanduser()
    return Path.home() / ".GetOrganelle"


def database_status(
    settings: Settings, organelle_types: Optional[Iterable[str]] = None
) -> Dict[str, DatabaseStatus]:
    settings.normalize()
    config_dir = config_directory(settings)
    types = list(organelle_types or ORGANELLES.keys())
    statuses: Dict[str, DatabaseStatus] = {}
    for organelle in types:
        seed_path = config_dir / "SeedDatabase" / f"{organelle}.fasta"
        label_path = config_dir / "LabelDatabase" / f"{organelle}.fasta"
        statuses[organelle] = DatabaseStatus(
            organelle=organelle,
            label=ORGANELLES.get(organelle, {}).get("label", organelle),
            seed=seed_path.is_file(),
            label_db=label_path.is_file(),
            seed_path=str(seed_path),
            label_path=str(label_path),
        )
    return statuses


def _python_modules(python: str, deep: bool) -> Dict[str, bool]:
    names = ["numpy", "gekko", "requests"]
    if not deep:
        return {name: importlib.util.find_spec(name) is not None for name in names}
    code = (
        "import importlib.util, json\n"
        "names = ['numpy', 'gekko', 'requests']\n"
        "print(json.dumps({n: importlib.util.find_spec(n) is not None for n in names}))\n"
    )
    returncode, output = _capture([python, "-c", code], timeout=15.0)
    if returncode != 0:
        return {name: False for name in names}
    try:
        import json

        payload = json.loads(output.splitlines()[-1])
        return {name: bool(payload.get(name)) for name in names}
    except (ValueError, IndexError):
        return {name: False for name in names}


def probe_dependencies(settings: Settings, check_versions: bool = False) -> DependencyReport:
    """Inspect the configured GetOrganelle installation.

    ``check_versions=False`` is the fast startup path (file existence plus
    versions readable from packaged text files).  The Settings dialog uses
    ``check_versions=True`` to actually start every executable.
    """
    settings.normalize()
    root = Path(settings.getorganelle_root)
    dep_root = Path(settings.dep_root)
    python = settings.python_executable

    report = DependencyReport(
        getorganelle_root=str(root),
        dep_root=str(dep_root),
        getorganelle_version=read_getorganelle_version(root),
        python_executable=python,
        config_dir=str(config_directory(settings)),
        checked_at=now_iso(),
    )

    reads_script = root / "get_organelle_from_reads.py"
    assembly_script = root / "get_organelle_from_assembly.py"
    getorg_ok = reads_script.is_file() and assembly_script.is_file()
    report.tools["getorganelle"] = ToolStatus(
        key="getorganelle",
        label="GetOrganelle",
        path=str(root),
        version=report.getorganelle_version,
        ok=getorg_ok,
        detail="" if getorg_ok else "get_organelle_from_reads.py not found",
    )

    spades_py = dep_root / "SPAdes" / "bin" / "spades.py"
    spades_ok = spades_py.is_file()
    spades_version = read_spades_version(dep_root)
    if check_versions and spades_ok:
        returncode, output = _capture([python, str(spades_py), "--version"], timeout=20.0)
        if returncode == 0:
            first = output.splitlines()[0] if output else ""
            match = re.search(r"v?(\d+\.\d+\.\d+\S*)", first)
            if match:
                spades_version = match.group(1)
    report.tools["spades"] = ToolStatus(
        key="spades",
        label="SPAdes",
        path=str(spades_py),
        version=spades_version,
        ok=spades_ok,
        detail="" if spades_ok else "Bundled SPAdes was not found",
    )

    bowtie2 = dep_root / "bowtie2" / f"bowtie2-align-s{_EXE}"
    if not bowtie2.is_file():
        bowtie2 = dep_root / "bowtie2" / "bowtie2"
    bowtie2_ok = bowtie2.is_file()
    bowtie2_version = ""
    if check_versions and bowtie2_ok:
        returncode, output = _capture([str(bowtie2), "--version"], timeout=10.0)
        match = re.search(r"version\s+(\S+)", output)
        if match:
            bowtie2_version = match.group(1)
    report.tools["bowtie2"] = ToolStatus(
        key="bowtie2",
        label="Bowtie2",
        path=str(bowtie2),
        version=bowtie2_version,
        ok=bowtie2_ok,
        detail="" if bowtie2_ok else "Bundled Bowtie2 was not found",
    )

    blastn = dep_root / "ncbi-blast" / f"blastn{_EXE}"
    if not blastn.is_file():
        blastn = dep_root / "ncbi-blast" / "blastn"
    blast_ok = blastn.is_file()
    blast_version = ""
    if check_versions and blast_ok:
        returncode, output = _capture([str(blastn), "-version"], timeout=10.0)
        match = re.search(r"blastn:\s*(\S+)", output, re.I)
        if match:
            blast_version = match.group(1)
    report.tools["blast"] = ToolStatus(
        key="blast",
        label="NCBI BLAST+",
        path=str(blastn),
        version=blast_version,
        ok=blast_ok,
        detail="" if blast_ok else "blastn was not found",
    )

    samtools = dep_root / "samtools" / "bin" / f"samtools{_EXE}"
    if not samtools.is_file():
        samtools = dep_root / "samtools" / "bin" / "samtools"
    samtools_ok = samtools.is_file()
    samtools_version = ""
    if check_versions and samtools_ok:
        returncode, output = _capture([str(samtools), "--version"], timeout=10.0)
        match = re.search(r"samtools\s+(\S+)", output)
        if match:
            samtools_version = match.group(1)
    report.tools["samtools"] = ToolStatus(
        key="samtools",
        label="samtools",
        path=str(samtools),
        version=samtools_version,
        ok=samtools_ok,
        detail="Optional component",
        required=False,
    )

    python_path = Path(python)
    python_ok = python_path.is_file()
    python_version = ""
    if check_versions and python_ok:
        returncode, output = _capture(
            [python, "-c", "import sys; print(sys.version.split()[0])"], timeout=10.0
        )
        if returncode == 0:
            python_version = output.strip().splitlines()[-1] if output else ""
    report.tools["python"] = ToolStatus(
        key="python",
        label="Python",
        path=python,
        version=python_version,
        ok=python_ok,
        detail="" if python_ok else "Configured Python interpreter is missing",
    )

    fastp = dep_root / "fastp" / f"fastp{_EXE}"
    if not fastp.is_file():
        fastp = dep_root / "fastp" / "fastp"
    fastp_ok = fastp.is_file()
    fastp_version = ""
    if check_versions and fastp_ok:
        returncode, output = _capture([str(fastp), "--version"], timeout=10.0)
        match = re.search(r"fastp\s+(\S+)", output)
        if match:
            fastp_version = match.group(1)
    report.tools["fastp"] = ToolStatus(
        key="fastp",
        label="fastp",
        path=str(fastp),
        version=fastp_version,
        ok=fastp_ok,
        detail="Optional adapter/quality preprocessing",
        required=False,
    )

    report.modules = _python_modules(python, deep=check_versions)
    return report


def prepend_path_entries(entries: Iterable[str]) -> List[str]:
    """Return PATH entries with unique, existing directories first."""
    seen = set()
    ordered: List[str] = []
    for entry in entries:
        if not entry:
            continue
        resolved = os.path.normcase(os.path.abspath(entry))
        if resolved in seen:
            continue
        seen.add(resolved)
        ordered.append(entry)
    return ordered


def dependency_environment(settings: Settings) -> Dict[str, str]:
    settings.normalize()
    dep_root = Path(settings.dep_root)
    python_dir = str(Path(settings.python_executable).parent)
    candidates = [
        python_dir,
        str(dep_root / "SPAdes" / "bin"),
        str(dep_root / "bowtie2"),
        str(dep_root / "ncbi-blast"),
        str(dep_root / "samtools" / "bin"),
    ]
    if settings.extra_path.strip():
        candidates.extend(
            part.strip()
            for part in settings.extra_path.split(os.pathsep)
            if part.strip()
        )
    current = os.environ.get("PATH", "")
    path = os.pathsep.join(
        prepend_path_entries(candidates)
        + [part for part in current.split(os.pathsep) if part]
    )
    environment = os.environ.copy()
    environment["PATH"] = path
    # Keep the child's stdout UTF-8 for streaming, but do not enable Python's
    # global UTF-8 mode: GetOrganelle shells out to cmd.exe and decodes some
    # localized output itself.
    environment["PYTHONIOENCODING"] = "utf-8"
    return environment


def open_in_file_manager(path: str) -> None:
    target = str(Path(path))
    if os.name == "nt":
        os.startfile(target)  # type: ignore[attr-defined]
    elif sys.platform == "darwin":
        subprocess.Popen(["open", target])
    else:
        subprocess.Popen(["xdg-open", target])
