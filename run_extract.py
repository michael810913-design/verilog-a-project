#!/usr/bin/env python3
"""Validated command-line launcher for the OCEAN leakage extractor."""

import argparse
import os
from pathlib import Path
import subprocess
import sys


EXAMPLE = """python3 run_extract.py \\
  --psf /absolute/path/to/psf \\
  --targets ./leakage_targets.csv \\
  --start 0.5u --stop 1u \\
  --output ./leakage_current.csv"""


def validate_current_csv(output):
    """Require a current CSV with a header and at least one measurement."""
    path = Path(output)
    if not path.is_file():
        raise RuntimeError(
            "OCEAN finished but did not create the current CSV: {}".format(path))
    try:
        with path.open("r") as stream:
            rows = [line for line in stream if line.strip()]
    except OSError as error:
        raise RuntimeError("cannot read output CSV: {}".format(error))
    if len(rows) < 2:
        raise RuntimeError(
            "The current CSV contains no data rows. Check for 'waveform ... not found' "
            "warnings and verify the PSF directory and saved terminal names.")


def parse_time_value(value):
    """Parse the Spectre time suffixes accepted by the bundled OCEAN script."""
    suffixes = {"p": 1e-12, "n": 1e-9, "u": 1e-6, "m": 1e-3,
                "k": 1e3, "M": 1e6}
    text = str(value).strip()
    if not text:
        raise ValueError("time value cannot be empty")
    scale = suffixes.get(text[-1], 1.0)
    number = text[:-1] if text[-1] in suffixes else text
    try:
        return float(number) * scale
    except ValueError:
        raise ValueError("invalid time value: {}".format(value))


def run_extraction(psf, targets, output, time_value=None, start=None,
                   stop=None, ocean="ocean", output_callback=None):
    """Validate extraction inputs and run the bundled OCEAN script."""
    psf = Path(psf)
    targets = Path(targets)
    output = Path(output)
    if bool(time_value) == bool(start):
        raise ValueError("select either a time point or an average start/stop window")
    if start and not stop:
        raise ValueError("--start requires --stop")
    if stop and not start:
        raise ValueError("--stop requires --start")
    if time_value is not None and parse_time_value(time_value) < 0:
        raise ValueError("--time cannot be negative")
    if start is not None and stop is not None:
        start_seconds = parse_time_value(start)
        stop_seconds = parse_time_value(stop)
        if start_seconds < 0:
            raise ValueError("--start cannot be negative")
        if stop_seconds <= start_seconds:
            raise ValueError("--stop must be greater than --start")
    for path, label in ((psf, "PSF"), (targets, "targets CSV")):
        if not path.exists():
            raise ValueError("{} not found: {}".format(label, path))

    env = os.environ.copy()
    env.update(LEAKAGE_PSF=str(psf.resolve()),
               LEAKAGE_TARGETS=str(targets.resolve()),
               LEAKAGE_OUTPUT=str(output.resolve()),
               LEAKAGE_MODE="time" if time_value else "average")
    if time_value:
        env["LEAKAGE_TIME"] = time_value
    else:
        env.update(LEAKAGE_START=start, LEAKAGE_STOP=stop)
    script = Path(__file__).with_name("extract_leakage.ocn")
    command = [ocean, "-nograph", "-restore", str(script)]
    if output_callback is None:
        return_code = subprocess.run(command, env=env).returncode
        if return_code == 0:
            validate_current_csv(output)
        return return_code

    # Merge stderr into stdout so a GUI can display startup, SKILL errors, and
    # missing-waveform warnings in the order OCEAN emitted them.
    process = subprocess.Popen(
        command, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        universal_newlines=True, bufsize=1)
    for line in iter(process.stdout.readline, ""):
        output_callback(line.rstrip("\r\n"))
    process.stdout.close()
    return_code = process.wait()
    if return_code == 0:
        validate_current_csv(output)
    return return_code


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Extract saved hierarchy terminal currents from Spectre PSF using OCEAN.",
        epilog="Example:\n  " + EXAMPLE.replace("\n", "\n  "),
        formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--psf", type=Path, default=Path("psf"))
    parser.add_argument("--targets", type=Path, default=Path("leakage_targets.csv"))
    parser.add_argument("--output", type=Path, default=Path("leakage_current.csv"))
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--time")
    mode.add_argument("--start")
    parser.add_argument("--stop")
    parser.add_argument("--ocean", default="ocean")
    if len(sys.argv) == 1:
        parser.print_help(sys.stderr)
        parser.exit(2, "\nERROR: select --time, or provide --start and --stop.\n")
    args = parser.parse_args()
    if args.start and not args.stop:
        parser.error("--start requires --stop")
    if args.stop and not args.start:
        parser.error("--stop requires --start")
    try:
        return run_extraction(args.psf, args.targets, args.output, args.time,
                              args.start, args.stop, args.ocean)
    except (ValueError, RuntimeError) as error:
        parser.error(str(error))


if __name__ == "__main__":
    raise SystemExit(main())
