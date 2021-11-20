import unittest
from struct import pack

from lisby.vm import VM, Op, Int, Program


def p64(arg):
    return [c for c in pack("<q", arg)]


class TestVM(unittest.TestCase):
    @staticmethod
    def v():
        return VM()

    @staticmethod
    def p():
        return Program()

    def test_basic(self):
        vm = self.v()
        p = self.p()
        p.tapes = [[Op.Type.HALT]]
        vm.run(p, trace=True)
        self.assertEqual(vm.pc, 1)

    def test_add(self):
        vm = self.v()
        p = self.p()
        p.tapes = [([Op.Type.PUSHI] + p64(-2) +
                  [Op.Type.PUSHI] + p64(5) +
                  [Op.Type.ADD] + [Op.Type.HALT])]
        vm.run(p, trace=True)
        self.assertEqual(vm.pc, 9 + 9 + 1 + 1)
        self.assertEqual(len(vm.stack), 1)
        v = vm.stack[0]
        self.assertTrue(isinstance(v, Int))
        self.assertEqual(v.value, 3)
