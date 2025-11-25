import jpamb
from jpamb import jvm
from dataclasses import dataclass
from jpamb.jvm.base import MethodID
import sys
from loguru import logger
import random

logger.remove()
logger.add(sys.stderr, format="[{level}] {message}")


@dataclass(frozen=True, slots=True)
class PC:
    method: jvm.AbsMethodID
    offset: int

    def __add__(self, delta):
        return PC(self.method, self.offset + delta)

    def __str__(self):
        return f"{self.method}:{self.offset}"


@dataclass
class Bytecode:
    suite: jpamb.Suite
    methods: dict[jvm.AbsMethodID, list[jvm.Opcode]]

    def __getitem__(self, pc: PC) -> jvm.Opcode:
        try:
            opcodes = self.methods[pc.method]
        except KeyError:
            opcodes = list(self.suite.method_opcodes(pc.method))
            self.methods[pc.method] = opcodes

        return opcodes[pc.offset]


@dataclass
class Stack[T]:
    items: list[T]

    def __bool__(self) -> bool:
        return len(self.items) > 0

    @classmethod
    def empty(cls):
        return cls([])

    def peek(self) -> T:
        return self.items[-1]

    def pop(self) -> T:
        return self.items.pop(-1)

    def push(self, value):
        self.items.append(value)
        return self

    def __str__(self):
        if not self:
            return "ϵ"
        return "".join(f"{v}" for v in self.items)


suite = jpamb.Suite()
bc = Bytecode(suite, dict())


@dataclass
class Frame:
    locals: dict[int, jvm.Value]
    stack: Stack[jvm.Value]
    pc: PC

    def __str__(self):
        locals = ", ".join(f"{k}:{v}" for k, v in sorted(self.locals.items()))
        return f"<{{{locals}}}, {self.stack}, {self.pc}>"

    def from_method(method: jvm.AbsMethodID) -> "Frame":
        return Frame({}, Stack.empty(), PC(method, 0))


@dataclass
class State:
    heap: dict[int, jvm.Value]
    frames: Stack[Frame]

    def __str__(self):
        return f"{self.heap} {self.frames}"
    
# def newHeapAddr(heap: dict[int, list[jvm.Value]]) -> int:
#     if not heap:
#         return 1
#     return max(heap.keys()) + 1

def arrayType(t) -> jvm.Value:
    if isinstance(t, jvm.Int):
        return jvm.Value.int(0)
    elif isinstance(t, jvm.Boolean):
        return jvm.Value.boolean(False)
    elif isinstance(t,jvm.Float):
        return jvm.Value(jvm.Float(), 0.0)
    elif isinstance(t, jvm.Long):
        return jvm.Value(jvm.Long(), 0)
    elif isinstance(t, jvm.Double):
        return jvm.Value(jvm.Double(), 0.0)
    elif isinstance(t, jvm.Char):
        return jvm.Value.char('\x00')
    elif isinstance(t, jvm.Short):
        return jvm.Value(jvm.Short(), 0)
    elif isinstance(t, jvm.Byte):
        return jvm.Value(jvm.Byte(), 0)
    elif isinstance(t, jvm.Reference):
        return jvm.Value(jvm.Reference(), None)
    raise NotImplementedError(f"new array default not implemented for type {t}")

"""Added mul, add, sub, rem, if, ifz, and store for ints. Not sure if i need NewArray, Dup, ArrayStore, ArrayLoad, ArrayLength, Cast, New, Throw, Goto and/or Invoke """
def step(state: State) -> State | str:
    assert isinstance(state, State), f"expected frame but got {state}"
    frame = state.frames.peek()
    opr = bc[frame.pc]
    logger.debug(f"STEP {opr}\n{state}")
    match opr:
# Push
        case jvm.Push(value=v):
            #Positiver space: v must always be a JVM value:
            assert isinstance(v,jvm.Value), f"Expected JVM value, got {v!r}"
            frame.stack.push(v)
            frame.pc += 1
            return state

