import hashlib
import math
import random
from pathlib import Path
from tree_sitter import QueryCursor
import logging
from .base import BaseSyntaxer, QueryRegistry
import jpamb
from jpamb.jvm.base import (
    Array,
    Boolean,
    Byte,
    Char,
    Double,
    Float as JVMFloat,
    Int,
    Long,
    Object,
    Reference,
    Short,
    Type,
)

log = logging
log.basicConfig(level=logging.DEBUG)

class RandomInputGenerator(BaseSyntaxer):
    def __init__(self, method_id: jpamb.jvm.base.AbsMethodID, min_sample_number: int = 10):
        super().__init__(method_id)
        encoded = self.method_id.encode().encode("utf-8")
        seed = int.from_bytes(hashlib.sha256(encoded).digest()[:8], "big", signed=False)
        self._rng = random.Random(seed)
        self.min_sample_number = min_sample_number

    def _format_float(self, value: float) -> str:
        if math.isnan(value):
            return "NaN"
        if math.isinf(value):
            return "Infinity" if value > 0 else "-Infinity"
        if value == 0.0:
            return "-0.0" if math.copysign(1.0, value) < 0 else "0.0"
        text = format(value, "g")
        if "e" not in text and "E" not in text and "." not in text:
            text = f"{text}.0"
        return text

    def _format_char(self, char: str) -> str:
        rep = repr(char)
        if rep.startswith('"') and rep.endswith('"'):
            inner = rep[1:-1].replace("'", "\\'")
            return f"'{inner}'"
        return rep

    def _fuzz_values_for_type(self, jvm_type: Type) -> list[str]:
        if isinstance(jvm_type, Boolean):
            samples = [True, False] * (self.min_sample_number // 2)
            self._rng.shuffle(samples)
            return samples

        if isinstance(jvm_type, Int):
            lower, upper = -2_147_483_648, 2_147_483_647
            samples = [lower, upper, 0, -1, 1]
            while len(samples) < self.min_sample_number:
                samples.append(self._rng.randint(lower, upper))
            self._rng.shuffle(samples)
            return [str(v) for v in samples]

        if isinstance(jvm_type, Byte):
            lower, upper = -128, 127
            samples = [lower, upper, 0, -1, 1]
            while len(samples) < self.min_sample_number:
                samples.append(self._rng.randint(lower, upper))
            self._rng.shuffle(samples)
            return [str(v) for v in samples]

        if isinstance(jvm_type, Short):
            lower, upper = -32_768, 32_767
            samples = [lower, upper, 0, -1, 1]
            while len(samples) < self.min_sample_number:
                samples.append(self._rng.randint(lower, upper))
            self._rng.shuffle(samples)
            return [str(v) for v in samples]

        if isinstance(jvm_type, Long):
            lower, upper = -9_223_372_036_854_775_808, 9_223_372_036_854_775_807
            samples = [lower, upper, 0, -1, 1, 42]
            while len(samples) < self.min_sample_number:
                samples.append(self._rng.randint(lower, upper))
            self._rng.shuffle(samples)
            return [str(v) for v in samples]

        if isinstance(jvm_type, JVMFloat):
            base = [-0.0, 0.0, -1.0, 1.0, 3.1415927, -2.7182818]
            samples = base[:]
            while len(samples) < self.min_sample_number:
                samples.append(self._rng.uniform(-1e6, 1e6))
            self._rng.shuffle(samples)
            return [self._format_float(v) for v in samples]

        if isinstance(jvm_type, Double):
            base = [-0.0, 0.0, -1.0, 1.0, 3.1415926535, -2.7182818284]
            samples = base[:]
            while len(samples) < 10:
                samples.append(self._rng.uniform(-1e12, 1e12))
            self._rng.shuffle(samples)
            return [self._format_float(v) for v in samples]

        if isinstance(jvm_type, Char):
            alphabet = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789" "!@#$%^&*()_+-=[]{};:'\",.<>/?"
            samples = [self._rng.choice(alphabet) for _ in range(10)]
            return [self._format_char(c) for c in samples]

        if isinstance(jvm_type, Array):
            inner_samples = self._fuzz_values_for_type(jvm_type.contains)
            results: list[str] = []
            for _ in range(10):
                length = self._rng.randint(0, min(4, len(inner_samples)))
                if length == 0:
                    results.append("[]")
                else:
                    elements = [self._rng.choice(inner_samples) for _ in range(length)]
                    results.append("[" + ", ".join(elements) + "]")
            return results

        if isinstance(jvm_type, Object) or isinstance(jvm_type, Reference):
            return ["null" for _ in range(10)]

        return [f"<unsupported {jvm_type.encode()}>" for _ in range(10)]

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
        target_method = None
        for cls in class_nodes:
            method_nodes = QueryCursor(QueryRegistry.method_query(method_name)).captures(cls).get("method", [])
            for node in method_nodes:
                params_node = node.child_by_field_name("parameters")
                if not params_node:
                    continue
                param_nodes = [c for c in params_node.children if c.type in {"formal_parameter", "spread_parameter"}]
                if len(param_nodes) != len(self.method_id.extension.params):
                    continue
                target_method = node
                break
            if target_method:
                break

        if target_method is None:
            log.warning(f"could not find a method of name {method_name} in {simple_classname}")
            return {}

        params_node = target_method.child_by_field_name("parameters")
        if not params_node:
            return {"parameters": []}

        param_nodes = [c for c in params_node.children if c.type in {"formal_parameter", "spread_parameter"}]
        if not param_nodes:
            return {"parameters": []}

        parameters: list[dict[str, object]] = []
        for declared, expected in zip(param_nodes, self.method_id.extension.params):
            type_node = declared.child_by_field_name("type")
            name_node = declared.child_by_field_name("name")

            if not name_node:
                for child in declared.children:
                    if child.type == "variable_declarator_id":
                        inner = child.child_by_field_name("name")
                        if inner and inner.text:
                            name_node = inner
                            break
                    elif child.type == "identifier" and child.text:
                        name_node = child
                        break

            name_text = name_node.text.decode().strip() if name_node and name_node.text else "<unknown>"
            type_text = type_node.text.decode().strip() if type_node and type_node.text else expected.math()
            if declared.type == "spread_parameter" and not type_text.endswith("..."):
                type_text = f"{type_text}..."

            fuzz_values = self._fuzz_values_for_type(expected)
            parameters.append(
                {
                    "name": name_text,
                    "declared_type": type_text,
                    "jvm_type": expected.encode(),
                    "fuzz_values": fuzz_values,
                }
            )

        value_columns = [param["fuzz_values"] for param in parameters]
        input_tuples: list[tuple[str, ...]] = []
        if value_columns:
            max_len = max(len(col) for col in value_columns) if value_columns else 0
            for i in range(max_len):
                input_tuples.append(tuple(str(col[i % len(col)]) for col in value_columns))

        return {"parameters": parameters, "tuples": input_tuples}
