package jpamb.cases;

import jpamb.utils.*;
import static jpamb.utils.Tag.TagType.*;

public class Bloated {
   @Case("(0) -> assertion error")
   @Case("(24) -> ok")
   @Tag({ LOOP })
  public static void collatz(int n) { 
    assert n > 0;
    while (n != 1) { 
      if (n % 2 == 0) { 
        n = n / 2;
      } else { 
        n = n * 3 + 1;
      }
    }
  }
   @Case("() -> prints first elem ")
  public static void ifarray(){
    int arr[] = {1, 2, 3, 4, 5, 6, 7, 8, 9,};

    if(arr[0] > 0){
        System.out.println("reached");

        if (arr[0] < 0){
            System.out.println("unreached 1");
        }
    }
    else{
        System.out.println("unreached 2");
    }

  }

  @Case("(12) -> prints reached")
  public static void ifint(){
    int x = 12;
    if(x > 7){
        System.out.println("reached");   
    }
    else{
        System.out.println("unreached");
    }
  }

   @Case("(true) -> prints reached")
  public static void ifbool(){
    boolean y = true;

    if(y == true){
        System.out.println("reached");
    }
    else{
        System.out.println("unreached");
    }
  }

   @Case("()prints 0 to 9")
  public static void loopint(){
    int z = 0;

    for (z = 0; z < 10; z++) {
        System.out.println("reached");
        if(z < 0){
            System.out.println("unreached 1");
        }
        if (z>10) {
            System.out.println("unreached 2");
            
        }
    }    
  }

   @Case("() -> prints all elems")
  public static void arrayloop(){
    int arr2 [] = {10, 23, 44, 30, 12, 63};

    for(int i = 0; i < arr2.length; i ++){
        System.out.println("reached" + i);

        if (arr2[i] > 100){
            System.out.println("unreached no number above 100");
        }
        else{
            System.out.println("reached no number above 100");
        }
    }
  }
}