# new array push        
        case jvm.NewArray(type = t):
            size_val = frame.stack.pop()
            assert size_val.type is jvm.Int(), f"new array must be int, got {size_val}"
            size = size_val.value
            if size < 0:
                return "negative size"
            
            addr = len(state.heap)
            default = arrayType(t)            
            #addr = newHeapAddr(state.heap)

            # if isinstance(t, jvm.Int):
            #     default = jvm.Value.int(0)
            # # if t ==jvm.Value():
            # #     default = jvm.Value.int(0)
            # elif isinstance(t, jvm.Boolean):
            #     default = jvm.Value.boolean(False)
            # elif isinstance(t,jvm.Float):
            #     default = jvm.Value(jvm.Float(), 0.0)
            # elif isinstance(t, jvm.Long):
            #     default = jvm.Value(jvm.Long(), 0)
            # elif isinstance(t, jvm.Double):
            #     default = jvm.Value(jvm.Double(), 0.0)
            # elif isinstance(t, jvm.Char):
            #     default = jvm.Value.char('\x00')
            # else:
            #     default = jvm.Value(jvm.Reference(), None)
            
            arr = [default for _ in range(size)]
            state.heap[addr] = arr

            frame.stack.push(jvm.Value(jvm.Reference(), addr))
            frame.pc += 1
            return state
# array load
        case jvm.ArrayLoad(type=t):
            index = frame.stack.pop()
            arrRef = frame.stack.pop()

            assert index.type is jvm.Int(), f"array index must be int, got {index}"
            assert arrRef.type is jvm.Reference(), f"array ref must be reference, got {arrRef}"

            #arr = state.heap.get[arrRef.value]
            arr = state.heap[arrRef.value]
            #assert isinstance(arr, jvm.Value)
            #arr: list[jvm.Value] = state.heap[arrRef.value]
            if index.value <0 or index.value >= len(arr):
                return "array out of bounds"

            frame.stack.push(arr[index.value])
            frame.pc += 1
            return state 
        
#array store 
        case jvm.ArrayStore(element_type=t):
            value = frame.stack.pop()
            index = frame.stack.pop()
            arrRef = frame.stack.pop()

            assert index.type is jvm.Int(), f"array index must be int, got {index}"
            assert arrRef.type is jvm.Reference(), f"array ref must be reference, got {arrRef}"

            arr = state.heap[arrRef.value]
            if isinstance(t, jvm.Int):
                assert value.type is jvm.Int(), f"expected int element, got {value}"
            elif isinstance(t, jvm.Boolean):
                assert value.type is jvm.Boolean(), f"expected boolean element, got {value}"
            elif isinstance(t, jvm.Float):
                assert value.type is jvm.Float(), f"expected float element, got {value}"
            elif isinstance(t, jvm.Long):
                assert value.type is jvm.Long(), f"expected long element, got {value}"
            elif isinstance(t, jvm.Double):
                assert value.type is jvm.Double(), f"expected double element, got {value}"
            elif isinstance(t, jvm.Char):
                assert value.type is jvm.Char(), f"expected char element, got {value}"
            elif isinstance(t, jvm.Short):
                assert value.type is jvm.Short(), f"expected char element, got {value}"
            elif isinstance(t, jvm.Byte):
                assert value.type is jvm.Byte(), f"expected byte element, got {value}"
            else:
                assert value.type is jvm.Reference(), f"expected reference element, got {value}"
            # if arr is None:
            #     return "null"
            arr[index.value] = value
            frame.pc += 1
            return state 

#array length
        case jvm.ArrayLength():
            arrRef = frame.stack.pop()
            assert arrRef.type is jvm.Reference(), f"array length needs reference, got {arrRef}"
            arr = state.heap.get[arrRef.value]
            if arr is None:
                return "null"

            frame.stack.push(jvm.Value.int(len(arr)))
            frame.pc += 1
            return state
# Load        
        
        case jvm.Load(type=jvm.Int(), index=i):
            frame.stack.push(frame.locals[i])
            frame.pc += 1
            return state
        
        case jvm.Dup():    # <--- NEW (dup)
            v = frame.stack.peek()
            #v must be a JVM Value (We didnt put the assertion at the start, bc v was not defined yet)
            assert isinstance(v,jvm.Value), f"Expected JVM value, got {v!r}"
            frame.stack.push(v)
            frame.pc += 1
            return state
        
        
        case jvm.Load(type=jvm.Boolean(), index=i):
            frame.stack.push(frame.locals[i])
            frame.pc += 1
            return state
        
        case jvm.Load(type=jvm.Float(), index=i):
            frame.stack.push(frame.locals[i])
            frame.pc += 1
            return state
