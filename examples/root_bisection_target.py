"""Small target adapter used only by the clean-room tutorial."""

from __future__ import annotations

from collections.abc import Callable


def bisection(
    function: Callable[[float], float],
    lower: float,
    upper: float,
    *,
    tolerance: float = 1.0e-12,
    max_iterations: int = 2000,
) -> tuple[float, float, int]:
    """Return root, function value, and a zero success flag."""
    f_lower = function(lower)
    f_upper = function(upper)
    if f_lower * f_upper > 0.0:
        midpoint = 0.5 * (lower + upper)
        return midpoint, function(midpoint), 1
    midpoint = lower
    f_midpoint = f_lower
    for _ in range(max_iterations):
        midpoint = 0.5 * (lower + upper)
        f_midpoint = function(midpoint)
        if abs(f_midpoint) <= tolerance or abs(upper - lower) <= tolerance:
            return midpoint, f_midpoint, 0
        if f_lower * f_midpoint < 0.0:
            upper = midpoint
            f_upper = f_midpoint
        else:
            lower = midpoint
            f_lower = f_midpoint
    return midpoint, f_midpoint, 2
