from dataclasses import dataclass
from enum import Enum, auto
import string
from typing import List, Dict, Self, Tuple, Optional, Iterable, Union, Any, FrozenSet
from copy import deepcopy
from jpamb import jvm
import jpamb

from solutions.interpreter import PC, Bytecode, Stack, State
from debloater.abstractions.sign_abstraction import SignSet

op_hit = set()

@dataclass
class PerVarFrame[AV]:
    locals: Dict[int, str]
    stack: Stack[AV]
    pc: PC

    @classmethod
    def abstract(cls, locals_conc: Dict[int, Any], stack_conc: List[Any], pc: PC) -> "PerVarFrame":
        if locals_conc:
            max_i = max(locals_conc.keys())
            locs = {i: AV.abstract([locals_conc[i]]) if i in locals_conc else AV.empty() for i in range(max_i + 1)}
        else:
            locs = {}
        st = Stack([AV.abstract([x]) for x in stack_conc])
        return cls(locs, st, pc)

    ## Lattice methods (order, meet, join) ##
    
    def __le__(self, other: "PerVarFrame") -> bool:
        if self.pc != other.pc:
            return False
        if set(self.locals.keys()) != set(other.locals.keys()):
            return False
        for k in self.locals:
            if not (self.locals[k] <= other.locals[k]):
                return False
        h = max(len(self.stack.items), len(other.stack.items))
        def get(s, i): return s.items[i] if i < len(s.items) else AV.empty()
        return all(get(self.stack, i) <= get(other.stack, i) for i in range(h))

    def meet(self, other: "PerVarFrame") -> Optional["PerVarFrame"]:
        if self.pc != other.pc or set(self.locals.keys()) != set(other.locals.keys()):
            return None
        new_locs = {k: self.locals[k] & other.locals[k] for k in self.locals}
        h = min(len(self.stack.items), len(other.stack.items))
        new_stack = Stack([self.stack.items[i] & other.stack.items[i] for i in range(h)])
        return PerVarFrame(new_locs, new_stack, self.pc)

    def join(self, other: "PerVarFrame") -> Optional["PerVarFrame"]:
        if self.pc != other.pc or set(self.locals.keys()) != set(other.locals.keys()):
            return None
        new_locs = dict(self.locals)
        new_locs.update(other.locals)
        h = max(len(self.stack.items), len(other.stack.items))
        def get(s, i): return s.items[i] if i < len(s.items) else AV.empty()
        new_stack = Stack([get(self.stack, i) | get(other.stack, i) for i in range(h)])
        return PerVarFrame(new_locs, new_stack, self.pc)
    
    def clone(self) -> "PerVarFrame":
        return PerVarFrame(
            locals=self.locals.copy(),
            stack=Stack(self.stack.items.copy()),
            pc=self.pc
        )
   
 
