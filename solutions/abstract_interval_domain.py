from hypothesis import given
from hypothesis.strategies import integers, sets


class Interval:
    
    Interval_TOP = [float('-inf'), float('inf')]
    Interval_BOTTOM = [float('inf'), float('-inf')]


    @given(sets(integers()))
    def test_interval_abstraction_valid(xs):
        r = Interval.abstract(xs) 
        assert all(x in r for x in xs)

    @given(sets(integers()), sets(integers()))
    def test_interval_abstraction_distributes(xs, ys):
        assert (Interval.abstract(xs) | Interval.abstract(ys)) == Interval.abstract(xs | ys)

    #Abstract
    @staticmethod
    def abstract(set):
        if set:
            low = min(set)
            high = max(set)
            return [low,high]
        else:  # if the set is empty
            return [float('inf'), float('-inf')]  # represents ⊥
        
    #Gamma   
    @staticmethod
    def gamma(interval):
        i, j = interval
        return set(range(i, j+1))
    

    #Order (Contain)
    @staticmethod
    def order(interval1, interval2):
        i,j = interval1
        k,h = interval2
        if k<=i and h>=j:
            return True
        else:
            return False
    

    #Join
    @staticmethod
    def join(interval1, interval2):
        i, j = interval1
        k, h = interval2
        return [min(i,k), max(j,h)]
    

    #Meet
    @staticmethod
    def meet(interval1, interval2):
        i, j = interval1
        k, h = interval2
        if max(i,k) <= min(j,h):
            return [max(i,k), min(j,h)]
        else:                                  #intervals dont overlap
            return [float('inf'), float('-inf')]
    

    #Implement Operations
    @given(sets(integers()), sets(integers()))
    def test_interval_abstraction_add(xs,ys):
        r = Interval.abstract(xs) + Interval.abstraction(ys)
        assert all(x + y in r for x in xs for y in ys)
        
    def test_interval_abstraction_subtract(xs,ys):
        r = Interval.abstract(xs) - Interval.abstraction(ys)
        assert all(x - y in r for x in xs for y in ys)

    
    #Add
    @staticmethod
    def add(interval1, interval2):
        i,j = interval1
        k,h = interval2
        return [i+k, j+h]
    

    #Substract ???
    @staticmethod
    def subtract(interval1, interval2):
        i, j = interval1
        k, h = interval2
        return [i - h, j - k]




    
    #Widening Operator
    @staticmethod
    def wid_abstract(K, set):
        if not set:
            return [float('-inf'), float('inf')]
        # then do the min/max comparisons

        if min(K) <= min(set):
            low = min(set)
        elif min(K) > min(set):
            low = float('-inf')
        if max(set) <= max(K):
            high = max(set)
        elif max(set) > max(K): 
            high = float('inf')
        
        return [low, high]




# simple test run
if __name__ == "__main__":
    xs = {1, 2, 3}
    ys = {4, 5}
    
    interval_x = Interval.abstract(xs)
    interval_y = Interval.abstract(ys)
    
    print("Interval X:", interval_x)
    print("Interval Y:", interval_y)
    
    print("Add:", Interval.add(interval_x, interval_y))
    print("Subtract:", Interval.subtract(interval_x, interval_y))
    print("Join:", Interval.join(interval_x, interval_y))
    print("Meet:", Interval.meet(interval_x, interval_y))
