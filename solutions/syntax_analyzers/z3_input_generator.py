import z3
from pathlib import Path
from tree_sitter import QueryCursor
import logging
from .base import BaseSyntaxer, QueryRegistry
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
    def __init__(self, method_id: jpamb.jvm.base.AbsMethodID, num_solutions=3):
        super().__init__(method_id)
        self._vars: dict[str, z3.ExprRef] = {}
        self.num_solutions = num_solutions

    def _get_z3_var(self, name: str, jvm_type: Type) -> z3.ExprRef | None:
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

    def _node_to_z3(self, node, var_states: dict[str, z3.ExprRef]) -> z3.ExprRef | None:
        if node.type == 'binary_expression':
            left = self._node_to_z3(node.child_by_field_name('left'), var_states)
            right = self._node_to_z3(node.child_by_field_name('right'), var_states)
            op = node.child_by_field_name('operator').text.decode()
            if left is None or right is None:
                return None
            
            op_map = {
                '>': lambda l, r: l > r, '<': lambda l, r: l < r,
                '>=': lambda l, r: l >= r, '<=': lambda l, r: l <= r,
                '==': lambda l, r: l == r, '!=': lambda l, r: l != r,
                '&&': z3.And, '||': z3.Or,
                '+': lambda l, r: l + r, '-': lambda l, r: l - r,
                '*': lambda l, r: l * r, '/': lambda l, r: l / r,
                '%': lambda l, r: l % r,
            }
            if op in op_map:
                return op_map[op](left, right)

        elif node.type == 'unary_expression':
            operand = self._node_to_z3(node.child_by_field_name('operand'), var_states)
            op = node.child_by_field_name('operator').text.decode()
            if operand is None: return None
            if op == '!': return z3.Not(operand)
            if op == '-': return -operand
        
        elif node.type == 'parenthesized_expression':
            return self._node_to_z3(node.children[1], var_states)

        elif node.type == 'identifier':
            name = node.text.decode()
            return var_states.get(name)

        elif node.type in ('decimal_integer_literal', 'integer_literal'):
            return z3.IntVal(int(node.text.decode()))
        elif node.type == 'character_literal':
            char_content = node.text.decode().strip("'")
            print(f"Character literal content: {char_content}")
            if len(char_content) == 1:
                return z3.IntVal(ord(char_content))
            else:
                return None
        elif node.type in ('decimal_floating_point_literal', 'hex_floating_point_literal'):
            return z3.RealVal(float(node.text.decode()))
        elif node.type == 'true':
            return z3.BoolVal(True)
        elif node.type == 'false':
            return z3.BoolVal(False)

        return None

    def _traverse_and_solve(self, node, var_states: dict[str, z3.ExprRef], input_tuples: set, param_names: list[str], char_param_names: list[str]):
        if node.type == 'if_statement':
            cond_node = node.child_by_field_name('condition')
            z3_expr = self._node_to_z3(cond_node, var_states)

            if z3_expr is not None:
                for condition in [True, False]:
                    s = z3.Solver()
                    s.add(z3_expr if condition else z3.Not(z3_expr))
                    
                    for _ in range(self.num_solutions):
                        if s.check() == z3.sat:
                            m = s.model()
                            input_tuple = []
                            block = []
                            for p_name in param_names:
                                var = self._vars[p_name]
                                interp = m.get_interp(var)
                                val = 0
                                z3_val = None
                                if interp is not None:
                                    if p_name in char_param_names and z3.is_int_value(interp):
                                        num = interp.as_long()
                                        val = chr(num)
                                        z3_val = z3.IntVal(num)
                                    elif z3.is_int_value(interp):
                                        num = interp.as_long()
                                        val = num
                                        z3_val = z3.IntVal(num)
                                    elif z3.is_true(interp) or z3.is_false(interp):
                                        val = z3.is_true(interp)
                                        z3_val = z3.BoolVal(val)
                                    else:
                                        eval_val = m.eval(var, model_completion=True)
                                        if z3.is_int_value(eval_val):
                                            num = eval_val.as_long()
                                            if p_name in char_param_names:
                                                val = chr(num)
                                                z3_val = z3.IntVal(num)
                                            else:
                                                val = num
                                                z3_val = z3.IntVal(num)
                                        elif z3.is_rational_value(eval_val):
                                            val = float(eval_val.as_fraction())
                                            z3_val = z3.RealVal(val)
                                        else:
                                            val = 0
                                            z3_val = z3.IntVal(val)
                                else:
                                    val = 0
                                    z3_val = z3.IntVal(val)

                                input_tuple.append(val)
                                if z3_val is not None:
                                    block.append(var != z3_val)
                            
                            input_tuples.add(tuple(input_tuple))
                            s.add(z3.Or(block))
                        else:
                            break

            consequence = node.child_by_field_name('consequence')
            if consequence:
                self._traverse_and_solve(consequence, var_states.copy(), input_tuples, param_names, char_param_names)
            
            alternative = node.child_by_field_name('alternative')
            if alternative:
                self._traverse_and_solve(alternative, var_states.copy(), input_tuples, param_names, char_param_names)
            return

        elif node.type == 'expression_statement':
            expr_node = node.children[0]
            if expr_node.type == 'assignment_expression':
                name_node = expr_node.child_by_field_name('left')
                if name_node.type == 'identifier':
                    name = name_node.text.decode()
                    if name in var_states:
                        right_node = expr_node.child_by_field_name('right')
                        new_val = self._node_to_z3(right_node, var_states)
                        if new_val is not None:
                            op = expr_node.child_by_field_name('operator').text.decode()
                            if op == '=': var_states[name] = new_val
                            elif op == '+=': var_states[name] += new_val
                            elif op == '-=': var_states[name] -= new_val
                            elif op == '*=': var_states[name] *= new_val
                            elif op == '/=': var_states[name] /= new_val
            elif expr_node.type == 'update_expression':
                name_node = expr_node.child_by_field_name('argument')
                if name_node.type == 'identifier':
                    name = name_node.text.decode()
                    if name in var_states:
                        op = expr_node.child_by_field_name('operator').text.decode()
                        if op == '++': var_states[name] += 1
                        elif op == '--': var_states[name] -= 1
        
        for child in node.children:
            self._traverse_and_solve(child, var_states, input_tuples, param_names, char_param_names)

    def analyze(self):
        if not self.input_check():
            return {}

        srcfile = jpamb.sourcefile(self.method_id).relative_to(Path.cwd())
        with open(srcfile, "rb") as f:
            tree = self.parser.parse(f.read())

        simple_classname = str(self.method_id.classname.name)
        class_nodes = QueryCursor(QueryRegistry.class_query(simple_classname)).captures(tree.root_node).get("class", [])
        if not class_nodes:
            log.error(f"could not find a class of name {simple_classname} in {srcfile}")
            return {}

        method_name = self.method_id.extension.name
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
            return {}

        params_node = target_method_node.child_by_field_name("parameters")
        param_nodes = [c for c in params_node.children if c.type in {"formal_parameter", "spread_parameter"}]
        
        parameters_info = []
        param_names = []
        char_param_names = []
        var_states: dict[str, z3.ExprRef] = {}
        for declared, expected in zip(param_nodes, self.method_id.extension.params):
            name_node = declared.child_by_field_name("name")
            name = name_node.text.decode()
            type_node = declared.child_by_field_name("type")
            type_text = type_node.text.decode()

            param_names.append(name)
            if isinstance(expected, Char):
                char_param_names.append(name)
            parameters_info.append({
                "name": name,
                "declared_type": type_text,
                "jvm_type": expected.encode(),
            })
            
            z3_var = self._get_z3_var(name, expected)
            if z3_var is not None:
                var_states[name] = z3_var

        body_node = target_method_node.child_by_field_name("body")
        
        input_tuples = set()

        if body_node:
            self._traverse_and_solve(body_node, var_states, input_tuples, param_names, char_param_names)

        return {"parameters": parameters_info, "tuples": [tuple(map(str, t)) for t in input_tuples]}
