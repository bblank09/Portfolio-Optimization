"""Thin orchestrator: calls Tasks 4-9's modules in the right order and
assembles their outputs into an OptimizeResult. No NAV loading, solver,
Black-Litterman, frontier, or diagnostics logic is reimplemented here --
see backend/app/optimizer/{inputs,solvers,black_litterman,frontier,
diagnostics}.py for those.

Deviation from the brief's sample code: none in the calls into the other
modules (those match the brief as-is). The only changes from the brief's
draft are the portfolio-return/variance/Sharpe computation, which the brief
recomputed manually with a bespoke inline loop -- that duplicates exactly
the (mu, sigma, weights) -> (return, volatility) math frontier.py already
implements and re-uses for every frontier point and marker
(`frontier._portfolio_stats`). Reusing it here keeps the "Optimized" row in
performanceSummary numerically consistent with the optimal marker plotted on
the frontier (frontier.py's module docstring calls this consistency out as
the landmine the module exists to avoid) instead of risking two independent
formulas drifting apart. `frontier._portfolio_stats` is a private helper, so
it is called via its qualified module path rather than re-exported.
"""

import numpy as np
import pandas as pd

from backend.app.domain.optimize_schemas import OptimizeRequest, OptimizeResult
from backend.app.engine import metrics
from backend.app.optimizer import (
    black_litterman,
    comparison,
    diagnostics,
    frontier,
    holdings,
    inputs,
    report,
    robust,
    rolling,
    solvers,
)


def _calendar_year_returns(period_returns: pd.Series, periods_per_year: int) -> list[float]:
    """Compounded return for each calendar year that is (nearly) complete.

    A partial year is not a "best/worst year" -- comparing a 2-month stub
    against full years would misreport both ends -- so years covered by fewer
    than 75% of the expected observations are dropped rather than reported.
    """
    if not isinstance(period_returns.index, pd.DatetimeIndex):
        return []
    minimum_periods = max(1, int(periods_per_year * 0.75))
    yearly: list[float] = []
    for _, group in period_returns.groupby(period_returns.index.year):
        if len(group) >= minimum_periods:
            compounded = float(np.prod(1.0 + group.to_numpy(dtype=float)))
            yearly.append((compounded - 1.0) * 100)
    return yearly


