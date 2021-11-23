#!/usr/bin/env python3

import readline
import argparse
import sys
from typing import List

from lisby.shared import LisbySyntaxError, LisbyRuntimeError
from lisby.lexer import Lexer, ImbalancedParentheses
from lisby.parser import Parser, Node
from lisby.compiler import Compiler
from lisby.vm import VM, Program


def make_completer(vocabulary):
    def custom_complete(text, state):
        results = [x for x in vocabulary if x.startswith(text)] + [None]
        return results[state] + " "

    return custom_complete


aparser = argparse.ArgumentParser(
    description="lisby interpreter",
    epilog="""
Running without the source or destination arguments will give you a REPL.
""",
)
aparser.add_argument(
    "-s",
    "--source",
    nargs="?",
    type=argparse.FileType("r"),
    help="input source or '-' for stdin",
)
aparser.add_argument(
    "-b",
    "--bytecode",
    nargs="?",
    type=argparse.FileType("rb"),
    help="input bytecode or '-' for stdin",
)
aparser.add_argument(
    "-v",
    "--verbose",
    action="store_true",
    help="print verbose output while compiling and running",
)
aparser.add_argument(
    "-d",
    "--dump",
    type=argparse.FileType("wb"),
    help="without executing, dump bytecode to a file",
)
aparser.add_argument(
    "-D",
    "--display",
    action="store_true",
    help="without executing, display decoded bytecode",
)
args = aparser.parse_args()

if args.verbose:
    debug = True
else:
    debug = False

lexer = Lexer()
parser = Parser(debug=debug)
compiler = Compiler(debug=debug)
vm = VM()
forest: List[Node] = []


def run(program: Program, pc: int = 0) -> int:
    if args.display:
        program.dump()
        sys.exit(0)
    pc = vm.run(prog, pc=pc, trace=debug)
    return pc


prog: Program = None
if args.source:
    code = []
    for line in args.source:
        code.append(line)
    toks = lexer.lex("\n".join(code))
    try:
        forest = parser.parse(toks)
    except LisbySyntaxError as e:
        print("syntax error: %s" % e)
    if debug:
        print("got %d nodes" % len(forest))
        for (i, node) in enumerate(forest):
            print("%3d: %s" % (i, node))
    prog = compiler.compile(Program(), forest)
elif args.bytecode:
    prog = Program.deserialize(args.bytecode.read())
else:
    # Note: The readline handling is pretty much straight from Bendersky's
    # example at
    # https://eli.thegreenplace.net/2016/basics-of-using-the-readline-library/
    vocabulary = {"define", "set!", "let", "lambda"}
    readline.parse_and_bind("tab: complete")
    readline.set_completer(make_completer(vocabulary))
    prog = Program()
    pc = 0
    try:
        line = ""
        while True:
            prompt = ""
            if len(line) > 0:
                prompt = "::"
            else:
                prompt = ">>"
            try:
                line += "\n" + input(prompt + " ")
                toks = lexer.lex(line)
            except KeyboardInterrupt:
                print("Interrupted.")
                line = ""
                continue
            except ImbalancedParentheses as e:
                if e.n < 0:
                    print("Surprising parentheses!")
                    line = ""
                continue
            line = ""
            if len(toks) == 1:
                continue
            try:
                forest = parser.parse(toks)
                prog = compiler.compile(prog, forest)
                if debug:
                    prog.dump()
                pc = run(prog, pc=pc)
                if len(vm.stack) > 0:
                    print("-> %s " % vm.stack[-1])
                else:
                    print("-> no stack value")
            except (LisbySyntaxError, LisbyRuntimeError) as e:
                print("%s" % e)
                pc = vm.rewind_after_error()
    except EOFError as e:
        print("Exiting...")
    sys.exit(1)

if args.dump:
    args.dump.write(prog.serialize())
    args.dump.close()
    print("Bytecode dumped to file `%s'" % args.dump.name)
    sys.exit(0)

run(prog)
print("Result: %s" % vm.stack[-1])
