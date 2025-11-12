from abc import ABC, abstractmethod
from typing import Iterable, Self

class Domain[V](ABC):
    """
    Abstract superclass for any Abstract Domain for concrete value V.
    """
    
    @classmethod
    @abstractmethod
    def empty(cls) -> Self: ...
    
    @classmethod
    @abstractmethod
    def abstract(cls, elems: Iterable[V]) -> Self: ...
    
    # TODO: do the rest