import random
import jpamb
from jpamb import jvm
from interpreter import Frame, State, Stack, step  # your interpreter
import sys



# FUNCTION IF YOU WANT TO USE RANDOM INPUTS ONLY:
def run_random_dynamic_analysis(methodid, num_trials=100):
    found_query_behavior = False

    for _ in range(num_trials):
        input_values = []

        for param_type in methodid.extension.params:
            # Random value for JVM int
            if isinstance(param_type, jvm.Int) or param_type == "I":
                val = random.randint(-10, 10)
            # Random value for JVM boolean
            elif isinstance(param_type, jvm.Bool) or param_type == "Z":
                val = random.choice([True, False])
            else:
                val = 0
        input_values.append(val)


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










# FUNCTION IF YOU WANT TO USE INTERESTING VALUES AND RANDOM INPUTS:
def run_interesting_dynamic_analysis(methodid, num_trials=100):
    found_query_behavior = False
    dictt = [1, -3, 0]  # Interesting values to try first
    dictt_index = 0      # Track which value to use next

    for _ in range(num_trials):
        input_values = []

        for param_type in methodid.extension.params:
            # Use dictt values first
            if dictt_index < len(dictt):
                val = dictt[dictt_index]
                dictt_index += 1
            else:
                # Random value for JVM int
                if isinstance(param_type, jvm.Int) or param_type == "I":
                    val = random.randint(-10, 10)
                # Random value for JVM boolean
                elif isinstance(param_type, jvm.Bool) or param_type == "Z":
                    val = random.choice([True, False])
                else:
                    val = 0
            input_values.append(val)


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
                if state == "divide by zero":  # your custom behaviour
                    found_query_behavior = True
                    print("divide by zero")
                break

    # Print results
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

    # Start with an empty byte-string as the first test case
    interesting = [b""]
    coverage_seen = set()  # Track bytecode offsets executed

    for _ in range(num_trials):

        if interesting:
            test_case = interesting.pop(0)
        else:
            # fallback: generate a random seed
            test_case = bytes([random.randint(0, 255)])


        # Mutate it: change, append, or remove a byte
        mutated_cases = []
        for i in range(len(test_case)):
            mutated = bytearray(test_case)
            mutated[i] = random.randint(0, 255)
            # Another method for coverage is appening: mutated_cases.append(bytes(mutated))
            mutated_cases.append(bytes(mutated))  # Turn them back to bytes and add them in an array
        
        #Another method if you want to remove last byte:
        # if len(test_case) > 0:
        #     mutated_cases.append(test_case[:-1])  # remove

        for mutated in mutated_cases:
            # Convert bytes to input values for the method
            input_values = []
            for param_type in methodid.extension.params:
                if isinstance(param_type, jvm.Int) or param_type == "I":
                    val = mutated[0] if mutated else 0
                elif isinstance(param_type, jvm.Bool) or param_type == "Z":
                    val = bool(mutated[0] % 2) if mutated else False   
                else:
                    val = 0
                input_values.append(val)

            # Create frame and fill locals
            frame = Frame.from_method(methodid)
            for i, v in enumerate(input_values):
                if isinstance(v, bool):
                    frame.locals[i] = jvm.Value.int(1 if v else 0)
                else:
                    frame.locals[i] = jvm.Value.int(v)

            # Run interpreter
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

                

    print(f"{methodid.extension.name} coverage-guided: {len(coverage_seen)} offsets seen, and {coverage_seen} are the paths it took")









import builtins

if __name__ == "_main_":
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