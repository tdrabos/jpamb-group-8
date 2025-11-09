package jpamb.cases;

import jpamb.utils.*;
import static jpamb.utils.Tag.TagType.*;

public class Bloated {
    public static int unreachableBranchSign(int n) {
    if (n != 0) {
      return 1 / n;
    }

    if (n > 0) {
        n = n+2;

        if (n == 0) { // unreachable
            int i = 2;
            n = i + n;
        }

        return 1;
    }
    assert 10 > n;
    return 0;
  }
}