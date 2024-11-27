from ir import *

STACK_LEN = 4096
TEMPLATE = """
data $__stack = { z #STACK_LEN# }
data $__stack_ptr = { l $__stack }

function $__stack_push(l %v) {
@start
    %i0 =l loadl $__stack_ptr
    storel %v, %i0
    %i1 =l add %i0, 8
    storel %i1, $__stack_ptr
    ret
}

function l $__stack_top() {
@start
    %i0 =l loadl $__stack_ptr
    %i1 =l sub %i0, 8
    %i2 =l loadl %i1
    ret %i2
}

function l $__stack_pop() {
@start
    %i0 =l loadl $__stack_ptr
    %i1 =l sub %i0, 8
    %i2 =l loadl %i1
    storel %i1, $__stack_ptr
    ret %i2
}

function $drop() {
@start
    call $__stack_pop()
    ret
}

function $dup() {
@start
    %i0 =l call $__stack_top()
    call $__stack_push(l %i0)
    call $__stack_push(l %i0)
    ret
}

function $swap() {
@start
    %i0 =l call $__stack_pop()
    %i1 =l call $__stack_pop()
    call $__stack_push(l %i0)
    call $__stack_push(l %i1)
    ret
}

# a b c -> b c a
# 2 1 0 -> 1 0 2
function $rot() {
@start
    %i0 =l call $__stack_pop()
    %i1 =l call $__stack_pop()
    %i2 =l call $__stack_pop()
    call $__stack_push(l %i1)
    call $__stack_push(l %i0)
    call $__stack_push(l %i2)
    ret
}

function $add() {
@start
    %i0 =l call $__stack_pop()
    %i1 =l call $__stack_pop()
    %i2 =l add %i1, %i0
    call $__stack_push(l %i2)
    ret
}

function $sub() {
@start
    %i0 =l call $__stack_pop()
    %i1 =l call $__stack_pop()
    %i2 =l sub %i1, %i0
    call $__stack_push(l %i2)
    ret
}

function $mul() {
@start
    %i0 =l call $__stack_pop()
    %i1 =l call $__stack_pop()
    %i2 =l mul %i1, %i0
    call $__stack_push(l %i2)
    ret
}

function $idiv() {
@start
    %i0 =l call $__stack_pop()
    %i1 =l call $__stack_pop()
    %i2 =l div %i1, %i0
    call $__stack_push(l %i2)
    ret
}

function $udiv() {
@start
    %i0 =l call $__stack_pop()
    %i1 =l call $__stack_pop()
    %i2 =l udiv %i1, %i0
    call $__stack_push(l %i2)
    ret
}

function $irem() {
@start
    %i0 =l call $__stack_pop()
    %i1 =l call $__stack_pop()
    %i2 =l rem %i1, %i0
    call $__stack_push(l %i2)
    ret
}

function $urem() {
@start
    %i0 =l call $__stack_pop()
    %i1 =l call $__stack_pop()
    %i2 =l urem %i1, %i0
    call $__stack_push(l %i2)
    ret
}

data $__putd_fmt = { b "%ld", b 0 }
function $putd() {
@start
    %i0 =l call $__stack_pop()
    call $printf(l $__putd_fmt, ..., l %i0)
    ret
}
""".replace("#STACK_LEN#", str(STACK_LEN))


class FunctionAssembler:
    def __init__(self, fn: FunctionDefinition, ctx: "CodeGenerator"):
        if fn.name == "main":
            ret = "l "
        else:
            ret = ""
        self.asm = "export function "+ret+"$"+fn.name+" () {\n@start\n"
        self.ctx = ctx
        self._immbmp = 0
        self._rets = fn.rets
        self.stack: list[DataType | int] = fn.args
        if fn.name == "main":
            assert fn.args == [] and fn.rets == [DataType(
                "int")], "wrong function type for main function. type should be ( -- int)"
        self.name = fn.name
        for ii in fn.code:
            self.compile_op(ii)

    def emit(self, inst: str):
        self.asm += ("" if inst.startswith("@") else "    ")+inst+"\n"

    def imm(self) -> str:
        self._immbmp += 1
        return f"%i{self._immbmp-1}"

    def apply_mutation(self, mutation: Mutation):
        generics = {}
        nargs = len(mutation[0])
        def get_arg(idx): return self.stack[-nargs + idx]

        for idx, arg in enumerate(mutation[0]):
            if isinstance(arg, int):
                if arg in generics:
                    assert get_arg(
                        idx) == generics[arg], "different types for same generic"
                else:
                    generics[arg] = get_arg(idx)
            else:
                assert get_arg(idx) == arg, "typeerror"

        for ii in mutation[0]:
            self.stack.pop()

        for arg in mutation[1]:
            if isinstance(arg, int):
                if arg not in generics:
                    assert False, "can't get generic without generic argument"
                self.stack.append(generics[arg])
            else:
                self.stack.append(arg)

    def compile_op(self, op: Op):
        self.apply_mutation(op.mutation)
        if isinstance(op, OpCall):
            assert op.name in self.ctx.fns, f"undefined function: {op.name}"
        for line in op.qbe(self.imm).splitlines():
            self.emit(line)

    def get_asm(self) -> str:
        self.apply_mutation((self._rets, []))
        assert len(self.stack) == 0, "too many arguments left on the stack"

        if self.name == "main":
            self.emit("@ret")
            imm = self.imm()
            self.emit(f"{imm} =l call $__stack_pop()")
            self.emit(f"ret {imm}")
        else:
            self.emit("ret")

        return self.asm + "}\n"


class CodeGenerator:
    def __init__(self):
        self.asm = TEMPLATE
        self.fns: dict[str, Mutation] = {
            "drop": ([0], []),
            "dup": ([0], [0, 0]),
            "swap": ([0, 1], [1, 0]),
            "rot": ([0, 1, 2], [2, 0, 1]),
            "add": ([DataType("int"), DataType("int")], [DataType("int")]),
            "sub": ([DataType("int"), DataType("int")], [DataType("int")]),
            "mul": ([DataType("int"), DataType("int")], [DataType("int")]),
            "idiv": ([DataType("int"), DataType("int")], [DataType("int")]),
            "udiv": ([DataType("int"), DataType("int")], [DataType("int")]),
            "irem": ([DataType("int"), DataType("int")], [DataType("int")]),
            "urem": ([DataType("int"), DataType("int")], [DataType("int")]),
            "putd": ([DataType("int")], []),
        }

    def get_fn(self, name: str) -> tuple[str, Mutation]:
        return name, self.fns[name]

    def define_func(self, fn: FunctionDefinition):
        assert fn.name not in self.fns, "function defined twice"
        self.fns[fn.name] = (fn.args, fn.rets)
        self.asm += "\n" + FunctionAssembler(fn, self).get_asm()


ctx = CodeGenerator()
ctx.define_func(FunctionDefinition("main", [], [DataType("int")], [
    OpPush(69),
    OpPush(60),
    OpCall(*ctx.get_fn("sub"))
]))

print(ctx.asm)
