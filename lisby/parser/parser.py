from typing import List

import ply.lex as plex

from .node import (
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
from lisby.shared import LisbySyntaxError

INT_MAX = 2 ** 63
INT_MIN = -(2 ** 63)


class End(Exception):
    def __init__(self):
        super().__init__("End of tokens")


class IntegerSize(Exception):
    def __init__(self, token: plex.LexToken, message) -> None:
        super().__init__("integer too large/small: %s: %s" % (token, message))


class Parser:
    def __init__(self, debug=False):
        self.debug = debug
        self.toks: List[plex.LexToken] = []

    def _debug(self, msg: str):
        if self.debug:
            print("parser: %s" % msg)

    def _cur(self) -> plex.LexToken:
        return self.toks[0]

    def _next(self) -> plex.LexToken:
        if len(self.toks) == 1:
            assert self.toks[0].type == "END"
            raise End
        self.toks = self.toks[1:]
        return self.toks[0]

    def _accept(self, ty: str) -> None:
        cur = self._cur()
        if cur.type == ty:
            self._next()
        else:
            raise LisbySyntaxError(cur, "expecting %s, got %s" % (ty, cur.type))

    def _atom(self) -> Node:
        cur = self._cur()
        ret: Node = None
        if cur.type == "INT":
            if cur.value > INT_MAX:
                raise IntegerSize(cur, "integer too large")
            elif cur.value <= INT_MIN:
                raise IntegerSize(cur, "integer too small")
            ctor = Int  # type: ignore
        elif cur.type == "FLOAT":
            ctor = Float  # type: ignore
        elif cur.type == "SYMBOL":
            ctor = Symbol  # type: ignore
        elif cur.type == "STRING":
            ctor = String  # type: ignore
        elif cur.type == "TRUE":
            ctor = TTrue  # type: ignore
        elif cur.type == "FALSE":
            ctor = TFalse  # type: ignore
        else:
            raise LisbySyntaxError(cur, "Unexpected token")
        ret = ctor(cur, cur.value)
        self._debug("atom -> %s" % ret)
        try:
            self._next()
        finally:
            return ret

    def _apply(self) -> Node:
        self._debug("application")
        self._accept("LPAREN")
        cur = self._cur()
        if cur.type == "RPAREN":
            self._accept("RPAREN")
            return Unit(cur)
        what = self._parse()
        args = []
        # The tokens may run out while we are parsing the application.
        try:
            while self._cur().type != "RPAREN":
                arg = self._parse()
                self._debug("arg -> %s" % arg)
                args.append(arg)
        except End:
            raise LisbySyntaxError(cur, "Application ended abruptly")
        self._accept("RPAREN")
        self._debug(
            "apply of %s with args <%s>"
            % (what, ", ".join(["%s" % arg for arg in args]))
        )
        return Application(cur, applier=what, args=args)

    def _quoted(self):
        cur = self._cur()
        self._debug("quote")
        self._accept("QUOTE")
        return Quoted(cur, self._parse())

    def _quasiquoted(self):
        cur = self._cur()
        self._debug("quasiquote")
        self._accept("QUASIQUOTE")
        return Quasiquoted(cur, self._parse())

    def _unquoted(self):
        cur = self._cur()
        self._debug("unquote")
        self._accept("UNQUOTE")
        return Unquoted(cur, self._parse())

    def _parse(self) -> Node:
        cur = self._cur()
        if cur.type == "LPAREN":
            return self._apply()
        elif cur.type == "QUOTE":
            return self._quoted()
        elif cur.type == "QUASIQUOTE":
            return self._quasiquoted()
        elif cur.type == "UNQUOTE":
            return self._unquoted()
        else:
            return self._atom()

    def parse(self, toks: List[plex.LexToken]) -> List[Node]:
        if len(toks) == 0:
            return []
        self._debug("tokens: %s" % toks)
        self.toks = toks
        forest = []
        while self._cur().type != "END":
            try:
                node = self._parse()
                forest.append(node)
                self._debug("parsed node: %s" % node)
            except End:
                self._debug("end of tokens")
                break
        return forest