@dataclass
class AState[AV]:
    heap: Dict[int, str]         # abstract heap (addresses -> variable name)
    constraints: Dict[str, AV]   # variable constraints (variable name -> abstract value) for both state heap and frame locals
    frames: Stack[PerVarFrame]   # stack of PerVarFrame

    @classmethod
    def abstract(cls, s: State) -> "AState":
        heap_abs: Dict[int, AV] = {addr: AV.abstract([val]) for addr, val in s.heap.items()}
        frames_abs = Stack([PerVarFrame.abstract(f.locals, f.stack.items, f.pc) for f in s.frames.items])
        return cls(heap_abs, frames_abs)

    def __le__(self, other: "AState") -> bool:
        # heap: pointwise <= 
        for addr in set(self.heap) | set(other.heap):
            if not (self.heap.get(addr, AV.empty()) <= other.heap.get(addr, AV.empty())): # if addr does not exist, treat as empty
                return False
        # frames: require same number of frames (same call depth) and pointwise <=
        if len(self.frames.items) != len(other.frames.items):
            return False
        for f1, f2 in zip(self.frames.items, other.frames.items):
            if not (f1 <= f2):
                return False
        return True

    def meet(self, other: "AState[AV]") -> Optional["AState[AV]"]:
        # heap meet
        new_heap = {
            addr: self.heap.get(addr, AV.empty()) & other.heap.get(addr, AV.empty()) # if addr does not exist, treat as empty
            for addr in set(self.heap) | set(other.heap)
        }
        # frames: require same count and all pairwise meets succeed
        if len(self.frames.items) != len(other.frames.items):
            return None
        new_frames = []
        for f1, f2 in zip(self.frames.items, other.frames.items):
            m = f1.meet(f2)
            if m is None:
                return None
            new_frames.append(m)
        return AState(new_heap, Stack(new_frames))

    def join(self, other: "AState") -> Optional["AState"]:
        # heap join
        new_heap = {
            addr: self.heap.get(addr) | other.heap.get(addr)
            for addr in set(self.heap) | set(other.heap)
        }
        
        # frames: require same count and all pairwise joins succeed
        if len(self.frames.items) != len(other.frames.items):
            return None
        new_frames = []
        for f1, f2 in zip(self.frames.items, other.frames.items):
            print(f"Frame1: {f1}")
            print(f"Frame2: {f2}")
            j = f1.join(f2)
            if j is None:
                return None
            new_frames.append(j)
        return AState(new_heap, Stack(new_frames))
    
    
    def clone(self) -> "AState[AV]":
        return AState(
            heap=self.heap.copy(),
            frames=Stack([f.clone() for f in self.frames.items]),
            constraints=self.constraints.copy()
        )
    
    def __ior__(self, other: "AState[AV]") -> Self:
        c_self = self.constraints
        c_other = other.constraints
        
        def merge_constraints(n1: str, n2: str) -> AV:
            v1 = c_self.get(n1, c_other[n1])
            v2 = c_other.get(n2, c_self[n2])
            
            return v1 | v2
        
        def resolve_names(n1: str, n2: str, location: str) -> str:
            if n1 == n2:
                c_self[n1] = merge_constraints(n1, n2)
                return n1
            
            count = sum(n.startswith(location) for n in c_self.keys())
            new_name = f"{location}_{count}"
            
            c_self[new_name] = merge_constraints(n1, n2)
            return new_name
        
        # dst = self, src = other - modify in place
        def merge_mapping(dst: Dict[int, str], src: Dict[int, str], location: str) -> None:
            for k, n_other in src.items():
                if k in dst:
                    # if dst has the same address, merge
                    dst[k] = resolve_names(dst[k], n_other, location)
                else:
                    # else, add the new key to dst and handle constraints
                    dst[k] = n_other
                    # ensure the name's value exists on self, join constraints if present on both
                    if n_other in c_self and n_other in c_other:
                        c_self[n_other] = merge_constraints(n_other, n_other)
                    elif n_other not in c_self and n_other in c_other:
                        c_self[n_other] = c_other[n_other]
                        
        # 1. Heap: pointwise by address
        merge_mapping(self.heap, other.heap, "heap")
        
        # 2. Frames: pointwise by depth
        for f1, f2 in zip(self.frames.items, other.frames.items, strict=True):
            assert f1.pc == f2.pc, f"PC differs: {f1.pc} != {f2.pc}"

            # locals: Dict[int, str]
            merge_mapping(f1.locals, f2.locals, "local")

            # stack: same height, elementwise names (str)
            s1, s2 = f1.stack.items, f2.stack.items
            assert len(s1) == len(s2), f"stacks should be of the same size to join"
            for i, (v1, v2) in enumerate(zip(s1, s2)):
                s1[i] = v1 | v2

        return self     
        

@dataclass
class StateSet[AV]:
    per_inst : dict[PC, AState[AV]]
    needswork : set[PC]

    def per_instruction(self):
        for pc in self.needswork: 
            yield (pc, self.per_inst[pc])

    # sts |= astate
    def __ior__(self, astate: AState[AV]):
        pc = astate.frames.peek().pc
        old = self.per_inst.get(pc)

        if old is None:
            # First time seeing this pc
            self.per_inst[pc] = astate
            self.needswork.add(pc)
            return self
        
        new_state = old.clone()
        new_state |= astate
        
        if new_state != old:
            self.per_inst[pc] = new_state
            self.needswork.add(pc)

        return self

