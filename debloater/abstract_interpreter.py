from dataclasses import dataclass
from enum import Enum, auto
from typing import List, Dict, Tuple, Optional, Iterable, Union
from copy import deepcopy

from solutions.interpreter import PC, Stack, State

class PerVarFrame[V, AV]:
    locals: Dict[int, V] # Maybe use AV here too?
    stack: Stack[AV]
    
    @classmethod
    def abstract(
        cls,
        locals_conc: Dict[int, V],
        stack_conc: List[V],
    ) -> "PerVarFrame":
        """
        Build a per-variable frame from one concrete state:
        """
        locs: Dict[int, int] = {i: locals_conc.get(i, 0) for i in range(max(locals_conc.keys()) + 1)}
        st = Stack([AV.abstract([x]) for x in stack_conc])
        return cls(locs, st)

    ## Lattice methods (order, meet, join) ##
    
    # Partial order: (local1, stack1) <= (locals2, stack2) iff (locals1 == locals2) and (stack1 <= stack2 pointwise)
    # OR: if locals are AV too, the also compare them pointwise (TODO)
    def __le__(self, other: "PerVarFrame") -> bool:
        if self.locals != other.locals:
            return False
        h = max(len(self.stack.items), len(other.stack.items))
        def get(s, i): return s.items[i] if i < len(s.items) else AV.empty()
        return all(get(self.stack,i) <= get(other.stack,i) for i in range(h)) # Abstraction also has to define __le__

    def meet(self, other: "PerVarFrame") -> Optional["PerVarFrame"]:
        if self.locals != other.locals:
            return None
        h = min(len(self.stack.items), len(other.stack.items))
        meet_stack = Stack([self.stack.items[i] & other.stack.items[i] for i in range(h)])
        return PerVarFrame(dict(self.locals), meet_stack)

    def join(self, other: "PerVarFrame") -> Optional["PerVarFrame"]:
        if self.locals != other.locals:
            return None
        h = max(len(self.stack.items), len(other.stack.items))
        def get(s, i): return s.items[i] if i < len(s.items) else AV.empty()
        joined_stack = Stack([get(self.stack,i) | get(other.stack,i) for i in range(h)])
        return PerVarFrame(dict(self.locals), joined_stack)
   
 
@dataclass
class AState[AV]:
    heap: dict[int, AV] # use AV?
    frames: Stack[PerVarFrame[AV]]
    
    @classmethod
    def abstract(cls, s: State) -> "AState":
        # Abstract the Heap and Frames here
        raise NotImplementedError 
    
    # TODO: implement lattice methods (le, meet, join)
    
# Step the abstract state (possibly returns more states due to branches)
def step(state : AState) -> Iterable[AState | str]:
    raise NotImplementedError 
    

def many_step(state : dict[PC, AState | str]) -> dict[PC, AState | str]:
  new_state = dict(state)
  for k, v in state.items():
      for s in step(v):
        new_state[s.pc] |= s
  return new_state


    
