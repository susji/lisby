import ply.lex as plex


class LisbySyntaxError(Exception):
    def __init__(self, what, message) -> None:
        if isinstance(what, plex.LexToken):
            token = what
        elif hasattr(what, "token"):
            token = what.token
        else:
            raise RuntimeError("Not node or token")
        super().__init__("syntax error: %s: %s" % (token, message))


class LisbyRuntimeError(Exception):
    def __init__(self, message) -> None:
        super().__init__("runtime error: %s" % message)
