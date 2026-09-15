"""Shared numerical contracts for physics and economic inputs."""
from __future__ import annotations

import math


def finite_number(value, name: str, minimum=None, maximum=None, *, positive=False) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be a finite number.") from exc
    if not math.isfinite(number):
        raise ValueError(f"{name} must be a finite number.")
    if positive and number <= 0:
        raise ValueError(f"{name} must be positive.")
    if minimum is not None and number < minimum:
        raise ValueError(f"{name} must be at least {minimum}.")
    if maximum is not None and number > maximum:
        raise ValueError(f"{name} must be at most {maximum}.")
    return number


def horizon_years(value) -> int:
    number = finite_number(value, "years", 1, 100)
    if number != int(number):
        raise ValueError("years must be an integer.")
    return int(number)


def evidence_flag(value) -> bool:
    """Missing values and text such as 'False' must never grant eligibility."""
    return str(value).strip().lower() in {"true", "1"}
