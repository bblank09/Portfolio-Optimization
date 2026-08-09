"""Reporting helpers that turn already-computed mu/Sigma into the
OptimizeResult's per-asset summary and pairwise correlation rows. Pure
presentation logic over inputs.py's outputs -- no NAV loading, solving, or
math beyond simple vol/correlation derivation from a covariance matrix."""

from datetime import UTC, datetime

import pandas as pd

from backend.app.domain.optimize_schemas import OptimizeRequest


def build_asset_summary(request: OptimizeRequest, mu: pd.Series, sigma: pd.DataFrame) -> list[dict]:
    rows = []
    for fund in request.funds:
        proj_id = fund.proj_id
        vol = (sigma.loc[proj_id, proj_id] ** 0.5) if proj_id in sigma.index else 0.0
        bound = request.fund_bounds.get(proj_id)
        rows.append({
            "projId": proj_id,
            "displayName": fund.display_name,
            "expectedReturnPct": round(float(mu.get(proj_id, 0.0)), 2),
            "volatilityPct": round(float(vol), 2),
            "sharpe": round(float(mu.get(proj_id, 0.0)) / max(float(vol), 0.5), 3),
            "minWeightPct": bound.min_weight_pct if bound else request.constraints.min_weight_pct,
            "maxWeightPct": bound.max_weight_pct if bound else request.constraints.max_weight_pct,
        })
    return rows


def build_correlations(sigma: pd.DataFrame) -> list[dict]:
    proj_ids = list(sigma.index)
    result = []
    for i in range(len(proj_ids)):
        for j in range(i + 1, len(proj_ids)):
            a, b = proj_ids[i], proj_ids[j]
            vol_a, vol_b = sigma.loc[a, a] ** 0.5, sigma.loc[b, b] ** 0.5
            corr = sigma.loc[a, b] / (vol_a * vol_b) if vol_a > 0 and vol_b > 0 else 0.0
            result.append({"projId1": a, "projId2": b, "correlation": round(float(corr), 2)})
    return result


def generated_at_now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")
