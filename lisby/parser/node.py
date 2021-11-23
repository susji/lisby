from typing import List

import ply.lex as plex


class NodeError(Exception):
    def __init__(self, message):
        super().__init__(message)


class Node:
    def __init__(self, token: plex.LexToken, arity: int, left=None, right=None) -> None:
        if arity == 1:
            if left is None:
                raise NodeError("Arity is one and no left node")
        elif arity == 2:
            if left is None:
                raise NodeError("Arity is two and no left node")
            if right is None:
                raise NodeError("Arity is two and no right node")
        elif arity == 0:
            if left is not None:
                raise NodeError("Arity is zero and left node")
            if right is not None:
                raise NodeError("Arity is zero and right node")
        else:
            raise NodeError("Invalid arity: %d" % arity)
        self.token = token
        self.arity = arity
        self.left = left
        self.right = right

    def __repr__(self):
        return "%r(%r, left=%r, right=%r)" % (
            type(self).__name__,
            self.arity,
            self.left,
            self.right,
        )


class Application(Node):
    def __init__(self, tok: plex.LexToken, applier: Node, args: List[Node]) -> None:
        super().__init__(tok, arity=2, left=applier, right=args)

    def __str__(self):
        ret = "(%s" % self.left
        if len(self.right) > 0:
            ret += ", "
            ret += ", ".join(["%s" % arg for arg in self.right])
        ret += ")"
        return ret

    def applier(self):
        return self.left

    def args(self):
        return self.right

    def tolist(self):
        return [self.left] + self.right

    def update(self, args):
        if len(args) == 0:
            return
        self.left = args[0]
        self.right = args[1:]


class Int(Node):
    def __init__(self, token: plex.LexToken, value: int) -> None:
        super().__init__(token, arity=0)
        self.value = value

    def __str__(self):
        return "%r" % self.value


class Float(Node):
    def __init__(self, token: plex.LexToken, value: float) -> None:
        super().__init__(token, arity=0)
        self.value = value

    def __str__(self):
        return "%r" % self.value


class Symbol(Node):
    def __init__(self, token: plex.LexToken, value: str) -> None:
        super().__init__(token, arity=0)
        self.value = value

    def __str__(self):
        return "%s" % self.value


class TTrue(Node):
    def __init__(self, token: plex.LexToken, value: str) -> None:
        super().__init__(token, arity=0)
        self.value = True

    def __str__(self):
        return "#t"


class TFalse(Node):
    def __init__(self, token: plex.LexToken, value: str) -> None:
        super().__init__(token, arity=0)
        self.value = False

    def __str__(self):
        return "#f"


class String(Node):
    def __init__(self, token: plex.LexToken, value: str) -> None:
        super().__init__(token, arity=0)
        self.value = value

    def __str__(self):
        return '"%s"' % self.value


class Unit(Node):
    def __init__(self, token: plex.LexToken) -> None:
        super().__init__(token, arity=0)
        self.value = None

    def __str__(self):
        return "()"


class Quoted(Node):
    def __init__(self, token: plex.LexToken, quoted: Node) -> None:
        super().__init__(token, arity=1, left=quoted)
        self.left = quoted
        self.value = None

    def __str__(self):
        return "(quote %s)" % self.left


class Quasiquoted(Node):
    def __init__(self, token: plex.LexToken, quoted: Node) -> None:
        super().__init__(token, arity=1, left=quoted)
        self.left = quoted
        self.value = None

    def __str__(self):
        return "(quasiquote %s)" % self.left


class Unquoted(Node):
    def __init__(self, token: plex.LexToken, unquoted: Node) -> None:
        super().__init__(token, arity=1, left=unquoted)
        self.left = unquoted
        self.value = None

    def __str__(self):
        return "(unquote %s)" % self.left
