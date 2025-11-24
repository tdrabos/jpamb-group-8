package main.java.jpamb.cases;

import jpamb.utils.*;
import static jpamb.utils.Tag.TagType.*;

public class DebloaterCases {

    // Dead local + dead store inside reachable code
    // The debloater should be able to remove debug/tmp without changing behavior.
    @Case("(0) -> ok")
    @Case("(1) -> ok")
    public static int deadLocalInitialization(int n) {
        int debug = 123; // never used
        int result = n;
        if (n > 0) {
            int tmp = 10;
            tmp = 20; // dead store: first assignment to tmp is never observed
        }
        return result;
    }

    // Dead store to array element
    @Case("() -> ok")
    @Tag({ ARRAY })
    public static int deadArrayStore() {
        int[] a = new int[3]; // [0, 0, 0]
        a[1] = 5;
        a[1] = 7; // dead write: value 5 is never read
        int sum = a[0] + a[1] + a[2];
        assert sum == 7;
        return sum;
    }

    // Boolean flag that never influences observable behavior
    // Tests that debloater can handle booleans and identify useless flag updates.
    @Case("(true) -> ok")
    @Case("(false) -> ok")
    public static int booleanFlagNeverUsed(boolean b) {
        boolean flag = false;
        if (b) {
            flag = true; // dead: no observable use of flag
        } else {
            flag = false; // dead as well
        }
        return b ? 1 : 0;
    }

    // Loop-invariant computation + always-false branch
    // Checks loop handling plus removal of loop-invariant dead code.
    @Case("(3) -> ok")
    @Tag({ LOOP })
    public static int loopInvariantComputation(int n) {
        int sum = 0;
        for (int i = 0; i < n; i++) {
            int invariant = 10; // same every iteration, never observed
            sum += i;
            if (invariant == 11) { // always false, dead branch
                sum += invariant;
            }
        }
        assert sum == n * (n - 1) / 2;
        return sum;
    }

    // Observable array write that must NOT be removed
    // Ensures debloater does not treat this as dead just because it's a simple
    // pattern
    @Case("() -> ok")
    @Tag({ ARRAY })
    public static int keepObservableArrayWrite() {
        int[] a = { 1, 2, 3 };
        a[1] = 5; // this write is observable via the later read
        int x = a[1]; // must still be 5 after debloating
        assert x == 5;
        return x;
    }

    // Helper with side effect used below
    public static boolean setFlag(int[] arr) {
        arr[0] = 42; // side effect that must only happen when short-circuit allows
        return true;
    }

    // Short-circuit boolean with side effects
    // Tests that the debloater respects side effects hidden behind short-circuit
    // logic.
    @Case("(0) -> ok")
    @Case("(1) -> ok")
    @Tag({ CALL, ARRAY })
    public static void shortCircuitBooleanSideEffect(int n) {
        int[] arr = new int[] { 0 };
        if (n > 0 && setFlag(arr)) {
            // body is irrelevant; side effect is in setFlag
        }
        if (n <= 0) {
            // setFlag should never have been called
            assert arr[0] == 0;
        } else {
            // setFlag MUST have been called
            assert arr[0] == 42;
        }
    }

    // Early return + dead tail with a potential exception
    // Debloater can safely remove the dead tail but must keep the live part.
    @Case("(0) -> ok")
    @Case("(1) -> ok")
    public static int earlyReturnDeadTail(int n) {
        if (n == 0) {
            return 0;
        }
        int result = n;
        if (result > 0) {
            return result;
        }
        // Dead code: impossible to reach
        int dead = 10 / 0;
        return dead;
    }

    // The debloater should keep i == 1 and remove i == 3 as unreachable
    @Case("() -> ok")
    @Tag({ ARRAY, LOOP })
    public static void unreachableLoopBranchOnIndex() {
        boolean[] items = { true, false, true };

        for (int i = 0; i < items.length; i++) {
            if (i == 1) {
                items[i] = true; // reachable and has observable effect
            }
            if (i == 3) { // unreachable: i is only 0,1,2
                items[i] = false; // candidate for debloating
            }
        }
    }

    // Static + CFG should both agree that i == 5 is unreachable
    @Case("() -> ok")
    @Tag({ ARRAY, LOOP })
    public static void unreachableArrayOutOfBounds() {
        int[] arr = { 1, 2, 3 };

        for (int i = 0; i < arr.length; i++) {
            if (i == 5) { // unreachable because i ∈ {0,1,2}
                int x = arr[5]; // would throw out of bounds if reachable
                assert x == 0;
            }
        }
    }

    // n != 0 && n == 0 is impossible, so reachability analysis should mark the 1 /
    // n as unreachable.
    @Case("() -> ok")
    public static int unreachableDivideByZeroBranch() {
        int n = 0;
        int res = 1;

        if (n != 0 && n == 0) { // logically impossible
            res = 1 / n; // unreachable
        }

        return res;
    }

}
