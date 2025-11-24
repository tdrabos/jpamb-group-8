package jpamb.cases.syntaxer;

public class Unused {

    public void unusedMethod() {
        System.out.println("This method is never used");
        anotherUnusedMethod();
    }

    public void anotherUnusedMethod() {
        System.out.println("Another unused method");
    }
}