_suite = jpamb.Suite()

def _opcode_at(pc: PC):
    ops = list(_suite.method_opcodes(pc.method))
    return ops[pc.offset]

# Step the abstract state (possibly returns more states due to branches)
def step[AV](state: AState[AV], domain: type[AV]) -> Iterable[AState[AV] | str]:
    assert isinstance(state, AState), "step expects AState"
    if not state.frames or not state.frames.items:
        return []  # nothing to do

    frame = deepcopy(state.frames.peek())
    constraints = deepcopy(state.constraints)
    pc = frame.pc
    
    opr = _opcode_at(pc)
    
    op_hit.add(opr)

    # helper to build successor states (deepcopy to isolate)
    def mk_successor(new_frame: PerVarFrame) -> AState:
        new_state = deepcopy(state)
        new_state.frames.items[-1] = new_frame  # replace top frame
        return new_state

    # handle instructions (similar to dynamic interpreter, but on AV)
    match opr:
        case jvm.Push(value=v):
            new_frame = deepcopy(frame)
            new_frame.stack.push(domain.abstract([v.value]))
            new_frame.pc += 1
            return [mk_successor(new_frame)]

        case jvm.Load(type=t, index=i):
            new_frame = deepcopy(frame)
            # locals are AV in PerVarFrame.abstract, if missing, use empty
            var_name = new_frame.locals.get(i, domain.empty())
            val = constraints.get(var_name)
            new_frame.stack.push(val)
            new_frame.pc += 1
            return [mk_successor(new_frame)]

        case jvm.Dup():
            new_frame = deepcopy(frame)
            v = new_frame.stack.peek()
            new_frame.stack.push(v)
            new_frame.pc += 1
            return [mk_successor(new_frame)]

        case jvm.Binary(type=jvm.Int(), operant=op):
            new_frame = deepcopy(frame)
            # pop order preserved: v2 = top, v1 = next
            v2 = new_frame.stack.pop()
            v1 = new_frame.stack.pop()
            if op == jvm.BinaryOpr.Add:
                res = v1.add(v2)
            elif op == jvm.BinaryOpr.Sub:
                res = v1.sub(v2)
            elif op == jvm.BinaryOpr.Mul:
                res = v1.mul(v2)
            elif op == jvm.BinaryOpr.Div:
                res = v1.div(v2)
            else:
                # Rem and others: over-approximate -> TOP
                res = AV(SignSet.of("+", "0", "-"))
            new_frame.stack.push(res)
            new_frame.pc += 1
            return [mk_successor(new_frame)]

        case jvm.Return(type=t):
            new_state = deepcopy(state)
            top_frame = new_state.frames.pop()
            if t:
                ret = top_frame.stack.pop()
            if new_state.frames:
                caller = new_state.frames.peek()
                if t:
                    caller.stack.push(ret)
                caller.pc += 1
                return [new_state]
            else:
                return ["ok"]

        case jvm.Get(field=field):
            new_frame = deepcopy(frame)
            # $assertionsDisabled pushed as 0
            new_frame.stack.push(domain.abstract([0]))
            new_frame.pc += 1
            return [mk_successor(new_frame)]

        case jvm.Ifz():
            v = frame.stack.pop()
            cond = opr.condition
            can_zero = "0" in v.signs
            can_pos = "+" in v.signs
            can_neg = "-" in v.signs

            def push_target(tgt_pc_offset):
                nf = deepcopy(frame)
                nf.pc = PC(frame.pc.method, tgt_pc_offset)
                return mk_successor(nf)

            # decide branch feasibility
            def branch_possible(cond_name: str, truth: bool) -> bool:
                if cond_name == "eq":
                    return truth and can_zero or (not truth and (can_pos or can_neg))
                if cond_name == "ne":
                    return truth and (can_pos or can_neg) or (not truth and can_zero)
                if cond_name == "lt":
                    return truth and can_neg or (not truth and (can_zero or can_pos))
                if cond_name == "le":
                    return truth and (can_neg or can_zero) or (not truth and can_pos)
                if cond_name == "gt":
                    return truth and can_pos or (not truth and (can_zero or can_neg))
                if cond_name == "ge":
                    return truth and (can_pos or can_zero) or (not truth and can_neg)
                return True

            targets: list[AState | str] = []
            # true branch -> jump target
            if branch_possible(cond, True):
                targets.append(push_target(opr.target))
            # false branch -> fall-through
            if branch_possible(cond, False):
                nf = deepcopy(frame)
                nf.pc += 1
                targets.append(mk_successor(nf))
            return targets

        case jvm.New(offset, classname):
            if classname == jvm.ClassName("java/lang/AssertionError"):
                return ["assertion error"]
            # otherwise continue
            new_frame = deepcopy(frame)
            new_frame.pc += 1
            return [mk_successor(new_frame)]

        case jvm.If():
            # two-operand comparison: over-approximate and emit both branches if possible
            v2 = frame.stack.pop()
            v1 = frame.stack.pop()
            cond = opr.condition

            def possible_true():
                # very conservative: assume true unless impossible for all combinations
                return True

            targets: list[AState | str] = []
            if possible_true():
                nf = deepcopy(frame)
                nf.pc = PC(frame.pc.method, opr.target)
                targets.append(mk_successor(nf))
            # false branch
            nf2 = deepcopy(frame)
            nf2.pc += 1
            targets.append(mk_successor(nf2))
            return targets
    

