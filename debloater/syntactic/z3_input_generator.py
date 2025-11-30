import z3
from pathlib import Path
from tree_sitter import QueryCursor
import logging
from syntaxer_base import BaseSyntaxer, QueryRegistry
import jpamb
from jpamb.jvm.base import (
    Boolean,
    Byte,
    Char,
    Double,
    Float as JVMFloat,
    Int,
    Long,
    Short,
    Type,
)

log = logging
log.basicConfig(level=logging.DEBUG)

class Z3InputGenerator(BaseSyntaxer):
    OP_MAP = {
        '>': lambda l, r: l > r, '<': lambda l, r: l < r,
        '>=': lambda l, r: l >= r, '<=': lambda l, r: l <= r,
        '==': lambda l, r: l == r, '!=': lambda l, r: l != r,
        '&&': z3.And, '||': z3.Or,
        '+': lambda l, r: l + r, '-': lambda l, r: l - r,
        '*': lambda l, r: l * r, '/': lambda l, r: l / r,
        '%': lambda l, r: l % r,
    }
    TYPE_SORT_MAP = {
        'I': z3.Int, 'B': z3.Int, 'S': z3.Int, 'C': z3.Int, 'J': z3.Int,
        'F': z3.Real, 'D': z3.Real,
        'Z': z3.Bool,
    }

    class Constraints:
        def __init__(self, owner: 'Z3InputGenerator'):
            self.o = owner
        def add_char_ranges(self, s: z3.Solver, char_param_names: list[str]):
            for p_name in char_param_names:
                s.add(self.o._vars[p_name] >= 0, self.o._vars[p_name] <= 255)
        def add_array_bounds(self, s: z3.Solver, array_params: list[str]):
            self.o._add_array_bounds_constraints(s, array_params)

    def __init__(self, method_id: jpamb.jvm.base.AbsMethodID, num_solutions=3):
        super().__init__(method_id)
        self._vars: dict[str, z3.ExprRef] = {}
        self.num_solutions = num_solutions
        self._param_jvm_types: dict[str, str] = {}

    def get_z3_var(self, name: str, jvm_type: Type) -> z3.ExprRef | None:
        if name in self._vars:
            return self._vars[name]

        if isinstance(jvm_type, Int) or isinstance(jvm_type, Byte) or isinstance(jvm_type, Short) or isinstance(jvm_type, Char):
            var = z3.Int(name)
        elif isinstance(jvm_type, Long):
            var = z3.Int(name)
        elif isinstance(jvm_type, JVMFloat) or isinstance(jvm_type, Double):
            var = z3.Real(name)
        elif isinstance(jvm_type, Boolean):
            var = z3.Bool(name)
        else:
            return None
        
        self._vars[name] = var
        return var

    def get_or_create_int(self, name: str) -> z3.ExprRef:
        if name in self._vars:
            return self._vars[name]
        var = z3.Int(name)
        self._vars[name] = var
        return var

    def get_or_create_array_elem(self, arr_name: str, idx: int) -> z3.ExprRef | None:
        key = f"{arr_name}_{idx}"
        if key in self._vars:
            return self._vars[key]
        jvm_sig = self._param_jvm_types.get(arr_name, '')
        elem_sort = None
        if jvm_sig.startswith('['):
            code = jvm_sig[1:]
            elem_sort = self.TYPE_SORT_MAP.get(code)
        if elem_sort is None:
            return None
        var = elem_sort(key)
        self._vars[key] = var
        return var

    def handle_binary(self, node, var_states):
        left = self.node_to_z3(node.child_by_field_name('left'), var_states)
        right = self.node_to_z3(node.child_by_field_name('right'), var_states)
        op = node.child_by_field_name('operator').text.decode()
        if left is None or right is None:
            return None
        if op in self.OP_MAP:
            return self.OP_MAP[op](left, right)
        return None

    def handle_unary(self, node, var_states):
        operand = self.node_to_z3(node.child_by_field_name('operand'), var_states)
        op = node.child_by_field_name('operator').text.decode()
        if operand is None:
            return None
        if op == '!':
            return z3.Not(operand)
        if op == '-':
            return -operand
        return None

    def handle_parenthes(self, node, var_states):
        return self.node_to_z3(node.children[1], var_states)

    def handle_field_access(self, node, var_states):
        recv = node.child_by_field_name('object') or node.child_by_field_name('receiver')
        field = node.child_by_field_name('field')
        if recv and field and field.type == 'identifier' and field.text.decode() == 'length':
            if recv.type == 'identifier':
                arr_name = recv.text.decode()
                return self._get_or_create_int(f"{arr_name}_length")
        return None

    def handle_array_access(self, node, var_states):
        arr = node.child_by_field_name('array')
        idx = node.child_by_field_name('index')
        if arr and arr.type == 'identifier' and idx:
            arr_name = arr.text.decode()
            idx_val = self._node_to_z3(idx, var_states)
            if idx_val is not None and z3.is_int_value(idx_val):
                index_int = idx_val.as_long()
                key = f"{arr_name}_{index_int}"
                # prefer expression from var_states if assignment modified it
                if key in var_states:
                    return var_states[key]
                return self._get_or_create_array_elem(arr_name, index_int)
            if idx.type in ('decimal_integer_literal', 'integer_literal'):
                try:
                    index_int = int(idx.text.decode().replace("_", "").rstrip('Ll'))
                    key = f"{arr_name}_{index_int}"
                    if key in var_states:
                        return var_states[key]
                    return self._get_or_create_array_elem(arr_name, index_int)
                except Exception:
                    return None
        return None

    def handle_identifier(self, node, var_states):
        name = node.text.decode()
        return var_states.get(name)

    def handle_int_literal(self, node, var_states):
        text = node.text.decode().replace("_", "")
        if text and text[-1] in 'Ll':
            text = text[:-1]
        return z3.IntVal(int(text))

    def handle_char_literal(self, node, var_states):
        char_content = node.text.decode().strip("'")
        if len(char_content) == 1:
            return z3.IntVal(ord(char_content))
        return None

    def handle_float_literal(self, node, var_states):
        text = node.text.decode().replace("_", "")
        if text and text[-1] in 'fFdD':
            text = text[:-1]
        try:
            if text.lower().startswith('0x') or 'p' in text.lower():
                val = float.fromhex(text)
            else:
                val = float(text)
        except ValueError:
            return None
        return z3.RealVal(val)

    def handle_bool_literal(self, node, var_states):
        if node.type == 'true':
            return z3.BoolVal(True)
        if node.type == 'false':
            return z3.BoolVal(False)
        return None

    def node_to_z3(self, node, var_states: dict[str, z3.ExprRef]) -> z3.ExprRef | None:
        if node.type == 'binary_expression':
            return self.handle_binary(node, var_states)
        elif node.type == 'unary_expression':
            return self.handle_unary(node, var_states)
        elif node.type == 'parenthesized_expression':
            return self.handle_parenthes(node, var_states)
        elif node.type == 'field_access':
            return self.handle_field_access(node, var_states)
        elif node.type == 'array_access':
            return self.handle_array_access(node, var_states)
        elif node.type == 'identifier':
            return self.handle_identifier(node, var_states)
        elif node.type in ('decimal_integer_literal', 'integer_literal'):
            return self.handle_int_literal(node, var_states)
        elif node.type == 'character_literal':
            return self.handle_char_literal(node, var_states)
        elif node.type in ('decimal_floating_point_literal', 'hex_floating_point_literal'):
            return self.handle_float_literal(node, var_states)
        elif node.type in ('true', 'false'):
            return self.handle_bool_literal(node, var_states)
        return None

    def _collect_array_indices(self, arr_name: str) -> list[int]:
        prefix = f"{arr_name}_"
        indices: list[int] = []
        for k in self._vars.keys():
            if k.startswith(prefix):
                try:
                    idx = int(k[len(prefix):])
                    indices.append(idx)
                except ValueError:
                    pass
        return sorted(set(indices))

    def _add_array_bounds_constraints(self, s: z3.Solver, array_params: list[str]):
        for arr_name in array_params:
            len_var = self._vars.get(f"{arr_name}_length")
            if len_var is not None:
                s.add(len_var >= 0)
                for idx in self._collect_array_indices(arr_name):
                    s.add(len_var >= idx + 1)

    def serialize_array(self, m: z3.ModelRef, name: str) -> tuple[str, list[tuple[z3.ExprRef, z3.ExprRef]]]:
        elem_vals: list[str] = []
        blockers: list[tuple[z3.ExprRef, z3.ExprRef]] = []
        len_var = self._vars.get(f"{name}_length")
        jvm_sig = self._param_jvm_types.get(name, '')
        is_char_array = jvm_sig.startswith('[') and jvm_sig[1:] == 'C'
        is_bool_array = jvm_sig.startswith('[') and jvm_sig[1:] == 'Z'
       
        if len_var is not None:
            len_ev = m.eval(len_var, model_completion=True)
            if z3.is_int_value(len_ev):
                arr_len = max(len_ev.as_long(), 0)
                blockers.append((len_var, z3.IntVal(arr_len)))
                for idx in range(arr_len):
                    elem_var = self._vars.get(f"{name}_{idx}")
                    if elem_var is not None:
                        ev = m.eval(elem_var, model_completion=True)
                        if z3.is_int_value(ev):
                            if is_char_array:
                                num = ev.as_long()
                                elem_vals.append(chr(num) if 0 <= num <= 255 else str(num))
                                blockers.append((elem_var, z3.IntVal(num)))
                            else:
                                num = ev.as_long()
                                elem_vals.append(str(num))
                                blockers.append((elem_var, z3.IntVal(num)))
                        elif z3.is_rational_value(ev):
                            val = float(ev.as_fraction())
                            elem_vals.append(str(val))
                            blockers.append((elem_var, z3.RealVal(val)))
                        elif z3.is_true(ev) or z3.is_false(ev):
                            b = z3.is_true(ev)
                            elem_vals.append('true' if b else 'false')
                            blockers.append((elem_var, z3.BoolVal(b)))
                        else:
                            elem_vals.append("0")
                    else:
                        elem_vals.append("0")
       
        if not elem_vals:
            for idx in self._collect_array_indices(name):
                elem_var = self._vars[f"{name}_{idx}"]
                ev = m.eval(elem_var, model_completion=True)
                if z3.is_int_value(ev):
                    if is_char_array:
                        num = ev.as_long()
                        elem_vals.append(chr(num) if 0 <= num <= 255 else str(num))
                        blockers.append((elem_var, z3.IntVal(num)))
                    else:
                        num = ev.as_long()
                        elem_vals.append(str(num))
                        blockers.append((elem_var, z3.IntVal(num)))
                elif z3.is_rational_value(ev):
                    val = float(ev.as_fraction())
                    elem_vals.append(str(val))
                    blockers.append((elem_var, z3.RealVal(val)))
                elif z3.is_true(ev) or z3.is_false(ev):
                    b = z3.is_true(ev)
                    elem_vals.append('true' if b else 'false')
                    blockers.append((elem_var, z3.BoolVal(b)))
                else:
                    elem_vals.append("0")
        return f"[{', '.join(elem_vals)}]", blockers

    def serialize_param(self, m: z3.ModelRef, p_name: str, char_param_names: list[str]) -> tuple[object, z3.ExprRef | None, list[tuple[z3.ExprRef, z3.ExprRef]]]:
        var = self._vars.get(p_name)
        if var is None:
            # array parameter
            arr_str, arr_blockers = self.serialize_array(m, p_name)
            return arr_str, None, arr_blockers
        eval_val = m.eval(var, model_completion=True)
        if z3.is_int_value(eval_val):
            num = eval_val.as_long()
            if p_name in char_param_names:
                return chr(num), z3.IntVal(num), []
            else:
                return num, z3.IntVal(num), []
        elif z3.is_rational_value(eval_val):
            val = float(eval_val.as_fraction())
            return val, z3.RealVal(val), []
        elif z3.is_true(eval_val) or z3.is_false(eval_val):
            val = z3.is_true(eval_val)
            return val, z3.BoolVal(val), []
        return 0, z3.IntVal(0), []

    def _handle_assignment(self, expr_node, var_states: dict[str, z3.ExprRef], path_constraints: list[z3.ExprRef]):
        name_node = expr_node.child_by_field_name('left')
        right_node = expr_node.child_by_field_name('right')
        op = expr_node.child_by_field_name('operator').text.decode()
        # identifier assignment
        if name_node.type == 'identifier':
            name = name_node.text.decode()
            if name in var_states:
                rhs = self.node_to_z3(right_node, var_states)
                if rhs is None: return
                if op == '=':
                    path_constraints.append(var_states[name] == rhs)
                    var_states[name] = rhs
                elif op == '+=':
                    var_states[name] = var_states[name] + rhs
                elif op == '-=':
                    var_states[name] = var_states[name] - rhs
                elif op == '*=':
                    var_states[name] = var_states[name] * rhs
                elif op == '/=':
                    var_states[name] = var_states[name] / rhs
        # array element assignment
        elif name_node.type == 'array_access':
            arr_node = name_node.child_by_field_name('array')
            idx_node = name_node.child_by_field_name('index')
            if not (arr_node and arr_node.type == 'identifier' and idx_node):
                return
            arr_name = arr_node.text.decode()
            idx_z3 = self.node_to_z3(idx_node, var_states)
            index_int = None
            if idx_z3 is not None and z3.is_int_value(idx_z3):
                index_int = idx_z3.as_long()
            elif idx_node.type in ('decimal_integer_literal', 'integer_literal'):
                try:
                    index_int = int(idx_node.text.decode().replace("_", "").rstrip('Ll'))
                except Exception:
                    index_int = None
            if index_int is None:
                return
            elem_var = self._get_or_create_array_elem(arr_name, index_int)
            if elem_var is None:
                return
            key = f"{arr_name}_{index_int}"
            var_states[key] = elem_var
            rhs = self.node_to_z3(right_node, var_states)
            if rhs is None: return
            if op == '=':
                path_constraints.append(elem_var == rhs)
                var_states[key] = rhs
            elif op == '+=':
                var_states[key] = elem_var + rhs
            elif op == '-=':
                var_states[key] = elem_var - rhs
            elif op == '*=':
                var_states[key] = elem_var * rhs
            elif op == '/=':
                var_states[key] = elem_var / rhs

    def _handle_update(self, expr_node, var_states: dict[str, z3.ExprRef], path_constraints: list[z3.ExprRef]):
        name_node = expr_node.child_by_field_name('argument')
        op_node = expr_node.child_by_field_name('operator')
        if op_node is None or op_node.text is None:
            return
        op = op_node.text.decode()
        if name_node.type == 'identifier':
            name = name_node.text.decode()
            if name in var_states:
                if op == '++':
                    var_states[name] = var_states[name] + 1
                elif op == '--':
                    var_states[name] = var_states[name] - 1
        elif name_node.type == 'array_access':
            arr_node = name_node.child_by_field_name('array')
            idx_node = name_node.child_by_field_name('index')
            if not (arr_node and arr_node.type == 'identifier' and idx_node):
                return
            arr_name = arr_node.text.decode()
            idx_z3 = self.node_to_z3(idx_node, var_states)
            index_int = None
            if idx_z3 is not None and z3.is_int_value(idx_z3):
                index_int = idx_z3.as_long()
            elif idx_node.type in ('decimal_integer_literal', 'integer_literal'):
                try:
                    index_int = int(idx_node.text.decode().replace("_", "").rstrip('Ll'))
                except Exception:
                    index_int = None
            if index_int is None:
                return
            elem_var = self._get_or_create_array_elem(arr_name, index_int)
            if elem_var is None:
                return
            key = f"{arr_name}_{index_int}"
            var_states[key] = elem_var
            if op == '++':
                var_states[key] = elem_var + 1
            elif op == '--':
                var_states[key] = elem_var - 1

    def _solve_branch(self, z3_expr: z3.ExprRef, condition: bool, path_constraints: list[z3.ExprRef],
                      param_names: list[str], char_param_names: list[str], input_tuples: set):
        s = z3.Solver()
        for pc in path_constraints:
            s.add(pc)
        s.add(z3_expr if condition else z3.Not(z3_expr))
        constraints = self.Constraints(self)
        constraints.add_char_ranges(s, char_param_names)
        array_params = [p for p in param_names if self._vars.get(p) is None]
        constraints.add_array_bounds(s, array_params)
        
        for _ in range(self.num_solutions):
            if s.check() != z3.sat:
                break
            m = s.model()
            input_tuple = []
            block = []
            for p_name in param_names:
                val, z3_val, extra_blockers = self.serialize_param(m, p_name, char_param_names)
                input_tuple.append(val)
                var = self._vars.get(p_name)
                if var is not None and z3_val is not None:
                    block.append(var != z3_val)
                for bvar, bval in extra_blockers:
                    block.append(bvar != bval)
            input_tuples.add(tuple(input_tuple))
            if block:
                s.add(z3.Or(block))

    def traverse_and_solve(self, node, var_states: dict[str, z3.ExprRef], input_tuples: set,
                             param_names: list[str], char_param_names: list[str],
                             path_constraints: list[z3.ExprRef] | None = None):
        if path_constraints is None:
            path_constraints = []
        if node.type == 'if_statement':
            cond_node = node.child_by_field_name('condition')
            z3_expr = self.node_to_z3(cond_node, var_states)
            if z3_expr is not None:
                for condition in [True, False]:
                    self._solve_branch(z3_expr, condition, path_constraints, param_names, char_param_names, input_tuples)
            consequence = node.child_by_field_name('consequence')
            if consequence:
                self.traverse_and_solve(consequence, var_states.copy(), input_tuples,
                                         param_names, char_param_names,
                                         path_constraints + ([z3_expr] if z3_expr is not None else []))
            alternative = node.child_by_field_name('alternative')
            if alternative:
                self.traverse_and_solve(alternative, var_states.copy(), input_tuples,
                                         param_names, char_param_names,
                                         path_constraints + ([z3.Not(z3_expr)] if z3_expr is not None else []))
            return
        elif node.type == 'expression_statement':
            expr_node = node.children[0]
            if expr_node.type == 'assignment_expression':
                self._handle_assignment(expr_node, var_states, path_constraints)
            elif expr_node.type == 'update_expression':
                self._handle_update(expr_node, var_states, path_constraints)
        for child in node.children:
            self.traverse_and_solve(child, var_states, input_tuples, param_names, char_param_names, path_constraints)

    def find_target_method(self, tree, simple_classname: str, method_name: str):
        class_nodes = QueryCursor(QueryRegistry.class_query(simple_classname)).captures(tree.root_node).get("class", [])
        if not class_nodes:
            log.error(f"could not find a class of name {simple_classname}")
            return None
        target_method_node = None
        for cls in class_nodes:
            for node in QueryCursor(QueryRegistry.method_query(method_name)).captures(cls).get("method", []):
                p = node.child_by_field_name("parameters")
                if not p:
                    continue
                params = [c for c in p.children if c.type == "formal_parameter"]
                if len(params) == len(self.method_id.extension.params):
                    target_method_node = node
                    break
            if target_method_node:
                break
        if not target_method_node:
            log.warning(f"could not find a method of name {method_name} in {simple_classname}")
        return target_method_node

    def extract_parameters(self, target_method_node) -> tuple[list[dict], list[str], list[str], dict[str, z3.ExprRef]]:
        params_node = target_method_node.child_by_field_name("parameters")
        param_nodes = [c for c in params_node.children if c.type in {"formal_parameter", "spread_parameter"}]
        parameters_info: list[dict] = []
        param_names: list[str] = []
        char_param_names: list[str] = []
        var_states: dict[str, z3.ExprRef] = {}
        for declared, expected in zip(param_nodes, self.method_id.extension.params):
            name_node = declared.child_by_field_name("name")
            type_node = declared.child_by_field_name("type")
            name = name_node.text.decode()
            type_text = type_node.text.decode()
            jvm_sig = expected.encode()
            self._param_jvm_types[name] = jvm_sig
            param_names.append(name)
            if isinstance(expected, Char):
                char_param_names.append(name)
            parameters_info.append({
                "name": name,
                "declared_type": type_text,
                "jvm_type": jvm_sig,
            })
            z3_var = self.get_z3_var(name, expected)
            if z3_var is not None:
                var_states[name] = z3_var
        return parameters_info, param_names, char_param_names, var_states

    def analyze(self):
        if not self.input_check():
            return {}
        srcfile = jpamb.sourcefile(self.method_id).relative_to(Path.cwd())
        with open(srcfile, "rb") as f:
            tree = self.parser.parse(f.read())

        simple_classname = str(self.method_id.classname.name)
        method_name = self.method_id.extension.name

        target_method_node = self.find_target_method(tree, simple_classname, method_name)
        if not target_method_node:
            return {}

        # extract parameters and initialize var states
        parameters_info, param_names, char_param_names, var_states = self.extract_parameters(target_method_node)

        body_node = target_method_node.child_by_field_name("body")
        input_tuples = set()
        if body_node:
            self.traverse_and_solve(body_node, var_states, input_tuples, param_names, char_param_names, [])
        return {"parameters": parameters_info, "inputs": [t for t in input_tuples]}
