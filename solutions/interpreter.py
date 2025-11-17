import jpamb
from jpamb import jvm
from dataclasses import dataclass

import sys
from loguru import logger

logger.remove()
logger.add(sys.stderr, format="[{level}] {message}")

methodid, input = jpamb.getcase()


@dataclass
class PC:
    method: jvm.AbsMethodID
    offset: int

    def __iadd__(self, delta):
        self.offset += delta
        return self

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

"""Added mul, add, sub, rem, if, ifz, and store for ints. Not sure if i need NewArray, Dup, ArrayStore, ArrayLoad, ArrayLength, Cast, New, Throw, Goto and/or Invoke """
def step(state: State) -> State | str:
    assert isinstance(state, State), f"expected frame but got {state}"
    frame = state.frames.peek()
    opr = bc[frame.pc]
    logger.debug(f"STEP {opr}\n{state}")
    match opr:
        case jvm.Push(value=v):
            frame.stack.push(v)
            frame.pc += 1
            return state
# new array push        
        case jvm.NewArray(element_type = t):
            size_val = frame.stack.pop()
            assert size_val.type is jvm.Int()
            size = size_val.value
            if size < 0:
                return "negative size"
            
            addr = len(state.heap)

            #if isinstance(t, jvm.Int):
            if t ==jvm.Value():
                default = jvm.Value.int(0)
            #elif t == jvm.Value.Boolean(False)
            else:
                default = jvm.Value(jvm.Reference(), None)
            
            arr = [default for _ in range(size)]

            state.heap[addr] = addr

            frame.stack.push(jvm.Value(jvm.Reference(), addr))
            frame.pc += 1
            return state
# array load
        case jvm.ArrayLoad(element_type=t):
            index = frame.stack.pop()
            arrRef = frame.stack.pop()

            assert index.type is jvm.Int()
            assert arrRef.type is jvm.Reference()

            arr = state.heap[arrRef.value]
            #assert isinstance(arr, jvm.Value)
            #arr: list[jvm.Value] = state.heap[arrRef.value]

            frame.stack.push(arr[index.value])
            frame.pc += 1
            return state 
        
#array store 
        case jvm.ArrayStore(element_type=t):
            value = frame.stack.pop()
            index = frame.stack.pop()
            arrRef = frame.stack.pop()

            assert index.type is jvm.Int()
            assert arrRef.type is jvm.Reference()

            arr = state.heap[arrRef.value]
            arr[index.value] = value

            frame.pc += 1
            return state 

#array length
        case jvm.ArrayLength():
            arrRef = frame.stack.pop()

            arr = state.heap[arrRef.value]

            frame.stack.push(jvm.Value.int(len(arr)))
            frame.pc += 1
            return state
        
        case jvm.Load(type=jvm.Int(), index=i):
            frame.stack.push(frame.locals[i])
            frame.pc += 1
            return state
        
        case jvm.Load(type=jvm.Boolean(), index=i):
            frame.stack.push(frame.locals[i])
            frame.pc += 1
            return state
        
        case jvm.Store(type=jvm.Int(), index=i):
            v1 = frame.stack.pop()
            assert v1.type is jvm.Int(), f"expected int, but got {v1}"
            frame.locals[i] = v1
            frame.pc += 1
            return state

        case jvm.Store(type=jvm.Boolean(), index=i):
            v1 = frame.stack.pop()
            assert v1.type is jvm.Int(), f"expected bool, but got {v1}"
            frame.locals[i] = v1
            frame.pc += 1
            return state

        case jvm.Binary(type=jvm.Int(), operant=jvm.BinaryOpr.Div):
            v2, v1 = frame.stack.pop(), frame.stack.pop()
            assert v1.type is jvm.Int(), f"expected int, but got {v1}"
            assert v2.type is jvm.Int(), f"expected int, but got {v2}"
            if v2.value == 0:
                return "divide by zero"

            frame.stack.push(jvm.Value.int(v1.value // v2.value))
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
        
        case jvm.If(condition=cond, target=t):
            v2, v1  = frame.stack.pop(), frame.stack.pop()
            assert v1.type is jvm.Int(), f"expected int, but got {v1}"
            assert v2.type is jvm.Int(), f"expected int, but got {v2}"

            assert v1.type is jvm.Boolean(), f"expected bool, but got {v1}"
            assert v2.type is jvm.Boolean(), f"expected bool, but got {v2}"

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


        case jvm.Return(type=jvm.Int()):
            v1 = frame.stack.pop()
            state.frames.pop()
            if state.frames:
                frame = state.frames.peek()
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
                return "ok" \
                    
        case a:
            raise NotImplementedError(f"Don't know how to handle: {a!r}")


frame = Frame.from_method(methodid)
for i, v in enumerate(input.values):
    frame.locals[i] = v

state = State({}, Stack.empty().push(frame))

for x in range(1000):
    state = step(state)
    if isinstance(state, str):
        print(state)
        break
else:
    print("*")
