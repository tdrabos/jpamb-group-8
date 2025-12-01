#!/usr/bin/env python3
import random
import jpamb
from jpamb import jvm
from debloater.interpreter import Frame, State, Stack, step #Interpreter  # your interpreter
import sys
# to use the random input generator
from debloater.syntactic.combined_input_generator import CombinedInputGenerator


# TODO: Lets only use this class to do the dynamic analyzer.
# We have agreed on 2 analysis: 
# 1. Checks if the program runs after debloating (must have)
# 2. Checks the program based on coverage (nice to have, but if no time, we can omit)
# TEST with input: Java source file, with NO bloated code (pick some from the Bloated.java and remove bloated code by hand then run analysis)
# Use random input for test, while the input selector is not available
# When it's ready, integrate with input selector
# Expected outcome: check if runs with some test values all return ok final state
# If not, then flag the function

# ANOTHER TODO: 
# Check runs with the new types (float, bool, array)
#methodid, input = jpamb.getcase()
#interp = Interpreter()

# frame = Frame.from_method(methodid)
# state = State({}, Stack.empty().push(frame))

#trying to get input generator to work
# the random input generator returns strings and the dynamic analyzer uses JVM runtime values
def converStringToJvmValue(text: str, param_type, state):
    if text == "null":
        return jvm.Value(jvm.Reference(param_type), None)
    
    #for bools
    if isinstance(param_type, jvm.Boolean): 
        return jvm.Value.int(1 if text.lower() == "true" else 0)
    
    #for ints (dont have handling for doubles and longs because they take up two spaces on stack and dont have any byte cases)
    if isinstance(param_type, jvm.Int):
        return jvm.Value.int(int(text))
    
    #for floats
    if isinstance(param_type, jvm.Float):
        if text == "NaN":
            val = float("nan")
        elif text == "Infinity":
            val = float("inf")
        elif text == "- Infinity":
            val = float("-inf")
        else:
            val = float(text)
        return jvm.Value.float(val)

    #dont have any tests for char, doubles, longs, and bytes so i am not making the conversion
    
    #for arrays
    if isinstance(param_type, jvm.Array):
        inner_type = param_type.contains
        raw = text.strip()[1:-1]
        elems_str = [e.strip() for e in raw.split(",")] if raw else []

        heapArr = []
        for e in elems_str:
            val = converStringToJvmValue(e, inner_type, state)
            heapArr.append(val)
        addr = len(state.heap)
        state.heap[addr] = heapArr
        return jvm.Value(jvm.Reference(param_type), addr)
    
    if isinstance(param_type, (jvm.Reference, jvm.Object)):
        return jvm.Value(jvm.Reference(param_type), None)
    try:
        return jvm.Value.int(int(text))
    except Exception:
        raise NotImplementedError(f" Unsupoorted JVM type {param_type}")  

def inputValues(methodid, tuple_of_strings):
    frame = Frame.from_method(methodid)
    state = State({}, Stack.empty().push(frame))

    values =[]
    for idx, text in enumerate(tuple_of_strings):
        param_type = methodid.extension.params[idx]
        v = converStringToJvmValue(text, param_type, state)
        values.append(v)
    return values, state

# GENERATE VALUES: INT, BOOLEAN, FLOATS, ARRAYS:
def gen_value(param_type, state):
    if isinstance(param_type, jvm.Array):
        comp = param_type.component_type
        length = random.randint(1,5)

        elems = [gen_value(comp, state) for _ in range(length)]
        addr = len(state.heap)
        state.heap[addr] = elems
        return jvm.Value(jvm.Reference(param_type), addr)
    
    if isinstance(param_type, jvm.Int) or param_type == "I":
        return random.randint(-10, 10)
    elif isinstance(param_type, jvm.Boolean) or param_type == "Z":
        return random.choice([True, False])
    elif isinstance(param_type, jvm.Float) or param_type == "F":
        return random.uniform(-10.0, 10.0)  # generates a float
    # elif isinstance(param_type, jvm.Array) or param_type == "array":
    #     length = random.randint(0, 5)
