"""Oracles that judge a backend on its own, without reference to another backend.

Cross-implementation agreement cannot tell you who is right, and cannot see a
mistake two packages share. Two oracles cover that gap:

* **Certified values** -- a known-true answer, e.g. NIST StRD, computed to far more
  digits than any package will reach. Scores each backend independently.
* **Metamorphic invariants** -- relations that must hold whatever the true answer
  is. Rescaling a predictor must scale its coefficient exactly; frequency weights
  must reproduce row duplication. A package can fail these on its own terms.
"""

from __future__ import annotations

import ast
import math
import operator
from dataclasses import dataclass

from milaan.compare import relative_difference
from milaan.schema import CaseSpec, Invariant, Result

_BINARY = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Pow: operator.pow,
}
_UNARY = {ast.UAdd: operator.pos, ast.USub: operator.neg}
_FUNCTIONS = {"abs": abs, "log": math.log, "sqrt": math.sqrt, "exp": math.exp}


class InvariantError(ValueError):
    """Raised when an invariant expression is malformed or unevaluable."""


@dataclass
class CertifiedCheck:
    """One backend scored against a known-true value.

    Attributes:
        quantity: Canonical quantity name.
        backend: Backend that produced the value.
        observed: What the backend reported.
        certified: The known-true value.
        reldiff: Relative difference between them.
        digits: Correct significant digits, `-log10(reldiff)`. Reported because
            certified-value work is conventionally about digit loss rather than
            pass/fail.
        passed: Whether `reldiff` is within tolerance.
    """

    quantity: str
    backend: str
    observed: float
    certified: float
    reldiff: float
    digits: float
    passed: bool


@dataclass
class InvariantCheck:
    """One metamorphic relation evaluated for one backend.

    Attributes:
        expr: The expression as written in `case.yaml`.
        backend: Backend whose quantities were used.
        observed: Value the expression took.
        expected: Value it should have taken.
        tol: Absolute tolerance.
        passed: Whether the relation held.
        reason: What the relation encodes.
        error: Why the relation could not be evaluated, if it could not be.
    """

    expr: str
    backend: str
    observed: float | None
    expected: float
    tol: float
    passed: bool
    reason: str = ""
    error: str | None = None


def _substitute(expr: str, names: list[str]) -> tuple[str, dict[str, str]]:
    """Rewrite quantity names into valid Python identifiers.

    Canonical quantity names like `se.x@HC1` are not Python identifiers, so the
    expression is rewritten before parsing. Longest names are substituted first so
    that `coef.x@scaled` is not clobbered by a prefix match on `coef.x`.

    Args:
        expr: The expression as written.
        names: Quantity names available in the backend's output.

    Returns:
        The rewritten expression and a map from placeholder to original name.
    """
    mapping = {}
    rewritten = expr
    for index, name in enumerate(sorted(names, key=len, reverse=True)):
        if name in rewritten:
            placeholder = f"_q{index}"
            rewritten = rewritten.replace(name, placeholder)
            mapping[placeholder] = name
    return rewritten, mapping


