import jpamb.cases.syntaxer.SyntaxerTestOther;

public class SyntaxerTestBase {

  private static boolean helperVisited = false;
  private SyntaxerTestOther other = new SyntaxerTestOther();
    
  public static void main(String[] args) {
     syntaxerMain();
  }

  public static void syntaxerMain() {
      
     System.out.println("Syntaxer Main");  

    if (!helperVisited) {
      helperVisited = true;
      syntaxerHelper();
    }
  }

  public static void syntaxerHelper() {
    System.out.println("Syntaxer Helper");
    other.anotherMethod(); 
    syntaxerMain();
  }

  public void neverCalledMethod() {
    System.out.println("Never Called Method");
    onlyCalledByANeverCalledMethod();
  }

  public void onlyCalledByANeverCalledMethod() {
    System.out.println("Called Method");
  }

  public void methodWithPrimitives(Int a, Char b, Boolean c, Double d, Byte e, JVMFloat f, String g) {
    if (a > 0) {
      System.out.println("Method with Primitives");
    } else {
      System.out.println("Method with Primitives - else");
    }
  }

  public void methodWithEasySingleIf(Int a) {
    if (a > 0) {
      System.out.println("Method with Single If a > 0");
    } else {
      System.out.println("Method with Single If a <= 0");
    }
  }

  public void methodWithSingleIf(Int a) {
    a += 3;
    if (a > 10) {
      System.out.println("Method with Single If a -3 > 10");
    } else {
      System.out.println("Method with Single If a -3 <= 10");
    }
  }

  public void methodWithSingleIfMultiParam(Int a, Int b, Char c) {
     a += 5;
     b -= 3;
    if (a * b > 10) {
      System.out.println("Method with Single If a + b > 10");
      if (a == 42) {
        System.out.println("Method with Single If a == 42");
      } else {
        System.out.println("Method with Single If a != 42");
      }
    } else {
      System.out.println("Method with Single If a + b <= 10");
    }

    if (c == 'c') {
      System.out.println("Method with Single If c is true");
    } else {
      System.out.println("Method with Single If c is false");
    }

    
  }
}