#double check as longs and doubles take up 2 spaces on the stack        
        case jvm.Load(type=jvm.Long(), index=i):
            frame.stack.push(frame.locals[i])
            frame.pc += 1
            return state
        
        case jvm.Load(type=jvm.Double(), index=i):
            frame.stack.push(frame.locals[i])
            frame.pc += 1
            return state
        
        case jvm.Load(type=jvm.Reference(), index=i):
            frame.stack.push(frame.locals[i])
            frame.pc += 1
            return state
# Store        
        case jvm.Store(type=jvm.Int(), index=i):
            v1 = frame.stack.pop()
            assert v1.type is jvm.Int(), f"expected int, but got {v1}"
            frame.locals[i] = v1
            frame.pc += 1
            return state

        case jvm.Store(type=jvm.Boolean(), index=i):
            v1 = frame.stack.pop()
            assert v1.type is jvm.Boolean(), f"expected bool, but got {v1}"
            frame.locals[i] = v1
            frame.pc += 1
            return state
        
        case jvm.Store(type=jvm.Float(), index=i):
            v1 = frame.stack.pop()
            assert v1.type is jvm.Float(), f"expected float, but got {v1}"
            frame.locals[i] = v1
            frame.pc += 1
            return state
#again check long and doubles since they take up 2 spaces on stack        
        case jvm.Store(type=jvm.Long(), index=i):
            v1 = frame.stack.pop()
            assert v1.type is jvm.Long(), f"expected long, but got {v1}"
            frame.locals[i] = v1
            frame.pc += 1
            return state
        
        case jvm.Store(type=jvm.Double(), index=i):
            v1 =  frame.stack.pop()
            assert v1.type is jvm.Double(), f"expected double, but got {v1}"
            frame.locals[i] = v1
            frame.pc += 1
            return state
        
        case jvm.Store(type=jvm.Reference(), index=i):
            v1 = frame.stack.pop()
            assert isinstance(v1.type, jvm.Type), f"expected reference, but got {v1}"
            frame.locals[i] = v1
            frame.pc += 1
            return state
