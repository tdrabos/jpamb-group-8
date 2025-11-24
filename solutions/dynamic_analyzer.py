import random
import jpamb
from jpamb import jvm
from interpreter import Frame, State, Stack, step  # your interpreter
import sys



# GENERATE VALUES: INT, BOOLEAN, FLOATS, ARRAYS:
def gen_value(param_type):
    if isinstance(param_type, jvm.Int) or param_type == "I":
        return random.randint(-10, 10)
    elif isinstance(param_type, jvm.Bool) or param_type == "Z":
        return random.choice([True, False])
    elif isinstance(param_type, jvm.Float) or param_type == "F":
        return random.uniform(-10.0, 10.0)  # generates a float
    elif isinstance(param_type, list) or param_type == "array":
        length = random.randint(0, 5)
        return [random.randint(-10, 10) for _ in range(length)]
    else:
        return 0







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
            elif isinstance(v, list):
                # Example: store array as a reference, depending on JVM representation
                frame.locals[i] = jvm.Value.array(v)
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
def run_interesting_dynamic_analysis(methodid, num_trials=100):
    found_query_behavior = False
    interesting_values = [1, -3, 0]  # Try these first
    interesting_index = 0

    for _ in range(num_trials):
        input_values = []

        for param_type in methodid.extension.params:
            val, interesting_index = gen_value(param_type, interesting_values, interesting_index)
            input_values.append(val)

        # Create frame and pre-fill locals
        frame = Frame.from_method(methodid)
        for i, v in enumerate(input_values):
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
        for _ in range(1000):
            state = step(state)
            if isinstance(state, str) and state == "divide by zero":
                found_query_behavior = True
                print("divide by zero")
                break

    print("Params for", methodid.extension.name, ":", methodid.extension.params)
    print(f"{methodid.extension.name}: 100%" if found_query_behavior else f"{methodid.extension.name}: 50%")








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
                elif isinstance(param_type, jvm.Bool) or param_type == "Z":
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












# FUNCTION FOR IF YOU WANT TO GET THE COVERAGE:
def run_coverage_guided_analysis(methodid, num_trials=100):
    interesting = [b""]
    coverage_seen = set()



    for _ in range(num_trials):
        if interesting:
            test_case = interesting.pop(0)
        else:
            test_case = bytes([random.randint(0, 255)])

        mutated_cases = []
        for i in range(len(test_case)):
            mutated = bytearray(test_case)
            mutated[i] = random.randint(0, 255)
            mutated_cases.append(bytes(mutated))

        for mutated in mutated_cases:
            input_values = [gen_value(param_type) for param_type in methodid.extension.params]

            frame = Frame.from_method(methodid)
            for i, v in enumerate(input_values):
                if isinstance(v, bool):
                    frame.locals[i] = jvm.Value.int(1 if v else 0)
                elif isinstance(v, float):
                    frame.locals[i] = jvm.Value.float(v)
                elif isinstance(v, list):
                    frame.locals[i] = jvm.Value.array(v)
                else:
                    frame.locals[i] = jvm.Value.int(v)

            state = State({}, Stack.empty().push(frame))
            for _ in range(1000):
                state = step(state)  # advance the frame first

                # Now track coverage
                pc_offset = frame.pc.offset  # integer
                if pc_offset not in coverage_seen:
                    coverage_seen.add(pc_offset)
                    interesting.append(mutated)

                # Optional debug
                print("[DEBUG] frame.pc =", frame.pc)

                if isinstance(state, str):
                    if state == "divide by zero":
                        print("divide by zero")
                    break

    print(f"{methodid.extension.name} coverage-guided: {len(coverage_seen)} offsets seen, paths: {coverage_seen}")







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




