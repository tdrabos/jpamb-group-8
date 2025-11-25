from __future__ import annotations
from dataclasses import dataclass
from typing import Iterable, Optional, Tuple, Union
from math import inf

from debloater.static.abstractions.sign_abstraction import holds

Number = Union[int, float]

@dataclass(frozen=True)
class Interval:
    lo: Number
    hi: Number
    none_zero = None

    @classmethod
    def empty(cls) -> Interval:
        return cls(1, 0)
    
    @classmethod
    def top(cls) -> Interval:
        """Top element: all integers (unbounded interval)."""
        return cls(-inf, inf)

    @classmethod
    def of(cls, lo: Number, hi: Number) -> Interval:
        return cls.empty() if lo > hi else cls(lo, hi)

    @classmethod
    def abstract(cls, items: Iterable[Number]) -> Interval:
        xs = list(items)
        if not xs:
            return cls.empty()
        return cls(min(xs), max(xs))

    def is_bottom(self) -> bool:
        return self.lo > self.hi
    
    def get_type(self) -> type:
        return self.lo.type

    def __contains__(self, x: Number) -> bool:
        return not self.is_bottom() and self.lo <= x <= self.hi
    
    def concrete_value(self) -> Optional[Number]:
        if self.is_bottom():
            return None
        if self.lo == self.hi:
            return self.lo
        return None
    
    
    # Arithmetic

    def add(self, other: Interval) -> Interval:
        if self.is_bottom() or other.is_bottom():
            return Interval.empty()
        return Interval(self.lo + other.lo, self.hi + other.hi)

    def __neg__(self) -> Interval:
        if self.is_bottom():
            return Interval.empty()
        return Interval(-self.hi, -self.lo)

    def sub(self, other: Interval) -> Interval:
        if self.is_bottom() or other.is_bottom():
            return Interval.empty()
        return Interval(self.lo - other.hi, self.hi - other.lo)

    def mul(self, other: Interval) -> Interval:
        if self.is_bottom() or other.is_bottom():
            return Interval.empty()

        a, b = self.lo, self.hi
        c, d = other.lo, other.hi

        products = [
            a * c,
            a * d,
            b * c,
            b * d,
        ]
        return Interval(min(products), max(products))

    def div(self, other: Interval) -> Interval:
        if self.is_bottom() or other.is_bottom():
            return Interval.empty()

        a, b = self.lo, self.hi
        c, d = other.lo, other.hi

        # If denominator is exactly [0,0] => division undefined => bot
        if c == 0 and d == 0:
            return Interval.empty()

        # If denominator includes 0 as one of several values => top
        if c <= 0 <= d:
            return Interval.top()

        # Otherwise: safe
        candidates = [
            a / c,
            a / d,
            b / c,
            b / d,
        ]
        return Interval(min(candidates), max(candidates))


    # Helper methods
    
    # Helper for handling CompareFloating operation
    def compare_floating(self, other: Interval) -> set[int]:
        if not isinstance(other, Interval):
            return NotImplemented

        if self.is_bottom() or other.is_bottom():
            return []

        a, b = self.lo, self.hi
        c, d = other.lo, other.hi

        rels: set[int] = set()

        # possible x < y ?
        if a < d:
            rels.add(-1)
        # possible x == y ?
        if max(a, c) <= min(b, d):
            rels.add(0)
        # possible x > y ?
        if b > c:
            rels.add(1)
            
        return rels
    
    def compare(self, other: Interval, op: str) -> list[bool]:
        if not isinstance(other, Interval):
            return NotImplemented

        if self.is_bottom() or other.is_bottom():
            return []

        a, b = self.lo, self.hi
        c, d = other.lo, other.hi

        rels: set[int] = set()

        # possible x < y ?
        if a < d:
            rels.add(-1)
        # possible x == y ?
        if max(a, c) <= min(b, d):
            rels.add(0)
        # possible x > y ?
        if b > c:
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
    def constrain(cls, prev: Interval, other: Interval, op: str) -> Tuple[Interval, Interval]:
        if prev.is_bottom() or other.is_bottom():
            return cls.empty(), cls.empty()

        a, b = prev.lo, prev.hi
        c, d = other.lo, other.hi

        # Convenience
        def inter(lo1: Number, hi1: Number, lo2: Number, hi2: Number) -> Interval:
            lo = max(lo1, lo2)
            hi = min(hi1, hi2)
            return cls.empty() if lo > hi else cls(lo, hi)

        #  lt: x < y
        if op == "lt":
            if a >= d:
                true_int = cls.empty()
                false_int = prev
            else:
                t_hi = min(b, d - 1)
                true_int = cls.of(a, t_hi)
                
                false_int = cls.of(t_hi + 1, b) if t_hi < b else cls.empty()
            return true_int, false_int

        # le: x <= y
        if op == "le":
            if a > d:
                true_int = cls.empty()
                false_int = prev
            else:
                t_hi = min(b, d)
                true_int = cls.of(a, t_hi)
                false_int = cls.of(t_hi + 1, b) if t_hi < b else cls.empty()
            return true_int, false_int

        # gt: x > y
        if op == "gt":
            if b <= c:
                true_int = cls.empty()
                false_int = prev
            else:
                t_lo = max(a, c + 1)
                true_int = cls.of(t_lo, b)
                false_int = cls.of(a, t_lo - 1) if t_lo > a else cls.empty()
            return true_int, false_int

        #  ge: x >= y
        if op == "ge":
            # x >= y possible ⇔ x >= c
            if b < c:
                true_int = cls.empty()
                false_int = prev
            else:
                t_lo = max(a, c)
                true_int = cls.of(t_lo, b)
                false_int = cls.of(a, t_lo - 1) if t_lo > a else cls.empty()
            return true_int, false_int

        # eq: x == y
        if op == "eq":
            inter_int = inter(a, b, c, d)
            if inter_int.is_bottom():
                return cls.empty(), prev
            if c <= a and b <= d:
                return prev, cls.empty()
            return inter_int, prev

        # ne: x != y
        if op == "ne":
            if inter(a, b, c, d).is_bottom():
                return prev, cls.empty()
            if a == b and c <= a <= d:
                return cls.empty(), prev
            return prev, prev

        raise ValueError(f"Unknown comparison op: {op!r}")
    
    # Lattice operators
    
    def __le__(self, other: "Interval") -> bool:
        if self.is_bottom():
            return True
        if other.is_bottom():
            return False
        return other.lo <= self.lo and self.hi <= other.hi
    
    def __or__(self, other: "Interval") -> "Interval":
        if self.is_bottom():
            return other
        if other.is_bottom():
            return self
        lo = min(self.lo, other.lo)
        hi = max(self.hi, other.hi)
        return Interval(lo, hi)

    def __and__(self, other: "Interval") -> "Interval":
        if self.is_bottom() or other.is_bottom():
            return Interval.empty()
        lo = max(self.lo, other.lo)
        hi = min(self.hi, other.hi)
        return Interval.empty() if lo > hi else Interval(lo, hi)


    # Pretty-print
    def __repr__(self) -> str:
        if self.is_bottom():
            return "Interval(bot)"
        return f"Interval([{self.lo}, {self.hi}])"