# Binary 
        case jvm.Binary(type=jvm.Int(), operant=op):
            v2, v1 = frame.stack.pop(), frame.stack.pop()
            assert v1.type is jvm.Int(), f"expected int, but got {v1}"
            assert v2.type is jvm.Int(), f"expected int, but got {v2}"

            if op == jvm.BinaryOpr.Add:
                result = v1.value +v2.value
            elif op == jvm.BinaryOpr.Div:
                if v2.value!=0:
                    result = v1.value // v2.value
                else:
                     return "divide by zero"
            elif op == jvm.BinaryOpr.Mul:
                result =v1.value *v2.value 
            elif op == jvm.BinaryOpr.Rem:
                result = v1.value % v2.value
            elif op == jvm.BinaryOpr.Sub:
                result =v1.value -v2. value
            
            frame.stack.push(jvm.Value.int(result))
            frame.pc += 1

            return state
        
        
        case jvm.Binary(type=jvm.Int(), operant=jvm.BinaryOpr.Mul):
            v2, v1 = frame.stack.pop(), frame.stack.pop()
            assert v1.type is jvm.Int(), f"expected int, but got {v1}"
            assert v2.type is jvm.Int(), f"expected int, but got {v2}"

            frame.stack.push(jvm.Value.int(v1.value * v2.value))
            frame.pc += 1
            return state
        
        case jvm.Binary(type=jvm.Int(), operant=jvm.BinaryOpr.Add):
            v2, v1 = frame.stack.pop(), frame.stack.pop()
            assert v1.type is jvm.Int(), f"expected int, but got {v1}"
            assert v2.type is jvm.Int(), f"expected int, but got {v2}"

            frame.stack.push(jvm.Value.int(v1.value + v2.value))
            frame.pc += 1
            return state
        
        case jvm.Binary(type=jvm.Int(), operant=jvm.BinaryOpr.Sub):
            v2, v1 = frame.stack.pop(), frame.stack.pop()
            assert v1.type is jvm.Int(), f"expected int, but got {v1}"
            assert v1.type is jvm.Int(), f"expected int, but got {v2}"

            frame.stack.push(jvm.Value.int(v1.value - v2.value))
            frame.pc += 1
            return state
        
        case jvm.Binary(type=jvm.Int(), operant=jvm.BinaryOpr.Rem):
            v2, v1 = frame.stack.pop(), frame.stack.pop()
            assert v1.type is jvm.Int(), f'expected int, but got {v1}'
            assert v2.type is jvm.Int(), f"expected int, but got {v2}"
            if v2.value == 0:
                return "divide by zero"

            frame.stack.push(jvm.Value.int(v1.value % v2.value))
            frame.pc += 1
            return state

        case jvm.Binary(type=jvm.Float(), operant=jvm.BinaryOpr.Add):
            v2, v1 = frame.stack.pop(), frame.stack.pop()
            assert v1.type is jvm.Float(), f'expected float, but got {v1}'
            assert v2.type is jvm.Float(), f"expected float, but got {v2}"

            frame.stack.push(jvm.Value(jvm.Float(), v1.value + v2.value))
            frame.pc += 1
            return state
        
        case jvm.Binary(type=jvm.Float(), operant=jvm.BinaryOpr.Sub):
            v2, v1 = frame.stack.pop(), frame.stack.pop()
            assert v1.type is jvm.Float(), f'expected float, but got {v1}'
            assert v2.type is jvm.Float(), f"expected float, but got {v2}"

            frame.stack.push(jvm.Value(jvm.Float(), float(v1.value - v2.value)))
            frame.pc += 1
            return state
        
        case jvm.Binary(type=jvm.Float(), operant=jvm.BinaryOpr.Mul):
            v2, v1 = frame.stack.pop(), frame.stack.pop()
            assert v1.type is jvm.Float(), f'expected float, but got {v1}'
            assert v2.type is jvm.Float(), f"expected float, but got {v2}"

            frame.stack.push(jvm.Value(jvm.Float(), float(v1.value * v2.value)))
            frame.pc += 1
            return state
        
        case jvm.Binary(type=jvm.Float(), operant=jvm.BinaryOpr.Div):
            v2, v1 = frame.stack.pop(), frame.stack.pop()
            assert v1.type is jvm.Float(), f'expected float, but got {v1}'
            assert v2.type is jvm.Float(), f"expected float, but got {v2}"
            if v2.value == 0:
                return "divide by zero"

            frame.stack.push(jvm.Value(jvm.Float(), float(v1.value / v2.value)))
            frame.pc += 1
            return state
        
        case jvm.Binary(type=jvm.Float(), operant=jvm.BinaryOpr.Rem):
            v2, v1 = frame.stack.pop(), frame.stack.pop()
            assert v1.type is jvm.Float(), f'expected float, but got {v1}'
            assert v2.type is jvm.Float(), f"expected float, but got {v2}"
            if v2.value == 0:
                return "divide by zero"

            frame.stack.push(jvm.Value(jvm.Float(), float(v1.value % v2.value)))
            frame.pc += 1
            return state
