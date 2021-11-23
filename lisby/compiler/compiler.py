from typing import List, Callable, Dict
from copy import deepcopy
from struct import pack

from lisby.shared import LisbySyntaxError
from lisby.parser import (
    Node,
    Application,
    Int,
    Float,
    String,
    Symbol,
    Unit,
    TTrue,
    TFalse,
    Quoted,
    Quasiquoted,
    Unquoted,
)
from lisby.vm import Op, Program, builtins


def nodes_to_str(expr) -> str:
    if isinstance(expr, list):
        res = []
        for e in expr:
            res.append(nodes_to_str(e))
        return ", ".join(res)
    return str(expr)


class Macro:
    def __init__(
        self,
        c: "Compiler",
        p: Program,
        name: str,
        params: List[str],
        body: List[Node],
        debug: bool = False,
    ) -> None:
        self.name = name
        self.params = params
        self.body = body
        self.debug = debug
        self.compiler = c
        self.program = p

    def _debug(self, msg: str) -> None:
        if not self.debug:
            return
        print("macro:", msg)

    def _expand(self, args: List[Node], n: Node, quotes: int = 0) -> Node:
        self._debug("expanding[%d]: %s" % (quotes, n))
        if isinstance(n, Symbol):
            if quotes == 0 and n.value in self.params:
                rep = args[self.params.index(n.value)]
                self._debug("replacing %s with %s" % (n.value, rep))
                return rep
        elif isinstance(n, Application):
            members = n.tolist()
            for i in range(len(members)):
                members[i] = self._expand(args, members[i], quotes)
            n.update(members)
        elif isinstance(n, Quasiquoted):
            n.left = self._expand(args, n.left, quotes + 1)
        elif isinstance(n, Unquoted):
            n.left = self._expand(args, n.left, quotes - 1)
        return n

    def expand(self, n: Application) -> None:
        args = n.args()
        self._debug("`%s' of node %s" % (self.name, n))
        if len(args) != len(self.params):
            raise LisbySyntaxError(
                n,
                "Macro %s expects %d arguments, got %d"
                % (self.name, len(self.params), len(args)),
            )
        body_orig = deepcopy(self.body)
        for node in self.body:
            node = self._expand(args, node)
            self.compiler._compile(self.program, node)
        self.body = body_orig
        self._debug("finished expansion")