def many_step(state : dict[PC, AState | str]) -> dict[PC, AState | str]:
  new_state = dict(state)
  for k, v in state.items():
      for s in step(v):
        if isinstance(s, AState):
            tgt = s.frames.items[0].pc if s.frames.items else k # target pc
            prev = new_state.get(tgt)
            if prev is None:
                new_state[tgt] = s
            elif isinstance(prev, AState):
                merged = prev.join(s)  # join with existing state
                if merged is not None:
                    new_state[tgt] = merged
        else:
            # terminal string outcome (terminal state)
            new_state[k] = s
  return new_state


def manystep[AV](sts: StateSet[AV], domain: type[AV]) -> Iterable[AState[AV] | str]:
    states = []
    for _pc, state in sts.per_instruction():
        s = step(state, domain)
        if s is not None:
            states.extend(s)
    return states



def initialstate_from_method[AV](methodid: jvm.AbsMethodID, domain: type[AV]) -> StateSet[AV]:
    init_pc = PC(methodid, 0)
    start_frame = PerVarFrame[AV](locals={}, stack=Stack.empty(), pc=init_pc) # New frame, with the method's starting PC
    params = methodid.extension.params
    constraints = {}
    
    for i, p in enumerate(params):
        name = f"local_{i}"
        constraints[name] = domain.top()
        start_frame.locals[i] = name
    
    state = AState[AV](heap={}, frames=Stack.empty().push(start_frame), constraints=constraints)
    
    return StateSet[AV](
        per_inst={start_frame.pc: state},
        needswork={start_frame.pc}
    )

method = jpamb.getmethodid(
    "Bounded Static Analysis",
    "1.0",
    "Group8",
    [],
    for_science=False
)

bc = Bytecode(jpamb.Suite(), dict())

sts = initialstate_from_method(method, SignSet)
all_ops = list(_suite.method_opcodes(method))



final = set()
MAX_STEPS = 100

for i in range(MAX_STEPS):
  for s in manystep(sts, SignSet):
    if isinstance(s, str):
      final.add(s)
    else:
      sts |= s
      
print(f"The following final states {final} is possible in {MAX_STEPS}")

for op in all_ops:
    print(f"{op.offset} -- {op}")

not_hit = [x for x in all_ops if x not in op_hit]

print("NOT HIT")
for op in not_hit:
    print(f"{op.offset} -- {op}")


    



