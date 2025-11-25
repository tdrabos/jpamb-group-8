from dataclasses import dataclass
import sys
from typing import List, Dict, Literal, Self, Tuple, Optional, Iterable, Union, Any, FrozenSet
from copy import deepcopy
from debloater.static.abstractions.interval_abstraction import Interval
from jpamb import jvm
import jpamb
from loguru import logger
import json

from solutions.interpreter import PC, Bytecode, Stack, State
from debloater.static.abstractions.sign_abstraction import SignSet, holds
from debloater.static.utils.json_utils import dead_indices_to_lines_in_class

op_hit = set()
dead_store: dict[int, any] = dict()
dead_arg: dict[int, any] = dict()

logger.remove()
logger.add(sys.stderr, format="[{level}] {message}", level="DEBUG")

CmpRel = Literal[-1, 0, 1]

@dataclass(frozen=True)
class FloatCmpResult:
    left_name: str
    right_name: str
    possible_rels: FrozenSet[CmpRel]
    onnan: int

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
    constraints: Dict[str, any]  # variable constraints (variable name -> abstract value) for both state heap and frame locals
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
                if n_other.startswith("arg"): location = "arg"
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
    

@dataclass
class StateSet[AV]:
    per_inst : dict[PC, AState[AV]]
    needswork : set[PC]

    # While there are PCs that need work, we just pick the next one with its corresponding AState
    def per_instruction(self):
        while self.needswork:
            pc = self.needswork.pop()
            yield self.per_inst[pc]

    # sts |= astate
    def __ior__(self, astate: AState[AV]):    
        pc = astate.frames.peek().pc
        old = self.per_inst.get(pc)

        if old is None:
            # First time seeing this pc
            self.per_inst[pc] = astate.clone()
            self.needswork.add(pc)
            return self
        
        new_state = deepcopy(old)
        new_state |= astate
        
        # If the working set is changed after ior, the PC still needs work
        # Otherwise a fixpoint is reached and we do nothing
        if new_state != old:
            self.per_inst[pc] = new_state
            self.needswork.add(pc)

        return self

_suite = jpamb.Suite()