# long binary ops (simplified single-slot representation)        
        case jvm.Binary(type=jvm.Long(), operant=jvm.BinaryOpr.Add):
            v2, v1 = frame.stack.pop(), frame.stack.pop()
            assert v1.type is jvm.Long(), f'expected long, but got {v1}'
            assert v2.type is jvm.Long(), f"expected long, but got {v2}"

            frame.stack.push(jvm.Value(jvm.Long(), int(v1.value + v2.value)))
            frame.pc += 1
            return state
        
        case jvm.Binary(type=jvm.Long(), operant=jvm.BinaryOpr.Sub):
            v2, v1 = frame.stack.pop(), frame.stack.pop()
            assert v1.type is jvm.Long(), f'expected long, but got {v1}'
            assert v2.type is jvm.Long(), f"expected long, but got {v2}"

            frame.stack.push(jvm.Value(jvm.Long(), int(v1.value - v2.value)))
            frame.pc += 1
            return state
        
        case jvm.Binary(type=jvm.Long(), operant=jvm.BinaryOpr.Mul):
            v2, v1 = frame.stack.pop(), frame.stack.pop()
            assert v1.type is jvm.Long(), f'expected long, but got {v1}'
            assert v2.type is jvm.Long(), f"expected long, but got {v2}"

            frame.stack.push(jvm.Value(jvm.Long(), int(v1.value * v2.value)))
            frame.pc += 1
            return state
        
        case jvm.Binary(type=jvm.Long(), operant=jvm.BinaryOpr.Div):
            v2, v1 = frame.stack.pop(), frame.stack.pop()
            assert v1.type is jvm.Long(), f'expected long, but got {v1}'
            assert v2.type is jvm.Long(), f"expected long, but got {v2}"
            if v2.value == 0:
                return "divide by zero"

            frame.stack.push(jvm.Value(jvm.Long(), int(v1.value / v2.value)))
            frame.pc += 1
            return state
        
        case jvm.Binary(type=jvm.Long(), operant=jvm.BinaryOpr.Rem):
            v2, v1 = frame.stack.pop(), frame.stack.pop()
            assert v1.type is jvm.Long(), f'expected long, but got {v1}'
            assert v2.type is jvm.Long(), f"expected long, but got {v2}"
            if v2.value == 0:
                return "divide by zero"

            frame.stack.push(jvm.Value(jvm.Long(), int(v1.value % v2.value)))
            frame.pc += 1
            return state
# double binary ops (use python float; simplified)        
        case jvm.Binary(type=jvm.Double(), operant=jvm.BinaryOpr.Add):
            v2, v1 = frame.stack.pop(), frame.stack.pop()
            assert v1.type is jvm.Double(), f'expected double, but got {v1}'
            assert v2.type is jvm.Double(), f"expected double, but got {v2}"

            frame.stack.push(jvm.Value(jvm.Double(), float(v1.value + v2.value)))
            frame.pc += 1
            return state
        
        case jvm.Binary(type=jvm.Double(), operant=jvm.BinaryOpr.Sub):
            v2, v1 = frame.stack.pop(), frame.stack.pop()
            assert v1.type is jvm.Double(), f'expected double, but got {v1}'
            assert v2.type is jvm.Double(), f"expected double, but got {v2}"

            frame.stack.push(jvm.Value(jvm.Double(), float(v1.value - v2.value)))
            frame.pc += 1
            return state
        
        case jvm.Binary(type=jvm.Double(), operant=jvm.BinaryOpr.Mul):
            v2, v1 = frame.stack.pop(), frame.stack.pop()
            assert v1.type is jvm.Double(), f'expected double, but got {v1}'
            assert v2.type is jvm.Double(), f"expected double, but got {v2}"

            frame.stack.push(jvm.Value(jvm.Double(), float(v1.value * v2.value)))
            frame.pc += 1
            return state
        
        case jvm.Binary(type=jvm.Double(), operant=jvm.BinaryOpr.Div):
            v2, v1 = frame.stack.pop(), frame.stack.pop()
            assert v1.type is jvm.Double(), f'expected double, but got {v1}'
            assert v2.type is jvm.Double(), f"expected double, but got {v2}"
            if v2.value == 0:
                return "divide by zero"

            frame.stack.push(jvm.Value(jvm.Double(), float(v1.value / v2.value)))
            frame.pc += 1
            return state
        
        case jvm.Binary(type=jvm.Double(), operant=jvm.BinaryOpr.Rem):
            v2, v1 = frame.stack.pop(), frame.stack.pop()
            assert v1.type is jvm.Double(), f'expected double, but got {v1}'
            assert v2.type is jvm.Double(), f"expected double, but got {v2}"
            if v2.value == 0:
                return "divide by zero"

            frame.stack.push(jvm.Value(jvm.Double(), float(v1.value % v2.value)))
            frame.pc += 1
            return state
        
