import jpamb.cases.syntaxer.SyntaxerTestOther;

public class SyntaxerTestBase {

  private static boolean helperVisited = false;
  private SyntaxerTestOther other = new SyntaxerTestOther();
    
  public static void main() {
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
    // other.anotherMethod(); 
    syntaxerMain();
  }

  public void neverCalledMethod() {
    System.out.println("Never Called Method");
    onlyCalledByANeverCalledMethod();
  }

  public void onlyCalledByANeverCalledMethod() {
    System.out.println("Called Method");
  }
}