class Compiler:
    def __init__(self, debug: bool = False) -> None:
        self.debug = debug
        self.macros: Dict[str, Macro] = {}
        self.forms: Dict[str, Callable[[Program, Application], None]] = {
            "let": self._let,
            "define": self._define,
            "lambda": self._lambda,
            "if": self._if,
            "begin": self._begin,
            "set!": self._set,
            "display": self._display,
            "list": self._list,
            "::": self._concat_list,
            "eval": self._eval,
            "or": self._or,
            "and": self._and,
            "call/cc": self._callcc,
            "defmacro": self._defmacro,
        }

    def _debug(self, msg: str) -> None:
        if not self.debug:
            return
        print("compiler: %s" % msg)

    def _builtin(self, p: Program, node: Application) -> None:
        app = node.applier()
        assert isinstance(app, Symbol)
        self._compile_list(p, node.args())
        p.emit(builtins[app.value])

    def _emit_int(self, p: Program, val: int) -> None:
        p.emitraw(pack("<q", val))

    def _emit_float(self, p: Program, val: float) -> None:
        p.emitraw(pack("<d", val))

    def _symbol_apply(self, p: Program, app: Application) -> None:
        sym, args = app.applier(), app.args()
        self._debug("symbol apply: %s with args %s " % (sym, nodes_to_str(args)))
        symindex = p.symbol_find(sym.value)
        self._compile_list(p, args)
        self._push_symbol(p, sym)
        p.emit(Op.Type.CALL)

    def _push_symbol(self, p: Program, sy: Symbol) -> None:
        symindex = p.find_or_add_sym(sy.value)
        p.emit(Op.Type.PUSHSY)
        self._emit_int(p, symindex)

    def _push_string(self, p: Program, val: str) -> None:
        strindex = p.find_or_add_str(val)
        p.emit(Op.Type.PUSHSTR)
        self._emit_int(p, strindex)

    def _atom(self, p: Program, atom: Node) -> None:
        self._debug("atom: %s" % atom)
        if isinstance(atom, Int):
            p.emit(Op.Type.PUSHI)
            self._emit_int(p, atom.value)
        elif isinstance(atom, Float):
            p.emit(Op.Type.PUSHF)
            self._emit_float(p, atom.value)
        elif isinstance(atom, Symbol):
            self._push_symbol(p, atom)
        elif isinstance(atom, TTrue):
            p.emit(Op.Type.PUSHTRUE)
        elif isinstance(atom, TFalse):
            p.emit(Op.Type.PUSHFALSE)
        elif isinstance(atom, String):
            self._push_string(p, atom.value)
        elif isinstance(atom, Unit):
            p.emit(Op.Type.PUSHUNIT)
        else:
            raise LisbySyntaxError(
                atom,
                "Atom expected, got %s (%s)"
                % (nodes_to_str(atom), type(atom).__name__),
            )

    def _or(self, p: Program, node: Application) -> None:
        """_or generates the short-circuiting boolean OR"""
        self._debug("or")
        orr = node.args()
        if len(orr) != 2:
            raise LisbySyntaxError(node, "or expects two arguments")
        first, second = orr
        self._compile(p, first)
        p.emit(Op.Type.JT)
        patch_true = p.emitpholder()
        self._compile(p, second)
        p.emit(Op.Type.JF)
        patch_false = p.emitpholder()
        pc_true = p.cursor()
        p.emit(Op.Type.PUSHTRUE)
        p.emit(Op.Type.JMP)
        patch_end = p.emitpholder()
        pc_false = p.cursor()
        p.emit(Op.Type.PUSHFALSE)
        pc_end = p.cursor()
        p.patch(p.tape, patch_false, pack("<q", pc_false))
        p.patch(p.tape, patch_true, pack("<q", pc_true))
        p.patch(p.tape, patch_end, pack("<q", pc_end))

    def _and(self, p: Program, node: Application) -> None:
        """_or generates the short-circuiting boolean AND"""
        self._debug("and")
        orr = node.args()
        if len(orr) != 2:
            raise LisbySyntaxError(node, "and expects two arguments")
        # Our goal is to compile the following:
        # - evaluate first condition
        # - it it failed, jump to a PUSHFALSE
        # - evaluate second condition
        # - if it failed, jump to the same PUSHFALSE
        # - do PUSHTRUE & jump over PUSHFALSE
        # - push PUSHFALSE
        first, second = orr
        self._compile(p, first)
        p.emit(Op.Type.JF)
        patch_false = p.emitpholder()
        self._compile(p, second)
        p.emit(Op.Type.JF)
        patch_false2 = p.emitpholder()
        p.emit(Op.Type.PUSHTRUE)
        p.emit(Op.Type.JMP)
        patch_end = p.emitpholder()
        pc_false = p.cursor()
        p.emit(Op.Type.PUSHFALSE)
        pc_end = p.cursor()
        p.patch(p.tape, patch_false, pack("<q", pc_false))
        p.patch(p.tape, patch_false2, pack("<q", pc_false))
        p.patch(p.tape, patch_end, pack("<q", pc_end))

    def _concat_list(self, p: Program, node: Application) -> None:
        self._debug("::")
        args = node.args()
        if len(args) < 2:
            raise LisbySyntaxError(
                node, "List concatenation needs at least two parameters"
            )
        for arg in args:
            self._compile(p, arg)
        for n in range(len(args) - 1):
            p.emit(Op.Type.LISTCAT)

    def _defmacro(self, p: Program, node: Application) -> None:
        """Implements unhygienic search-and-replace macros"""
        self._debug("defmacro")
        args = node.args()
        if len(args) < 2:
            raise LisbySyntaxError(node, "defmacro needs at least two parameters")
        if not isinstance(args[0], Application):
            raise LisbySyntaxError(
                args[0], "No macro parameters given, got %s" % (type(args[0]).__name__)
            )
        rawparams = args[0].tolist()
        if len(rawparams) == 0:
            raise LisbySyntaxError(rawparams, "Need at least macro name")
        params = []
        for param in rawparams:
            if not isinstance(param, Symbol):
                raise LisbySyntaxError(
                    param,
                    "Macro parameter not a symbol, got %s" % (type(param).__name__),
                )
            params.append(param.value)
        name = params[0]
        params = params[1:]
        self._debug("macro `%s' with parameters: %s" % (name, params))
        if name in self.macros:
            raise LisbySyntaxError(node, "Macro %s already defined" % name)
        if name in self.forms:
            raise LisbySyntaxError(
                node, "Macro name %s collides with a special form" % name
            )
        self.macros[name] = Macro(self, p, name, params, args[1:], self.debug)

    ccerr = (
        "call/cc parameter has to be a lambda expression "
        + "with one parameter, got %s [%d]"
    )

    def _callcc(self, p: Program, node: Application) -> None:
        """Implements and imitates Scheme's call-with-current-continuation"""
        self._debug("call/cc")
        args = node.args()
        if len(args) != 1:
            raise LisbySyntaxError(node, "call/cc accepts only one paramter")
        param = args[0]
        if not isinstance(param, Application):
            raise LisbySyntaxError(node, Compiler.ccerr % (type(param).__name__, 1))
        parargs = param.tolist()
        if len(parargs) < 2:
            raise LisbySyntaxError(node, Compiler.ccerr % (type(param).__name__, 2))
        if not isinstance(parargs[0], Symbol) or parargs[0].value != "lambda":
            raise LisbySyntaxError(node, Compiler.ccerr % (type(param).__name__, 3))
        binds = parargs[1]
        self._debug(binds)
        if not isinstance(binds, Application) or len(binds.tolist()) != 1:
            raise LisbySyntaxError(node, Compiler.ccerr % (type(param).__name__, 4))
        exprs = parargs[2:]
        if not isinstance(binds, Application):
            raise LisbySyntaxError(node, Compiler.ccerr % (type(param).__name__, 5))
        params = binds.tolist()
        p.emit(Op.Type.PUSHCONT)
        patch_cont_end = p.emitpholder()
        self._lambda_unpacked(p, params, exprs)
        p.emit(Op.Type.CALL)
        pc_after = p.cursor()
        p.patch(p.tape, patch_cont_end, pack("<q", pc_after))

    def _list(self, p: Program, node: Application) -> None:
        self._debug("list")
        args = node.args()
        for arg in reversed(args):
            self._compile(p, arg)
        p.emit(Op.Type.LIST)
        self._emit_int(p, len(args))

    def _display(self, p: Program, node: Application) -> None:
        self._debug("display")
        for arg in node.args():
            self._compile(p, arg)
            p.emit(Op.Type.PRINT)
        self._push_string(p, "\n")
        p.emit(Op.Type.PRINT)
        p.emit(Op.Type.PUSHUNIT)

    def _begin(self, p: Program, node: Application) -> None:
        self._debug("begin")
        args = node.args()
        if len(args) == 0:
            raise LisbySyntaxError(node, "begin form needs at least one expression")
        self._compile_exprs(p, args)

    def _set(self, p: Program, node: Application) -> None:
        self._debug("set!")
        args = node.args()
        if len(args) != 2:
            raise LisbySyntaxError(
                node, "set! form expects two arguments, binding and expression"
            )
        target, val = args
        if not isinstance(target, Symbol):
            raise LisbySyntaxError(target, "set! target should be a symbol")
        self._compile(p, val)
        self._store(p, target.value)
        p.emit(Op.Type.PUSHUNIT)

    def _if(self, p: Program, node: Application) -> None:
        self._debug("if")
        # The if form:
        #   `(if cond-expr then-expr else-expr)`
        iff = node.args()
        if len(iff) != 3:
            raise LisbySyntaxError(
                node, "if expects three arguments: cond-expr then-expr else-expr"
            )
        cond, then, els = iff
        self._compile(p, cond)
        p.emit(Op.Type.JF)
        patch_false = p.emitpholder()
        self._compile(p, then)
        p.emit(Op.Type.JMP)
        patch_end = p.emitpholder()
        # Patch the else branch's address for JF.
        pc_else = p.cursor()
        p.patch(p.tape, patch_false, pack("<q", pc_else))
        self._compile(p, els)
        # Patch the JMP target after else.
        pc_end = p.cursor()
        p.patch(p.tape, patch_end, pack("<q", pc_end))

    def _application(self, p: Program, node: Application) -> None:
        self._debug("application")
        # The first case is applying a symbol. This means that we expect a
        # binding of `what` to represent something callable.
        app = node.applier()
        if isinstance(app, Symbol):
            name = app.value
            # Builtin is a form which has a special instruction
            if name in builtins:
                self._builtin(p, node)
            # or the application may be a special form...
            elif name in self.forms:
                self.forms[name](p, node)
            # or the name of a macro
            elif name in self.macros:
                self.macros[name].expand(node)
            # or it must be a application of a bound symbol.
            else:
                self._symbol_apply(p, node)
        # The second case is applying an application. This means that we
        # expect to see a lambda being returned, which we then apply with the
        # arguments.
        elif isinstance(app, Application):
            self._compile_list(p, node.args())
            self._application(p, app)
            p.emit(Op.Type.CALL)
        else:
            raise LisbySyntaxError(node, "Cannot apply with %s" % type(node).__name__)

    def _lambda(self, p: Program, node: Application) -> None:
        # Our lambda form is straight from Scheme:
        #   `(lambda (arg1 ... argN) expr1 ... exprN)`
        args = node.args()
        self._debug("lambda: %s" % nodes_to_str(node.tolist()))
        if len(args) < 2:
            raise LisbySyntaxError(
                node, "lambda form needs at least two parameters, got %d" % len(args)
            )
        params: List[Node] = None
        if isinstance(args[0], Application):
            params = args[0].tolist()
        elif isinstance(args[0], Unit):
            params = []
        else:
            raise LisbySyntaxError(
                params,
                "lambda parameters have to be a list, got %s " % type(params).__name__,
            )
        exprs = args[1:]
        self._lambda_unpacked(p, params, exprs)

    def _lambda_unpacked(
        self, p: Program, params: List[Node], exprs: List[Node]
    ) -> None:
        self._debug(
            "lambda unpacked: params %s with with exprs %s"
            % (nodes_to_str(params), nodes_to_str(exprs))
        )
        (tape_orig, tape_new) = p.lambda_start()
        for param in params:
            if not isinstance(param, Symbol):
                raise LisbySyntaxError(
                    param,
                    "parameter has to be a symbol, got %s " % type(param).__name__,
                )
            symindex = p.find_or_add_sym(param.value)
            p.emit(Op.Type.DECLARE)
            self._emit_int(p, symindex)
            p.emit(Op.Type(Op.Type.STORE))
            self._emit_int(p, symindex)
        self._compile_exprs(p, exprs)
        p.lambda_end(tape_orig)
        p.emit(Op.Type.PUSHCLOSURE)
        self._emit_int(p, tape_new)

    def _define(self, p: Program, node: Application) -> None:
        self._debug("define")
        # Our define permits two forms:
        #   - `(define x ...)` meaning a regular top-level binding
        #   - `(define (<name> <arg1> ... <argN>) ... )` for lambda binding
        # The latter is the shorthand for `def <name> (lambda ...)`.
        args = node.args()
        if len(args) < 2:
            raise LisbySyntaxError(node, "define needs two parameters")
        binding = args[0]
        exprs = args[1:]
        if isinstance(binding, Symbol):
            if len(exprs) > 1:
                raise LisbySyntaxError(
                    node, "symbol definition accepts only one expression"
                )
            self._define_symbol(p, binding.value, exprs[0])
        elif isinstance(binding, Application):
            self._define_lambda(p, binding.tolist(), exprs)
        else:
            raise LisbySyntaxError(node, "def should have `binding expr`")
        p.emit(Op.Type.PUSHUNIT)

    def _define_symbol(self, p: Program, name: str, expr: Node) -> None:
        assert len(name) > 0, "no symbol name"
        self._compile(p, expr)
        p.emit(Op.Type.DECLARE)
        self._emit_int(p, p.find_or_add_sym(name))
        self._storetop(p, name)

    def _define_lambda(self, p: Program, args: List[Node], exprs: List[Node]) -> None:
        self._debug("define lambda")
        if len(args) < 1:
            raise LisbySyntaxError(
                args, "lambda definition needs at least binding name"
            )
        for arg in args:
            if not isinstance(arg, Symbol):
                raise LisbySyntaxError(
                    arg,
                    "lambda argument must be a symbol, got %s" % (nodes_to_str(arg)),
                )
        binding: Symbol = args[0]  # type: ignore
        name = binding.value
        self._debug(
            "lambda binding: `%s' with args %s" % (name, nodes_to_str(args[1:]))
        )
        p.emit(Op.Type.DECLARE)
        self._emit_int(p, p.find_or_add_sym(name))
        self._lambda_unpacked(p, args[1:], exprs)
        self._storetop(p, name)

    def _storetop(self, p: Program, binding: str) -> None:
        self._debug("storetop: %s" % binding)
        p.emit(Op.Type.STORETOP)
        self._emit_int(p, p.find_or_add_sym(binding))

    def _store(self, p: Program, binding: str) -> None:
        symindex = p.find_or_add_sym(binding)
        p.emit(Op.Type.STORE)
        self._emit_int(p, symindex)

    def _let(self, p: Program, let: Application) -> None:
        self._debug("let")
        # A let expression is of the form
        #
        #   (let ((arg1 val1) ... (argN valN)) expr1 ... exprN)
        #
        args = let.args()
        if len(args) < 2:
            raise LisbySyntaxError(let, "Invalid let form")
        raw_params = args[0]
        exprs = args[1:]
        if not isinstance(raw_params, Application):
            raise LisbySyntaxError(raw_params, "Let parameters not a list")
        params = {}
        p.emit(Op.Type.NEWENV)
        for raw_param in raw_params.tolist():
            if not isinstance(raw_param, Application):
                raise LisbySyntaxError(raw_param, "Let parameter not a list")
            values = raw_param.tolist()
            if len(values) != 2:
                raise LisbySyntaxError(values, "Expecting one binding value")
            binding = values[0]
            value = values[1]
            if not isinstance(binding, Symbol):
                raise LisbySyntaxError(binding, "Let binding not a symbol")
            name = binding.value
            params[name] = value
            self._debug("store: %s <- %s" % (binding, value))
            p.emit(Op.Type.DECLARE)
            self._emit_int(p, p.find_or_add_sym(name))
            self._compile(p, value)
            self._store(p, name)
        self._debug("params: %s" % nodes_to_str(params))
        self._compile_exprs(p, exprs)
        p.emit(Op.Type.DEPARTENV)

    def _eval(self, p: Program, node: Application) -> None:
        self._debug("eval")
        args = node.args()
        if len(args) != 1:
            raise LisbySyntaxError(node, "eval expects one parameter")
        p.emit(Op.Type.EVAL)

    def _quoted_contents(self, p: Program, q: Node, level: int) -> None:
        def emit_quotes():
            p.emit(Op.Type.QUOTED)
            self._emit_int(p, level)

        self._debug("quoted contents: %s (%s)" % (q, type(q).__name__))
        if isinstance(q, Application):
            members = q.tolist()
            for member in reversed(members):
                self._quoted_contents(p, member, 0)
            emit_quotes()
            p.emit(Op.Type.LIST)
            self._emit_int(p, len(members))
        # Quoted symbols are an exception: We don't to push them such that
        # they are immediately resolved.
        elif isinstance(q, Symbol):
            emit_quotes()
            symindex = p.find_or_add_sym(q.value)
            p.emit(Op.Type.PUSHSYRAW)
            self._emit_int(p, symindex)
        elif isinstance(q, Quoted):
            self._quoted(p, q, level + 1)
        else:
            emit_quotes()
            self._atom(p, q)

    def _quasiquoted_contents(self, p: Program, q: Node, level: int) -> None:
        self._debug("quasiquoted contents [%d]: %s" % (level, q))
        assert q is not None
        # XXX Ugly almost-duplicate handling with quote and quasiquote.

        def emit_quotes():
            p.emit(Op.Type.QUASIQUOTED)
            self._emit_int(p, level)

        if isinstance(q, Application):
            members = q.tolist()
            for member in reversed(members):
                self._quasiquoted_contents(p, member, 0)
            emit_quotes()
            p.emit(Op.Type.LIST)
            self._emit_int(p, len(members))
        elif isinstance(q, Symbol):
            emit_quotes()
            symindex = p.find_or_add_sym(q.value)
            p.emit(Op.Type.PUSHSYRAW)
            self._emit_int(p, symindex)
        elif isinstance(q, Quasiquoted):
            self._quasiquoted(p, q, level + 1)
        elif isinstance(q, Unquoted):
            self._debug("unquote level: %d" % level)
            if level < 0:
                raise LisbySyntaxError(q, "Unquoting too hard")
            elif level == 0:
                self._debug("unquoted -> compiling")
                self._compile(p, q.left)
            else:
                self._debug("unquoted level left")
                self._quasiquoted_contents(p, q.left, level - 1)
        else:
            if level >= 0:
                emit_quotes()
            self._atom(p, q)

    def _quoted(self, p: Program, node: Quoted, level: int) -> None:
        self._debug("quoted: %s (%s)" % (node, type(node).__name__))
        q = node.left
        self._quoted_contents(p, q, level)

    def _quasiquoted(self, p: Program, node: Quasiquoted, level: int) -> None:
        self._debug("quasiquoted: %s (%s)" % (node, type(node).__name__))
        q = node.left
        self._quasiquoted_contents(p, q, level)

    def _compile_exprs(self, p: Program, exprs: List[Node]) -> None:
        for (i, expr) in enumerate(exprs):
            self._compile(p, expr)
            # Only the last expression value will be preserved. This is the
            # simplistic solution -- alternatively we might propagate some
            # kind of a "don't push" notification.
            if i + 1 != len(exprs):
                p.emit(Op.Type.POP)

    def _compile_list(self, p: Program, nodes: List[Node]) -> None:
        for node in reversed(nodes):
            self._compile(p, node)

    def _compile(self, p: Program, node: Node) -> None:
        self._debug("node: %s" % nodes_to_str(node))
        if isinstance(node, Application):
            self._application(p, node)
        elif isinstance(node, Quoted):
            self._quoted(p, node, 0)
        elif isinstance(node, Quasiquoted):
            self._quasiquoted(p, node, 0)
        else:
            self._atom(p, node)

    def compile(self, program: Program, forest: List[Node]) -> Program:
        for node in forest:
            self._compile(program, node)
        program.emit(Op.Type.HALT)
        return program
