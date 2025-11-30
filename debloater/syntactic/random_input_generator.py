import hashlib
import math
import random
import logging
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

class RandomInputGenerator:
    def __init__(self, seed: int | None = None, max_array_length: int = 30):
        self._rng = random.Random(seed if seed is not None else random.getrandbits(64))
        self._max_array_length = max_array_length

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

    def _fuzz_values_for_type(self, jvm_type: Type, count: int) -> list[str]:
        # booleans
        if isinstance(jvm_type, Boolean):
            samples = [True, False]
            return [str(self._rng.choice(samples)) for _ in range(count)]

        # integers
        if isinstance(jvm_type, Int):
            lower, upper = -2_147_483_648, 2_147_483_647
            return [str(self._rng.randint(lower, upper)) for _ in range(count)]

        if isinstance(jvm_type, Byte):
            lower, upper = -128, 127
            return [str(self._rng.randint(lower, upper)) for _ in range(count)]

        if isinstance(jvm_type, Short):
            lower, upper = -32_768, 32_767
            return [str(self._rng.randint(lower, upper)) for _ in range(count)]

        if isinstance(jvm_type, Long):
            lower, upper = -9_223_372_036_854_775_808, 9_223_372_036_854_775_807
            return [str(self._rng.randint(lower, upper)) for _ in range(count)]

        # floats
        if isinstance(jvm_type, JVMFloat):
            return [self._format_float(self._rng.uniform(-1e6, 1e6)) for _ in range(count)]

        if isinstance(jvm_type, Double):
            return [self._format_float(self._rng.uniform(-1e12, 1e12)) for _ in range(count)]

        # chars
        if isinstance(jvm_type, Char):
            alphabet = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789" "!@#$%^&*()_+-=[]{};:'\",.<>/?"
            return [self._format_char(self._rng.choice(alphabet)) for _ in range(count)]

        # arrays
        if isinstance(jvm_type, Array):
            inner = jvm_type.contains
            results: list[str] = []
            for _ in range(count):
                length = self._rng.randint(0, self._max_array_length)
                if length == 0:
                    results.append("[]")
                else:
                    elems = self._fuzz_values_for_type(inner, length)
                    results.append("[" + ", ".join(elems) + "]")
            return results

        # object/reference -> null
        if isinstance(jvm_type, Object) or isinstance(jvm_type, Reference):
            return ["null" for _ in range(count)]

        return [f"<unsupported {jvm_type.encode()}>" for _ in range(count)]

    def generate(self, jvm_types: list[Type], count: int) -> list[list[str]]:
        return [self._fuzz_values_for_type(t, count) for t in jvm_types]
