"""Small, connectivity-oriented parser for Spectre hierarchical netlists."""

from pathlib import Path
import re
import shlex
from typing import Dict, List, Optional, Set, Union


class Instance:
    def __init__(self, name, connections, cell, source, line):
        # type: (str, List[str], str, str, int) -> None
        self.name = name
        self.connections = connections
        self.cell = cell
        self.source = source
        self.line = line


class SubcktDefinition:
    def __init__(self, name, terminals, instances=None):
        # type: (str, List[str], Optional[List[Instance]]) -> None
        self.name = name
        self.terminals = terminals
        self.instances = instances if instances is not None else []


class Netlist:
    def __init__(self, subckts=None, top_instances=None, files=None):
        # type: (Optional[Dict[str, SubcktDefinition]], Optional[List[Instance]], Optional[List[Path]]) -> None
        self.subckts = subckts if subckts is not None else {}
        self.top_instances = top_instances if top_instances is not None else []
        self.files = files if files is not None else []


class SpectreParseError(ValueError):
    pass


class SpectreNetlistParser:
    """Parse subcircuits and instances without interpreting device parameters.

    Both ``subckt X (a b)`` and ``subckt X a b`` forms, ``+``/backslash
    continuation, quoted include paths, bus tokens, and escaped identifiers are
    retained.  Local includes are followed by default; model-library sections
    are deliberately outside this connectivity parser's scope.
    """

    def __init__(self, recursive_includes: bool = True):
        self.recursive_includes = recursive_includes
        self.result = Netlist()
        self._seen = set()  # type: Set[Path]

    def parse(self, path):
        # type: (Union[str, Path]) -> Netlist
        self.result = Netlist()
        self._seen = set()
        self._parse_file(Path(path).resolve())
        return self.result

    def _parse_file(self, path: Path) -> None:
        if path in self._seen:
            return
        if not path.is_file():
            raise SpectreParseError(f"netlist not found: {path}")
        self._seen.add(path)
        self.result.files.append(path)
        current = None  # type: Optional[SubcktDefinition]
        for line_no, statement in self._statements(path):
            tokens = self._tokens(statement)
            if not tokens:
                continue
            keyword = tokens[0].lower()
            if keyword in {"include", "ahdl_include"}:
                if self.recursive_includes and len(tokens) >= 2:
                    included = (path.parent / tokens[1]).resolve()
                    if included.is_file():
                        self._parse_file(included)
                continue
            if keyword == "subckt":
                if len(tokens) < 2:
                    raise SpectreParseError(f"{path}:{line_no}: malformed subckt")
                name = tokens[1]
                terminals = self._subckt_terminals(tokens[2:])
                current = SubcktDefinition(name, terminals)
                if name in self.result.subckts:
                    raise SpectreParseError(f"{path}:{line_no}: duplicate subckt {name}")
                self.result.subckts[name] = current
                continue
            if keyword == "ends":
                current = None
                continue
            instance = self._instance(tokens, path, line_no)
            if instance:
                (current.instances if current else self.result.top_instances).append(instance)

    @staticmethod
    def _statements(path: Path):
        pending = ""
        start = 0
        for number, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            stripped = raw.strip()
            if not stripped or stripped.startswith(("//", "*")):
                continue
            stripped = re.split(r"\s+//", stripped, maxsplit=1)[0]
            plus = stripped.startswith("+")
            if plus:
                stripped = stripped[1:].lstrip()
            backslash = stripped.endswith("\\")
            if backslash:
                stripped = stripped[:-1].rstrip()
            if not pending:
                start = number
            if plus or pending:
                pending = (pending + " " + stripped).strip()
            else:
                pending = stripped
            if not backslash:
                yield start, pending
                pending = ""
        if pending:
            yield start, pending

    @staticmethod
    def _tokens(statement):
        # type: (str) -> List[str]
        normalized = statement.replace("(", " ( ").replace(")", " ) ")
        lexer = shlex.shlex(normalized, posix=True)
        lexer.whitespace_split = True
        lexer.commenters = ""
        return list(lexer)

    @staticmethod
    def _subckt_terminals(tokens):
        # type: (List[str]) -> List[str]
        if "(" in tokens:
            begin = tokens.index("(") + 1
            try:
                end = tokens.index(")", begin)
            except ValueError as exc:
                raise SpectreParseError("unclosed subckt terminal list") from exc
            return tokens[begin:end]
        return [token for token in tokens if "=" not in token]

    @staticmethod
    def _instance(tokens, path, line):
        # type: (List[str], Path, int) -> Optional[Instance]
        # Analyses, options, simulator directives, and primitive devices cannot
        # contribute nodes to the subcircuit hierarchy.
        if len(tokens) < 3 or tokens[0].lower() in {
            "simulator", "global", "parameters", "save", "tran", "dc", "ac",
            "options", "model", "library", "section", "endsection", "endlibrary",
        }:
            return None
        name = tokens[0]
        if "(" in tokens:
            begin = tokens.index("(") + 1
            try:
                end = tokens.index(")", begin)
            except ValueError as exc:
                raise SpectreParseError(f"{path}:{line}: unclosed instance nodes") from exc
            nodes = tokens[begin:end]
            remainder = tokens[end + 1:]
        else:
            first_parameter = next((i for i, token in enumerate(tokens[1:], 1) if "=" in token), len(tokens))
            positional = tokens[1:first_parameter]
            if len(positional) < 2:
                return None
            nodes, remainder = positional[:-1], positional[-1:]
        cell = next((token for token in remainder if "=" not in token), "")
        return Instance(name, nodes, cell, str(path), line) if cell else None
