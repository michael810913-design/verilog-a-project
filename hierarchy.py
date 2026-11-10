"""Hierarchy construction and supply-connectivity tracing."""

import sys
from typing import List, Optional, Tuple

from spectre_parser import Instance, Netlist, SubcktDefinition


class HierarchyNode:
    def __init__(self, instance, definition, hierarchy, level, supply_terminal,
                 parent_supply_net, children=None, supply_mappings=None):
        # type: (Instance, SubcktDefinition, str, int, str, str, Optional[List[HierarchyNode]], Optional[List[Tuple[str, str]]]) -> None
        self.instance = instance
        self.definition = definition
        self.hierarchy = hierarchy
        self.level = level
        self.supply_terminal = supply_terminal
        self.parent_supply_net = parent_supply_net
        self.supply_mappings = (supply_mappings if supply_mappings is not None
                                else [(supply_terminal, parent_supply_net)])
        self.children = children if children is not None else []


class SupplyTraceError(ValueError):
    pass


class SupplyTracer:
    def __init__(self, netlist, debug=False):
        # type: (Netlist, bool) -> None
        self.netlist = netlist
        self.debug = debug
        self.warnings = []  # type: List[str]

    def trace(self, root_name: str, supply_net: str, max_level: int) -> HierarchyNode:
        root = next((item for item in self.netlist.top_instances if item.name == root_name), None)
        if root is None:
            raise SupplyTraceError(f"root instance {root_name} not found")
        definition = self.netlist.subckts.get(root.cell)
        if definition is None:
            raise SupplyTraceError(f"root instance {root_name} is not a parsed sub-circuit ({root.cell})")
        mappings = self._mapped_terminals(root, definition, [supply_net])
        # At the root boundary users commonly know the subckt supply terminal
        # (for example VDDI2), while its top-level actual net has an unrelated
        # generated name.  An exact formal-terminal match is deterministic and
        # is therefore safe; descendants still use connectivity only.
        if not mappings and definition.terminals.count(supply_net) == 1:
            mappings = [(supply_net, supply_net)]
            if self.debug:
                print("DEBUG: root supply {0} matched formal terminal; top-level actual net is {1}"
                      .format(supply_net, self._actual_for_terminal(root, definition, supply_net)),
                      file=sys.stderr)
        if not mappings:
            raise SupplyTraceError(
                "root instance {0}: cannot determine terminal connected to supply net {1}\n"
                "root cell: {2}\n"
                "available terminal mapping: {3}\n"
                "Hint: --net accepts either the top-level actual net or the root subckt formal terminal."
                .format(root_name, supply_net, definition.name,
                        self._format_terminal_mapping(root, definition)))
        if self.debug:
            print("DEBUG: resolved root supply terminals: {0}".format(
                ", ".join("{0}<-{1}".format(terminal, actual)
                          for terminal, actual in mappings)), file=sys.stderr)
        node = HierarchyNode(root, definition, root.name, 1, mappings[0][0],
                             mappings[0][1], supply_mappings=mappings)
        self._descend(node, [item[0] for item in mappings], max_level)
        deepest = max(item.level for item in flatten(node))
        if deepest < max_level:
            raise SupplyTraceError(f"No sub-circuit found up to hierarchy level {max_level}")
        return node

    def _descend(self, parent, local_supplies, max_level):
        # type: (HierarchyNode, List[str], int) -> None
        if parent.level >= max_level:
            return
        for instance in parent.definition.instances:
            child_def = self.netlist.subckts.get(instance.cell)
            if child_def is None:  # transistor/model primitive
                continue
            hierarchy = f"{parent.hierarchy}.{instance.name}"
            mappings = self._mapped_terminals(instance, child_def, local_supplies)
            if not mappings:
                if any(self._uses_net(child_def, supply) for supply in local_supplies):
                    warning = (f"{hierarchy} uses global supply.\n"
                               "Sub-circuit terminal current cannot be measured using terminal current.")
                else:
                    warning = f"{hierarchy}:\ncannot determine terminal connected to supply net"
                self.warnings.append(warning)
                print(f"WARNING:\n{warning}", file=sys.stderr)
                continue
            child = HierarchyNode(instance, child_def, hierarchy, parent.level + 1,
                                  mappings[0][0], mappings[0][1], supply_mappings=mappings)
            parent.children.append(child)
            self._descend(child, [item[0] for item in mappings], max_level)

    @staticmethod
    def _mapped_terminal(instance, definition, net):
        # type: (Instance, SubcktDefinition, str) -> Optional[str]
        matches = [definition.terminals[i] for i, node in enumerate(instance.connections)
                   if node == net and i < len(definition.terminals)]
        return matches[0] if len(matches) == 1 else None

    @staticmethod
    def _mapped_terminals(instance, definition, nets):
        # type: (Instance, SubcktDefinition, List[str]) -> List[Tuple[str, str]]
        matches = []
        for index, actual in enumerate(instance.connections):
            if actual in nets and index < len(definition.terminals):
                matches.append((definition.terminals[index], actual))
        return matches

    @staticmethod
    def _actual_for_terminal(instance, definition, terminal):
        # type: (Instance, SubcktDefinition, str) -> Optional[str]
        index = definition.terminals.index(terminal)
        return instance.connections[index] if index < len(instance.connections) else None

    @staticmethod
    def _format_terminal_mapping(instance, definition):
        # type: (Instance, SubcktDefinition) -> str
        mappings = []
        for index, terminal in enumerate(definition.terminals):
            actual = instance.connections[index] if index < len(instance.connections) else "<missing>"
            mappings.append("{0}={1}".format(terminal, actual))
        if len(instance.connections) > len(definition.terminals):
            mappings.append("<extra actual nodes: {0}>".format(
                " ".join(instance.connections[len(definition.terminals):])))
        return ", ".join(mappings) if mappings else "<no terminals parsed>"

    @staticmethod
    def _uses_net(definition: SubcktDefinition, net: str) -> bool:
        return any(net in instance.connections for instance in definition.instances)


def flatten(root):
    # type: (HierarchyNode) -> List[HierarchyNode]
    return [root] + [descendant for child in root.children for descendant in flatten(child)]
