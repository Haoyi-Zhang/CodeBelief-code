"""Fail-closed parser for a deliberately tiny, straight-line C grammar.
No preprocessing, branches, pointer reasoning, aliases, or actual C execution.
"""
from dataclasses import dataclass
import re

@dataclass(frozen=True)
class Call:
    name: str
    line: int

@dataclass(frozen=True)
class Function:
    name: str
    first_line: int
    last_line: int
    calls: tuple[Call, ...]

@dataclass(frozen=True)
class Observation:
    name: str
    first_line: int
    last_line: int
    mask: int

TOKEN = re.compile(r"\s+|/\*[^*]*(?:\*(?!/)[^*]*)*\*/|//[^\n]*|[A-Za-z_]\w*|[(){};]", re.ASCII)
ALLOWED = {"lock", "unlock", "touch", "noop"}


def parse(source: str) -> tuple[Function, ...]:
    if len(source.encode("utf-8")) > 262144:
        raise ValueError("source exceeds 256 KiB grammar bound")
    tokens = []
    offset = 0
    line = 1
    while offset < len(source):
        m = TOKEN.match(source, offset)
        if m is None:
            raise ValueError(f"unsupported token at line {line}")
        value = m.group()
        if not (value.isspace() or value.startswith(("/*", "//"))):
            tokens.append((value, line))
        line += value.count("\n")
        offset = m.end()
    i = 0
    def take(expected=None):
        nonlocal i
        if i >= len(tokens):
            raise ValueError("truncated declaration or function")
        item = tokens[i]
        i += 1
        if expected is not None and item[0] != expected:
            raise ValueError(f"expected {expected} at line {item[1]}")
        return item
    functions = []
    seen = set()
    while i < len(tokens):
        first = take("void")[1]
        name = take()[0]
        if not re.fullmatch(r"[A-Za-z_]\w*", name, re.ASCII):
            raise ValueError("invalid function name")
        take("("); take("void"); take(")")
        if i < len(tokens) and tokens[i][0] == ";":
            take(";")
            if name not in ALLOWED:
                raise ValueError("unknown API prototype")
            continue
        take("{")
        if name in seen or name in ALLOWED:
            raise ValueError("duplicate function or reserved API name")
        seen.add(name)
        calls = []
        while i < len(tokens) and tokens[i][0] != "}":
            call, line = take()
            if call not in ALLOWED:
                raise ValueError("unsupported statement or call")
            take("("); take(")"); take(";")
            calls.append(Call(call, line))
        last = take("}")[1]
        functions.append(Function(name, first, last, tuple(calls)))
    if len(functions) > 128:
        raise ValueError("function bound exceeded")
    return tuple(functions)


def extract(source: str) -> tuple[Observation, ...]:
    result = []
    for f in parse(source):
        depth, mask = 0, 0
        for call in f.calls:
            if call.name == "lock":
                depth += 1
                if depth > 1:
                    raise ValueError("nested locking outside fragment")
            elif call.name == "unlock":
                depth -= 1
                if depth < 0:
                    raise ValueError("unmatched unlock")
            elif call.name == "touch":
                mask |= 1 if depth else 2
        if depth:
            raise ValueError("unclosed locking scope")
        if mask:
            result.append(Observation(f.name, f.first_line, f.last_line, mask))
    return tuple(result)
