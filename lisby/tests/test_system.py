import unittest

from math import factorial

from lisby.shared import LisbyRuntimeError
from lisby.lexer import Lexer
from lisby.parser import Parser
from lisby.vm import (
    VM,
    Program,
    Int,
    Symbol,
    VList,
    Quoted,
    VTrue,
    VFalse,
    Float,
    Quasiquoted,
)
from lisby.compiler import Compiler


class TestSystem(unittest.TestCase):
    @staticmethod
    def invoke(code: str, debug=False) -> VM:
        lexer = Lexer()
        parser = Parser(debug=False)
        compiler = Compiler(debug=debug)
        vm = VM()
        vm.run(compiler.compile(Program(), parser.parse(lexer.lex(code))), trace=debug)
        return vm

    def test_arith(self):
        vm = self.invoke("(+ 10 (* 2 (/ 9 3)))")
        self.assertEqual(vm.stack[-1].value, 16)

    def test_mod(self):
        tests = (("(% 20 5)", 0), ("(% -5 10)", 5))
        for test in tests:
            vm = self.invoke(test[0])
            val = vm.stack[-1]
            self.assertTrue(isinstance(val, Int))
            self.assertEqual(val.value, test[1])

    def test_bits(self):
        tests = (
            ("(| 170 85)", 170 | 85),
            ("(^ 255 128)", 255 ^ 128),
            ("(& 255 7)", 255 & 7),
            ("(~ 170)", ~170 & 0xFFFFFFFFFFFFFFFF),
        )
        for test in tests:
            print("bit test: %s " % test[0])
            vm = self.invoke(test[0])
            self.assertEqual(vm.stack[-1].value, test[1])

    def test_conds(self):
        tests = (
            ("(if (< 1 10) #t #f)", True),
            ("(if (> 1 10) #t #f)", False),
            ("(if (= 1 10) #t #f)", False),
            ("(if (= 10 10) #t #f)", True),
            ("(if (<= 10 10) #t #f)", True),
            ("(if (>= 10 10) #t #f)", True),
            ("(if (not #f) #t #f)", True),
            ("(if (not #t) #t #f)", False),
        )
        for test in tests:
            print("cond test: %s" % test[0])
            vm = self.invoke(test[0])
            self.assertTrue(
                isinstance(vm.stack[-1], VTrue) or isinstance(vm.stack[-1], VFalse)
            )
            self.assertEqual(vm.stack[-1].value, test[1])

    def test_let(self):
        vm = self.invoke("(let ((x 123) (y 2)) (+ 1 (* x y)))")
        self.assertEqual(len(vm.stack), 1)
        self.assertEqual(vm.stack[-1].value, 247)

    def test_let_scoping(self):
        vm = self.invoke(
            """
(define res 0)
(define res2 0)
(let ((x 123))
    (let ((x 321))
        (set! res2 x))
    (set! res x))
"""
        )
        p = vm.program
        env = vm.topenv
        res = env.values[p.symbol_find("res")]
        res2 = env.values[p.symbol_find("res2")]
        self.assertTrue(isinstance(res, Int))
        self.assertEqual(res.value, 123)
        self.assertTrue(isinstance(res2, Int))
        self.assertEqual(res2.value, 321)

    def test_define(self):
        vm = self.invoke("(define xyz 123)")
        self.assertEqual(len(vm.stack), 1)
        symindex = vm.program.symbol_find("xyz")
        val = vm.topenv.values[symindex]
        self.assertTrue(isinstance(val, Int))
        self.assertEqual(val.value, 123)

    def test_unbound_symbol(self):
        with self.assertRaises(LisbyRuntimeError):
            self.invoke("x")
        with self.assertRaises(LisbyRuntimeError):
            self.invoke("(define x 123) y")

    def test_lambda_application(self):
        vm = self.invoke("((lambda (x y) (* 3 (+ x y))) 1 2)")
        self.assertEqual(len(vm.stack), 1)
        self.assertEqual(vm.stack[-1].value, 9)

    def test_lambda_nested(self):
        vm = self.invoke("((lambda (y) ((lambda (x) (+ x y)) 2)) 3)")
        self.assertEqual(len(vm.stack), 1)
        self.assertEqual(vm.stack[-1].value, 5)

    def test_bound_lambda(self):
        vm = self.invoke(
            """
(define plusser (lambda (x y) (+ x y)))
(plusser 1 2)
        """
        )
        self.assertEqual(len(vm.stack), 2)
        self.assertEqual(vm.stack[-1].value, 3)

    def test_lambda_define(self):
        vm = self.invoke(
            """
(define (plusser x y) (+ x y))
(define (multer a b) (* a b))
(plusser 1 (multer 2 3))
        """
        )
        self.assertEqual(len(vm.stack), 3)
        self.assertEqual(vm.stack[-1].value, 7)

    def test_lambda_passing(self):
        vm = self.invoke(
            """
(define (oner fun y) 321 789 (fun 10 y))
(oner (lambda (a b) (+ a b)) 20)
        """
        )
        self.assertEqual(len(vm.stack), 2)
        self.assertEqual(vm.stack[-1].value, 30)

    def test_or(self):
        tests = (
            ("(or #f #f)", False),
            ("(or #t #f)", True),
            ("(or #t #t)", True),
            ("(or #f #t)", True),
        )
        for test in tests:
            print("or: %s" % test[0])
            vm = self.invoke(test[0])
            self.assertEqual(len(vm.stack), 1)
            val = vm.stack[-1]
            if test[1]:
                self.assertTrue(isinstance(val, VTrue))
            else:
                self.assertTrue(isinstance(val, VFalse))
            self.assertEqual(val.value, test[1])

    def test_and(self):
        tests = (
            ("(and #f #f)", False),
            ("(and #t #f)", False),
            ("(and #t #t)", True),
            ("(and #f #t)", False),
        )
        for test in tests:
            print("and: %s" % test[0])
            vm = self.invoke(test[0])
            self.assertEqual(len(vm.stack), 1)
            val = vm.stack[-1]
            if test[1]:
                self.assertTrue(isinstance(val, VTrue))
            else:
                self.assertTrue(isinstance(val, VFalse))
            self.assertEqual(val.value, test[1])

    def test_if(self):
        vm = self.invoke(
            """
(if (= 0 1) #f #t)
(if (!= 0 1) #f #t)
        """
        )
        self.assertEqual(len(vm.stack), 2)
        self.assertEqual(vm.stack[0].value, True)
        self.assertEqual(vm.stack[1].value, False)

    def test_begin(self):
        vm = self.invoke(
            """
(begin 1 2 3 4 5 6 7 8 9 10)
        """
        )
        self.assertEqual(len(vm.stack), 1)
        self.assertEqual(vm.stack[0].value, 10)

    def test_set(self):
        vm = self.invoke(
            """
(define testi 123)
(set! testi 321)
        """
        )
        p = vm.program
        env = vm.topenv
        self.assertEqual(env.values[p.symbol_find("testi")].value, 321)

    def test_closure(self):
        vm = self.invoke(
            """
(define counter 0)
(define (gen-adder start)
    (lambda () (set! start (+ start 1))
    (set! counter (+ 1 counter))
    start))
(define a (gen-adder 10))
(define b (gen-adder 20))
(define eka (a))
(define toka (b))
(define kolmas (a))
(define neljas (b))
        """
        )
        p = vm.program
        env = vm.topenv
        for var in (("eka", 11), ("toka", 21), ("kolmas", 12), ("neljas", 22)):
            self.assertEqual(env.values[p.symbol_find(var[0])].value, var[1])
        self.assertEqual(env.values[p.symbol_find("counter")].value, 4)

    def test_recursion(self):
        n = 50
        vm = self.invoke(
            """
(define (fact n)
    (if (= n 0)
        1
        (* n (fact (- n 1)))))
(define result (fact %d))
        """
            % n
        )
        p = vm.program
        env = vm.topenv
        self.assertEqual(env.values[p.symbol_find("result")].value, factorial(n))

    def test_naive_fibonacci(self):
        n = 10
        vm = self.invoke(
            """
(define (-fibo x sum)
        (if (= x 0)
            0
            (if (= x 1)
                1
                (+
                    (-fibo (- x 1) (+ sum x))
                    (-fibo (- x 2) (+ sum x))))))
(define (fibo x) (-fibo x 0))
(define result (fibo %d))
        """
            % n
        )
        p = vm.program
        env = vm.topenv
        self.assertEqual(env.values[p.symbol_find("result")].value, 55)

    def test_list(self):
        vm = self.invoke(
            """
(define result (list 123 "viisi" 123.456))
        """
        )
        p = vm.program
        env = vm.topenv
        res = env.values[p.symbol_find("result")].value
        self.assertEqual(len(res), 3)
        gots = (res[0].value, res[1].value, res[2].value)
        wants = (123, "viisi", 123.456)
        for (exp, got) in zip(gots, wants):
            self.assertEqual(exp, got)

    def test_concat_list(self):
        vm = self.invoke(
            """
(define one (list 1 2))
(define two (list 3 4))
(define result (:: one two (list 5 6)))
        """
        )

        p = vm.program
        env = vm.topenv
        gots = env.values[p.symbol_find("result")].value
        for (exp, got) in zip(range(1, 7), gots):
            print(got.value)
            self.assertEqual(exp, got.value)

    def test_head(self):
        vm = self.invoke("(define result (head (list 1 2 3)))")
        p = vm.program
        env = vm.topenv
        got = env.values[p.symbol_find("result")].value
        self.assertEqual(got, 1)

    def test_tail(self):
        vm = self.invoke("(define result (tail (list 1 2 3)))")
        p = vm.program
        env = vm.topenv
        res = env.values[p.symbol_find("result")].value
        self.assertEqual(len(res), 2)
        for (exp, got) in zip((2, 3), (res[0].value, res[1].value)):
            self.assertEqual(exp, got)

    def test_map(self):
        vm = self.invoke(
            """
(define (mapr with what)
    (if (= what '())
        '()
        (:: (list (with (head what))) (mapr with (tail what)))))
(define result
    (mapr
        (lambda (x) (* 2 x))
        '(1 2 3 4)))
        """
        )
        p = vm.program
        env = vm.topenv
        res = env.values[p.symbol_find("result")].value
        self.assertEqual(len(res), 4)
        for (exp, got) in zip((2, 4, 6, 8), (got.value for got in res)):
            self.assertEqual(exp, got)

    def test_quoted_symbol(self):
        vm = self.invoke("'x")
        self.assertEqual(len(vm.stack), 1)
        res = vm.stack[-1]
        self.assertTrue(isinstance(res, Symbol))
        self.assertEqual(res.value, "x")

    def test_quoted_list(self):
        vm = self.invoke("''(1 '2 ''x)")
        res = vm.stack[-1]
        self.assertTrue(isinstance(res, Quoted))
        self.assertEqual(res.degree, 1)
        self.assertTrue(isinstance(res.value, VList))
        res = res.value

        self.assertTrue(isinstance(res, VList))
        self.assertEqual(len(res.value), 3)

        self.assertTrue(isinstance(res.value[0], Int))

        self.assertTrue(isinstance(res.value[1], Quoted))
        self.assertEqual(res.value[1].degree, 1)
        self.assertTrue(isinstance(res.value[1].value, Int))
        self.assertEqual(res.value[1].value.value, 2)

        self.assertTrue(isinstance(res.value[2], Quoted))
        self.assertEqual(res.value[2].degree, 2)
        self.assertTrue(isinstance(res.value[2].value, Symbol))
        self.assertEqual(res.value[2].value.value, "x")

    def test_binding_purity(self):
        """Make sure that our bindings are not accidentally modified
        by reference."""
        vm = self.invoke(
            """
(define one (list 1 2 3))
(define two (tail one))
        """
        )
        p = vm.program
        env = vm.topenv
        one = env.values[p.symbol_find("one")].value
        two = env.values[p.symbol_find("two")].value
        self.assertEqual(len(one), 3)
        self.assertEqual(len(two), 2)

    def test_continuation(self):
        vm = self.invoke(
            """
(+ 10 (call/cc (lambda (k) (k 1) 2)))
        """
        )
        val = vm.stack[-1]
        self.assertEqual(val.value, 11)

    def test_continuation_harder(self):
        vm = self.invoke(
            """
(define (inv v)
    (call/cc (lambda (return)
        (display "doing things")
        (if (= v 0.0) (return 0) #f)
        (display "otherwise doing other things")
        (/ 1 v))))
(define one (inv 2.0))
(define two (inv 0.0))
        """
        )
        p = vm.program
        env = vm.topenv
        one = env.values[p.symbol_find("one")]
        two = env.values[p.symbol_find("two")]
        self.assertTrue(isinstance(one, Float))
        self.assertTrue(isinstance(two, Int))
        self.assertAlmostEqual(one.value, 0.5)
        self.assertEqual(two.value, 0)

    def test_quasiquote(self):
        vm = self.invoke("```,1")
        res = vm.stack[-1]
        self.assertTrue(isinstance(res, Quasiquoted), res)
        val = res.value
        self.assertTrue(isinstance(val, Int), val)

    def test_quasiquote_unquote(self):
        vm = self.invoke("`(1 ,(+ 1 2))")
        res = vm.stack[-1]
        self.assertTrue(isinstance(res, VList), res)
        vals = res.value
        self.assertEqual(len(vals), 2)
        self.assertTrue(isinstance(vals[0], Int))
        self.assertEqual(vals[0].value, 1)
        self.assertTrue(isinstance(vals[1], Int))
        self.assertEqual(vals[1].value, 3)

    def test_defmacro(self):
        vm = self.invoke(
            """
(defmacro (multiplier a b) (* a b))
(multiplier 5 6)
(+ (multiplier 10 7) 5)
(multiplier 2 (multiplier 3 4))
        """,
            debug=True,
        )
        third = vm.stack.pop()
        second = vm.stack.pop()
        first = vm.stack.pop()
        for v in ((first, 30), (second, 75), (third, 24)):
            print(v)
            self.assertTrue(isinstance(v[0], Int), v)
            self.assertEqual(v[0].value, v[1], f"got {v[0]}, want {v[1]}")

    def test_defmacro_looper(self):
        vm = self.invoke(
            """
(define counter 1)
(defmacro (looperer init cond on-each action)
    (let (init (loop
        (lambda ()
            (if cond
                (begin on-each action (loop))
                #t))))
        (loop)))
(looperer
    (-i 0)
    (< -i 10)
    (set! -i (+ -i 1))
    (set! counter (* counter 2)))
        """
        )
        p = vm.program
        env = vm.topenv
        res = env.values[p.symbol_find("counter")]
        self.assertTrue(isinstance(res, Int), res)
        self.assertEqual(res.value, 1024)

    def test_reified_builtins(self):
        vm = self.invoke(
            """
(define (bin-op fun a b) (fun a b))

(+ 5 7)
(bin-op + 2 3)
"""
        )
        latter = vm.stack.pop()
        self.assertTrue(isinstance(latter, Int), latter)
        self.assertEqual(latter.value, 5)

        first = vm.stack.pop()
        self.assertTrue(isinstance(first, Int), first)
        self.assertEqual(first.value, 12)
