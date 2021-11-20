import unittest
from lisby.lexer import Lexer
from lisby.parser import (Parser, Application, Symbol, Int, TTrue, TFalse,
                          IntegerSize, Quasiquoted, Unquoted,
                          INT_MIN, INT_MAX)


class TestParser(unittest.TestCase):
    @staticmethod
    def p():
        return Parser(debug=True)

    @staticmethod
    def lx():
        return Lexer()

    def test_atom(self):
        lexer = self.lx()
        toks = lexer.lex("1")
        parser = self.p()
        forest = parser.parse(toks)
        self.assertEqual(len(forest), 1)
        node = forest[0]
        self.assertEqual(node.__class__, Int)
        self.assertEqual(node.value, 1)

    def test_atoms(self):
        lexer = self.lx()
        toks = lexer.lex("1 2 3")
        parser = self.p()
        forest = parser.parse(toks)
        self.assertEqual(len(forest), 3)
        self.assertEqual(forest[0].__class__, Int)
        self.assertEqual(forest[0].value, 1)
        self.assertEqual(forest[1].__class__, Int)
        self.assertEqual(forest[1].value, 2)
        self.assertEqual(forest[2].__class__, Int)
        self.assertEqual(forest[2].value, 3)

    def test_apply(self):
        lexer = self.lx()
        toks = lexer.lex("(+ 1 2)")
        parser = self.p()
        forest = parser.parse(toks)
        self.assertEqual(len(forest), 1)
        node = forest[0]
        self.assertEqual(node.__class__, Application)
        self.assertEqual(node.left.__class__, Symbol)
        self.assertEqual(node.left.value, "+")
        self.assertEqual(len(node.right), 2)
        self.assertEqual(node.right[0].__class__, Int)
        self.assertEqual(node.right[1].__class__, Int)
        self.assertEqual(node.right[0].value, 1)
        self.assertEqual(node.right[1].value, 2)

    def test_small_large_int(self):
        lexer = self.lx()
        for val in (INT_MIN, INT_MAX + 1):
            toks = lexer.lex(str(val))
            parser = self.p()
            with self.assertRaises(IntegerSize):
                parser.parse(toks)

    def test_truth(self):
        lexer = self.lx()
        toks = lexer.lex("#t #f")
        parser = self.p()
        forest = parser.parse(toks)
        self.assertEqual(len(forest), 2)
        self.assertTrue(isinstance(forest[0], TTrue), forest[0])
        self.assertTrue(isinstance(forest[1], TFalse), forest[1])

    def test_quoted(self):
        lexer = self.lx()
        toks = lexer.lex("'(1 2 3)")
        parser = self.p()
        forest = parser.parse(toks)
        self.assertEqual(len(forest), 1)

    def test_quasiquoted(self):
        lexer = self.lx()
        toks = lexer.lex("`(1 2 `,3)")
        parser = self.p()
        forest = parser.parse(toks)
        self.assertEqual(len(forest), 1)
        n = forest[0]
        self.assertTrue(isinstance(n, Quasiquoted), n)
        nn = n.left
        self.assertTrue(isinstance(nn, Application), nn)
        a = nn.tolist()
        self.assertEqual(len(a), 3)
        self.assertTrue(isinstance(a[0], Int), a[0])
        self.assertTrue(isinstance(a[1], Int), a[1])
        self.assertTrue(isinstance(a[2], Quasiquoted), a[2])
        aa = a[2].left
        self.assertTrue(isinstance(aa, Unquoted), aa)
        self.assertTrue(isinstance(aa.left, Int), aa.left)
        self.assertEqual(aa.left.value, 3)
