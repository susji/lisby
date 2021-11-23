from enum import IntEnum
from struct import pack, unpack


class Op:
    class Type(IntEnum):
        """Type contains all our VM instructions.

        We have two variants of VM instructions: those without any subsequent
        data, and those with 8 bytes of some data. We assume little-endian.
        """

        @staticmethod
        def fromint(code):
            e = Op.Type(code)
            return e

        HALT = 0
        ADD = 1  # binary arithmetic
        SUB = 2
        MUL = 3
        DIV = 4
        XOR = 5
        MOD = 6
        AND = 7
        OR = 8
        INV = 9  # unary arithmetic
        PUSHI = 10  # int follows
        PUSHF = 11  # float follows
        PUSHSTR = 12  # string table reference follows (int)
        PUSHSY = 13  # symbol table reference follows (int)
        PUSHSYRAW = 14  # raw (unresolved) symbol table reference follows
        PUSHTRUE = 15
        PUSHFALSE = 16
        PUSHUNIT = 17
        PUSHCLOSURE = 18  # tape identifier follows (int)
        PUSHCONT = 19  # pushes the current continuation to stack
        QUOTED = 20  # increases quoting level of next push by follower (int)
        POP = 21  # just pops a value from the stack, does not store
        CALL = 22  # pops closure, calls it
        TAILCALL = 23  # like call except tail call
        RET = 24  # pops a return address from stack, jumps there
        JT = 25  # jumps on true, target pc follows (int)
        JF = 26  # jump on false, target pc follows (int)
        JMP = 27  # unconditional jump to following pc (int)
        STORE = 28  # stores popped stack value to following symindex (int)
        STORETOP = 29  # stores popped stack value to top level symindex (int)
        EQ = 30  # conditionals: pop two values from stack, push comparison
        NEQ = 31
        GT = 32
        GE = 33
        LT = 34
        LE = 35
        NOT = 36
        DECLARE = 37  # declare a variable with following symindex (int)
        PRINT = 38  # pops one value and attempts to display it
        LIST = 39  # constructs a list of N entries (int)
        HEAD = 40  # pops a list and pushes its first element
        TAIL = 41  # pops a list and pushes it without its first element
        LISTCAT = 42  # pops two lists and pushes their concatenation
        EVAL = 43  # pops a value, evals it in a fresh environment
        DUMP = 44  # dumps the current vm status
        NEWENV = 45  # activates a fresh environment with current as parent
        DEPARTENV = 46  # departs the current environment, activates parent
        QUASIQUOTED = 47
        _MAX = 48

    @classmethod
    def rawfollows(cls, ty) -> int:
        """Determine how many following bytes to skip if an instruction
        happens to define subsequent raw data."""
        followers = (
            cls.Type.PUSHI,
            cls.Type.PUSHF,
            cls.Type.PUSHSTR,
            cls.Type.PUSHSY,
            cls.Type.STORE,
            cls.Type.STORETOP,
            cls.Type.PUSHCLOSURE,
            cls.Type.JF,
            cls.Type.JMP,
            cls.Type.DECLARE,
            cls.Type.LIST,
            cls.Type.PUSHSYRAW,
            cls.Type.QUOTED,
            cls.Type.JT,
            cls.Type.PUSHCONT,
            cls.Type.QUASIQUOTED,
        )
        if ty in followers:
            return 8
        return 0

    def __init__(self, ty: Type) -> None:
        self.type = ty

    @classmethod
    def deserialize(cls, raw: str) -> "Op":
        if len(raw) != 1:
            raise ValueError("deserialize accepts string of length one")
        ty = unpack("c", memoryview(raw.encode()))[0]
        if ty >= Op.Type._MAX:
            raise ValueError("invalid operand: %d" % ty)
        return cls(ty)

    def serialize(self) -> bytes:
        return pack("c", int(self.type))
