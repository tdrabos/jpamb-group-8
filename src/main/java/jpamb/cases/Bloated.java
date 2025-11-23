package jpamb.cases;

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

        return 1;
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

    for (int i = 0; i<4; i++) {
      n += 1;
      if ( i == 4) { // unreachable
            n -= i;
            return 2;
      }
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

  public static int deadStore() {
    int i = 0;

    return 1;
  }

  public static void keepObservableArrayWrite(int[] arr) {
    int[] tmp = new int[1];
    tmp[0] = 42;  
    arr[0] = 1;
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

}