def _evaluate(node: ast.AST, values: dict[str, float]) -> float:
    """Recursively evaluate a restricted arithmetic AST.

    Only literals, names, the four arithmetic operators plus exponentiation, unary
    sign, and a small allowlist of functions are permitted. Anything else raises,
    so a `case.yaml` cannot execute arbitrary code.

    Args:
        node: AST node to evaluate.
        values: Placeholder name to numeric value.

    Returns:
        The node's value.

    Raises:
        InvariantError: On any unsupported construct or unknown name.
    """
    if isinstance(node, ast.Expression):
        return _evaluate(node.body, values)
    if isinstance(node, ast.Constant):
        if isinstance(node.value, (int, float)) and not isinstance(node.value, bool):
            return float(node.value)
        raise InvariantError(f"unsupported literal {node.value!r}")
    if isinstance(node, ast.Name):
        if node.id not in values:
            raise InvariantError(f"unknown quantity {node.id!r}")
        return values[node.id]
    if isinstance(node, ast.BinOp) and type(node.op) in _BINARY:
        return _BINARY[type(node.op)](
            _evaluate(node.left, values), _evaluate(node.right, values)
        )
    if isinstance(node, ast.UnaryOp) and type(node.op) in _UNARY:
        return _UNARY[type(node.op)](_evaluate(node.operand, values))
    if isinstance(node, ast.Call):
        if not isinstance(node.func, ast.Name) or node.func.id not in _FUNCTIONS:
            raise InvariantError("only abs, log, sqrt, exp may be called")
        args = [_evaluate(a, values) for a in node.args]
        return float(_FUNCTIONS[node.func.id](*args))
    raise InvariantError(f"unsupported expression node {type(node).__name__}")


def evaluate_expression(expr: str, quantities: dict[str, float | None]) -> float:
    """Evaluate an invariant expression against a backend's quantities.

    Args:
        expr: Arithmetic expression over quantity names.
        quantities: The backend's reported quantities.

    Returns:
        The expression's value.

    Raises:
        InvariantError: If the expression references a missing or undefined
            quantity, or uses an unsupported construct.
    """
    usable = {k: v for k, v in quantities.items() if v is not None}
    rewritten, mapping = _substitute(expr, list(usable))
    values = {ph: float(usable[name]) for ph, name in mapping.items()}
    try:
        tree = ast.parse(rewritten, mode="eval")
    except SyntaxError as exc:
        raise InvariantError(f"cannot parse {expr!r}: {exc}") from exc
    try:
        return _evaluate(tree, values)
    except ZeroDivisionError as exc:
        raise InvariantError(f"division by zero evaluating {expr!r}") from exc


def check_invariants(
    results: list[Result], invariants: list[Invariant]
) -> list[InvariantCheck]:
    """Evaluate every invariant for every backend that ran.

    Args:
        results: Results for one case.
        invariants: Relations declared in `case.yaml`.

    Returns:
        One check per (invariant, successful backend) pair.
    """
    checks = []
    for result in results:
        if result.status != "ok":
            continue
        for inv in invariants:
            try:
                observed = evaluate_expression(inv.expr, result.quantities)
            except InvariantError as exc:
                checks.append(
                    InvariantCheck(
                        expr=inv.expr,
                        backend=result.backend,
                        observed=None,
                        expected=inv.equals,
                        tol=inv.tol,
                        passed=False,
                        reason=inv.reason,
                        error=str(exc),
                    )
                )
                continue
            checks.append(
                InvariantCheck(
                    expr=inv.expr,
                    backend=result.backend,
                    observed=observed,
                    expected=inv.equals,
                    tol=inv.tol,
                    passed=abs(observed - inv.equals) <= inv.tol,
                    reason=inv.reason,
                )
            )
    return checks


def check_certified(results: list[Result], spec: CaseSpec) -> list[CertifiedCheck]:
    """Score each backend against the case's certified values.

    Args:
        results: Results for one case.
        spec: The case, carrying `certified` values and tolerances.

    Returns:
        One check per (certified quantity, backend that reported it) pair.
    """
    checks = []
    for result in results:
        if result.status != "ok":
            continue
        for quantity, truth in spec.certified.items():
            observed = result.quantities.get(quantity)
            if observed is None:
                continue
            agree_tol, _ = spec.tolerances_for(quantity)
            reldiff = relative_difference(float(observed), truth)
            digits = math.inf if reldiff == 0 else -math.log10(max(reldiff, 1e-300))
            checks.append(
                CertifiedCheck(
                    quantity=quantity,
                    backend=result.backend,
                    observed=float(observed),
                    certified=truth,
                    reldiff=reldiff,
                    digits=digits,
                    passed=reldiff < agree_tol,
                )
            )
    return checks
