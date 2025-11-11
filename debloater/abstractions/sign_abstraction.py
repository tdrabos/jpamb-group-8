from __future__ import annotations
from dataclasses import dataclass
from typing import Iterable, Literal, TypeAlias

Sign: TypeAlias = Literal["+", "-", "0"]

# TODO: Create interface (eg. Domain for all the different abstractions)
@dataclass(frozen=True)
class SignSet:
    """
    A finite abstraction of integer sets that records whether 0, positive,
    and/or negative numbers are possible.
    """
    signs: frozenset[Sign]

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
    def __add__(self, other: "SignSet") -> "SignSet":
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
    def __sub__(self, other: "SignSet") -> "SignSet":
        return self + (-other)

    # Multiplication
    def __mul__(self, other: "SignSet") -> "SignSet":
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

    # Absolute value
    def abs(self) -> "SignSet":
        out: set[Sign] = set()
        if "-" in self.signs or "+" in self.signs:
            out.add("+")
        if "0" in self.signs:
            out.add("0")
        return SignSet(frozenset(out if out else set()))

    # Pretty
    def __repr__(self) -> str:
        inside = ",".join(sorted(self.signs))
        return f"SignSet({{{inside}}})"