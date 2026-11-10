import csv
import io
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from hierarchy import SupplyTracer, flatten
from gen_leakage_save import spectre_escape_identifier
from gui_settings import load_settings, save_settings, settings_path
from rank_leakage import generate_report, load, print_report, render
from spectre_parser import SpectreNetlistParser
from run_extract import parse_time_value, run_extraction, validate_current_csv

ROOT = Path(__file__).parents[1]
FIXTURE = ROOT / "tests/fixtures/hierarchy.scs"


class PhaseOneTests(unittest.TestCase):
    def test_step_one_gui_module_imports_without_starting_window(self):
        module = __import__("gen_leakage_save_gui__step_1")
        self.assertTrue(hasattr(module, "LeakageGeneratorGui"))

    def test_gui_settings_persist_and_preserve_sections(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "settings.json"
            with mock.patch.dict("os.environ", {"SPECTRE_LEAKAGE_SETTINGS": str(path)}):
                save_settings("extractor", {"psf": "/tmp/psf"})
                save_settings("generator", {"root": "ANATOP_H", "level": "4"})
                self.assertEqual(settings_path(), path)
                self.assertEqual(load_settings("generator"),
                                 {"root": "ANATOP_H", "level": "4"})
                self.assertEqual(load_settings("extractor"), {"psf": "/tmp/psf"})
                self.assertEqual(path.stat().st_mode & 0o777, 0o600)

    def test_no_arguments_prints_actionable_example(self):
        run = subprocess.run(
            [sys.executable, str(ROOT / "gen_leakage_save.py")],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            universal_newlines=True)
        self.assertEqual(run.returncode, 2)
        self.assertIn("python3 gen_leakage_save.py --netlist input.scs", run.stderr)
        self.assertIn("please provide --netlist, --root, --net, and --level", run.stderr)

    def test_recursive_connectivity_mapping(self):
        netlist = SpectreNetlistParser().parse(FIXTURE)
        targets = flatten(SupplyTracer(netlist).trace("IA", "VDD12", 3))
        self.assertEqual(
            [(item.hierarchy, item.supply_terminal, item.parent_supply_net) for item in targets],
            [("IA", "VDD12", "VDD12"), ("IA.IB1", "VDD", "VDD12"),
             ("IA.IB1.IC1", "AVDD", "VDD"), ("IA.IB1.IC2", "VPWR", "VDD"),
             ("IA.IB1.IC3", "VDD", "VDD"), ("IA.IB2", "AVDD", "VDD12"),
             ("IA.IB2.IC4", "VDDA", "AVDD")])

    def test_root_supply_can_be_formal_terminal(self):
        with tempfile.TemporaryDirectory() as temporary:
            netlist_path = Path(temporary) / "formal-root.scs"
            netlist_path.write_text(
                "subckt CHILD (VPWR VSS)\nends CHILD\n"
                "subckt ROOT (VDDI2 VSS)\nIC (VDDI2 VSS) CHILD\nends ROOT\n"
                "ANATOP_H (generated_supply 0) ROOT\n")
            netlist = SpectreNetlistParser().parse(netlist_path)
            targets = flatten(SupplyTracer(netlist).trace("ANATOP_H", "VDDI2", 2))
            self.assertEqual(
                [(item.hierarchy, item.supply_terminal) for item in targets],
                [("ANATOP_H", "VDDI2"), ("ANATOP_H.IC", "VPWR")])

    def test_root_actual_supply_can_fan_out_to_multiple_terminals(self):
        with tempfile.TemporaryDirectory() as temporary:
            netlist_path = Path(temporary) / "fanout.scs"
            netlist_path.write_text(
                "subckt CHILD (VPWR VSS)\nends CHILD\n"
                "subckt ROOT (VDDI2_USB VDDI2_OSC VSS)\n"
                "IC (VDDI2_OSC VSS) CHILD\nends ROOT\n"
                "ANATOP_H (VDDI2 VDDI2 0) ROOT\n")
            netlist = SpectreNetlistParser().parse(netlist_path)
            targets = flatten(SupplyTracer(netlist).trace("ANATOP_H", "VDDI2", 2))
            self.assertEqual(targets[0].supply_mappings,
                             [("VDDI2_USB", "VDDI2"), ("VDDI2_OSC", "VDDI2")])
            self.assertEqual(targets[1].supply_mappings, [("VPWR", "VDDI2_OSC")])

    def test_bad_root_supply_lists_actual_to_formal_mapping(self):
        netlist = SpectreNetlistParser().parse(FIXTURE)
        with self.assertRaisesRegex(ValueError, "available terminal mapping: VDD12=VDD12"):
            SupplyTracer(netlist).trace("IA", "NOT_A_SUPPLY", 1)

    def test_cli_outputs(self):
        with tempfile.TemporaryDirectory() as temporary:
            save = Path(temporary) / "save.scs"
            targets = Path(temporary) / "targets.csv"
            run = subprocess.run(
                [sys.executable, str(ROOT / "gen_leakage_save.py"), "--netlist", str(FIXTURE),
                 "--root", "IA", "--net", "VDD12", "--level", "3",
                 "--output", str(save), "--targets", str(targets)],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                universal_newlines=True)
            self.assertEqual(run.returncode, 0, run.stderr)
            self.assertIn("save IA.IB1.IC2:VPWR", save.read_text())
            with targets.open() as stream:
                rows = list(csv.DictReader(stream))
            self.assertEqual(len(rows), 7)
            self.assertTrue(all(row["supply_terminal_index"] == "1" for row in rows))

    def test_vector_instance_manifest_records_terminal_ordinal(self):
        with tempfile.TemporaryDirectory() as temporary:
            netlist = Path(temporary) / "vector.scs"
            save = Path(temporary) / "save.scs"
            targets = Path(temporary) / "targets.csv"
            netlist.write_text(
                "subckt BLOCK_A (IN VDDA VSS)\nends BLOCK_A\n"
                "subckt TOP (VDDMA VSS)\n"
                "B1<0> (sig VDDMA VSS) BLOCK_A\n"
                "ends TOP\nTop (VDDMA 0) TOP\n")
            generate = __import__("gen_leakage_save").generate
            generate(netlist, "Top", "VDDMA", 2, save, targets)
            with targets.open() as stream:
                rows = list(csv.DictReader(stream))
            vector = next(row for row in rows if row["hierarchy"] == "Top.B1<0>")
            self.assertEqual(vector["supply_terminal"], "VDDA")
            self.assertEqual(vector["supply_terminal_index"], "2")
            self.assertIn("save Top.B1\\<0\\>:VDDA", save.read_text())

    def test_nested_vector_instance_is_escaped_in_spectre_save_path(self):
        self.assertEqual(
            spectre_escape_identifier("Top.I_R_calibration.R2<0>.N1"),
            "Top.I_R_calibration.R2\\<0\\>.N1")

    def test_missing_root_is_error(self):
        netlist = SpectreNetlistParser().parse(FIXTURE)
        with self.assertRaisesRegex(ValueError, "root instance NOPE not found"):
            SupplyTracer(netlist).trace("NOPE", "VDD12", 3)


class RankingTests(unittest.TestCase):
    def test_gui_module_imports_without_starting_window(self):
        __import__("rank_leakage_gui")

    def test_shared_report_api_writes_utf8_report(self):
        with tempfile.TemporaryDirectory() as temporary:
            current = Path(temporary) / "current.csv"
            output = Path(temporary) / "report.txt"
            current.write_text(
                "level,hierarchy,cell,supply_terminal,current_A\n"
                "1,IA,A,VDD12,0.001\n"
                "2,IA.IB1,B1,VDD,0.0008\n")
            report = generate_report(current, output)
            self.assertIn("Leakage Current Global Ranking", report)
            self.assertIn("IA.IB1", report)
            self.assertEqual(output.read_text(encoding="utf-8"), report + "\n")

    def test_ascii_terminal_uses_safe_tree_fallback(self):
        raw = io.BytesIO()
        stream = io.TextIOWrapper(raw, encoding="ascii")
        print_report("ROOT\n\u2514\u2500\u2500 CHILD\n\u2502   LEAF", stream)
        stream.flush()
        self.assertEqual(raw.getvalue().decode("ascii"),
                         "ROOT\n`-- CHILD\n|   LEAF\n")

    def test_missing_current_csv_has_actionable_error(self):
        missing = ROOT / "does-not-exist-leakage-current.csv"
        completed = subprocess.run(
            [sys.executable, str(ROOT / "rank_leakage.py"), str(missing)],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            universal_newlines=True)
        self.assertEqual(completed.returncode, 2)
        self.assertIn("input current CSV not found", completed.stderr)
        self.assertIn("run_extract.py", completed.stderr)
        self.assertNotIn("Traceback", completed.stderr)

    def test_rank_and_tree(self):
        with tempfile.NamedTemporaryFile("w", suffix=".csv", delete=False) as stream:
            stream.write("level,hierarchy,cell,supply_terminal,current_A\n")
            stream.write("1,IA,A,VDD12,0.00105\n2,IA.IB1,B1,VDD,0.0009\n")
            stream.write("2,IA.IB2,B2,AVDD,0.00015\n3,IA.IB1.IC2,C2,VPWR,0.00082\n")
            path = Path(stream.name)
        try:
            report = render(load(path))
            self.assertLess(report.index("IA.IB1     900.0 uA"), report.index("IA.IB2     150.0 uA"))
            self.assertIn("\u251c\u2500\u2500 IB1", report)
            self.assertIn("<<<", report)
        finally:
            path.unlink()

    def test_multiple_terminal_currents_are_summed_per_hierarchy(self):
        readings = [
            __import__("rank_leakage").Reading(1, "ANATOP_H", "ROOT", "VDDI2_USB", 1e-6),
            __import__("rank_leakage").Reading(1, "ANATOP_H", "ROOT", "VDDI2_OSC", 2e-6),
        ]
        report = render(readings)
        self.assertIn("ANATOP_H   3.000 uA", report)
        self.assertEqual(report.count("ANATOP_H"), 3)  # global, level, tree


class ExtractionLauncherTests(unittest.TestCase):
    def test_average_window_order_is_validated_before_ocean(self):
        self.assertAlmostEqual(parse_time_value("0.5u"), 0.5e-6)
        with self.assertRaisesRegex(ValueError, "greater than --start"):
            run_extraction("psf", "targets.csv", "current.csv",
                           start="1u", stop="0.5u")

    def test_ocean_script_rejects_window_outside_waveform_range(self):
        script = (ROOT / "extract_leakage.ocn").read_text()
        self.assertIn("drGetWaveformXVec", script)
        self.assertIn("average window %.15g to %.15g s is outside", script)
        self.assertIn("start<waveStart || stop>waveStop", script)
        self.assertIn("status=errset(leakageExtract() t)", script)
        self.assertIn("exit(1)", script)
        self.assertIn("fallbackSignal=strcat(hierarchy \":\" terminalIndex)", script)
        self.assertIn("leakageEscapeVectorName", script)
        self.assertIn("escapedFallbackSignal", script)
        self.assertIn("resolved as PSF signal", script)
        self.assertIn("refusing to rank a partial hierarchy", script)

    def test_no_arguments_prints_multiline_command_example(self):
        completed = subprocess.run(
            [sys.executable, str(ROOT / "run_extract.py")],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            universal_newlines=True)
        self.assertEqual(completed.returncode, 2)
        self.assertIn("python3 run_extract.py", completed.stderr)
        self.assertIn("--psf /absolute/path/to/psf", completed.stderr)
        self.assertIn("--start 0.5u --stop 1u", completed.stderr)

    def test_gui_module_imports_without_starting_window(self):
        module = __import__("run_extract_gui__step_2")
        self.assertIs(module.generate_report, generate_report)
        self.assertIs(module.load_settings, load_settings)
        self.assertIs(module.save_settings, save_settings)

    def test_combined_gui_workflow_extracts_then_ranks(self):
        module = __import__("run_extract_gui__step_2")
        messages = []
        with mock.patch("run_extract_gui__step_2.run_extraction", return_value=0) as extraction:
            with mock.patch("run_extract_gui__step_2.generate_report",
                            return_value="ranking") as ranking:
                report = module.extract_and_rank(
                    "psf", "targets.csv", "current.csv", "report.txt",
                    start="0.5u", stop="1u", output_callback=messages.append)
        self.assertEqual(report, "ranking")
        extraction.assert_called_once_with(
            "psf", "targets.csv", "current.csv", None, "0.5u", "1u",
            "ocean", messages.append)
        ranking.assert_called_once_with("current.csv", "report.txt")
        self.assertEqual(messages, ["Step 2/2: Generating leakage ranking..."])

    def test_shared_extraction_api_sets_average_environment(self):
        with tempfile.TemporaryDirectory() as temporary:
            psf = Path(temporary) / "psf"
            psf.mkdir()
            targets = Path(temporary) / "targets.csv"
            targets.write_text("level,hierarchy,cell,supply_terminal,parent_supply_net\n")
            output = Path(temporary) / "current.csv"
            completed = mock.Mock(returncode=0)
            def fake_run(*args, **kwargs):
                output.write_text(
                    "level,hierarchy,cell,supply_terminal,current_A\n"
                    "1,IA,A,VDD,1e-6\n")
                return completed
            with mock.patch("run_extract.subprocess.run", side_effect=fake_run) as runner:
                result = run_extraction(psf, targets, output, start="9u", stop="10u")
            self.assertEqual(result, 0)
            environment = runner.call_args[1]["env"]
            self.assertEqual(environment["LEAKAGE_MODE"], "average")
            self.assertEqual(environment["LEAKAGE_START"], "9u")
            self.assertEqual(environment["LEAKAGE_STOP"], "10u")
            self.assertEqual(environment["LEAKAGE_OUTPUT"], str(output.resolve()))

    def test_shared_extraction_api_rejects_incomplete_window(self):
        with self.assertRaisesRegex(ValueError, "start requires"):
            run_extraction("psf", "targets.csv", "output.csv", start="9u")

    def test_gui_result_validation_rejects_missing_or_empty_csv(self):
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "current.csv"
            with self.assertRaisesRegex(RuntimeError, "did not create"):
                validate_current_csv(output)
            output.write_text("level,hierarchy,cell,supply_terminal,current_A\n")
            with self.assertRaisesRegex(RuntimeError, "contains no data rows"):
                validate_current_csv(output)

    def test_streaming_extraction_forwards_ocean_output(self):
        with tempfile.TemporaryDirectory() as temporary:
            psf = Path(temporary) / "psf"
            psf.mkdir()
            targets = Path(temporary) / "targets.csv"
            targets.write_text("header\n")
            process = mock.Mock()
            process.stdout.readline.side_effect = ["Loading OCEAN\n", "WARNING: missing\n", ""]
            process.wait.return_value = 0
            messages = []
            output = Path(temporary) / "out.csv"
            output.write_text("header\n1,IA,A,VDD,1e-6\n")
            with mock.patch("run_extract.subprocess.Popen", return_value=process):
                result = run_extraction(psf, targets, output,
                                        time_value="10u", output_callback=messages.append)
            self.assertEqual(result, 0)
            self.assertEqual(messages, ["Loading OCEAN", "WARNING: missing"])
            process.stdout.close.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
