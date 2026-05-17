"""
Safe mathematical expression evaluator.

Supports: arithmetic, percentages, exponentiation, and common math functions.
Uses a restricted eval — no builtins, no imports, no file access.
"""

from __future__ import annotations
import math
import re

# Whitelist of names available inside the expression
_SAFE_ENV: dict = {
    "__builtins__": {},
    "abs": abs,
    "round": round,
    "min": min,
    "max": max,
    "sum": sum,
    "sqrt": math.sqrt,
    "floor": math.floor,
    "ceil": math.ceil,
    "log": math.log,
    "log10": math.log10,
    "log2": math.log2,
    "sin": math.sin,
    "cos": math.cos,
    "tan": math.tan,
    "pi": math.pi,
    "e": math.e,
    "inf": math.inf,
}


def _normalise(expression: str) -> str:
    """Rewrite human-friendly syntax into something eval can handle."""
    expr = expression.strip()

    # "15% of 240"  →  "0.15 * 240"
    expr = re.sub(
        r"(\d+(?:\.\d+)?)\s*%\s*of\s*(\d+(?:\.\d+)?)",
        lambda m: f"({float(m.group(1)) / 100} * {m.group(2)})",
        expr,
        flags=re.IGNORECASE,
    )

    # Bare "15%" not followed by "of"  →  "(0.15)"
    expr = re.sub(
        r"(\d+(?:\.\d+)?)\s*%",
        lambda m: f"({float(m.group(1)) / 100})",
        expr,
    )

    # "x^y"  →  "x ** y"
    expr = re.sub(r"\^", "**", expr)

    return expr


def calculate(expression: str) -> str:
    """
    Evaluate a mathematical expression and return the result as a string.

    Returns an error message (not an exception) if evaluation fails —
    so Claude can gracefully relay the problem to the user.
    """
    normalised = _normalise(expression)

    try:
        result = eval(normalised, _SAFE_ENV, {})  # noqa: S307
    except ZeroDivisionError:
        return "Error: division by zero."
    except (SyntaxError, NameError, TypeError) as exc:
        return f"Error: could not evaluate '{expression}' — {exc}"
    except Exception as exc:
        return f"Error: {exc}"

    # Pretty-print: drop the decimal if the result is a whole number
    if isinstance(result, float):
        if result == int(result) and not math.isinf(result):
            return f"{int(result):,}"
        return f"{result:,.6g}"
    if isinstance(result, int):
        return f"{result:,}"
    return str(result)
