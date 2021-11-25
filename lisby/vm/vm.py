import array
from typing import List, Dict, Union
from struct import unpack
import operator

from lisby.shared import LisbyRuntimeError
from .bytecode import Op
from .value import (
    Environment,
    Value,
    Int,
    Float,
    String,
    Symbol,
    Builtin,
    VTrue,
    VFalse,
    Closure,
    VList,
    Quoted,
    Continuation,
    Address,
    Quasiquoted,
    Unquoted,
)
from .program import Program


builtins = {
    "+": Op.Type.ADD,
    "-": Op.Type.SUB,
    "*": Op.Type.MUL,
    "/": Op.Type.DIV,
    "%": Op.Type.MOD,
    "=": Op.Type.EQ,
    "!=": Op.Type.NEQ,
    "<": Op.Type.LT,
    "<=": Op.Type.LE,
    ">": Op.Type.GT,
    ">=": Op.Type.GE,
    "not": Op.Type.NOT,
    "head": Op.Type.HEAD,
    "tail": Op.Type.TAIL,
    "dump": Op.Type.DUMP,
    "^": Op.Type.XOR,
    "&": Op.Type.AND,
    "|": Op.Type.OR,
    "~": Op.Type.INV,
}


class ArithmeticError(Exception):
    pass


class VM:
    def __init__(self) -> None:
        self.tapes: List = []
        self.stack: List[Value] = []
        self.topenv = Environment(None)
        self.env = self.topenv
        self.program: Program = None
        self.tape: int = 0
        self.pc: int = -1
        self.rets: List[Address] = []
        self.quoted: int = 0
        self.quasiquoted: int = 0
        self.trace = False

    def _trace(self, msg):
        if not self.trace:
            return
        print("vm: ", msg)

    def _dump_stack(self) -> None:
        print("# stack (%d)" % len(self.stack))
        for (i, val) in enumerate(self.stack):
            print("%4d  %s" % (i, val))

    def _dump_env(self) -> None:
        curenv = self.env
        print("# environment")
        while curenv:
            print("## env=%d (%d)" % (curenv.id, len(curenv.values)))
            for symindex, symvalue in curenv.values.items():
                symname = self.program.symbol_name(symindex)
                print("%4d  %15s  %s" % (symindex, symname, symvalue))
            curenv = curenv.parent

    def _push(self, val: Value) -> None:
        if self.quoted > 0:
            val = Quoted(val, self.quoted)
            self.quoted = 0
        elif self.quasiquoted > 0:
            val = Quasiquoted(val, self.quasiquoted)
            self.quasiquoted = 0
        self.stack.append(val)

    def _pop(self) -> Value:
        assert len(self.stack) > 0, "stack ran out"
        top: Value = self.stack[-1]
        self.stack = self.stack[:-1]
        return top

    def _pop_noret(self) -> None:
        self.stack = self.stack[:-1]

    def _read_bytes(self, pc: int, n: int) -> bytes:
        return bytes(self.tapes[self.tape][pc : pc + n])

    def _read_int(self, pc: int) -> int:
        return unpack("<q", self.tapes[self.tape][pc : pc + 8])[0]

    def _read_float(self, pc: int) -> float:
        return unpack("<d", self.tapes[self.tape][pc : pc + 8])[0]

    def _store(self, env: Environment, pc: int) -> None:
        val = self._pop()
        target = self._read_int(pc)
        tname = self.program.symbol_name(target)
        env = self._find_sym_env(target)
        env.values[target] = val
        self._trace("[%d] storing %s -> %s" % (env.id, val, tname))

    def _find_sym_env(self, symindex: int) -> Environment:
        curenv = self.env
        while curenv:
            try:
                curenv.values[symindex]
                return curenv
            except KeyError:
                curenv = curenv.parent
        sym = self.program.symbol_name(symindex)
        raise LisbyRuntimeError("Cannot resolve symbol: %s" % sym)

    def rewind_after_error(self) -> int:
        self.pc = len(self.tapes[0])
        return self.pc

    def run(self, program: Program, pc: int = 0, trace: bool = False) -> int:
        self._trace("running from pc=%d" % pc)
        if trace:
            program.dump()
        self.tapes = [array.array("B", tape) for tape in program.tapes]
        self.program = program
        self.trace = trace
        self.stack = []
        if len(self.tapes) == 0:
            print("No tapes.")
            return 0
        if len(self.tapes[0]) == 0:
            print("Nothing to run.")
            return 0
        assert self.tapes[0][-1] == Op.Type.HALT

        class Halted(Exception):
            pass

        def halt(pc: int) -> int:
            self._trace("halted, stack: %s" % [str(v) for v in self.stack])
            raise Halted()

        def arith(op):
            left = self._pop()
            # We'll save one pop on arithmetic by overwriting the top value.
            right = self.stack[-1]
            # Our arithmetic on two values has four possibilities:
            #   - float, float
            #   - float, int
            #   - int, int,
            #   - int, float
            #
            # As most others, we'll do implicit conversion to float if either
            # or both are float.
            if isinstance(left, Int) and isinstance(right, Int):
                r = op(left.value, right.value)
                result = Int(int(r))
            elif (
                isinstance(left, Float)
                and isinstance(right, Float)
                or isinstance(left, Int)
                and isinstance(right, Float)
                or isinstance(left, Float)
                and isinstance(right, Int)
            ):
                result = Float(op(left.value, right.value))  # type: ignore
            else:
                raise ArithmeticError(
                    "cannot %s types %s and %s: %s vs. %s"
                    % (str(op), type(left).__name__, type(right).__name__, left, right)
                )  # type: ignore
            self.stack[-1] = result

        def add(pc: int) -> int:
            arith(operator.add)
            return pc

        def sub(pc: int) -> int:
            arith(operator.sub)
            return pc

        def mul(pc: int) -> int:
            arith(operator.mul)
            return pc

        def div(pc: int) -> int:
            arith(operator.truediv)
            return pc

        def xor(pc: int) -> int:
            arith(operator.xor)
            return pc

        def mod(pc: int) -> int:
            arith(operator.mod)
            return pc

        def andd(pc: int) -> int:
            arith(operator.and_)
            return pc

        def orr(pc: int) -> int:
            arith(operator.or_)
            return pc

        def inv(pc: int) -> int:
            un = self.stack[-1]
            if not isinstance(un, Int):
                raise ArithmeticError(
                    "bitwise inversion applies only to ints, got %s"
                    % (type(un).__name__)
                )
            un.value = ~un.value & 0xFFFFFFFFFFFFFFFF
            return pc

        def pushi(pc: int) -> int:
            self._push(Int(self._read_int(pc)))
            return pc + 8

        def pushf(pc: int) -> int:
            self._push(Float(self._read_float(pc)))
            return pc + 8

        def pushtrue(pc: int) -> int:
            self._push(VTrue())
            return pc

        def pushfalse(pc: int) -> int:
            self._push(VFalse())
            return pc

        def pushsy(pc: int) -> int:
            symindex = self._read_int(pc)
            try:
                env = self._find_sym_env(symindex)
                self._push((env.values[symindex]).copy())
            except LisbyRuntimeError as e:
                symname = self.program.symbol_name(symindex)
                if symname in builtins:
                    self._push(Builtin(symname))
                else:
                    self._dump_env()
                    raise e
            return pc + 8

        def pushsyraw(pc: int) -> int:
            symindex = self._read_int(pc)
            symname = self.program.symbol_name(symindex)
            self._push(Symbol(symname))
            return pc + 8

        def pushstr(pc: int) -> int:
            strindex = self._read_int(pc)
            self._push(String(self.program.string_value(strindex)))
            return pc + 8

        def pushunit(pc: int) -> int:
            self._push(VList([]))
            return pc

        def pushclosure(pc: int) -> int:
            # To create a new closure, we need two things:
            #   1) The current environment, which it closes over
            #   2) The program tape for the closure's code.
            self._push(Closure(self.env, self._read_int(pc)))
            return pc + 8

        def pushcont(pc: int) -> int:
            # We don't want to save the Continuation and Closure from the
            # stack.
            self._push(
                Continuation(self.stack[:-2], self.rets, self.tape, self._read_int(pc))
            )
            return pc + 8

        def quote(pc: int) -> int:
            self.quoted = self._read_int(pc)
            return pc + 8

        def pop(pc: int) -> int:
            self._pop_noret()
            return pc

        def store(pc: int) -> int:
            self._store(self.env, pc)
            return pc + 8

        def storetop(pc: int) -> int:
            self._store(self.topenv, pc)
            return pc + 8

        def builtin(pc: int, fun: Union[Builtin, Symbol]):
            # Keep this in sync with `builtins`.
            i = {
                "+": add,
                "-": sub,
                "*": mul,
                "/": div,
                "%": mod,
                "=": eq,
                "!=": neq,
                "<": lt,
                "<=": le,
                ">": gt,
                ">=": ge,
                "not": nott,
                "head": head,
                "tail": tail,
                "dump": dump,
                "^": xor,
                "&": andd,
                "|": orr,
                "~": inv,
            }
            if fun.value in i:
                return i[fun.value](pc)
            else:
                raise LisbyRuntimeError("unrecognized builtin: %s" % fun)

        def call(pc: int) -> int:
            callee = self._pop()
            if isinstance(callee, Closure):
                self.rets.append(Address(self.tape, pc, self.env))
                self.tape = callee.tape
                self.env = Environment(callee.parent)
                return 0
            elif isinstance(callee, Continuation):
                val = self.stack[-1]
                self.stack = callee.stack
                self.stack.append(val)
                self.rets = callee.rets
                self.tape = callee.tape
                return callee.pc
            elif isinstance(callee, Builtin) or isinstance(callee, Symbol):
                return builtin(pc, callee)
            else:
                raise LisbyRuntimeError(
                    "can only apply a continuation, closure or a builtin, got %s"
                    % (type(callee).__name__)
                )

        def tailcall(pc: int) -> int:
            assert 0, "XXX IMPLEMENT ME"
            return pc

        def ret(pc: int) -> int:
            addr = self.rets[-1]
            self.rets = self.rets[:-1]
            self.tape = addr.tape
            self.env = addr.env
            return addr.pc

        def comp(op):
            left = self._pop()
            right = self.stack[-1]
            if type(left) != type(right):
                raise LisbyRuntimeError(
                    "Non-comparable types: %s vs. %s " % (left, right)
                )
            if op(left.value, right.value):
                self.stack[-1] = VTrue()
            else:
                self.stack[-1] = VFalse()

        def eq(pc: int) -> int:
            comp(operator.eq)
            return pc

        def neq(pc: int) -> int:
            comp(operator.ne)
            return pc

        def gt(pc: int) -> int:
            comp(operator.gt)
            return pc

        def ge(pc: int) -> int:
            comp(operator.ge)
            return pc

        def lt(pc: int) -> int:
            comp(operator.lt)
            return pc

        def le(pc: int) -> int:
            comp(operator.le)
            return pc

        def nott(pc: int) -> int:
            un = self.stack[-1]
            if not isinstance(un, VFalse) and not isinstance(un, VTrue):
                raise ArithmeticError(
                    "not only applies to boolean values, got %s" % (type(un).__name__)
                )
            if isinstance(un, VTrue):
                self.stack[-1] = VFalse()
            else:
                self.stack[-1] = VTrue()
            return pc

        def _bool_check(val: Value) -> None:
            if not isinstance(val, VTrue) and not isinstance(val, VFalse):
                raise LisbyRuntimeError("not a conditional value, got %s" % val)

        def jt(pc: int) -> int:
            val = self._pop()
            _bool_check(val)
            jpc = self._read_int(pc)
            if val.value:
                return jpc
            return pc + 8

        def jf(pc: int) -> int:
            val = self._pop()
            _bool_check(val)
            jpc = self._read_int(pc)
            if not val.value:
                return jpc
            return pc + 8

        def jmp(pc: int) -> int:
            return self._read_int(pc)

        def declare(pc: int) -> int:
            symindex = self._read_int(pc)
            self.env.values[symindex] = None
            self._trace("declare symbol `%s'" % self.program.symbol_name(symindex))
            return pc + 8

        def printt(pc: int) -> int:
            val = self._pop()
            res = str(val)
            print(res, end="")
            return pc

        def listt(pc: int) -> int:
            n = self._read_int(pc)
            vals: List[Value] = []
            for n in range(n):
                vals.append(self._pop())
            self._push(VList(vals))
            return pc + 8

        def _list_check_type(val: Value, name: str) -> None:
            if not isinstance(val, VList):
                raise LisbyRuntimeError(
                    "%s expects a list, got %s " % (name, type(val).__name__)
                )

        def _list_check(val: Value, name: str) -> None:
            _list_check_type(val, name)
            if len(val.value) == 0:
                raise LisbyRuntimeError("%s got an empty list" % name)

        def head(pc: int) -> int:
            _list_check(self.stack[-1], "head")
            self.stack[-1] = self.stack[-1].value[0]
            return pc

        def tail(pc: int) -> int:
            _list_check(self.stack[-1], "tail")
            self.stack[-1].value = self.stack[-1].value[1:]
            return pc

        def listcat(pc: int) -> int:
            label = "list concatenation"
            _list_check_type(self.stack[-1], label)
            _list_check_type(self.stack[-2], label)
            lst = self._pop()
            self.stack[-1].value += lst.value
            return pc

        def evall(pc: int) -> int:
            n = self._read_int(pc)
            epr = self._read_bytes(pc + 8, n)
            ep = Program.deserialize(epr)
            evm = VM()
            evm.run(ep, trace=self.trace)
            self.stack.append(evm.stack[-1])
            return pc + 8 + n

        def dump(pc: int) -> int:
            self.program.dump()
            self._dump_env()
            self._dump_stack()
            self._push(VList([]))
            return pc

        def newenv(pc: int) -> int:
            self.env = Environment(self.env)
            return pc

        def departenv(pc: int) -> int:
            self.env = self.env.parent
            return pc

        def quasiquote(pc: int) -> int:
            self.quasiquoted = self._read_int(pc)
            return pc + 8

        ops = (
            halt,
            add,
            sub,
            mul,
            div,
            xor,
            mod,
            andd,
            orr,
            inv,
            pushi,
            pushf,
            pushstr,
            pushsy,
            pushsyraw,
            pushtrue,
            pushfalse,
            pushunit,
            pushclosure,
            pushcont,
            quote,
            pop,
            call,
            tailcall,
            ret,
            jt,
            jf,
            jmp,
            store,
            storetop,
            eq,
            neq,
            gt,
            ge,
            lt,
            le,
            nott,
            declare,
            printt,
            listt,
            head,
            tail,
            listcat,
            evall,
            dump,
            newenv,
            departenv,
            quasiquote,
        )
        assert len(ops) == Op.Type._MAX, "%d != %d" % (len(ops), int(Op.Type._MAX))

        try:
            while True:
                op = self.tapes[self.tape][pc]
                pc += 1
                handler = ops[op]
                self._trace(
                    "[tape=%04d, pc=%04d, env=%d]: %s"
                    % (self.tape, pc, self.env.id, handler.__name__)
                )
                pc = ops[op](pc)
                if self.trace:
                    self._dump_stack()
                    self._dump_env()
        except Halted:
            pass
        except IndexError:
            # XXX Collides with index errors other than from `code` indexing.
            raise LisbyRuntimeError("Program ended abruptly.")
        except ArithmeticError as e:
            raise LisbyRuntimeError("Arithmetic error: %s" % e)
        self.pc = pc
        return pc
