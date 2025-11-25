package jpamb.cases;

import jpamb.utils.Case;
import jpamb.utils.Tag;
import jpamb.utils.*;
import static jpamb.utils.Tag.TagType.*;

public class Bloated {
    public static int unreachableBranchBasic(int n) {
    if (n == 0) {
      return 1 + n;
    }

    if (n > 0) {
        n = n+2;

        if (n == 0) { // unreachable
            int i = 2;
            n = i + n;
        }

        return unreachableBranchFor(0);
    }
    return 0;
  }

  public static int localInitButNotUsed() {
    int i = 0;

    return 0;
  }

  public static int unreachableBranchFor(int n) {
    if (n == 0) {
      return 1 + n;
    }

    for (int i = 0; i<4; i++) {
      n += 1;
      if ( i == 4) { // unreachable
            n -= i;
            return 2;
      }
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
      if ( i == 4) { // unreachable
            n -= i;
            return 2;
      }
      i++;
    }
    return 0;
  }

  public static int unreachableBranchArray(int n) {
    if (n > 0) {
      int[] numbers = {1,2,3,4,5};

      if (numbers.length > 5) {
        n += 1;
        return n;
      }

      return numbers[0];
    }

    return 0;
  }

  public static int deadArg(int n) {
    return 0;
  }

  public static float unreachableBranchBasicFloat(float f) {
    if (f == 0.0f) {
      return 1.5f + f;
    }

    if (f > 0.0f) {
        f = f+2.0f;

        if (f == 0.0f) { // unreachable
            int i = 2;
            i++;
        }

        return 1.0f;
    }
    return 0.0f;
  }

  public static int deadLocalInitialization(int n) {
        int debug = 123; // never used

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
            if (i == 3) items[i] = false; // candidate for debloating
        }
    }

    
    public static void unreachableArrayOutOfBounds() {
        int[] arr = { 1, 2, 3 };

        for (int i = 0; i < arr.length; i++) {
            if (i == 5) { int x = arr[5]; } // would throw out of bounds if reachable
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