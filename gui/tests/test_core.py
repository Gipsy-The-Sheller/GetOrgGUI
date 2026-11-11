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
                )
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
