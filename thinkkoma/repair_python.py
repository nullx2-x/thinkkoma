from __future__ import annotations

import ast
import operator
import re
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from thinkkoma.tools.fs import inventory, read_text, write_text
from thinkkoma.tools.pytest_runner import TestRun, run_tests

_OPS: list[tuple[type[ast.operator], str, Callable[[object, object], object]]] = [
    (ast.Add, "+", operator.add),
    (ast.Sub, "-", operator.sub),
    (ast.Mult, "*", operator.mul),
    (ast.Div, "/", operator.truediv),
    (ast.FloorDiv, "//", operator.floordiv),
    (ast.Mod, "%", operator.mod),
    (ast.Pow, "**", operator.pow),
    (ast.BitXor, "^", operator.xor),
    (ast.BitOr, "|", operator.or_),
    (ast.BitAnd, "&", operator.and_),
]


@dataclass
class Example:
    func: str
    args: tuple[object, ...]
    expected: object
    source: str


@dataclass
class RepairOutcome:
    changed: bool
    detail: str
    test: TestRun | None = None


def _parse_examples(source: str) -> list[Example]:
    tree = ast.parse(source)
    examples: list[Example] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assert) or not isinstance(node.test, ast.Compare):
            continue
        compare = node.test
        if not isinstance(compare.left, ast.Call) or not compare.ops:
            continue
        if not isinstance(compare.ops[0], ast.Eq):
            continue
        call = compare.left
        if not call.args or not compare.comparators:
            continue
        expected_node = compare.comparators[0]
        try:
            args = tuple(ast.literal_eval(arg) for arg in call.args)
            expected = ast.literal_eval(expected_node)
        except (ValueError, TypeError):
            continue
        if isinstance(call.func, ast.Name):
            func = call.func.id
        elif isinstance(call.func, ast.Attribute):
            func = call.func.attr
        else:
            continue
        examples.append(Example(func=func, args=args, expected=expected, source=source))
    return examples


def _import_modules(source: str) -> dict[str, str]:
    mapping: dict[str, str] = {}
    tree = ast.parse(source)
    for node in tree.body:
        if isinstance(node, ast.ImportFrom) and node.module:
            for alias in node.names:
                mapping[alias.asname or alias.name] = node.module.replace(".", "/") + ".py"
        elif isinstance(node, ast.Import):
            for alias in node.names:
                name = alias.asname or alias.name.split(".")[-1]
                mapping[name] = alias.name.replace(".", "/") + ".py"
    return mapping


def _functions(source: str) -> dict[str, ast.FunctionDef]:
    tree = ast.parse(source)
    return {node.name: node for node in tree.body if isinstance(node, ast.FunctionDef)}


def _indent_of(line: str) -> str:
    return line[: len(line) - len(line.lstrip(" \t"))]


def _replace_return(source: str, func: ast.FunctionDef, expression: str) -> str:
    lines = source.splitlines(keepends=True)
    returns = [node for node in func.body if isinstance(node, ast.Return)]
    exprs = [node for node in func.body if isinstance(node, ast.Expr)]
    target = returns[-1] if returns else (exprs[-1] if exprs else None)
    if target is None:
        insert_at = func.end_lineno or func.lineno
        indent = "    "
        lines.insert(insert_at, f"{indent}return {expression}\n")
        return "".join(lines)
    lineno = target.lineno
    indent = _indent_of(lines[lineno - 1])
    newline = "\n" if lines[lineno - 1].endswith("\n") else ""
    lines[lineno - 1] = f"{indent}return {expression}{newline}"
    return "".join(lines)


def _arg_names(func: ast.FunctionDef) -> list[str]:
    return [arg.arg for arg in func.args.args]


def _fits(op: Callable[[object, object], object], examples: list[Example]) -> bool:
    for example in examples:
        if len(example.args) != 2:
            return False
        try:
            actual = op(*example.args)
        except Exception:
            return False
        if actual != example.expected:
            return False
    return True


def _binop_expression(func: ast.FunctionDef, symbol: str) -> str | None:
    names = _arg_names(func)
    if len(names) < 2:
        return None
    return f"{names[0]} {symbol} {names[1]}"


def repair_python(workspace: Path) -> RepairOutcome:
    files = inventory(workspace)
    test_files = [
        name
        for name in files
        if Path(name).name.startswith("test_") or Path(name).name.endswith("_test.py")
    ]
    if not test_files:
        return RepairOutcome(False, "No test files found")

    examples_by_func: dict[str, list[Example]] = {}
    module_for_func: dict[str, str] = {}
    for test_file in test_files:
        source = read_text(workspace, test_file)
        imports = _import_modules(source)
        for example in _parse_examples(source):
            examples_by_func.setdefault(example.func, []).append(example)
            if example.func in imports:
                module_for_func[example.func] = imports[example.func]

    if not examples_by_func:
        test = run_tests(workspace)
        return RepairOutcome(False, "Could not extract literal assertions from tests", test)

    changed_any = False
    notes: list[str] = []
    for func_name, examples in examples_by_func.items():
        module = module_for_func.get(func_name)
        if module is None:
            candidates = [name for name in files if name.endswith(".py") and name not in test_files]
            module = candidates[0] if len(candidates) == 1 else None
        if module is None:
            notes.append(f"{func_name}: implementation file not found")
            continue
        source = read_text(workspace, module)
        functions = _functions(source)
        func = functions.get(func_name)
        if func is None:
            notes.append(f"{func_name}: definition missing in {module}")
            continue
        names = _arg_names(func)
        winner: str | None = None
        if len(names) >= 2:
            for _op_type, symbol, impl in _OPS:
                if _fits(impl, examples):
                    winner = _binop_expression(func, symbol)
                    break
        if winner is None and all(len(ex.args) == 1 for ex in examples):
            identity = all(ex.args[0] == ex.expected for ex in examples)
            if identity:
                winner = names[0] if names else None
        if winner is None:
            notes.append(f"{func_name}: no operator fit the examples")
            continue
        rewritten = _replace_return(source, func, winner)
        if rewritten != source:
            write_text(workspace, module, rewritten)
            changed_any = True
            notes.append(f"{module}:{func_name} -> return {winner}")

    test = run_tests(workspace)
    if not changed_any:
        return RepairOutcome(False, "; ".join(notes) or "No mutation applied", test)
    return RepairOutcome(True, "; ".join(notes), test)


_TRACE_RE = re.compile(r'File "([^"]+\.py)", line (\d+)')


def summarize_failure(output: str) -> str:
    match = _TRACE_RE.search(output)
    if match:
        return f"{match.group(1)}:{match.group(2)}"
    lines = [line.strip() for line in output.splitlines() if line.strip()]
    return lines[-1] if lines else "unknown failure"