# Conditionals        
        case jvm.If(condition=cond, target=t):
            v2, v1  = frame.stack.pop(), frame.stack.pop()
            if v1.type is jvm.Reference() and v2.type is jvm.Reference():
                match cond:
                    case "is":
                        jump = (v1.value == v2.value)
                    case "isnot":
                        jump = (v1.value != v2.value)
                    case _:
                        raise NotImplementedError(f"Unknown ref condition: {cond}")
            
                    
                # assert v1.type is jvm.Int(), f"expected int, but got {v1}"
                # assert v2.type is jvm.Int(), f"expected int, but got {v2}"

                # assert v1.type is jvm.Boolean(), f"expected bool, but got {v1}"
                # assert v2.type is jvm.Boolean(), f"expected bool, but got {v2}"

            elif isinstance(v1.type, (jvm.Int, jvm.Boolean, jvm.Float, jvm.Double, jvm.Long)):
                match cond:
                    case "eq": jump = (v1.value == v2.value)
                    case "ne": jump = (v1.value != v2.value)
                    case "lt": jump = (v1.value < v2.value)
                    case "le": jump = (v1.value <= v2.value)
                    case "gt": jump = (v1.value > v2.value)
                    case "ge": jump = (v1.value >= v2.value)
                    case _:
                        raise NotImplementedError(f"Unknown condition: {cond}")

            if jump:
                frame.pc = PC(frame.pc.method, t)
            else:
                frame.pc += 1

            return state

        case jvm.Ifz(condition=cond, target=t):
            v1 = frame.stack.pop()
            if v1.type is jvm.Reference():
                match cond:
                    case "is":
                        jump = (v1.value is None)
                    case "isnot":
                        jump = (v1.value is not None)
                    case _:
                        raise NotImplementedError(f"Unknown condition: {cond}")
            
            elif isinstance(v1.type, (jvm.Int, jvm.Boolean, jvm.Float, jvm.Double, jvm.Long)):        
                assert v1.type is jvm.Int(), f"expected int, but got {v1}"
                assert v1.type is jvm.Boolean(), f"expected bool, but got {v1}"

                match cond:
                    case "eq": jump = (v1.value == 0)
                    case "ne": jump = (v1.value != 0)
                    case "lt": jump = (v1.value < 0)
                    case "le": jump = (v1.value <= 0)
                    case "gt": jump = (v1.value > 0)
                    case "ge": jump = (v1.value >= 0)
                    case _:
                        raise NotImplementedError(f"Unknown condition: {cond}")

            if jump:
                frame.pc = PC(frame.pc.method, t)
            else:
                frame.pc += 1
            return state 

        case jvm.Goto(target=t):
            frame.pc = PC(frame.pc.method, t)
            return state                


        


        case jvm.Return(type=t):
            #t is a type: None, jvm.Int(), jvm.Boolean(). It is not a null, int or boolean (these are the methods that it returns)
            #The return instruction can return a void or a value
            assert t is None or isinstance(t,jvm.Type), f"Expected JVM type or None, got a {t!r}"

            if t:
                v1 = frame.stack.pop()
                #The returned value must be a JVM Value
                assert isinstance(v1,jvm.Value), f"Expected JVM value, got a {v1!r}"

            state.frames.pop()
            if state.frames:
                frame = state.frames.peek()
                if t:
                    frame.stack.push(v1)
                frame.pc += 1
                return state
            else:
                return "ok"
            
        case jvm.Return(type=jvm.Boolean()):
            v1 = frame.stack.pop()
            state.frames.pop()
            if state.frames:
                frame = state.frames.peek()
                frame.stack.push(v1)
                return state
            else:
                return "ok" 
            
        case jvm.Return(type=jvm.Float()):
            v1 = frame.stack.pop()
            state.frames.pop()
            if state.frames:
                frame = state.frames.peek()
                frame.stack.push(v1)
                return state
            else:
                return "ok" 
            
        case jvm.Return(type=jvm.Long()):
            v1 = frame.stack.pop()
            state.frames.pop()
            if state.frames:
                frame = state.frames.peek()
                frame.stack.push(v1)
                return state
            else:
                return "ok" 
            
        case jvm.Return(type=jvm.Double()):
            v1 = frame.stack.pop()
            state.frames.pop()
            if state.frames:
                frame = state.frames.peek()
                frame.stack.push(v1)
                return state
            else:
                return "ok" 
                    

                 
            
        case jvm.Get(field=field):
            assert field.extension.name == "$assertionsDisabled", f"should be $assertionsDisabled but was {field!r}"
            frame.stack.push(jvm.Value.int(0))
            frame.pc += 1
            return state


        case jvm.Ifz():
            v = frame.stack.pop()  #pop the top value from the stack
            assert isinstance(v,jvm.Value), f"Expected JVM value, got a {v!r}"
            
            cond = opr.condition
            assert cond in {"eq", "ne", "lt", "le", "gt", "ge"}, f"Unexpected condition {cond!r}"


            if cond == "ne":
                if v != jvm.Value.int(0):
                    frame.pc.offset = opr.target
                else:
                    frame.pc += 1
            if cond =="eq":
                if v==jvm.Value.int(0):
                    frame.pc.offset = opr.target
                else:
                    frame.pc +=1
            if cond == "lt":
                if v < jvm.Value.int(0):
                    frame.pc.offset = opr.target
                else:
                    frame.pc += 1
            if cond == "le":
                if v<=jvm.Value.int(0):
                    frame.pc.offset = opr.target
                else:
                    frame.pc += 1
            if cond == "gt":
                if v > jvm.Value.int(0):
                    frame.pc.offset = opr.target
                else:
                    frame.pc += 1
            if cond == "ge":
                if v >= jvm.Value.int(0):
                    frame.pc.offset = opr.target
                else:
                    frame.pc +=1
            return state
        

        
        case jvm.New(offset, classname):
            
            assert classname == jvm.ClassName("java/lang/AssertionError")

            return "assertion error"
        


        case jvm.If():
            v2 = frame.stack.pop()
            v1 = frame.stack.pop()
            cond = opr.condition

            assert isinstance(v1,jvm.Value), f"Expected JVM value, got a {v1!r}"
            assert isinstance(v2,jvm.Value), f"Expected JVM value, got a {v2!r}"
            assert cond in {"eq", "ne", "lt", "le", "gt", "ge"}, f"Unexpected condition {cond!r}"

            if cond == "ne":
                if v1!=v2:
                    frame.pc.offset = opr.target
                else:
                    frame.pc += 1
            if cond =="eq":
                if v1==v2:
                    frame.pc.offset = opr.target
                else:
                    frame.pc +=1
            if cond == "lt":
                if v1<v2:
                    frame.pc.offset = opr.target
                else:
                    frame.pc += 1
            if cond == "le":
                if v1<=v2:
                    frame.pc.offset = opr.target
                else:
                    frame.pc += 1
            if cond == "gt":
                if v1 > v2:
                    frame.pc.offset = opr.target
                else:
                    frame.pc += 1
            if cond == "ge":
                if v1 >= v2:
                    frame.pc.offset = opr.target
                else:
                    frame.pc +=1
            return state

    
        
        case a:
            raise NotImplementedError(f"Don't know how to handle: {a!r}")