def run_optimize(request: OptimizeRequest) -> OptimizeResult:
    returns = inputs.build_returns_panel(request)
    mu, sigma = inputs.build_mu_sigma(request, returns)

    bl_result = None
    # The ORIGINAL (historical / override-derived) expected returns, kept
    # before Black-Litterman rebinds `mu` to the posterior below. Only the
    # comparison portfolio uses it: everything else downstream (solve,
    # frontier, markers, asset summary) intentionally works in the space the
    # solve actually happened in. A max_sharpe comparison computed on the BL
    # posterior IS the BL solve -- they share an objective code -- which made
    # compareWeights bit-identical to optimalWeights.
    original_mu = mu
    if request.goal.value == "black_litterman":
        equilibrium, posterior = black_litterman.blend_posterior(request, mu, sigma)
        bl_result = {
            "equilibriumReturnPct": {k: round(float(v), 2) for k, v in equilibrium.items()},
            "adjustedReturnPct": {k: round(float(v), 2) for k, v in posterior.items()},
        }
        mu = posterior

    robust_initial_weights = None
    robust_optimization_note = None
    if request.robust_optimization:
        robust_initial_weights, robust_optimization_note = robust.resample_and_solve(request, mu, sigma, returns)

    optimal_weights, constraint_note = holdings.enforce_max_holdings(
        request, mu, sigma, returns, initial_weights=robust_initial_weights
    )

    # A rolling-evaluation failure never blocks the primary weights result
    # (design spec). run_rolling_evaluation raises
    # ValueError("INSUFFICIENT_ROLLING_HISTORY") when the window is too
    # short for two folds; letting that propagate would turn a request that
    # solved perfectly well into a 422 with no weights at all.
    try:
        rolling_folds, rolling_note = rolling.run_rolling_evaluation(request, returns)
    except ValueError:
        rolling_folds = []
        rolling_note = (
            "Rolling validation unavailable: not enough history for at least 2 folds "
            "at the selected frequency."
        )

    compare_weights, compare_note = comparison.build_comparison_weights(request, original_mu, sigma, returns)
    benchmark_comparison = comparison.build_benchmark_comparison(request, optimal_weights, returns)

    compared_risk_value = None
    if compare_weights is not None:
        compared_risk_value, _ = solvers.realized_risk(request, compare_weights, sigma, returns, inputs.periods_per_year(request))

    frontier_points = frontier.build_frontier(request, mu, sigma, returns)
    optimal_marker, gmv_marker, tangency_marker = frontier.extract_markers(frontier_points, optimal_weights, mu, sigma)

    trade_list, total_turnover = diagnostics.build_trade_list(request, optimal_weights)
    findings = diagnostics.binding_constraints(request, optimal_weights)

    portfolio_return, portfolio_vol = frontier._portfolio_stats(optimal_weights, mu, sigma)
    sharpe = (portfolio_return - request.constraints.risk_free_rate_pct) / portfolio_vol if portfolio_vol > 0 else 0.0

    # Realized (ex-post) performance is computed from the portfolio's own
    # periodic return series using backend/app/engine/metrics.py -- the same
    # implementations the backtest engine uses -- rather than derived from
    # volatility. Fields that series cannot support are None, not invented.
    periods_per_year = inputs.periods_per_year(request)
    risk_free_fraction = request.constraints.risk_free_rate_pct / 100
    # Shared with rolling.py's per-fold scoring -- one implementation of the
    # weights -> realized series alignment, not two copies free to drift.
    period_returns = inputs.portfolio_return_series(returns, optimal_weights)
    growth = (1 + period_returns).cumprod()
    yearly = _calendar_year_returns(period_returns, periods_per_year)
    sharpe_ex_post = metrics.sharpe_ratio(period_returns, risk_free_fraction, periods_per_year)
    sortino = metrics.sortino_ratio(period_returns, risk_free_fraction, periods_per_year)

    performance_summary = [{
        "label": "Optimized",
        "cagrPct": round(metrics.annualized_return(period_returns, periods_per_year) * 100, 2),
        # Ex-ante: the mu/Sigma the optimizer actually solved against.
        "expectedReturnPct": round(portfolio_return, 2),
        "stdDevPct": round(portfolio_vol, 2),
        "bestYearPct": round(max(yearly), 2) if yearly else None,
        "worstYearPct": round(min(yearly), 2) if yearly else None,
        "maxDrawdownPct": round(metrics.max_drawdown(growth) * 100, 2) if not growth.empty else None,
        "sharpeExAnte": round(sharpe, 2),
        "sharpeExPost": round(sharpe_ex_post, 2) if sharpe_ex_post is not None else None,
        "sortino": round(sortino, 2) if sortino is not None else None,
    }]

    realized_risk_value, risk_is_annualized = solvers.realized_risk(
        request, optimal_weights, sigma, returns, periods_per_year
    )
    risk_label = solvers.RM_LABELS[request.risk_measure.value]
    if not risk_is_annualized:
        risk_label = f"{risk_label} ({request.data_frequency.value})"

    return OptimizeResult.model_validate({
        "feasibility": "ok",
        "feasibilityMessage": None,
        "robustNote": rolling_note,
        "robustOptimizationNote": robust_optimization_note,
        "constraintNote": constraint_note,
        "optimalWeights": optimal_weights,
        "compareWeights": compare_weights,
        "compareNote": compare_note,
        # Real per-asset decomposition of the selected risk measure via
        # riskfolio-lib's own Risk_Contribution (was: a flat 100/n stand-in
        # that said nothing about the actual portfolio).
        "riskContributionPct": solvers.risk_contribution_pct(request, optimal_weights, sigma, returns),
        "frontier": frontier_points,
        "assetSummary": report.build_asset_summary(request, mu, sigma),
        "correlations": report.build_correlations(sigma),
        "performanceSummary": performance_summary,
        "rolling": rolling_folds,
        "blackLitterman": bl_result,
        "monthlyReturnsPct": (period_returns * 100).round(2).tolist(),
        "selectedRiskMeasure": {
            "measure": request.risk_measure.value,
            "label": risk_label,
            "optimizedValue": round(realized_risk_value, 2),
            "comparedValue": round(compared_risk_value, 2) if compared_risk_value is not None else None,
            "unit": "pct",
        },
        "benchmarkComparison": benchmark_comparison,
        "tradeList": trade_list,
        "totalTurnoverPct": total_turnover,
        "bindingConstraints": findings,
        "optimalPoint": optimal_marker,
        "gmvPoint": gmv_marker,
        "tangencyPoint": tangency_marker,
        "generatedAt": report.generated_at_now(),
    })