# Step the abstract state (possibly returns more states due to branches)
def step[AV](state: AState[AV], domain: type[AV]) -> Iterable[AState[AV] | str]:
    assert isinstance(state, AState), "step expects AState"
    if not state.frames or not state.frames.items:
        return []
    
    def opcode_at(pc: PC):
        ops = list(_suite.method_opcodes(pc.method))
        return ops[pc.offset]

    frame = state.frames.peek()
    constraints = state.constraints
    pc = frame.pc
    opr = opcode_at(pc)
    op_hit.add(opr)

    # helper to build successor states (deepcopy to isolate)
    def mk_successor(new_frame: PerVarFrame, constraints: dict[str, AV]=None, heap: Dict[int, str]=None) -> AState:
        new_state = deepcopy(state)
        new_state.frames.items[-1] = new_frame  # replace top frame
        if constraints is not None:
            new_state.constraints = constraints
        if heap is not None:
            new_state.heap = heap
        return new_state
    
    def float_conditional(nf, cmp_res: FloatCmpResult, cond):
        l_name = cmp_res.left_name
        r_name = cmp_res.right_name
        
        all_rels = cmp_res.possible_rels
        
        val_l = constraints[l_name]
        val_r = constraints[r_name]

        true_rels = {r for r in all_rels if holds(r, cond)}
        false_rels = all_rels - true_rels
    
        # helper: refine 'left_av' for a set of rels by joining constraints
        def refine_for_rels(rels: set[int]) -> Interval:
            if not rels:
                return Interval.empty()

            acc = Interval.empty()
            for r in rels:
                if r == -1:
                    op_name = "lt"
                elif r == 0:
                    op_name = "eq"
                else:  # 1
                    op_name = "gt"

                t_left, _ = Interval.constrain(val_l, val_r, op_name)
                
                acc = acc | t_left
            return acc
        
        targets: list[AState | str] = []
        
        # True branch
        if true_rels:
            true_frame = deepcopy(nf)
            new_left_true = refine_for_rels(true_rels)
            
            const_true = deepcopy(constraints)
            const_true[l_name] = new_left_true
            true_frame.pc = PC(frame.pc.method, opr.target)
            
            targets.append(mk_successor(new_frame=true_frame, constraints=const_true))
            

        # False branch
        if false_rels:
            false_frame = deepcopy(nf)
            new_left_false = refine_for_rels(false_rels)
            
            const_false = deepcopy(constraints)
            const_false[l_name] = new_left_false

            false_frame.pc += 1
            
            targets.append(mk_successor(new_frame=false_frame, constraints=const_false))
        else: op_hit.remove(opr)
            
        return targets

    
    def conditional(nf, n1: str, cond, n2: str = None):
        if not n2: v2 = domain.abstract([0])
        else: v2 = constraints[n2]
        
        v1 = constraints[n1]
        
        if isinstance(v1, FloatCmpResult):
            states = float_conditional(nf, v1, cond)
            return states
        
        res = v1.compare(v2, cond)
        c_true, c_false = domain.constrain(v1, v2, cond)
            
        targets: list[AState | str] = []
            
        if True in res:
            true_frame = deepcopy(nf)
            true_const = deepcopy(constraints)
            true_const[n1] = c_true
            true_frame.pc = PC(frame.pc.method, opr.target)
            targets.append(mk_successor(true_frame, true_const))
            
        if False in res:
            false_frame = deepcopy(nf)
            false_const = deepcopy(constraints)
            false_const[n1] = c_false
            false_frame.pc += 1
            targets.append(mk_successor(false_frame, false_const))
        else: op_hit.remove(opr)
        
        return targets


    # handle instructions (similar to dynamic interpreter, but on AV)
    match opr:
        case jvm.Push(value=v):
            val_name = f"stack_{len(frame.stack.items)}"
            constraints[val_name] = domain.abstract([v.value])
            
            nf = deepcopy(frame)
            
            nf.stack.push(val_name)
            nf.pc += 1
            
            return [mk_successor(nf, constraints)]
            
        case jvm.Load(type=t, index=i):
            var_name = frame.locals.get(i)
            
            nf = deepcopy(frame)
            
            nf.stack.push(var_name)
            
            if var_name.startswith("local") and i in dead_store.keys():
                del dead_store[i]
                
            if var_name.startswith("arg") and i in dead_arg.keys():
                del dead_arg[i]
                
            nf.pc += 1
            return [mk_successor(nf)]

        case jvm.Dup():
            new_frame = deepcopy(frame)
            v = new_frame.stack.peek()
            new_frame.stack.push(v)
            new_frame.pc += 1
            return [mk_successor(new_frame)]

        case jvm.Binary(type=t, operant=op):
            # pop order preserved: v2 = top, v1 = next
            nf = deepcopy(frame)
            new_const = deepcopy(constraints)
            
            n2 = nf.stack.pop()
            n1 = nf.stack.pop()
            
            if n1.startswith("stack"):
                v1 = new_const.pop(n1)
            else:
                v1 = constraints[n1]
                
            if n2. startswith("stack"):
                v2 = new_const.pop(n2)
            else:
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
            
            new_const = deepcopy(constraints)
            new_const[res_name] = res
            
            nf.stack.push(res_name)
            nf.pc += 1
            
            return [mk_successor(nf, new_const)]

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
            nf = deepcopy(frame)
            var_name = nf.stack.pop()            
            targets = conditional(nf=nf, n1=var_name, cond=opr.condition)            
                
            return targets

        case jvm.New(offset, classname):
            if classname == jvm.ClassName("java/lang/AssertionError"):
                return ["assertion error"]
            # otherwise continue
            new_frame = deepcopy(frame)
            new_frame.pc += 1
            return [mk_successor(new_frame)]

        case jvm.If():
            # two-operand comparison
            nf = deepcopy(frame)
            
            n2 = nf.stack.pop()
            n1 = nf.stack.pop()
            
            return conditional(nf=nf, n1=n1, cond=opr.condition, n2=n2)
        
        case jvm.Store(index=i):
            nf = deepcopy(frame)
            v_name = nf.stack.pop()
            v = constraints[v_name]
            
            new_const = deepcopy(constraints)
            
            local_name = nf.locals.get(i)
            
            if local_name is None:
                local_name = f"local_{i}"
                nf.locals[i] = local_name
            
            new_const[local_name] = v
            
            if not local_name.startswith("arg"):
                dead_store[i] = opr
            
            nf.pc += 1
            
            return [mk_successor(nf, new_const)]
        
        case jvm.Goto(target=t):
            nf = deepcopy(frame)
            nf.pc = PC(frame.pc.method, t)
            return [mk_successor(nf)]
        
        case jvm.Incr(index=i, amount=a):
            # Load
            var_name = frame.locals.get(i)
            v = constraints[var_name]
            v_i = domain.abstract([a])
            
            # Add
            res = v.add(v_i)
            
            # Store
            const_upd = deepcopy(constraints)
            const_upd[var_name] = res
            
            new_frame = deepcopy(frame)
            new_frame.pc += 1
            
            return [mk_successor(new_frame=new_frame, constraints=const_upd)]
        
        case jvm.NewArray():
            nf = deepcopy(frame)
            size_val = nf.stack.pop()
            size = constraints[size_val]
            size_conc = size.concrete_value()
            
            if size_conc < 0:
                return "negative size"
            
            addr = len(state.heap)

            new_const = deepcopy(constraints)
            new_heap = deepcopy(state.heap)
            
            arr_name = f"arr_{addr}"
            new_heap[addr] = arr_name
            new_const[arr_name] = [addr, size_val]

            nf.stack.push(arr_name)
            nf.pc += 1
            
            return [mk_successor(nf, new_const, new_heap)]
        
        
        case jvm.ArrayStore():
            nf = deepcopy(frame)
            
            value_name = nf.stack.pop()
            index_name = nf.stack.pop()
            arrRe_name = nf.stack.pop()
            
            value = constraints[value_name]
            index = constraints[index_name]
            arrRef = constraints[arrRe_name]

            arr = state.heap[arrRef[0]]
            
            elem_name = f"{arr}_{index.concrete_value()}"
            new_const = deepcopy(constraints)
            new_const[elem_name] = value

            nf.pc += 1
            return [mk_successor(new_frame=nf, constraints=new_const)] 
        
        
        case jvm.ArrayLoad():
            nf = deepcopy(frame)
            
            index_name = frame.stack.pop()
            arr_name = frame.stack.pop()

            index = constraints[index_name].concrete_value()
            addr = constraints[arr_name][0]

            arr = state.heap[addr]

            name = f"{arr}_{index}"
            val = constraints[name]

            nf.stack.push(val)
            nf.pc += 1
            return [mk_successor(nf)] 
            
        case jvm.ArrayLength():
            nf = deepcopy(frame)
            
            arr_name = nf.stack.pop()
            length = constraints[arr_name][1]
            
            nf.stack.push(length)
            nf.pc += 1
            return [mk_successor(nf)]
        
        case jvm.CompareFloating(type=t, onnan=on):
            nf = deepcopy(frame)
            
            n2 = nf.stack.pop()
            n1 = nf.stack.pop()
            
            v1 = constraints[n1]
            v2 = constraints[n2]
            
            res = v1.compare_floating(v2)
            
            cmp_res = FloatCmpResult(
                left_name=n1,
                right_name=n2,
                possible_rels=frozenset(res),
                onnan=on,
            )
            
            new_const = deepcopy(constraints)
            new_name = f"stack_{len(nf.stack.items)}"
                
            new_const[new_name] = cmp_res
            res_frame = deepcopy(nf)
            res_frame.stack.push(new_name)
            res_frame.pc += 1
            
            return [mk_successor(new_frame=res_frame, constraints=new_const)]
                
        

