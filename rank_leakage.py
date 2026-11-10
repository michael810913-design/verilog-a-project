#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Rank extracted hierarchical supply currents."""

import argparse
import csv
from pathlib import Path
import sys
from typing import Dict, List, Optional


class Reading:
    def __init__(self, level, hierarchy, cell, terminal, current):
        # type: (int, str, str, str, float) -> None
        self.level = level
        self.hierarchy = hierarchy
        self.cell = cell
        self.terminal = terminal
        self.current = current


def load(path):
    # type: (Path) -> List[Reading]
    with path.open(newline="", encoding="utf-8") as stream:
        rows = list(csv.DictReader(stream))
    required = {"level", "hierarchy", "cell", "supply_terminal", "current_A"}
    if not rows or not required.issubset(rows[0]):
        raise ValueError(f"{path} is empty or lacks columns: {', '.join(sorted(required))}")
    return [Reading(int(row["level"]), row["hierarchy"], row["cell"],
                    row["supply_terminal"], float(row["current_A"])) for row in rows]


def engineering(value: float) -> str:
    absolute = abs(value)
    for threshold, scale, unit in ((1, 1, "A"), (1e-3, 1e3, "mA"),
                                   (1e-6, 1e6, "uA"), (1e-9, 1e9, "nA"),
                                   (0, 1e12, "pA")):
        if absolute >= threshold:
            scaled = value * scale
            return f"{scaled:.3f} {unit}" if abs(scaled) < 10 else f"{scaled:.1f} {unit}"
    return "0.000 A"


def render(readings):
    # type: (List[Reading]) -> str
    # A supply net can fan out to several formal power terminals on the same
    # instance.  The manifest has one row per terminal; report one block current
    # by summing all of that hierarchy's terminal currents.
    grouped = {}  # type: Dict[str, Reading]
    for item in readings:
        if item.hierarchy in grouped:
            grouped[item.hierarchy].current += item.current
            grouped[item.hierarchy].terminal += "+" + item.terminal
        else:
            grouped[item.hierarchy] = Reading(item.level, item.hierarchy, item.cell,
                                              item.terminal, item.current)
    readings = list(grouped.values())
    ranked = sorted(readings, key=lambda item: (-abs(item.current), item.hierarchy))
    lines = ["Leakage Current Global Ranking", "", "Rank  Level  Hierarchy  Current",
             "--------------------------------"]
    lines += [f"{rank:<5} {item.level:<6} {item.hierarchy:<10} {engineering(item.current)}"
              for rank, item in enumerate(ranked, 1)]
    for level in sorted({item.level for item in readings}):
        group = sorted((item for item in readings if item.level == level),
                       key=lambda item: (-abs(item.current), item.hierarchy))
        lines += ["", f"===== Level {level} =====", "", "Rank  Hierarchy  Current",
                  "------------------------"]
        lines += [f"{rank:<5} {item.hierarchy:<10} {engineering(item.current)}"
                  for rank, item in enumerate(group, 1)]
    lines += ["", "Hierarchy Tree Summary", ""]
    by_path = {item.hierarchy: item for item in readings}
    children = {}  # type: Dict[Optional[str], List[Reading]]
    for item in readings:
        parent = item.hierarchy.rpartition(".")[0] or None
        children.setdefault(parent, []).append(item)
    def draw(parent, prefix=""):
        # type: (Optional[str], str) -> None
        siblings = sorted(children.get(parent, []), key=lambda item: item.hierarchy)
        maximum = max((abs(item.current) for item in siblings), default=-1)
        for index, item in enumerate(siblings):
            last = index == len(siblings) - 1
            # Keep this source file ASCII-only.  Some legacy Python 3.6 sites
            # copy scripts through tools that corrupt literal UTF-8 bytes.
            branch = "\u2514\u2500\u2500 " if last else "\u251c\u2500\u2500 "
            name = item.hierarchy.rsplit(".", 1)[-1]
            marker = "  <<<" if len(siblings) > 1 and abs(item.current) == maximum else ""
            lines.append(f"{prefix}{branch if parent else ''}{name:<24} {engineering(item.current)}{marker}")
            draw(item.hierarchy, prefix + ("    " if last else "\u2502   "))
    draw(None)
    return "\n".join(lines)


def ascii_tree(report):
    # type: (str) -> str
    """Return a terminal-safe fallback without changing the UTF-8 report file."""
    return (report.replace("\u251c\u2500\u2500 ", "+-- ")
                  .replace("\u2514\u2500\u2500 ", "`-- ")
                  .replace("\u2502   ", "|   "))


def print_report(report, stream=None):
    # type: (str, object) -> None
    """Print Unicode when supported, otherwise use an ASCII tree."""
    stream = stream or sys.stdout
    encoding = getattr(stream, "encoding", None) or "utf-8"
    try:
        report.encode(encoding)
    except (LookupError, UnicodeEncodeError):
        report = ascii_tree(report)
    stream.write(report + "\n")


def generate_report(csv_path, output_path=None):
    """Load a leakage-current CSV, render rankings, and optionally save them."""
    csv_path = Path(csv_path)
    if not csv_path.is_file():
        raise ValueError("input current CSV not found: {}".format(csv_path))
    report = render(load(csv_path))
    if output_path:
        Path(output_path).write_text(report + "\n", encoding="utf-8")
    return report


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__,
        epilog=("leakage_current.csv is created by run_extract.py after the "
                "Spectre/ADE simulation has produced a PSF result."))
    parser.add_argument("csv", nargs="?", type=Path, default=Path("leakage_current.csv"))
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if not args.csv.is_file():
        print("ERROR: input current CSV not found: {}".format(args.csv), file=sys.stderr)
        print("Run OCEAN extraction first, for example:", file=sys.stderr)
        print("  python3 run_extract.py --psf /path/to/psf "
              "--targets leakage_targets.csv --start 9u --stop 10u",
              file=sys.stderr)
        return 2
    try:
        report = generate_report(args.csv, args.output)
    except (OSError, ValueError) as error:
        print("ERROR: cannot read {}: {}".format(args.csv, error), file=sys.stderr)
        return 2
    print_report(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
