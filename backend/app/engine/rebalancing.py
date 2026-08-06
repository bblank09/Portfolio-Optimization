import pandas as pd

from backend.app.domain.enums import RebalanceMode

# A portfolio computed as exactly on the band edge (e.g. 550.0 / 1000.0 target
# 50%) can land a few ULPs past it in float arithmetic. Without this tolerance
# that residue reads as a real breach -- see DEGENERACY_TOLERANCE in metrics.py
# for the same class of bug.
BAND_EDGE_TOLERANCE = 1e-9


def rebalance_due(
    current_date: pd.Timestamp,
    previous_date: pd.Timestamp | None,
    mode: RebalanceMode,
    *,
    values: pd.Series | None = None,
    target_weights: pd.Series | None = None,
    threshold_pct: float | None = None,
) -> bool:
    if previous_date is None or mode == RebalanceMode.none:
        return False
    if mode == RebalanceMode.monthly:
        return True
    if mode == RebalanceMode.quarterly:
        return current_date.to_period("Q") != previous_date.to_period("Q")
    if mode == RebalanceMode.annual:
        return current_date.year != previous_date.year
    if mode == RebalanceMode.threshold:
        if values is None or target_weights is None or threshold_pct is None:
            return False
        total = float(values.sum())
        if not total:
            return False
        current_weights = values / total
        drift_pct = (current_weights - target_weights).abs() * 100
        # Strictly greater than: a portfolio sitting exactly on the band edge
        # has not yet breached it.
        return bool((drift_pct > threshold_pct + BAND_EDGE_TOLERANCE).any())
    return False


def rebalance_values(values: pd.Series, target_weights: pd.Series) -> tuple[pd.Series, float, float]:
    total = float(values.sum())
    target_values = target_weights * total
    money_turnover = float((target_values - values).abs().sum() / 2)
    turnover_ratio = money_turnover / total if total else 0.0
    return target_values, turnover_ratio, money_turnover
