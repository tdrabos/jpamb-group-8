import math
from typing import Dict, List, Tuple

import jpamb
from jpamb.jvm.base import Type

from debloater.syntactic.random_input_generator import RandomInputGenerator
from debloater.syntactic.z3_input_generator import Z3InputGenerator


class CombinedInputGenerator:

    def __init__(
        self,
        initial_distribution: Dict[str, float] | None = None,
        random_seed: int | None = None,
        max_array_length: int = 30,
    ) -> None:
        self.initial_distribution = initial_distribution or {"random": 0.5, "z3": 0.5}
        self.random_gen = RandomInputGenerator(seed=random_seed, max_array_length=max_array_length)

    def _generate_random_tuples(self, param_types: List[Type], count: int) -> List[Tuple[str, ...]]:
        if count <= 0:
            return []
        per_param_values = self.random_gen.generate(param_types, count)
        tuples: List[Tuple[str, ...]] = []
        for i in range(count):
            tup = tuple(per_param_values[p][i] for p in range(len(param_types)))
            tuples.append(tup)
        return tuples

    def _generate_z3_tuples(self, method_id, count: int) -> List[Tuple[object, ...]]:
        if count <= 0:
            return []
        z3_gen = Z3InputGenerator(method_id, num_solutions=count)
        result = z3_gen.analyze() or {}
        inputs = result.get("inputs", [])
        # Ensure tuple type
        return [tuple(t) for t in inputs][:count]

    def generate_inputs(self, methods: List[str], expected_count: int) -> Dict[str, List[Tuple]]:
        out: Dict[str, List[Tuple]] = {}
        rand_share = float(self.initial_distribution.get("random", 0.0) or 0.0)
        z3_share = float(self.initial_distribution.get("z3", 0.0) or 0.0)

        for mid_str in methods:
            method_id = jpamb.parse_methodid(mid_str)
            param_types: List[Type] = list(method_id.extension.params)

            # Split desired counts
            z3_count = int(math.ceil(expected_count * z3_share))
            rand_count = int(math.ceil(expected_count * rand_share))

            # Generate Z3-guided inputs
            z3_tuples = self._generate_z3_tuples(method_id, z3_count)

            # Generate random inputs
            rand_tuples = self._generate_random_tuples(param_types, rand_count)

            combined: List[Tuple] = []
            # Prefer Z3 tuples first, then random
            combined.extend(z3_tuples)
            combined.extend(rand_tuples)

            # If still short, top up with random
            shortfall = max(0, expected_count - len(combined))
            if shortfall > 0:
                combined.extend(self._generate_random_tuples(param_types, shortfall))

            # Trim to expected_count
            out[mid_str] = combined[:expected_count]

        return out
    

def generate_inputs(methods: List[str], expected_count: int) -> Dict[str, List[Tuple]]:
    generator = CombinedInputGenerator()
    return generator.generate_inputs(methods, expected_count)

# called = [
#             "jpamb.cases.Bloated.unreachableBranchBasic:(I)I",
#             "jpamb.cases.Bloated.localInitButNotUsed:()I",
#             "jpamb.cases.Bloated.unreachableBranchFor:(I)I",
#             "jpamb.cases.Bloated.unreachableBranchWhile:(I)I"]

# result = generate_inputs(called, 10)
# print(result)