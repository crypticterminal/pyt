import ast

from .base_cfg import AssignmentNode, EntryOrExitNode
from .analysis_base import AnalysisBase
from .lattice import Lattice
from .constraint_table import constraint_table, constraint_join
from .ast_helper import get_call_names_as_string
from .vars_visitor import VarsVisitor


class LivenessAnalysis(AnalysisBase):
    """Reaching definitions analysis rules implemented."""

    def __init__(self, cfg):
        super().__init__(cfg, None)

    def join(self, cfg_node):
        """Joins all constraints of the ingoing nodes and returns them.
        This represents the JOIN auxiliary definition from Schwartzbach."""
        return constraint_join(cfg_node.outgoing)

    def is_output(self, cfg_node):
        if isinstance(cfg_node.ast_node, ast.Call):
            call_name = get_call_names_as_string(cfg_node.ast_node.func)
            if 'print' in call_name:
                return True
        return False

    def is_condition(self, cfg_node):
        if isinstance(cfg_node.ast_node, ast.While):
            return True
        elif self.is_output(cfg_node):
            return True
        elif isinstance(cfg_node.ast_node, ast.If):
            return True
        return False

    def remove_id_assignment(self, JOIN, cfg_node):
        lvars = list()
        try:
            for expr in cfg_node.ast_node.targets:
                vv = VarsVisitor()
                vv.visit(expr)
                lvars.extend(vv.result)
        except AttributeError:  # If it is AugAssign
            vv = VarsVisitor()
            vv.visit(cfg_node.ast_node.target)
            lvars.extend(vv.result)

        for var in lvars:
            if var in self.lattice.get_elements(JOIN):  # Check if var in JOIN
                JOIN = JOIN ^ self.lattice.el2bv[var]
        return JOIN

    def add_vars_assignment(self, JOIN, cfg_node):
        rvars = list()
        vv = VarsVisitor()
        vv.visit(cfg_node.ast_node.value)
        rvars.extend(vv.result)

        for var in rvars:
            JOIN = JOIN | self.lattice.el2bv[var]
        return JOIN

    def add_vars_conditional(self, JOIN, cfg_node):
        varse = None
        if isinstance(cfg_node.ast_node, ast.While):
            vv = VarsVisitor()
            vv.visit(cfg_node.ast_node.test)
            varse = vv.result
        elif self.is_output(cfg_node):
            vv = VarsVisitor()
            vv.visit(cfg_node.ast_node)
            varse = vv.result
        elif isinstance(cfg_node.ast_node, ast.If):
            vv = VarsVisitor()
            vv.visit(cfg_node.ast_node.test)
            varse = vv.result

        for var in varse:
            JOIN = JOIN | self.lattice.el2bv[var]

        return JOIN

    def fixpointmethod(self, cfg_node):

        if isinstance(cfg_node, EntryOrExitNode) and 'Exit' in cfg_node.label:
            constraint_table[cfg_node] = 0
        elif isinstance(cfg_node, AssignmentNode):
            JOIN = self.join(cfg_node)
            JOIN = self.remove_id_assignment(JOIN, cfg_node)
            JOIN = self.add_vars_assignment(JOIN, cfg_node)
            constraint_table[cfg_node] = JOIN
        elif self.is_condition(cfg_node):
            JOIN = self.join(cfg_node)
            JOIN = self.add_vars_conditional(JOIN, cfg_node)
            constraint_table[cfg_node] = JOIN
        else:
            constraint_table[cfg_node] = self.join(cfg_node)

    def dep(self, q_1):
        """Represents the dep mapping from Schwartzbach."""
        for node in q_1.outgoing:
            yield node

    def get_lattice_elements(cfg_nodes):
        """Returns all assignment nodes as they are the only lattice elements
        in the reaching definitions analysis.
        This is a static method which is overwritten from the base class.
        """
        lattice_elements = set()  # set() to avoid duplicates
        for node in (node for node in cfg_nodes if node.ast_node):
            vv = VarsVisitor()
            vv.visit(node.ast_node)
            for var in vv.result:
                lattice_elements.add(var)
        return lattice_elements

    def equal(self, value, other):
        return value == other

    def build_lattice(self, cfg):
        self.lattice = Lattice(cfg.nodes, LivenessAnalysis)
