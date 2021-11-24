import unittest
from lisby.lexer import Lexer, ImbalancedParentheses


class TestLexer(unittest.TestCase):
    @staticmethod
    def lx():
        return Lexer()

    def test_basic(self):
        lexer = self.lx()
        toks = lexer.lex('(+ 1 2 "heh")')
        self.assertEqual(len(toks), 7, toks)
        self.assertEqual(toks[0].type, "LPAREN")
        self.assertEqual(toks[1].type, "SYMBOL")
        self.assertEqual(toks[1].value, "+")
        self.assertEqual(toks[2].type, "INT")
        self.assertEqual(toks[2].value, 1)
        self.assertEqual(toks[3].type, "INT")
        self.assertEqual(toks[3].value, 2)
        self.assertEqual(toks[4].type, "STRING")
        self.assertEqual(toks[4].value, "heh")
        self.assertEqual(toks[5].type, "RPAREN")
        self.assertEqual(toks[6].type, "END")

    def test_empty(self):
        lexer = self.lx()
        lexer.lex("")

    def test_incomplete_apply(self):
        lexer = self.lx()
        with self.assertRaises(ImbalancedParentheses):
            lexer.lex("(+ 1 2")

    def test_incomplete_apply_harder(self):
        lexer = self.lx()
        with self.assertRaises(ImbalancedParentheses):
            lexer.lex(")+ 1 2")

    def test_numbers(self):
        lexer = self.lx()
        toks = lexer.lex("123 -321 123.456 -654.321")
        self.assertEqual(len(toks), 5)
        for (i, val) in enumerate([123, -321, 123.456, -654.321]):
            self.assertEqual(toks[i].value, val)

    def test_truth(self):
        lexer = self.lx()
        toks = lexer.lex("#t #f")
        self.assertEqual(len(toks), 3)
        self.assertEqual(toks[0].type, "TRUE")
        self.assertEqual(toks[1].type, "FALSE")

    def test_quote(self):
        lexer = self.lx()
        toks = lexer.lex("'1 ''x")
        wanted = ("QUOTE", "INT", "QUOTE", "QUOTE", "SYMBOL")
        self.assertEqual(len(toks), len(wanted) + 1)
        for (i, val) in enumerate(wanted):
            self.assertEqual(toks[i].type, val)

    def test_quasiquoted(self):
        lexer = self.lx()
        toks = lexer.lex("`,`,")
        wanted = ["QUASIQUOTE", "UNQUOTE"] * 2
        self.assertEqual(len(toks), len(wanted) + 1)
        for (i, val) in enumerate(wanted):
            self.assertEqual(toks[i].type, val)

    def test_comment(self):
        lexer = self.lx()
        toks = lexer.lex(
            r"""
(+ 1 2) ; this should be ignored
;; this too ()()
(* 3 4)"""
        )
        wanted = [
            "LPAREN",
            "SYMBOL",
            "INT",
            "INT",
            "RPAREN",
            "LPAREN",
            "SYMBOL",
            "INT",
            "INT",
            "RPAREN",
            "END",
        ]
        print(toks)
        for (i, val) in enumerate(toks):
            self.assertEqual(val.type, wanted[i])

    def test_period(self):
        lexer = self.lx()
        toks = lexer.lex("...")
        wanted = ["PERIOD"] * 3
        self.assertEqual(len(toks), len(wanted) + 1)
        for (i, val) in enumerate(wanted):
            self.assertEqual(toks[i].type, val)
