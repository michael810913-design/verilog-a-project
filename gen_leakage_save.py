#!/usr/bin/env python3
"""Generate Spectre terminal-current saves and their extraction manifest."""

import argparse
import csv
from pathlib import Path
import sys

from hierarchy import SupplyTraceError, SupplyTracer, flatten
from spectre_parser import SpectreNetlistParser, SpectreParseError


class SaveGenerator:
    def __init__(self, root: str, supply: str, level: int):
        self.root, self.supply, self.level = root, supply, level

    def write(self, tree, save_path: Path, targets_path: Path) -> None:
        # Level-major order makes the 1..N coverage immediately auditable while
        # retaining deterministic lexical order within each level.
        targets = sorted(flatten(tree), key=lambda item: (item.level, item.hierarchy))
        lines = ["// Auto-generated leakage current save file",
                 f"// Root   : {self.root}", f"// Supply : {self.supply}",
                 f"// Level  : {self.level}", ""]
        previous = 0
        for target in targets:
            if target.level != previous and previous:
                lines.append("")
            for terminal, unused_parent_net in target.supply_mappings:
                lines.append("save {0}:{1}".format(
                    spectre_escape_identifier(target.hierarchy),
                    spectre_escape_identifier(terminal)))
            previous = target.level
        save_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        with targets_path.open("w", newline="", encoding="utf-8") as stream:
            writer = csv.writer(stream)
            writer.writerow(["level", "hierarchy", "cell", "supply_terminal",
                             "parent_supply_net", "supply_terminal_index"])
            for target in targets:
                for terminal, parent_net in target.supply_mappings:
                    # Some PSF versions expose vector-instance terminals only
                    # as :1, :2, ... . Record the connectivity-derived formal
                    # terminal position as a deterministic extraction fallback.
                    terminal_index = target.definition.terminals.index(terminal) + 1
                    writer.writerow([target.level, target.hierarchy, target.definition.name,
                                     terminal, parent_net, terminal_index])


def spectre_escape_identifier(identifier):
    """Escape vector delimiters when an identifier is used in a save path.

    Spectre accepts ``B1<0>`` as an instance name in several netlist contexts,
    but in a hierarchical save path such as ``B1<0>.N1`` it can tokenize ``>``
    as an operator. Backslash escaping keeps the angle brackets in the
    identifier. The manifest deliberately retains the original hierarchy for
    reporting and OCEAN lookup.
    """
    return identifier.replace("<", "\\<").replace(">", "\\>")


def generate(netlist_path, root, supply, level, save_path, targets_path, debug=False):
    """Generate both Phase 1 files for CLI and GUI front ends."""
    if level < 1:
        raise ValueError("level must be at least 1")
    netlist = SpectreNetlistParser().parse(Path(netlist_path))
    tree = SupplyTracer(netlist, debug=debug).trace(root, supply, level)
    SaveGenerator(root, supply, level).write(
        tree, Path(save_path), Path(targets_path))


def build_argument_parser():
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""example:
  python3 gen_leakage_save.py --netlist input.scs --root IA \\
      --net VDD12 --level 3 --output leakage_save.scs

This also writes leakage_targets.csv by default. Use --targets to rename it.
--level 3 means levels 1 through 3, including the root as level 1.
--net may be the root's top-level actual net or its formal subckt terminal.""")
    parser.add_argument("--netlist", required=True, type=Path)
    parser.add_argument("--root", required=True)
    parser.add_argument("--net", required=True)
    parser.add_argument("--level", required=True, type=int)
    parser.add_argument("--output", type=Path, default=Path("leakage_save.scs"))
    parser.add_argument("--targets", type=Path, default=Path("leakage_targets.csv"))
    parser.add_argument("--debug", action="store_true",
                        help="show how the root supply terminal is resolved")
    return parser


def arguments(argv=None):
    return build_argument_parser().parse_args(argv)


def main(argv=None) -> int:
    command_line = sys.argv[1:] if argv is None else argv
    if not command_line:
        parser = build_argument_parser()
        parser.print_help(sys.stderr)
        print("\nERROR:\nplease provide --netlist, --root, --net, and --level; see the example above",
              file=sys.stderr)
        return 2
    args = arguments(command_line)
    try:
        generate(args.netlist, args.root, args.net, args.level,
                 args.output, args.targets, args.debug)
    except (OSError, ValueError, SpectreParseError, SupplyTraceError) as error:
        print(f"ERROR:\n{error}", file=sys.stderr)
        return 1
    print(f"Wrote {args.output} and {args.targets}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
