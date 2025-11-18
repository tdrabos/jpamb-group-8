from dataclasses import dataclass
import sys
from enum import Enum, auto
import string
from typing import List, Dict, Self, Tuple, Optional, Iterable, Union, Any, FrozenSet
from copy import deepcopy
from jpamb import jvm
import jpamb
from loguru import logger

from solutions.interpreter import PC, Bytecode, Stack, State
from debloater.static.abstractions.sign_abstraction import SignSet

op_hit = set()

logger.remove()
logger.add(sys.stderr, format="[{level}] {message}", level="DEBUG")

@dataclass
class PerVarFrame[AV]:
    locals: Dict[int, str]
    stack: Stack[str]
    pc: PC

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
            for i, (n1, n2) in enumerate(zip(s1, s2)):
                # merge the constraints of the 2 stacks of value names in place
                # since equal length is ensured, just marge them pairwise
                c_self[n1] = merge_constraints(n1, n2)

        return self
    
    def __str__(self) -> str:
        # Heap: show addr: var = abstract_value
        heap_lines: list[str] = []
        for addr in sorted(self.heap):
            var = self.heap[addr]
            av = self.constraints.get(var, None)
            if av is None:
                heap_lines.append(f"    {addr}: {var}")
            else:
                heap_lines.append(f"    {addr}: {var} = {av}")

        if not heap_lines:
            heap_block = "  heap: <empty>"
        else:
            heap_block = "  heap:\n" + "\n".join(heap_lines)

        # Constraints: show var -> abstract_value
        cons_lines: list[str] = []
        for var in sorted(self.constraints):
            cons_lines.append(f"    {var}: {self.constraints[var]}")
        if not cons_lines:
            cons_block = "  constraints: <empty>"
        else:
            cons_block = "  constraints:\n" + "\n".join(cons_lines)

        # Frames: use their own repr/str, one per line
        frame_lines: list[str] = []
        for i, f in enumerate(self.frames.items):
            frame_lines.append(f"    [{i}] {f!r}")
        if not frame_lines:
            frames_block = "  frames: <empty>"
        else:
            frames_block = "  frames:\n" + "\n".join(frame_lines)

        return "AState(\n" + "\n".join([heap_block, cons_block, frames_block]) + "\n)"     
        

@dataclass
class StateSet[AV]:
    per_inst : dict[PC, AState[AV]]
    needswork : set[PC]

    def per_instruction(self):
        while self.needswork:
            pc = self.needswork.pop()
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
def step[AV](state: AState[AV], domain: type[AV], all_ops: list[jvm.Opcode]) -> Iterable[AState[AV] | str]:
    
    #logger.debug(f"Currently handling state: {state}")
    
    assert isinstance(state, AState), "step expects AState"
    if not state.frames or not state.frames.items:
        return []  # nothing to do

    frame = state.frames.peek()
    constraints = state.constraints
    pc = frame.pc
    
    opr = _opcode_at(pc)
    
    op_hit.add(opr)
    
    logger.debug(f"Current operation: {opr}")

    # helper to build successor states (deepcopy to isolate)
    def mk_successor(new_frame: PerVarFrame, constraints: dict[str, AV]=None) -> AState:
        new_state = deepcopy(state)
        new_state.frames.items[-1] = new_frame  # replace top frame
        if constraints is not None:
            new_state.constraints = constraints
        return new_state

    # handle instructions (similar to dynamic interpreter, but on AV)
    match opr:
        case jvm.Push(value=v):
            val_name = f"stack_{len(frame.stack.items)}"
            constraints[val_name] = domain.abstract([v.value])
            
            frame.stack.push(val_name)
            frame.pc += 1
            
            return [state]
            

        case jvm.Load(type=t, index=i):
            var_name = frame.locals.get(i)
            
            frame.stack.push(var_name)
            frame.pc += 1
            return [state]

        case jvm.Dup():
            new_frame = deepcopy(frame)
            v = new_frame.stack.peek()
            new_frame.stack.push(v)
            new_frame.pc += 1
            return [mk_successor(new_frame)]

        case jvm.Binary(type=jvm.Int(), operant=op):
            # pop order preserved: v2 = top, v1 = next
            n2 = frame.stack.pop()
            n1 = frame.stack.pop()
            
            v1 = constraints[n1]
            v2 = constraints[n2]
                        
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
                res = domain.top()
            res_name = f"stack_{len(frame.stack.items)}"
            constraints[res_name] = res
            
            frame.stack.push(res_name)
            frame.pc += 1
            
            return [state]

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
            # Compare variable on top of the stack to Zero
            var_name = frame.stack.pop()
            print(var_name)
            v = constraints[var_name]
            v_zero = domain.abstract([0])
            cond = opr.condition

            logger.debug(f"Comparing value: {var_name} : {v} {cond} {v_zero}")
            res = v.compare(v_zero, cond)
            c_true, c_false = domain.constrain(v, v_zero, cond)
            
            logger.debug(f"New constrains for True branch: {c_true}, for False: {c_false}")
            
            print(res)
            
            targets: list[AState | str] = []
            
            if True in res:
                true_const = deepcopy(constraints)
                true_const[var_name] = c_true
                nf = deepcopy(frame)
                
                nf.pc = PC(frame.pc.method, opr.target)
                targets.append(mk_successor(nf, true_const))
            
            if False in res:
                false_const = deepcopy(constraints)
                false_const[var_name] = c_false
                nf = deepcopy(frame)
                nf.pc += 1
                targets.append(mk_successor(nf, false_const))
            else: op_hit.remove(opr)
                
            print(f"Branching targets: {targets}")
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
        
        case jvm.Store(index=i):
            v_name = frame.stack.pop()
            v = constraints[v_name]
            
            local_name = frame.locals.get(i)
            if local_name is None:
                local_name = f"local_{i}"
                frame.locals[i] = local_name
            print(local_name)
            constraints[local_name] = v
            frame.pc += 1
            
            return [state]
            
            
            
    

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


def manystep[AV](sts: StateSet[AV], domain: type[AV], all_ops: list[jvm.Opcode]) -> Iterable[AState[AV] | str]:
    states = []
    for _pc, state in sts.per_instruction():
        s = step(state, domain, all_ops)
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
    for s in manystep(sts, SignSet, all_ops):
        if isinstance(s, str):
            final.add(s)
        else:
            sts |= s
      
    logger.debug(f"Iteration {i}: {len(sts.needswork)} PCs need work")
    for pc in sts.needswork:
        logger.debug(pc)
    logger.debug(f"Final states: {final}")

    # If needswork is empty, we've reached fixed point
    if not sts.needswork:
        logger.debug("Fixed point reached!")
        break
      
print(f"The following final states {final} is possible in {MAX_STEPS}")

for op in all_ops:
    print(f"{op.offset} -- {op}")

not_hit = [x for x in all_ops if x not in op_hit]

print("NOT HIT")
for op in not_hit:
    print(f"{op.offset} -- {op}")


    



