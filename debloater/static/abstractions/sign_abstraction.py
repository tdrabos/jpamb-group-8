from __future__ import annotations
from dataclasses import dataclass
from typing import Iterable, Literal, Tuple, TypeAlias

Sign: TypeAlias = Literal["+", "-", "0"]

def holds(rel: set[int], opr: str) -> bool:
            if opr == "lt":
                return rel == -1
            if opr == "le":
                return rel in {-1, 0}
            if opr == "gt":
                return rel == 1
            if opr == "ge":
                return rel in {1, 0}
            if opr == "eq":
                return rel == 0
            if opr == "ne":
                return rel in {-1, 1}

@dataclass(frozen=True)
class SignSet:
    """
    A finite abstraction of integer sets that records whether 0, positive,
    and/or negative numbers are possible.
    """
    signs: frozenset[Sign]
    
    @classmethod
    def top(cls) -> "SignSet":
        return cls(frozenset(["+", "-", "0"]))

    @classmethod
    def empty(cls) -> "SignSet":
        return cls(frozenset())

    @classmethod
    def of(cls, *signs: Sign) -> "SignSet":
        return cls(frozenset(signs))

    @classmethod
    def abstract(cls, items: Iterable[int]) -> "SignSet":
        """Map a (finite) set/iterable of ints to the abstract domain."""
        s: set[Sign] = set()
        for x in items:
            if x == 0:
                s.add("0")
            elif x > 0:
                s.add("+")
            else:
                s.add("-")
            # Early exit if we have seen all three
            if len(s) == 3:
                break
        return cls(frozenset(s))

    def concretize(self, x: int) -> bool:
        """True iff this abstract element allows x."""
        return (
            ("0" in self.signs and x == 0)
            or ("+" in self.signs and x > 0)
            or ("-" in self.signs and x < 0)
        )
        
    def __contains__(self, member : int): 
        if (member == 0 and "0" in self.signs): 
            return True
        elif (member > 0 and "+" in self.signs): 
            return True
        elif (member < 0 and "-" in self.signs): 
            return True
        return False

    def __le__(self, other: "SignSet") -> bool:
        return self.signs.issubset(other.signs)

    def __and__(self, other: "SignSet") -> "SignSet":
        """Meet = greatest lower bound = intersection on signs."""
        return SignSet(frozenset(self.signs & other.signs))

    def __or__(self, other: "SignSet") -> "SignSet":
        """Join = least upper bound = union on signs."""
        return SignSet(frozenset(self.signs | other.signs))

    def __repr__(self) -> str:
        inside = ",".join(sorted(self.signs))
        return f"SignSet({{{inside}}})"
    
    ### Abstract arithmetic
    
    @staticmethod
    def _lift_bin(a: "SignSet", b: "SignSet", table: dict[tuple[Sign, Sign], set[Sign]]) -> "SignSet":
        out: set[Sign] = set()
        for sa in a.signs:
            for sb in b.signs:
                out |= table[(sa, sb)]
                if len(out) == 3:  # reached top {-,0,+}
                    return SignSet(frozenset(out))
        return SignSet(frozenset(out))

    # Addition
    def add(self, other: "SignSet") -> "SignSet":
        add_table: dict[tuple[Sign, Sign], set[Sign]] = {
            # x + y -> possible sign(s)
            ("+", "+"): { "+" },
            ("+", "0"): { "+" },
            ("+", "-"): { "-", "0", "+" },
            ("0", "+"): { "+" },
            ("0", "0"): { "0" },
            ("0", "-"): { "-" },
            ("-", "+"): { "-", "0", "+" },
            ("-", "0"): { "-" },
            ("-", "-"): { "-" },
        }
        return self._lift_bin(self, other, add_table)

    # Negation
    def __neg__(self) -> "SignSet":
        mapping = {"+" : "-", "-" : "+", "0" : "0"}
        return SignSet(frozenset(mapping[s] for s in self.signs))

    # Subtraction
    def sub(self, other: "SignSet") -> "SignSet":
        return self.add(-other)

    # Multiplication
    def mul(self, other: "SignSet") -> "SignSet":
        mul_table: dict[tuple[Sign, Sign], set[Sign]] = {
            ("+", "+"): { "+" },
            ("+", "0"): { "0" },
            ("+", "-"): { "-" },
            ("0", "+"): { "0" },
            ("0", "0"): { "0" },
            ("0", "-"): { "0" },
            ("-", "+"): { "-" },
            ("-", "0"): { "0" },
            ("-", "-"): { "+" },
        }
        return self._lift_bin(self, other, mul_table)
    
    def div(self, other: "SignSet") -> "SignSet":
        out: set[Sign] = set()
        for sa in self.signs:
            for sb in other.signs:
                if sb == "0":
                    # Division by zero is undefined: skip this pair
                    continue
                if sa == "0":
                    out.add("0")
                elif sa == sb:          # +/+ or -/- -> +
                    out.add("+")
                else:                   # +/- or -/+ -> -
                    out.add("-")
                if len(out) == 3:       # reached top {-,0,+}
                    return SignSet(frozenset(out))
        return SignSet(frozenset(out))

    # Absolute value
    def abs(self) -> "SignSet":
        out: set[Sign] = set()
        if "-" in self.signs or "+" in self.signs:
            out.add("+")
        if "0" in self.signs:
            out.add("0")
        return SignSet(frozenset(out if out else set()))

    def compare(self, other: "SignSet", op: str) -> frozenset[bool]:
        if not isinstance(other, SignSet):
            return NotImplemented

        diff = self.sub(other)
        rels: set[int] = set()

        if "-" in diff.signs:
            rels.add(-1)
        if "0" in diff.signs:
            rels.add(0)
        if "+" in diff.signs:
            rels.add(1)
            
        may_be_true = any(holds(r, op) for r in rels)
        may_be_false = any(not holds(r, op) for r in rels)

        result: list[bool] = []
        if may_be_true:
            
            result.append(True)
        if may_be_false:
            result.append(False)
        return result
    
    @classmethod
    def constrain(cls, prev: "SignSet", other: "SignSet", op: "str") -> Tuple["SignSet",  "SignSet"]:
        valid_signs: set[Sign] = set()
        
        compare_table = {
            ("-", "-"): {-1, 0, 1},
            ("-", "0"): {-1},        
            ("-", "+"): {-1},       
            ("0", "-"): {1},       
            ("0", "0"): {0},        
            ("0", "+"): {-1},       
            ("+", "-"): {1},        
            ("+", "0"): {1},         
            ("+", "+"): {-1, 0, 1},
        }

        for sx in prev.signs:
            for sy in other.signs:
                rels = compare_table[(sx, sy)]
                if any(holds(r, op) for r in rels):
                    valid_signs.add(sx)
                    break  # no need to test more sy for this sx

        true_set = cls(frozenset(valid_signs))
        false_set = cls(frozenset(prev.signs-valid_signs))
        
        return true_set, false_set

    # Pretty
    def __repr__(self) -> str:
        inside = ",".join(sorted(self.signs))
        return f"SignSet({{{inside}}})"