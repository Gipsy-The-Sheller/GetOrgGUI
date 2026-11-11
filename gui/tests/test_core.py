"""Headless tests for command building, validation and result objects."""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

GUI_ROOT = Path(__file__).resolve().parents[1]
if str(GUI_ROOT) not in sys.path:
    sys.path.insert(0, str(GUI_ROOT))

from getorganelle_gui.command import build_plan, normalize_kmers, split_extra_args
from getorganelle_gui.graph_model import (
    edge_endpoint_sides,
    layout_graph,
    layout_graph_with_ends,
    parse_fastg,
    parse_gfa,
)
from getorganelle_gui.models import (
    MODE_ASSEMBLY,
    MODE_DATABASE,
    MODE_READS,
    STATUS_SUCCESS,
    DependencyReport,
    DatabaseStatus,
    RunConfig,
    ToolStatus,
)
from getorganelle_gui.plugin_meta import control_bindings, plugin_info
from getorganelle_gui.preprocess import build_preprocess_plan, summarize_fastp
from getorganelle_gui.results import (
    build_result_spec,
    build_run_result,
    fasta_stats,
    scan_outputs,
    write_run_json,
)
from getorganelle_gui.settings import Settings
from getorganelle_gui.validation import has_errors, parse_kmers, validate_config


class CommandTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        (self.root / "get_organelle_from_reads.py").write_text("", encoding="utf-8")
        (self.root / "get_organelle_from_assembly.py").write_text("", encoding="utf-8")
        self.settings = Settings.from_dict(
            {
                "getorganelle_root": str(self.root),
                "dep_root": str(self.root / "dep"),
                "python_executable": sys.executable,
                "workspace_root": str(self.root / "runs"),
            }
        )

    def tearDown(self):
        self.temp.cleanup()

    def test_extra_args_preserve_quotes_and_backslashes(self):
        tokens = split_extra_args(
            '--bowtie2-options "--very-fast -t" --genes "C:\\ref\\genes.fa"'
        )
        self.assertEqual(
            tokens,
            ["--bowtie2-options", "--very-fast -t", "--genes", "C:\\ref\\genes.fa"],
        )

    def test_normalize_kmers(self):
        self.assertEqual(normalize_kmers("21, 45,65"), "21,45,65")

    def test_reads_plan(self):
        config = RunConfig(
            mode=MODE_READS,
            reads_1="R1.fq",
            reads_2="R2.fq",
            organelle="embplant_pt",
            output_root=str(self.root / "runs"),
            run_name="sample",
            threads=4,
            rounds=15,
            kmer_mode="custom",
            kmers="21,45,65",
            preset="fast",
            keep_temp=True,
            overwrite=True,
        )
        plan = build_plan(config, self.settings)
        argv = plan.argv
        self.assertIn("-1", argv)
        self.assertIn("R1.fq", argv)
        self.assertIn("-2", argv)
        self.assertIn("-F", argv)
        self.assertIn("embplant_pt", argv)
        self.assertIn("-t", argv)
        self.assertIn("4", argv)
        self.assertIn("-k", argv)
        self.assertIn("21,45,65", argv)
        self.assertIn("--fast", argv)
        self.assertIn("--keep-temp", argv)
        self.assertIn("--overwrite", argv)
        self.assertEqual(Path(plan.cwd), self.root)

    def test_multi_organelle_plan_expands_extending_length(self):
        config = RunConfig(
            mode=MODE_READS,
            reads_1="R1.fq",
            organelle="embplant_pt,embplant_mt",
            output_root=str(self.root / "runs"),
            run_name="multi",
            threads=4,
            rounds=30,
            max_extending_len="inf",
        )
        argv = build_plan(config, self.settings).argv
        index = argv.index("--max-extending-len")
        self.assertEqual(argv[index + 1], "inf,inf")
        self.assertIn("embplant_pt,embplant_mt", argv)

    def test_preprocess_plan(self):
        config = RunConfig(
            mode=MODE_READS,
            reads_1="R1.fq",
            reads_2="R2.fq",
            organelle="embplant_pt",
            output_root=str(self.root / "runs"),
            run_name="pre",
            threads=4,
            preprocess=True,
            adapter_mode="auto",
        )
        plan = build_preprocess_plan(config, self.settings, self.root / "pre")
        self.assertEqual(len(plan.commands), 1)
        argv = plan.commands[0].argv
        for flag in ("-i", "-I", "-o", "-O", "--detect_adapter_for_pe", "--json", "--html"):
            self.assertIn(flag, argv)
        self.assertTrue(plan.reads_1.endswith("trimmed_R1.fq.gz"))
        self.assertTrue(plan.reads_2.endswith("trimmed_R2.fq.gz"))
        self.assertIn(str(plan.reads_1), plan.artifacts)
        config.adapter_mode = "custom"
        config.adapter_sequence = "AGATCGGAAGAGC"
        plan = build_preprocess_plan(config, self.settings, self.root / "pre")
        argv = plan.commands[0].argv
        self.assertIn("--adapter_sequence", argv)
        self.assertIn("AGATCGGAAGAGC", argv)
        self.assertNotIn("--detect_adapter_for_pe", argv)

    def test_fastp_summary_tolerates_invalid_command_json(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "fastp.json"
            path.write_text(
                '{"summary": {"before_filtering": {"total_reads": 100, "total_bases": 1000},'
                ' "after_filtering": {"total_reads": 80, "total_bases": 700}},'
                ' "command": "C:\\\\data\\\\fastp.exe"}',
                encoding="utf-8",
            )
            summary = summarize_fastp([str(path)])
            self.assertEqual(summary["before_reads"], 100)
            self.assertEqual(summary["after_reads"], 80)

    def test_assembly_plan(self):
        config = RunConfig(
            mode=MODE_ASSEMBLY,
            graph="graph.gfa",
            organelle="embplant_mt",
            output_root=str(self.root / "runs"),
            run_name="asm",
            threads=2,
            no_slim=True,
        )
        argv = build_plan(config, self.settings).argv
        self.assertIn("-g", argv)
        self.assertIn("graph.gfa", argv)
        self.assertIn("--no-slim", argv)
        self.assertNotIn("-R", argv)

    def test_database_plan(self):
        config = RunConfig(
            mode=MODE_DATABASE,
            organelle="embplant_pt,embplant_mt",
            database_types="embplant_pt,embplant_mt",
            output_root=str(self.root / "runs"),
            run_name="db",
        )
        argv = build_plan(config, self.settings).argv
        self.assertTrue(any("get_organelle_config.py" in part for part in argv))
        self.assertIn("-a", argv)
        self.assertIn("embplant_pt,embplant_mt", argv)


class ValidationTests(unittest.TestCase):
    def test_parse_kmers(self):
        self.assertEqual(parse_kmers("21,45,65")[0], [21, 45, 65])
        self.assertIsNotNone(parse_kmers("21,44,65")[1])
        self.assertIsNotNone(parse_kmers("45,21")[1])
        self.assertIsNotNone(parse_kmers("20,21")[1])
        self.assertIsNotNone(parse_kmers("21,21")[1])
        self.assertIsNotNone(parse_kmers("")[1])

    def test_ready_config(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            reads = root / "R1.fq"
            reads.write_text("@r\nACGT\n+\nIIII\n", encoding="utf-8")
            settings = Settings.from_dict({"workspace_root": str(root / "runs")})
            deps = DependencyReport(
                tools={
                    name: ToolStatus(name, name, "x", "1", True)
                    for name in ("getorganelle", "spades", "bowtie2", "blast", "python", "samtools")
                },
                modules={"numpy": True, "gekko": True, "requests": True},
            )
            db = {
                "embplant_pt": DatabaseStatus(
                    "embplant_pt", "Plastome", True, True, "seed.fa", "label.fa"
                ),
                "embplant_mt": DatabaseStatus(
                    "embplant_mt", "Mitogenome", True, True, "seed.fa", "label.fa"
                ),
            }
            config = RunConfig(
                mode=MODE_READS,
                reads_1=str(reads),
                organelle="embplant_pt",
                output_root=str(root / "runs"),
                run_name="sample",
                threads=2,
                rounds=1,
                kmer_mode="auto",
            )
            issues = validate_config(config, settings, deps, db)
            self.assertFalse(has_errors(issues), [i.message for i in issues])

    def test_preprocess_requires_fastp(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            reads = root / "R1.fq"
            reads.write_text("@r\nACGT\n+\nIIII\n", encoding="utf-8")
            settings = Settings.from_dict({"workspace_root": str(root / "runs")})
            deps = DependencyReport(
                tools={
                    "getorganelle": ToolStatus("getorganelle", "GetOrganelle", "x", "1", True),
                    "spades": ToolStatus("spades", "SPAdes", "x", "1", True),
                    "bowtie2": ToolStatus("bowtie2", "Bowtie2", "x", "1", True),
                    "blast": ToolStatus("blast", "BLAST", "x", "1", True),
                    "python": ToolStatus("python", "Python", "x", "1", True),
                },
                modules={"numpy": True, "gekko": True, "requests": True},
            )
            config = RunConfig(
                mode=MODE_READS,
                reads_1=str(reads),
                organelle="embplant_pt",
                output_root=str(root / "runs"),
                run_name="pre",
                threads=2,
                rounds=15,
                preprocess=True,
            )
            issues = validate_config(config, settings, deps, None)
            self.assertTrue(any(i.field == "preprocess" and i.is_error for i in issues))

    def test_multi_organelle_validation(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            reads = root / "R1.fq"
            reads.write_text("@r\nACGT\n+\nIIII\n", encoding="utf-8")
            settings = Settings.from_dict({"workspace_root": str(root / "runs")})
            deps = DependencyReport(
                tools={
                    name: ToolStatus(name, name, "x", "1", True)
                    for name in ("getorganelle", "spades", "bowtie2", "blast", "python")
                },
                modules={"numpy": True, "gekko": True, "requests": True},
            )
            db = {
                key: DatabaseStatus(key, key, True, True, "seed.fa", "label.fa")
                for key in ("embplant_pt", "embplant_mt")
            }
            config = RunConfig(
                mode=MODE_READS,
                reads_1=str(reads),
                organelle="embplant_pt,embplant_mt",
                output_root=str(root / "runs"),
                run_name="multi",
                threads=2,
                rounds=30,
                max_extending_len="inf",
            )
            issues = validate_config(config, settings, deps, db)
            self.assertFalse(has_errors(issues), [i.message for i in issues])
            db_missing = {"embplant_pt": db["embplant_pt"]}
            issues = validate_config(config, settings, deps, db_missing)
            self.assertTrue(any(i.field == "database" for i in issues if i.is_error))
            config.organelle = "anonym,embplant_pt"
            issues = validate_config(config, settings, deps, db)
            self.assertTrue(any("must be run alone" in i.message for i in issues))

    def test_missing_reads_is_error(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            settings = Settings.from_dict({"workspace_root": str(root / "runs")})
            config = RunConfig(
                mode=MODE_READS,
                reads_1=str(root / "missing.fq"),
                output_root=str(root / "runs"),
                run_name="sample",
            )
            self.assertTrue(has_errors(validate_config(config, settings)))


class ResultTests(unittest.TestCase):
    def test_fasta_stats_and_scan(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            fasta = root / "sample.K65.scaffolds.graph1.1.path_sequence.fasta"
            fasta.write_text(">a\nACGTACGT\n>b\nGGCC\n", encoding="utf-8")
            (root / "graph.gfa").write_text("H\tVN:Z:1.0\n", encoding="utf-8")
            stats = fasta_stats(fasta)
            self.assertEqual(stats["sequences"], 2)
            self.assertEqual(stats["total_bp"], 12)
            self.assertEqual(stats["max_len"], 8)
            self.assertAlmostEqual(stats["gc_percent"], 66.67)
            items, artifacts = scan_outputs(root)
            self.assertEqual(len(items), 2)
            self.assertEqual(len(artifacts), 2)
            kinds = {item.kind for item in items}
            self.assertIn("scaffolds", kinds)
            self.assertIn("graph", kinds)

    def test_run_result_and_spec(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            run_dir = root / "sample"
            run_dir.mkdir()
            fasta = run_dir / "sample.K65.scaffolds.graph1.1.path_sequence.fasta"
            fasta.write_text(">a\nACGT\n", encoding="utf-8")
            config = RunConfig(
                mode=MODE_READS,
                reads_1="R1.fq",
                organelle="embplant_pt",
                output_root=str(root),
                run_name="sample",
            )
            result = build_run_result(
                config,
                run_id="run1",
                exit_code=0,
                log_lines=["2026-01-01 - INFO: Writing output"],
                started_at="2026-01-01T00:00:00",
                finished_at="2026-01-01T00:01:00",
                elapsed_s=60.0,
            )
            result.command = ["python", "script.py"]
            self.assertEqual(result.status, STATUS_SUCCESS)
            self.assertEqual(result.total_bp, 4)
            run_json = write_run_json(result)
            self.assertTrue(run_json.is_file())
            loaded = json.loads(run_json.read_text(encoding="utf-8"))
            self.assertEqual(loaded["schema"], "getorganelle.run.v1")
            spec = build_result_spec(result, config, tool_version="1.8.0.1")
            self.assertEqual(spec.validate(), [])
            self.assertEqual(spec.source, "getorganelle")
            self.assertEqual(spec.datasets[0].items[0].item_type, "sequence")
            roundtrip = json.loads(spec.to_json())
            self.assertEqual(roundtrip["schema"], "yrmpe.result.v1")
            self.assertEqual(roundtrip["datasets"][0]["items"][0]["item_type"], "sequence")
            self.assertEqual(roundtrip["runs"][0]["method"], "getorganelle-reads")


class GraphTests(unittest.TestCase):
    def test_parse_gfa(self):
        text = r"""S	3	ACGTACGT	LN:i:8	RC:i:80
S	4	GGCC	LN:i:4	RC:i:8
L	3	+	4	-	0M
"""
        graph = parse_gfa(text)
        self.assertEqual(len(graph.nodes), 2)
        self.assertEqual(len(graph.edges), 1)
        self.assertEqual(graph.nodes["3"].length, 8)
        self.assertEqual(graph.nodes["3"].coverage, 10.0)
        self.assertIn("components", graph.stats())

    def test_parse_fastg(self):
        text = (
            ">EDGE_1_length_100_cov_20.5:EDGE_2_length_50_cov_10.0';\n"
            "ACGT\n"
            ">EDGE_1_length_100_cov_20.5';\n"
            "ACGT\n"
            ">EDGE_2_length_50_cov_10.0;\n"
            "GGCC\n"
        )
        graph = parse_fastg(text)
        self.assertEqual(len(graph.nodes), 2)
        self.assertEqual(len(graph.edges), 1)
        node_id = next(n for n in graph.nodes if n.startswith("EDGE_1"))
        self.assertEqual(graph.nodes[node_id].coverage, 20.5)

    def test_layout_returns_every_node(self):
        graph = parse_gfa(
            "S\t1\tACGT\tLN:i:4\tRC:i:4\n"
            "S\t2\tGGCC\tLN:i:4\tRC:i:4\n"
            "L\t1\t+\t2\t+\t0M\n"
        )
        positions, note = layout_graph(graph)
        self.assertEqual(set(positions), {"1", "2"})
        self.assertIn("nodes", note)

    def test_endpoint_layout_gives_nodes_length_and_direction(self):
        graph = parse_gfa(
            "S\t1\tACGTACGTACGT\tLN:i:12\tRC:i:24\n"
            "S\t2\tGGCC\tLN:i:4\tRC:i:4\n"
            "L\t1\t+\t2\t-\t0M\n"
        )
        centers, ends, note = layout_graph_with_ends(graph)
        self.assertEqual(set(centers), {"1", "2"})
        self.assertEqual(set(ends), {"1", "2"})
        self.assertIn("length-aware", note)
        for node_id, (start, end) in ends.items():
            self.assertNotEqual(start, end)
            midpoint = ((start[0] + end[0]) / 2, (start[1] + end[1]) / 2)
            self.assertAlmostEqual(centers[node_id][0], midpoint[0])
            self.assertAlmostEqual(centers[node_id][1], midpoint[1])
        long_span = abs(ends["1"][1][0] - ends["1"][0][0]) + abs(ends["1"][1][1] - ends["1"][0][1])
        short_span = abs(ends["2"][1][0] - ends["2"][0][0]) + abs(ends["2"][1][1] - ends["2"][0][1])
        self.assertGreater(long_span, short_span)
        edge = graph.edges[0]
        self.assertEqual(edge_endpoint_sides(graph, edge), (1, 1))


class MetadataTests(unittest.TestCase):
    def test_plugin_metadata(self):
        info = plugin_info()
        self.assertEqual(info["tool"], "GetOrganelle")
        bindings = control_bindings()
        ids = [binding["id"] for binding in bindings]
        self.assertEqual(len(ids), len(set(ids)))
        for binding in bindings:
            self.assertIn("cli", binding)
            self.assertIsInstance(binding["cli"], list)

    def test_settings_roundtrip(self):
        settings = Settings.from_dict({"theme": "dark", "threads": 3})
        restored = Settings.from_dict(settings.to_dict())
        self.assertEqual(restored.theme, "dark")
        self.assertEqual(restored.threads, 3)


if __name__ == "__main__":
    unittest.main()
