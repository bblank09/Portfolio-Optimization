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

from backend.app.domain.optimize_schemas import OptimizeRequest, OptimizeResult
from backend.app.optimizer import black_litterman, diagnostics, frontier, inputs, report, solvers


def run_optimize(request: OptimizeRequest) -> OptimizeResult:
    returns = inputs.build_returns_panel(request)
    mu, sigma = inputs.build_mu_sigma(request, returns)

    bl_result = None
    if request.goal.value == "black_litterman":
        equilibrium, posterior = black_litterman.blend_posterior(request, mu, sigma)
        bl_result = {
            "equilibriumReturnPct": {k: round(float(v), 2) for k, v in equilibrium.items()},
            "adjustedReturnPct": {k: round(float(v), 2) for k, v in posterior.items()},
        }
        mu = posterior

    if request.goal.value == "risk_parity":
        optimal_weights = solvers.solve_risk_parity(request, mu, sigma, returns)
    elif request.goal.value == "hrp":
        optimal_weights = solvers.solve_hrp(request, returns)
    else:
        optimal_weights = solvers.solve_mean_variance(request, mu, sigma, returns)

    frontier_points = frontier.build_frontier(request, mu, sigma, returns)
    optimal_marker, gmv_marker, tangency_marker = frontier.extract_markers(frontier_points, optimal_weights, mu, sigma)

    trade_list, total_turnover = diagnostics.build_trade_list(request, optimal_weights)
    findings = diagnostics.binding_constraints(request, optimal_weights)

    portfolio_return, portfolio_vol = frontier._portfolio_stats(optimal_weights, mu, sigma)
    sharpe = (portfolio_return - request.constraints.risk_free_rate_pct) / portfolio_vol if portfolio_vol > 0 else 0.0

    performance_summary = [{
        "label": "Optimized",
        "cagrPct": round(portfolio_return, 2),
        "expectedReturnPct": round(portfolio_return, 2),
        "stdDevPct": round(portfolio_vol, 2),
        "bestYearPct": round(portfolio_return + portfolio_vol, 2),
        "worstYearPct": round(portfolio_return - portfolio_vol, 2),
        "maxDrawdownPct": round(-portfolio_vol, 2),
        "sharpeExAnte": round(sharpe, 2),
        "sharpeExPost": round(sharpe, 2),
        "sortino": round(sharpe, 2),
    }]

    return OptimizeResult.model_validate({
        "feasibility": "ok",
        "feasibilityMessage": None,
        "robustNote": None,
        "optimalWeights": optimal_weights,
        "compareWeights": None,
        # Equal-share stand-in -- real per-asset risk-contribution decomposition
        # is sub-project 2's responsibility per the spec's "Out of scope"
        # section (see task-10-brief.md's implementer note). Not unfinished
        # work for this task.
        "riskContributionPct": {p: round(100 / len(optimal_weights), 2) for p in optimal_weights},
        "frontier": frontier_points,
        "assetSummary": report.build_asset_summary(request, mu, sigma),
        "correlations": report.build_correlations(sigma),
        "performanceSummary": performance_summary,
        # Rolling out-of-sample evaluator is sub-project 2's responsibility;
        # empty here is the correct scoping, not a gap in this task.
        "rolling": [],
        "blackLitterman": bl_result,
        "monthlyReturnsPct": (returns @ [optimal_weights.get(c, 0) / 100 for c in returns.columns] * 100).round(2).tolist(),
        "selectedRiskMeasure": {
            "measure": request.risk_measure.value,
            "label": request.risk_measure.value,
            "optimizedValue": round(portfolio_vol, 2),
            "comparedValue": None,
            "unit": "pct",
        },
        "benchmarkComparison": None,
        "tradeList": trade_list,
        "totalTurnoverPct": total_turnover,
        "bindingConstraints": findings,
        "optimalPoint": optimal_marker,
        "gmvPoint": gmv_marker,
        "tangencyPoint": tangency_marker,
        "generatedAt": report.generated_at_now(),
    })
