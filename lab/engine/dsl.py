"""Safe alpha-formula DSL.

A formula is a single expression string over the price fields and the operator
library in ops.py, e.g.:

    -1 * correlation(rank(delta(log(volume), 2)), rank((close - open) / open), 6)
    ts_rank(close, 9) - ts_rank(adv(20), 9)
    iif(close > delay(close, 5), rank(returns), -rank(returns))

Security: the expression is parsed to an AST and every node is checked against a
whitelist (no attribute access, subscripts, imports, comprehensions, lambdas,
dunder names). Only whitelisted operator/field names and numeric literals are
allowed, then it is eval'd with empty builtins. This makes it safe to run
arbitrary LLM-generated formulas.
"""
import ast
import re
import numpy as np
import pandas as pd

from . import ops

FIELDS = ["open", "high", "low", "close", "volume", "vwap", "returns"]

_ALLOWED_NODES = (
    ast.Expression, ast.BinOp, ast.UnaryOp, ast.Call, ast.Name, ast.Load,
    ast.Constant, ast.Compare, ast.Add, ast.Sub, ast.Mult, ast.Div, ast.Pow,
    ast.Mod, ast.USub, ast.UAdd, ast.Lt, ast.Gt, ast.LtE, ast.GtE, ast.Eq,
    ast.NotEq, ast.BitAnd, ast.BitOr, ast.Invert,
)
_ALLOWED_FUNCS = set(ops.OP_NAMES) | {"adv"}
_ALLOWED_NAMES = _ALLOWED_FUNCS | set(FIELDS) | {"adv"}


class DSLError(ValueError):
    pass


def normalize(formula: str) -> str:
    """Light syntactic sugar so WorldQuant-style strings parse cleanly."""
    f = formula.strip()
    if f.endswith(";"):
        f = f[:-1]
    # advNN -> adv(NN)   (e.g. adv20 -> adv(20))
    f = re.sub(r"\badv(\d+)\b", r"adv(\1)", f)
    # abs( -> abs_(   (abs is a python builtin we don't expose)
    f = re.sub(r"\babs\s*\(", "abs_(", f)
    # ternary  a ? b : c  ->  iif(a, b, c)  (non-nested; best effort)
    for _ in range(5):
        m = re.search(r"\?", f)
        if not m:
            break
        f = _convert_one_ternary(f)
    return f


def _convert_one_ternary(f: str) -> str:
    qi = f.index("?")
    # find matching ':' at same paren depth after '?'
    depth = 0
    ci = -1
    for i in range(qi + 1, len(f)):
        c = f[i]
        if c in "([":
            depth += 1
        elif c in ")]":
            if depth == 0:
                break
            depth -= 1
        elif c == ":" and depth == 0:
            ci = i
            break
        elif c == "?" and depth == 0:
            break
    if ci == -1:
        raise DSLError("malformed ternary (no matching ':')")
    # cond = text before '?' back to an unmatched '(' or start
    depth = 0
    si = 0
    for i in range(qi - 1, -1, -1):
        c = f[i]
        if c in ")]":
            depth += 1
        elif c in "([":
            if depth == 0:
                si = i + 1
                break
            depth -= 1
    # b = between ? and :, c = after : up to an unmatched ')' or end
    depth = 0
    ei = len(f)
    for i in range(ci + 1, len(f)):
        c = f[i]
        if c in "([":
            depth += 1
        elif c in ")]":
            if depth == 0:
                ei = i
                break
            depth -= 1
        elif c == "," and depth == 0:
            ei = i
            break
    cond, a, b = f[si:qi], f[qi + 1:ci], f[ci + 1:ei]
    return f[:si] + f"iif({cond.strip()}, {a.strip()}, {b.strip()})" + f[ei:]


def validate(formula: str) -> ast.AST:
    f = normalize(formula)
    try:
        tree = ast.parse(f, mode="eval")
    except SyntaxError as e:
        raise DSLError(f"syntax error: {e}")
    for node in ast.walk(tree):
        if not isinstance(node, _ALLOWED_NODES):
            raise DSLError(f"disallowed syntax: {type(node).__name__}")
        if isinstance(node, ast.Name):
            if node.id.startswith("_") or node.id not in _ALLOWED_NAMES:
                raise DSLError(f"unknown name: {node.id!r}")
        if isinstance(node, ast.Call):
            if not isinstance(node.func, ast.Name) or node.func.id not in _ALLOWED_FUNCS:
                raise DSLError("only whitelisted function calls allowed")
            if node.keywords:
                raise DSLError("keyword arguments not allowed")
        if isinstance(node, ast.Constant) and not isinstance(node.value, (int, float)):
            raise DSLError("only numeric literals allowed")
    return tree


def _namespace(panel: dict) -> dict:
    ns = ops.op_namespace()
    for fld in FIELDS:
        ns[fld] = panel[fld]
    ns["adv"] = ops.adv_builder(panel["volume"])
    return ns


def evaluate(formula: str, panel: dict) -> pd.DataFrame:
    """Compute a raw signal DataFrame (days x stocks) for `formula` on `panel`.

    Raises DSLError on invalid/degenerate formulas.
    """
    validate(formula)
    code = compile(ast.parse(normalize(formula), mode="eval"), "<alpha>", "eval")
    ns = _namespace(panel)
    try:
        sig = eval(code, {"__builtins__": {}}, ns)
    except Exception as e:  # noqa: BLE001
        raise DSLError(f"eval failed: {type(e).__name__}: {str(e)[:160]}")
    close = panel["close"]
    if np.isscalar(sig) or isinstance(sig, (int, float)):
        raise DSLError("formula reduced to a scalar (needs a panel-shaped result)")
    if isinstance(sig, pd.Series):
        raise DSLError("formula reduced to a Series (cross-section collapsed)")
    sig = pd.DataFrame(sig).reindex(index=close.index, columns=close.columns)
    sig = sig.astype(float).replace([np.inf, -np.inf], np.nan)
    # non-degeneracy: needs cross-sectional variation on a reasonable number of days
    valid_days = (sig.notna().sum(axis=1) >= 5)
    if valid_days.sum() < 50:
        raise DSLError("signal has <50 usable days (too sparse)")
    xs_var_days = (sig[valid_days].std(axis=1) > 1e-12).sum()
    if xs_var_days < 50:
        raise DSLError("signal is cross-sectionally constant (no ranking signal)")
    return sig
