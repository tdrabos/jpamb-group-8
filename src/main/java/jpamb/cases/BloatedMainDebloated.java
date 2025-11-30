package jpamb.cases;

import jpamb.utils.Case;
import jpamb.utils.Tag;
import jpamb.utils.*;
import static jpamb.utils.Tag.TagType.*;

public class BloatedMainDebloated {

    public static int main() {

        // Basic branch reachability: inner n == 0 branch is unreachable for n > 0
        int b1 = unreachableBranchBasic(1);

        // Dead argument: n is never used inside the method
        int dead = deadArg();

        // For-loop with unreachable branch (i == 4 never true since i in {0,1,2,3})
        int f1 = unreachableBranchFor(1);

        // While-loop with unreachable branch (i == 4 never true since i in {0,1,2,3})
        int w1 = unreachableBranchWhile(1);

        // Array-based reachability: numbers.length is always 5, so numbers.length > 5
        // is unreachable
        int arr1 = unreachableBranchArray(1);

        // Float variant of unreachable branch: f == 0.0f inside f > 0.0f branch is
        // unreachable
        float fb = unreachableBranchBasicFloat(1.0f);

        // Dead local initialization / dead tmp pattern
        int dl = deadLocalInitialization(10);

        // Loop/index reachability with unreachable i == 3 branch
        unreachableLoopBranchOnIndex();

        // Out-of-bounds access that is syntactically present but unreachable (i == 5
        // impossible)
        unreachableArrayOutOfBounds();

        // Logically impossible condition: n != 0 && n == 0, so divide-by-zero is
        // unreachable
        int udz = unreachableDivideByZeroBranch();

        // Local init that is never used (simple dead local)
        int li = localInitButNotUsed();

        int combined = b1 + dead + f1 + w1 + arr1 + dl + udz + li;
        return combined;
    }

    public static int unreachableBranchBasic(int n) {
        if (n == 0) {
            return 1 + n;
        }

        if (n > 0) {
            n = n + 2;
            return 0;
        }
        return 0;
    }

    public static int localInitButNotUsed() {
        return 0;
    }

    public static int unreachableBranchFor(int n) {
        if (n == 0) {
            return 1 + n;
        }

        for (int i = 0; i < 4; i++) {
            n += 1;
        }
        return 0;
    }

    public static int unreachableBranchWhile(int n) {
        if (n == 0) {
            return 1 + n;
        }
        int i = 0;
        while (i < 4) {
            n += 1;
            i++;
        }
        return 0;
    }

    public static int unreachableBranchArray(int n) {
        if (n > 0) {
            int[] numbers = { 1, 2, 3, 4, 5 };
            return numbers[0];
        }
        return 0;
    }

    public static int deadArg() {
        return 0;
    }

    public static float unreachableBranchBasicFloat(float f) {
        if (f == 0.0f) {
            return 1.5f + f;
        }
        if (f > 0.0f) {
            f = f + 2.0f;

            return 1.0f;
        }
        return 0.0f;
    }

    public static int deadLocalInitialization(int n) {
        int result = n;
        int tmp = 10;
        if (n > 0) {
            tmp = 20;
        }
        return result + tmp;
    }

    // The debloater should keep i == 1 and remove i == 3 as unreachable
    public static void unreachableLoopBranchOnIndex() {
        boolean[] items = { true, false, true };

        for (int i = 0; i < items.length; i++) {
            if (i == 1) items[i] = true; // reachable and has observable effect
        }
    }

    public static void unreachableArrayOutOfBounds() {
        int[] arr = { 1, 2, 3 };

        for (int i = 0; i < arr.length; i++) {
        }
    }

    // n != 0 && n == 0 is impossible, so reachability analysis should mark the 1 /
    // n as unreachable.
    public static int unreachableDivideByZeroBranch() {
        int n = 0;
        int res = 1;

        return res;
    }

    // TWO METHODS THAT ARE NEVER CALLED, thus unreachable from main.
    // Should be pre-pruned by syntaxer

    public static void completelyUncalledHelper() {
        int x = 10;
        x = x + 20; // dead store
        if (false) {
            System.out.println(x);
        }
    }

    @Tag({ ARRAY })
    public static int unusedArrayMutation() {
        int[] a = { 7, 7, 7 };
        a[2] = 99; // observable internally, but method never called
        return a[2];
    }
}