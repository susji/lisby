from typing import Dict, List
import abc
import copy

from lisby.parser import Node


class Environment:
    counter = 0

    def __init__(self, parent: "Environment") -> None:
        self.values: Dict[int, Value] = {}
        self.parent = parent
        self.id = Environment.counter
        Environment.counter += 1


class Address:
    def __init__(self, tape: int, pc: int, env: Environment) -> None:
        self.tape = tape
        self.pc = pc
        self.env = env


class Value(abc.ABC):
    def __init__(self, value) -> None:
        self.value = value

    @abc.abstractmethod
    def copy(self):
        """Force all Value implementors to define a copy method.

        As more complex Value implementations may contain values, which
        are stored as references, they need to make sure that a copy of
        them may be safely created such that the original source is not
        affected by potential modifications to the copy."""
        pass


class Int(Value):
    def __init__(self, value: int) -> None:
        super().__init__(value)

    def __str__(self):
        return "%d" % self.value

    def copy(self):
        return self


class Float(Value):
    def __init__(self, value: float) -> None:
        super().__init__(value)

    def __str__(self):
        return "%f" % self.value

    def copy(self):
        return self


class Symbol(Value):
    def __init__(self, value: str) -> None:
        super().__init__(value)

    def __str__(self):
        return "%s" % self.value

    def copy(self):
        return self


class String(Value):
    def __init__(self, value: str) -> None:
        super().__init__(value)

    def __str__(self):
        return "%s" % self.value

    def copy(self):
        return self


class VTrue(Value):
    def __init__(self) -> None:
        super().__init__(True)

    def __str__(self):
        return "#t"

    def copy(self):
        return self


class VFalse(Value):
    def __init__(self) -> None:
        super().__init__(False)

    def __str__(self):
        return "#f"

    def copy(self):
        return self


class VList(Value):
    def __init__(self, value: List[Value]) -> None:
        super().__init__(value)

    def __str__(self):
        ret = "("
        ret += " ".join(["%s" % elem for elem in self.value])
        ret += ")"
        return ret

    def copy(self):
        # This makes, for instance, list tailing really slow.
        return VList(copy.deepcopy(self.value))


class Closure(Value):
    def __init__(self, parent: Environment, tape: int) -> None:
        super().__init__(tape)
        self.parent = parent
        self.tape = tape

    def __str__(self):
        return "Closure(tape=%d, parent=%d)" % (self.tape, self.parent.id)

    def copy(self):
        return self


class Continuation(Value):
    def __init__(
        self, stack: List[Value], rets: List[Address], tape: int, pc: int
    ) -> None:
        super().__init__(tape)
        self.stack = stack
        self.rets = rets
        self.tape = tape
        self.pc = pc

    def __str__(self):
        return "Continuation(tape=%d, pc=%d)" % (self.tape, self.pc)

    def copy(self):
        return self


class Quoted(Value):
    def __init__(self, value: Value, degree: int) -> None:
        super().__init__(value)
        self.degree = degree

    def __str__(self):
        ret = str(self.value)
        for i in range(self.degree):
            ret = "(quote %s)" % ret
        return ret

    def copy(self):
        return Quoted(self.value.copy(), self.degree)


class Quasiquoted(Value):
    def __init__(self, value: Value, degree: int) -> None:
        super().__init__(value)
        self.degree = degree

    def __str__(self):
        ret = str(self.value)
        for i in range(self.degree):
            ret = "(quasiquote %s)" % ret
        return ret

    def copy(self):
        return Quasiquoted(self.value.copy(), self.degree)


class Unquoted(Value):
    def __init__(self, value: Value) -> None:
        super().__init__(value)

    def __str__(self):
        return "(unquote %s)" % self.value

    def copy(self):
        return Unquoted(self.value.copy())
