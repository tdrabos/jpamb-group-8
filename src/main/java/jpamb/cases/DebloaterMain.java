package jpamb.cases;

import jpamb.utils.Case;
import jpamb.utils.Tag;
import jpamb.utils.*;
import static jpamb.utils.Tag.TagType.*;

public class DebloaterMain {

    public static void main(String[] args) {
        // Use some of the results so compiler doesn’t optimize everything away
        int b1 = unreachableBranchBasic(1);
        int dead = deadArg();
        int f1 = unreachableBranchFor(1);
        int w1 = unreachableBranchWhile(1);
        int arr1 = unreachableBranchArray(1);
        float fb = unreachableBranchBasicFloat(1.0f);
        int dl = deadLocalInitialization(10);
        unreachableLoopBranchOnIndex();
        unreachableArrayOutOfBounds();
        int udz = unreachableDivideByZeroBranch();
        int li = localInitButNotUsed();

        int combined = b1 + dead + f1 + w1 + arr1 + (int) fb + dl + udz + li;
        if (combined == 123456789) {
            System.out.println("Impossible combined value: " + combined);
        }
    }

    // ---- ALL YOUR DEBLOATED METHODS BELOW ----

    public static int unreachableBranchBasic(int n) {
    if (n == 0) {
      return 1 + n;
    }

    if (n > 0) {
        n = n+2;

        return unreachableBranchFor(0);
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

    for (int i = 0; i<4; i++) {
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
      int[] numbers = {1,2,3,4,5};

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
        f = f+2.0f;

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

}