def manystep[AV](sts: StateSet[AV], domain: type[AV]) -> Iterable[AState[AV] | str]:
    states = []
    for state in sts.per_instruction():
        next_states = step(state, domain)
        if next_states is not None:
            states.extend(next_states)
    return states


def initialstate_from_method[AV](methodid: jvm.AbsMethodID, domain: type[AV]) -> StateSet[AV]:
    init_pc = PC(methodid, 0)
    start_frame = PerVarFrame[AV](locals={}, stack=Stack.empty(), pc=init_pc) # New frame, with the method's starting PC
    params = methodid.extension.params
    constraints = {}
    
    for i, p in enumerate(params):
        name = f"arg_{i}"
        dead_arg[i] = p
        constraints[name] = domain.top()
        start_frame.locals[i] = name
    
    state = AState[AV](heap={}, frames=Stack.empty().push(start_frame), constraints=constraints)
    
    return StateSet[AV](
        per_inst={start_frame.pc: state},
        needswork={start_frame.pc}
    )

# ------- ANALYSIS BEGIN ---------

DOMAIN = Interval
bc = Bytecode(jpamb.Suite(), dict())

def static_bytecode_analysis(method_list: list[str]):
    
    logger.debug(f"Starting Bytecode Analysis...")
    
    unreachable_offset_by_method: dict[str, list[int]] = dict()
    dead_args_mapping: dict[str, list[int]] = dict()
    
    for m in method_list:
        method = jvm.AbsMethodID.decode(m)
        
        logger.debug(f"Currently analysing method: {method.extension.name}")
        
        sts = initialstate_from_method(method, DOMAIN)
        all_ops = list(_suite.method_opcodes(method))
        
        final = set()
        
        # Unbounded Static Analysis
        while sts.needswork:
            for s in manystep(sts, DOMAIN):
                if isinstance(s, str):
                    final.add(s)
                else:
                    sts |= s
                    
        not_hit = [idx for idx, x in enumerate(all_ops) if x not in op_hit]

        
        dead_store_ops = [idx for idx, x in enumerate(all_ops) if x in dead_store.values()]
        not_hit.extend(dead_store_ops)
        
        
        unreachable_offset_by_method[method.methodid.name] = not_hit
        dead_args_mapping[method.methodid.name] = list(dead_arg.keys())
        
        op_hit.clear()
        dead_arg.clear()
        dead_store.clear()
        
    logger.debug(unreachable_offset_by_method)
        
    with open("target/decompiled/jpamb/cases/Bloated.json", "r", encoding="utf-8") as f:
        data = json.load(f)
        json_data = dead_indices_to_lines_in_class(data, unreachable_offset_by_method, dead_args_mapping)
        logger.debug(json.dumps(json_data, indent=4))
        return json_data







    



