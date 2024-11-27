from dataclasses import dataclass
from enum import Enum, auto
from typing import Literal, TypeAlias, List, Tuple, Any, Type, Callable


PrimitiveDataType: TypeAlias = Literal["byte", "bool", "int"]
Mutation: TypeAlias = Tuple[list["DataType | int"], list["DataType | int"]]
ImmediateGenerator: TypeAlias = Callable[[], str]


@dataclass
class DataType:
    base: PrimitiveDataType
    pointer: int = 0

    def __str__(self) -> str:
        return "*"*self.pointer + self.base


@dataclass
class FunctionDefinition:
    name: str
    args: List[DataType | int]
    rets: List[DataType | int]
    code: List["Op"]


class Op:
    mutation: Mutation

    def qbe(self, imm: ImmediateGenerator) -> str:
        raise NotImplementedError(self.__class__.__name__)


class OpPush(Op):
    def __init__(self, val: int, t: DataType = DataType("int")):
        self.value = val
        self.mutation = ([], [t])

    def qbe(self, imm: ImmediateGenerator) -> str:
        return f"call $__stack_push(l {self.value})"


class OpCall(Op):
    def __init__(self, name: str, mutation: Mutation):
        self.name = name
        self.mutation = mutation

    def qbe(self, imm: ImmediateGenerator) -> str:
        return f"call ${self.name}()"