# this isnt generic this is a hard coded example    
    # elif param_type == "[C":
    #     chars = ['h', 'e', 'l', 'l', 'o']
    #     heap_arr = [jvm.Value(jvm.Char(), c) for c in chars]
    #     addr = len(state.heap)
    #     state.heap[addr] = heap_arr
        #return jvm.Value(jvm.Reference(jvm.Array(jvm.Char())), addr)
    elif isinstance(param_type, jvm.Reference):
        return jvm.Value(jvm.Reference(), None)
    
    return jvm.Value.int( 0)
    #     return [random.randint(-10, 10) for _ in range(length)]
    # else:
    #     return 0







# FUNCTION IF YOU WANT TO USE RANDOM INPUTS ONLY:
def run_random_dynamic_analysis(methodid, num_trials=100):
    found_query_behavior = False

    for _ in range(num_trials):
        input_values = [gen_value(param) for param in methodid.extension.params]
    
        # Create frame and pre-fill locals
        frame = Frame.from_method(methodid)

        # Fill locals
        for i, v in enumerate(input_values):
            if isinstance(v, bool):
                frame.locals[i] = jvm.Value.int(1 if v else 0)
            elif isinstance(v, float):
                frame.locals[i] = jvm.Value.float(v)
            elif isinstance(v, jvm.Array):
                # Example: store array as a reference, depending on JVM representation
                frame.locals[i] = jvm.Value.array(v) # check because this 
            else:
                frame.locals[i] = jvm.Value.int(v)

        # Run interpreter
        state = State({}, Stack.empty().push(frame))
        for _ in range(1000):
            state = step(state)
            if isinstance(state, str) and state == "divide by zero":
                found_query_behavior = True
                print("divide by zero")
                break

    print("Params for", methodid.extension.name, ":", methodid.extension.params)
    print(f"{methodid.extension.name}: 100%" if found_query_behavior else f"{methodid.extension.name}: 50%")


# FUNCTION IF YOU WANT TO USE INTERESTING VALUES AND RANDOM INPUTS:
# Dynamic analysis using interesting values + random fallback
def run_interesting_dynamic_analysis(methodid: jvm.AbsMethodID, inputs: list[any], num_trials=100):
    # Create frame and pre-fill locals
    frame = Frame.from_method(methodid)
    for i, v in enumerate(inputs):
        if isinstance(v, bool):
            frame.locals[i] = jvm.Value.int(1 if v else 0)
        elif isinstance(v, float):
            frame.locals[i] = jvm.Value.float(v)
        elif isinstance(v, list):
            frame.locals[i] = jvm.Value.array(v)  # adjust depending on your JVM array type
        else:
            frame.locals[i] = jvm.Value.int(v)
    
    # Run interpreter
    state = State({}, Stack.empty().push(frame))

    while isinstance(state, State):
        state = step(state)
        if not isinstance(state, State):
            break
        
    return state


# HELPER FUNCTION to generate small numbers for the run_smallcheck_dynamic_analysis function
def gen_int(depth): 
  yield 0
  for i in range(depth):
    yield (i + 1)
    yield -(i + 1)


# FUNCTION IF YOU WANT TO USE THE SMALL-CHECK IDEA:
def run_smallcheck_dynamic_analysis(methodid, num_trials=100):
    found_query_behavior = False
    int_gen = gen_int(20)  # generator

    for _ in range(num_trials):
        input_values = []

        try:
            for param_type in methodid.extension.params:
                if isinstance(param_type, jvm.Int) or param_type == "I":
                    # may raise StopIteration when exhausted
                    input_values.append(next(int_gen))
                elif isinstance(param_type, jvm.Boolean) or param_type == "Z":
                    input_values.append(random.choice([True, False]))
                else:
                    input_values.append(0)
        except StopIteration:
            print("gen_int exhausted — stopping smallcheck.")
            return  # stop whole analysis 


        # Create frame and pre-fill locals
        frame = Frame.from_method(methodid)

        # fill locals with random values
        for i, v in enumerate(input_values):
            if isinstance(v, bool):
                frame.locals[i] = jvm.Value.int(1 if v else 0)
            else:
                frame.locals[i] = jvm.Value.int(v)


        # Run interpreter
        state = State({}, Stack.empty().push(frame))
        for _ in range(1000):
            state = step(state)
            if isinstance(state, str):
                if state == "divide by zero":  # our custom behaviour
                    found_query_behavior = True
                    print("divide by zero")
                break

    # Print results
    print("Params for", methodid.extension.name, ":", methodid.extension.params)
    print(f"{methodid.extension.name}: 100%" if found_query_behavior else f"{methodid.extension.name}: 50%")

    return state




