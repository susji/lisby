from typing import List, Tuple
from struct import pack, unpack

from lisby.shared import LisbyRuntimeError
from .bytecode import Op

MAGIC = b"LISBY001"


class Program:
    @classmethod
    def deserialize(cls, raw: bytes) -> "Program":
        """Deserializes the raw bytecode representation into a Program."""

        def next_int():
            nonlocal raw
            ret = unpack("<q", raw[:8])[0]
            raw = raw[8:]
            return ret

        def next_bytes(ll):
            nonlocal raw
            ret = unpack("%ds" % ll, raw[:ll])[0]
            raw = raw[ll:]
            return ret

        def next_str(ll):
            return next_bytes(ll).decode("utf8")

        ml = len(MAGIC)
        if len(raw) < ml or raw[0:ml] != MAGIC:
            raise RuntimeError("Initial magic not found")
        raw = raw[ml:]
        p = cls()

        nstrings = next_int()
        for _ in range(nstrings):
            sl = next_int()
            p.strings.append(next_str(sl))
        nsymbols = next_int()
        for _ in range(nsymbols):
            sl = next_int()
            p.symbols.append(next_str(sl))
        ntapes = next_int()
        tapes = []
        for i in range(ntapes):
            tl = next_int()
            print("Tape #%d length: %d" % (i, tl))
            tapes.append(next_bytes(tl))
        p.tapes = tapes
        if len(raw) != ml:
            raise RuntimeError("End magic not found")
        print("Tapes: %d" % ntapes)
        print("Strings: %s" % p.strings)
        print("Symbols: %s" % p.symbols)
        return p

    def __init__(self, debug: bool = False) -> None:
        self.debug: bool = debug
        self.tapes: List[List[int]] = [[]]  # all code tapes
        self.strings: List[str] = []  # interned static strings
        self.symbols: List[str] = []  # interned static symbols
        self.tape: int = 0  # currently active tape

    def serialize(self) -> bytes:
        """Serialize delivers the bytecode representation of the current
        program."""
        ret = MAGIC
        for which in (self.strings, self.symbols):
            ret += pack("<q", len(which))
            for cur in which:
                encoded = cur.encode("utf8")
                le = len(encoded)
                ret += pack("<q", le)
                ret += pack("%ds" % le, encoded)
        ret += pack("<q", len(self.tapes))
        for tape in self.tapes:
            raw = bytes(tape)
            ret += pack("<q", len(raw))
            ret += raw
        ret += MAGIC[::-1]
        return ret

    def _debug(self, msg):
        if not self.debug:
            return
        print("program: %s" % msg)

    def cursor(self) -> int:
        return len(self.tapes[self.tape])

    def symbol_find(self, sym: str) -> int:
        try:
            return self.symbols.index(sym)
        except ValueError:
            raise LisbyRuntimeError("symbol %s not found" % sym)

    def lambda_start(self) -> Tuple[int, int]:
        orig = self.tape
        self.tape = len(self.tapes)
        self.tapes.append([])
        return orig, self.tape

    def lambda_end(self, orig: int) -> None:
        self.emit(Op.Type.RET)
        self.tape = orig

    def find_or_add_sym(self, sym: str) -> int:
        symindex = None
        try:
            symindex = self.symbols.index(sym)
        except ValueError:
            self.symbols.append(sym)
            symindex = len(self.symbols) - 1
        return symindex

    def find_or_add_str(self, s: str) -> int:
        strindex = None
        try:
            strindex = self.strings.index(s)
        except ValueError:
            self.strings.append(s)
            strindex = len(self.strings) - 1
        return strindex

    def symbol_name(self, i: int) -> str:
        return self.symbols[i]

    def string_value(self, i: int) -> str:
        return self.strings[i]

    def patch(self, tape: int, pc: int, raw: bytes) -> None:
        assert len(raw) == 8, "We support only 8 byte raw values"
        self.tapes[self.tape][pc : pc + 8] = raw

    def emit(self, code: int) -> None:
        assert code >= 0 and code <= 255, "Invalid byte"
        self.tapes[self.tape].append(code)
        self._debug("[%d] emitted %s" % (self.tape, Op.Type.fromint(code).name))

    def emitpholder(self) -> int:
        """Emits a placeholder value."""
        start = len(self.tapes[self.tape])
        self.tapes[self.tape] += [0x42] * 8
        self._debug("[%d] emitted placeholder bytes" % self.tape)
        return start

    def emitraw(self, raw: bytes) -> None:
        assert len(raw) >= 8, "emitraw at least 8 bytes"
        self.tapes[self.tape] += [int(c) for c in raw]
        self._debug("emitted raw bytes: %r" % raw)

    def dump(self):
        print("# strings")
        for (i, string) in enumerate(self.strings):
            print("%4d  %s" % (i, string))
        print("# symbols")
        for (i, symbol) in enumerate(self.symbols):
            print("%4d  %s" % (i, symbol))

        print("# code")
        no_decode = 0

        for tape in range(len(self.tapes)):
            print("# tape %d" % tape)
            fmt = "%%%dd" % (len(str(len(self.tapes[tape]))) + 1) + "  %4d  %s"
            for (i, val) in enumerate(self.tapes[tape]):
                if no_decode == 0:
                    op = Op.Type.fromint(val)
                    no_decode = Op.rawfollows(op)
                else:
                    no_decode -= 1
                    op = ""
                print(fmt % (i, val, op))