# #RUN RANDOM ANALYSIS -----------------------------------------------------------------

# def run_random_analysis(methodid, interpreter, num_trials=100):
#     """
#     Run dynamic analysis with random inputs.
    
#     - methodid: the function/method to analyze
#     - interpreter: your interpreter function that executes a method
#     - num_trials: how many random inputs to try
#     """
#     found_query_behavior = False  # Track if we ever see the query behavior

#     for _ in range(num_trials):
#         # 1. Generate random inputs based on method parameters
#         inputs = []
#         for param_type in methodid.extension.params:
#             if param_type == "int":
#                 # example: random integers from -10 to 10
#                 inputs.append(random.randint(-10, 10))
#             elif param_type == "bool":
#                 inputs.append(random.choice([True, False]))
#             # You can add more types if needed

#         # 2. Run the interpreter with these inputs
#         result = interpreter(methodid, inputs)

#         # 3. Check for query behavior
#         # Replace this with the actual condition you consider a "query behavior"
#         if result == "query_detected":  # <-- example
#             found_query_behavior = True
#             break  # stop early if you already found it

#     # 4. Emit percentages
#     if found_query_behavior:
#         print(f"{methodid.extension.name}: 100%")  # behavior observed
#     else:
#         print(f"{methodid.extension.name}: 50%")   # behavior not observed


# #END ------------------------------------------------------------------------------------