def makeJvmArray(rawArray, componentType, state):
    heapArr = []
        #iterable = list(rawArray) if isinstance(rawArray, str) else rawArray
    for elem in rawArray:
        if isinstance(componentType, jvm.Char):
            heapArr.append(jvm.Value.char(elem))
        elif isinstance(componentType, jvm.Int):
            heapArr.append(jvm.Value.int(elem))
        elif isinstance(componentType, jvm.Boolean):
            heapArr.append(jvm.Value.boolean(elem))
        elif isinstance(componentType, jvm.Float):
            heapArr.append(jvm.Value(jvm.Float(), float(elem)))
        else:    
            raise NotImplementedError(f"Component type {componentType} not supported ")
    addr = len(state.heap)
    state.heap[addr] =heapArr
        #checking if the loading of arrays from the dynamic_analyzer is the problem
    #print("DEBUGGING Heap keys:", list(state.heap.keys()), "addr:", addr, "heapArr:", heapArr)
    return jvm.Value(jvm.Reference(jvm.Array(componentType)), addr)



# FUNCTION FOR IF YOU WANT TO GET THE COVERAGE:
def run_coverage_guided_analysis(methodid, num_trials=3):
    input_gen = CombinedInputGenerator()
    try:
        method_str = methodid.encoded()
    except Exception:
        try:
            method_str = methodid.encoded()
        except Exception:
            method_str = str(methodid)

    # interesting = [b""]
    coverage_seen = set()
    seeds_queue = []

    try: 
        batch = input_gen.generate_inputs([method_str], 10).get(method_str, [])
    except Exception:
        batch = []
    for i in batch:
        seeds_queue.append(i)
    if not seeds_queue:
        try:
            rand_batch = input_gen.generate_inputs([method_str], 10).get(method_str, [])
            seeds_queue.extend(rand_batch)
        except Exception:
            pass

    trials = 0
    while trials < num_trials and seeds_queue:
        i = seeds_queue.pop(0)
        trials += 1

        # Convert strings -> jvm.Value and create state/frame
        try:
            input_values, state = inputValues(methodid, i)
        except Exception as e:
            # bad conversion; skip this tuple
            print(f"[coverage] conversion error for tuple {i}: {e}")
            continue

        frame = state.frames.peek()
        coverage_seen.add(frame.pc.offset)
        for i, v in enumerate(input_values):
            # if v is already a jvm.Value reference or primitive wrapper, assign directly
            frame.locals[i] = v

        # Run the interpreter and collect coverage
        local_coverage = set()
        for _ in range(2000):
            state = step(state)

            # Track coverage by frame.pc.offset (if available)
            try:
                pc_offset = frame.pc.offset
            except Exception:
                # if frame.pc not available, break out
                break

            if pc_offset not in coverage_seen:
                # new offset discovered
                coverage_seen.add(pc_offset)
                # When new coverage is discovered we request more inputs:
                # call the generator for more inputs and add to queue
                try:
                    more = input_gen.generate_inputs([method_str], 4).get(method_str, [])
                    for m in more:
                        seeds_queue.append(m)
                except Exception:
                    # ignore failures in generator during fuzzing
                    pass

            local_coverage.add(pc_offset)

            # Optional debug
            # print("[DEBUG] frame.pc =", frame.pc)

            if not isinstance(state, State):
                break

        # If we didn't get any coverage from this seed, optionally mutate and requeue
        if not local_coverage:
            # simple mutation: ask for another random input from generator
            try:
                extra = input_gen.generate_inputs([method_str], 1).get(method_str, [])
                if extra:
                    seeds_queue.append(extra[0])
            except Exception:
                pass
            
    all_ops = set(jpamb.Suite().method_opcodes(methodid))
    
    all_offsets = {instr.offset for instr in all_ops}

    #print(f"{methodid.extension.name} coverage-guided: {len(coverage_seen)} offsets seen, paths: {coverage_seen} out of {all_offsets}")
    
    return len(all_offsets.intersection(coverage_seen)) / len(all_offsets) * 100



        ### old implement ###
    # def getComponentType(v):
    #     if len(v) == 0:
    #         return jvm.Int()
    #     firstElem = v[0]
    #     if isinstance(firstElem, str) and len(firstElem) == 1:
    #         return jvm.Char()
    #     elif isinstance(firstElem, int):
    #         return jvm.Int()
    #     elif isinstance(firstElem, bool):
    #         return jvm.Boolean()
    #     elif isinstance(firstElem, float):
    #         return jvm.Float()
    #     else:
    #         raise NotImplementedError(f"Cannot determine array type from {firstElem}")

    # def makeJvmArray(rawArray, componentType, state):
    #     heapArr = []
    #     iterable = list(rawArray) if isinstance(rawArray, str) else rawArray
    #     for elem in iterable:
    #         if isinstance(componentType, jvm.Char):
    #             heapArr.append(jvm.Value.char(elem))
    #         elif isinstance(componentType, jvm.Int):
    #             heapArr.append(jvm.Value.int(elem))
    #         elif isinstance(componentType, jvm.Boolean):
    #             heapArr.append(jvm.Value.boolean(elem))
    #         elif isinstance(componentType, jvm.Float):
    #             heapArr.append(jvm.Value(jvm.Float(), float(elem)))
    #         else:    
    #             raise NotImplementedError(f"Component type {componentType} not supported ")
    #     addr = len(state.heap)
    #     state.heap[addr] =heapArr
    #     #checking if the loading of arrays from the dynamic_analyzer is the problem
    #     print("DEBUGGING Heap keys:", list(state.heap.keys()), "addr:", addr, "heapArr:", heapArr)
    #     return jvm.Value(jvm.Reference(), addr)
    # for _ in range(num_trials):
    #         input_values = [gen_value(param) for param in methodid.extenstion.params]
    #         frame = Frame.from_method(methodid)
        # if interesting:
        #     test_case = interesting.pop(0)
        # else:
        #     test_case = bytes([random.randint(0, 255)])

        # mutated_cases = []
        # for i in range(len(test_case)):
        #     mutated = bytearray(test_case)
        #     mutated[i] = random.randint(0, 255)
        #     mutated_cases.append(bytes(mutated))

        # for mutated in mutated_cases:
        #     frame = Frame.from_method(methodid)
        #     state = State({}, Stack.empty().push(frame))
            
            #input_values = [gen_value(param_type, state) for param_type in methodid.extension.params]

        # for i, v in enumerate(input_values):
        #     if isinstance(v, bool):
        #         frame.locals[i] = jvm.Value.int(1 if v else 0)
        #     elif isinstance(v, float):
        #         frame.locals[i] = jvm.Value.float(v)
        #     elif isinstance(v, jvm.Value) and isinstance(v.type, jvm.Reference):
        #         frame.locals[i] = v
        #     elif isinstance(v, list):
        #         comp_type = getComponentType(v)
        #         frame.locals[i] = makeJvmArray(v, comp_type, state)
        #     else:
        #         frame.locals[i] = jvm.Value.int(v)
                # elif isinstance(v, list):
                #     if len(v) > 0:
                #         firstElem = v[0]
                #         if isinstance(firstElem, str) and len(firstElem) == 1:
                #             componentType = jvm.Char()
                #         elif isinstance(firstElem, int):
                #             componentType = jvm.Int()
                #         elif isinstance(firstElem, bool):
                #             componentType = jvm.Boolean()
                #         elif isinstance(firstElem, float):
                #             componentType = jvm.Float()
                #         else:
                #             componentType = jvm.Reference()
                #     else:
                #         componentType = jvm.Int()
                # elif isinstance(v, list):
                #     componentType = componentType(v)
                #     frame.locals[i] = makeJvmArray(v, componentType, state)
                # else: 
                #     frame.locals[i] = jvm.Value.int(v)

            #         heapArr = []
            #         for elem in v:
            #             if isinstance(componentType, jvm.Char):
            #                 heapArr.append(jvm.Value.char(elem))
            #             elif isinstance(componentType, jvm.Int):
            #                 heapArr.append(jvm.Value.int(elem))
            #             elif isinstance(componentType, jvm.Boolean):
            #                 heapArr.append(jvm.Value.boolean(elem))
            #             elif isinstance(componentType, jvm.Float):
            #                 heapArr.append(jvm.Value(jvm.Float(), float(elem)))
            #             elif isinstance(componentType, jvm.Reference):
            # # For reference/object types, elem must already be a jvm.Value or None
            #                 if elem is None: 
            #                     heapArr.append(jvm.Value(jvm.Reference(), None))
            #                 elif isinstance(elem, jvm.Value):
            #                     heapArr.append(elem)
            #                 else:
            #                     raise NotImplementedError(f"Cannot wrap object element {elem}")
            #             else:
            #                 raise NotImplementedError(f"Component type {componentType} not supported")
                    # if len(v) > 0 and isinstance(v[0], str) and len(v[0]) == 1:
                    #     componentType = jvm.Char()
                    # elif len(v) > 0 and isinstance(v[0], int):
                    #     componentType = jvm.Int()
                    # elif len(v) > 0 and isinstance(v[0], bool):
                    #     componentType = jvm.Boolean()
                    # else:
                    #     componentType = jvm.Int()
                    # addr = len(state.heap)
                    # state.heap[addr] = heapArr
                    # frame.locals[i] = jvm.Value(jvm.Reference(), addr)
                    #frame.locals[i] = makeJvmArray(v, componentType, state)
                # elif isinstance(v, jvm.Array):
                #     frame.locals[i] = jvm.Value.array(v)
                # else:
                #     frame.locals[i] = jvm.Value.int(v)

            # state = State({}, Stack.empty().push(frame))
            # for _ in range(1000):
            #     state = step(state)  # advance the frame first

                # Now track coverage
    #             pc_offset = frame.pc.offset  # integer
    #             if pc_offset not in coverage_seen:
    #                 coverage_seen.add(pc_offset)
    #                 interesting.append(mutated)

    #             # Optional debug
    #             print("[DEBUG] frame.pc =", frame.pc)

    #             if isinstance(state, str):
    #                 if state == "divide by zero":
    #                     print("divide by zero")
    #                 break

    # print(f"{methodid.extension.name} coverage-guided: {len(coverage_seen)} offsets seen, paths: {coverage_seen}")




def run(methodid, inputs):
    output = run_interesting_dynamic_analysis(methodid, inputs)
    return output


def run_coverage(methodid):
    output = run_coverage_guided_analysis(methodid)
    return output
    
    
import builtins

if __name__ == "__main__":
    methodid, input = jpamb.getcase()

    choice = builtins.input("Choose analysis type (random / interesting / smallcheck / coverage): ").strip().lower()
    if choice == "coverage":
        run_coverage_guided_analysis(methodid, num_trials=100)
    elif choice == "random":
        run_random_dynamic_analysis(methodid, num_trials=100)
    elif choice == "interesting":
        run_interesting_dynamic_analysis(methodid, num_trials=100)
    elif choice == "smallcheck":
        run_smallcheck_dynamic_analysis(methodid, num_trials=100)
    else:
        print("Not a choice")




