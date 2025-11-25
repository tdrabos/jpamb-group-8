package jpamb.cases;
import jpamb.utils.Case;
import jpamb.utils.Tag;
import jpamb.utils.*;
import static jpamb.utils.Tag.TagType.*;

// TODO: set up this class so that it can be built into a cfg, meaning, all methods accessibble from main are kept, the ones that are not are not
// Example:
// public static void main() {
//         res1 = deadLocalInitialization(10)
//         res2 = deadArrayStore()

//         return earlyReturnDeadTail(res1 + res2)
//     }
// Do this for some functions, and leave some that are not reachable, these will be pre-pruned by the syntaxer

public class BloatedMain {

    private static boolean helperVisited = false;

    public static void main() {
        
    }

    // Dead local + dead store inside reachable code
    // The debloater should be able to remove debug/tmp without changing behavior.x
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
    @Tag({ ARRAY })
    public static int deadArrayStore() {
        int[] a = new int[3]; // [0, 0, 0]
        a[1] = 5;
        a[1] = 7; // dead write: value 5 is never read
        int sum = a[0] + a[1] + a[2];
        assert sum == 7;
        return sum;
    }

    // Loop-invariant computation + always-false branch
    // Checks loop handling plus removal of loop-invariant dead code.
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

    @Tag({ ARRAY, LOOP })
    public static void unreachableArrayOutOfBounds() {
        int[] arr = { 1, 2, 3 };

        for (int i = 0; i < arr.length; i++) {
            if (i == 5) { // unreachable because i in {0,1,2}
                int x = arr[5]; // would throw out of bounds if reachable
                assert x == 0;
            }
        }
    }

    // n != 0 && n == 0 is impossible, so reachability analysis should mark the 1 /
    // n as unreachable.
    public static int unreachableDivideByZeroBranch() {
        int n = 0;
        int res = 1;

        if (n != 0 && n == 0) { // logically impossible
            res = 1 / n; // unreachable
        }

        return res;
    }
}