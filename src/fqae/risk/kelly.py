"""Fractional Kelly with a hard per-bet cap (FR-5.1)."""


def full_kelly(p: float, decimal_odds: float) -> float:
    b = decimal_odds - 1.0
    return max(0.0, (b * p - (1 - p)) / b) if b > 0 else 0.0


def stake_fraction(p: float, decimal_odds: float, kelly_mult: float = 0.25, cap: float = 0.015) -> tuple[float, bool]:
    """Returns (stake as fraction of bankroll, was_capped)."""
    raw = kelly_mult * full_kelly(p, decimal_odds)
    return min(raw, cap), raw > cap
