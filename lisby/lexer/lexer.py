from typing import List

import ply.lex as plex


def find_column(token):
    line_start = token.lexer.c.rfind("\n", 0, token.lexpos) + 1
    return (token.lexpos - line_start) + 1


class ImbalancedParentheses(Exception):
    def __init__(self, n):
        super().__init__("Parenthesis imbalance: %d" % n)
        self.n = n


tokens = (
    "QUOTE",
    "LPAREN",
    "RPAREN",
    "INT",
    "FLOAT",
    "STRING",
    "TRUE",
    "FALSE",
    "SYMBOL",
    "END",
    "QUASIQUOTE",
    "UNQUOTE",
    "PERIOD",
)

t_ignore = " \t"
t_QUOTE = r"'"
t_SYMBOL = r"[^ .`,'\t\n\(\)#]+"
t_TRUE = r"\#t"
t_FALSE = r"\#f"
t_QUASIQUOTE = r"`"
t_UNQUOTE = r","
t_PERIOD = r"."


def t_LPAREN(t):
    r"\("
    t.lexer.parens += 1
    return t


def t_RPAREN(t):
    r"\)"
    t.lexer.parens -= 1
    if t.lexer.parens < 0:
        raise ImbalancedParentheses(t.lexer.parens)
    return t


def t_STRING(t):
    r'"([^"]+|\.)*"'
    t.value = t.value[1:-1]
    return t


def t_FLOAT(t):
    r"-*\d+\.\d+"
    t.value = float(t.value)
    return t


def t_INT(t):
    r"-*\d+"
    t.value = int(t.value)
    return t


def t_newline(t):
    r"\n+"
    t.lexer.lineno += t.value.count("\n")


def t_error(t):
    raise ValueError("Unexpected character: %s" % t.value[0])


class Lexer:
    def __init__(self):
        self.lexer = plex.lex()

    def lex(self, what: str) -> List[plex.LexToken]:
        toks: List[plex.LexToken] = []
        self.lexer.errored = False
        self.lexer.parens = 0
        self.lexer.input(what)
        for tok in self.lexer:
            toks.append(tok)
        # We use the END token as a marker to ease parsing.
        if self.lexer.parens != 0:
            raise ImbalancedParentheses(self.lexer.parens)
        end = plex.LexToken()
        end.type = "END"
        end.value = "the end"
        if len(toks) > 0:
            end.lineno = toks[-1].lineno
            end.lexpos = toks[-1].lineno
        else:
            end.lineno = 0
            end.lexpos = 0
        toks.append(end)
        return toks
