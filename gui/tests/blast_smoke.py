"""Optional BLAST+ integration smoke test.

Run after the Windows toolchain has been built:

    venv\\Scripts\\python.exe gui\\tests\\blast_smoke.py

The test is skipped (exit 0) when blastn/tblastn/makeblastdb are unavailable.
It exercises both reference modes against a synthetic graph and GenBank file.
"""
from __future__ import annotations

import random
import sys
import tempfile
from pathlib import Path

GUI_ROOT = Path(__file__).resolve().parents[1]
if str(GUI_ROOT) not in sys.path:
    sys.path.insert(0, str(GUI_ROOT))

from getorganelle_gui.graph_model import parse_gfa  # noqa: E402
from getorganelle_gui.reference_blast import (  # noqa: E402
    BlastFilters,
    BlastRunConfig,
    ReferenceBlastRunner,
    filter_node_hits,
    resolve_blast_tools,
)
from getorganelle_gui.settings import Settings  # noqa: E402


def make_inputs(root: Path):
    rng = random.Random(7)
    codons = [
        "GCT", "AAA", "ACC", "CGT", "GAA", "TTC", "GGT", "CAT", "ATT",
        "CTG", "AAC", "CCG", "CAG", "TCT", "GTT", "TGG", "TAT", "GAC",
        "GAG", "AAG", "ATG", "CAC", "CCT", "AGA", "TCA", "GTA", "TGC",
        "TAC", "GAT", "GTG",
    ]
    coding = "ATG" + "".join(rng.choice(codons) for _ in range(60)) + "TAA"
    reference = (
        "".join(rng.choice("ACGT") for _ in range(80))
        + coding
        + "".join(rng.choice("ACGT") for _ in range(80))
    )
    node_two = "".join(rng.choice("ACGT") for _ in range(240))
    gfa = (
        f"S\t1\t{reference}\tLN:i:{len(reference)}\tRC:i:{len(reference) * 20}\n"
        f"S\t2\t{node_two}\tLN:i:{len(node_two)}\tRC:i:{len(node_two) * 8}\n"
        "L\t1\t+\t2\t+\t0M\n"
    )
    gfa_path = root / "demo.gfa"
    gfa_path.write_text(gfa, encoding="utf-8")
    gb_path = root / "demo.gbk"
    start = 81
    end = start + len(coding) - 1
    gb_path.write_text(
        f"""LOCUS       DEMO {len(reference):>11} bp    DNA     linear
ACCESSION   DEMO
VERSION     DEMO.1
FEATURES             Location/Qualifiers
     source          1..{len(reference)}
     CDS             {start}..{end}
                     /gene="rbcL"
                     /product="ribulose bisphosphate carboxylase"
                     /transl_table=11
ORIGIN
        1 {reference.lower()}
//
""",
        encoding="utf-8",
    )
    graph = parse_gfa(gfa, str(gfa_path))
    return graph, gb_path


def main() -> int:
    settings = Settings.load()
    try:
        tools = resolve_blast_tools(settings)
    except FileNotFoundError as exc:
        print("SKIP:", exc)
        return 0
    with tempfile.TemporaryDirectory(prefix="getorganelle-blast-") as temp:
        root = Path(temp)
        graph, gb_path = make_inputs(root)
        for mode in ("blastn", "tblastn"):
            config = BlastRunConfig(
                reference_path=str(gb_path),
                mode=mode,
                evalue=1e-3,
                threads=2,
                work_dir=str(root / mode),
                blastn=tools["blastn"],
                tblastn=tools["tblastn"],
                makeblastdb=tools["makeblastdb"],
            )
            result = ReferenceBlastRunner(graph, config).run(
                lambda message: print(f"[{mode}] {message}")
            )
            views = filter_node_hits(result, BlastFilters(evalue=1e-10))
            print(f"[{mode}] queries={result.query_count} hits={len(result.hits)} views={len(views)}")
            if not views or views[0].node_id != "1":
                print(f"FAIL: {mode} did not identify node 1")
                return 1
    print("BLAST smoke test passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
