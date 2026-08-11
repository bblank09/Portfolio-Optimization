# Optimizer Formula Reference

Formulas used by `backend/app/optimizer/` (the optimization engine), with
academic/primary citations and the exact code location implementing each.
Companion to `docs/formula-reference.md`, which covers the backtest
engine's return/risk metrics (CAGR, volatility, Sharpe, Sortino, max
drawdown, tracking error) — reused as-is by this optimizer's Performance
and Rolling tabs, not duplicated here.

Verified against riskfolio-lib **7.3.0** as installed in
`/private/tmp/sec_open_data_portfolio_backtester_venv`
(`riskfolio/src/Portfolio.py`, `HCPortfolio.py`, `RiskFunctions.py`);
line numbers below refer to that installed version.

## Notation

- `w` — portfolio weight vector (n funds × 1)
- `μ` — expected return vector (n × 1)
- `Σ` — covariance matrix (n × n)
- `r_f` — risk-free rate
- `Π` — Black-Litterman equilibrium (implied) return vector

## Mean-Variance / Sharpe Ratio Maximization

**Formula:** maximize `(w'μ − r_f) / √(w'Σw)` subject to `Σw = 1`, `w ≥ 0` (long-only).

**Citation:** Markowitz, H. (1952). "Portfolio Selection." *Journal of
Finance*, 7(1), 77-91. Sharpe, W. F. (1966, revised 1994). "The Sharpe
Ratio." *Journal of Portfolio Management*.

**Code:** `backend/app/optimizer/solvers.py::solve_mean_variance` calls
`port.optimization(model="Classic", rm=rm, obj=obj, rf=port.rf, l=0, hist=True)`
on an `rp.Portfolio` built by `_build_portfolio`. `obj` comes from
`_OBJ_CODES`: `max_sharpe → "Sharpe"`, `min_volatility → "MinRisk"`,
`max_return_target_vol → "MaxRet"`, `min_variance → "MinRisk"`,
`black_litterman → "Sharpe"`. `rm` is forced to `"MV"` for
`min_variance` and is otherwise `RM_CODES[request.risk_measure]`. This
matches the cited formula: `model="Classic"` is the sample-estimate
mean-risk model, `obj="Sharpe"` with `rm="MV"` is exactly the
`(w'μ − r_f)/√(w'Σw)` maximization, and `l=0` disables the alternative
risk-aversion (`Utility`) objective so no `μ − l·risk` term interferes.
`port.rf` is set from `request.constraints.risk_free_rate_pct / 100` and
`μ`/`Σ` are assigned directly (`port.mu = (mu/100).to_frame().T`,
`port.cov = sigma/100/100`) rather than via `assets_stats()`, so the
solver optimizes exactly the estimates `inputs.build_mu_sigma` produced.
Long-only is enforced by `sht=not request.constraints.long_only` with
`uppersht=0.0`, and the budget constraint `Σw = 1` is riskfolio-lib's own
built-in. Per-fund and group weight bounds are additional constraints not
in the textbook formula, imposed via `port.ainequality`/`port.binequality`
(`A w ≤ b`).

## Semi-Variance

**Formula:** downside-only variance, `E[min(R − target, 0)²]`, in place of
full variance in the same mean-risk objective above.

**Citation:** Markowitz, H. (1959). *Portfolio Selection: Efficient
Diversification of Investments*, Chapter 9 (semi-variance as a risk
measure more aligned with investor loss-aversion than full variance).

**Code:** `backend/app/optimizer/solvers.py`, `RM_CODES["semi_variance"] = "MSV"`.
`"MSV"` is riskfolio-lib's *mean semi-deviation* code — the square root of
semi-variance, `[Σ min(X_t − E[X], 0)² / (T−1)]^(1/2)` per
`RiskFunctions.SemiDeviation` (line 107). Two genuine caveats against
the formula as stated:

1. **The target is the sample mean, not a configurable threshold.**
   riskfolio-lib hard-codes `E[X_t]` as the reference point in
   `SemiDeviation`; there is no `target`/MAR parameter, and this project
   passes none. (riskfolio-lib's `"FLPM"`/`"SLPM"` codes are the ones that
   take a `MAR=rf` target, and this project does not use them.) So the
   implemented measure is semi-deviation *below the mean*, which is
   Markowitz (1959)'s `E[min(R − target, 0)²]` with `target = E[R]` —
   one of the two variants Markowitz discusses, not below-zero or
   below-`r_f`.
2. **Deviation vs. variance.** The optimizer minimizes the square root
   (semi-*deviation*), not semi-variance itself. Since `√·` is monotone,
   the argmin weights are identical; only the reported risk *number*
   differs in units. `realized_risk` treats `"MSV"` as annualizable
   (`_ANNUALIZABLE_RM = {"MV", "MSV"}`) and scales it by
   `periods_per_year**0.5`, which is only valid for a deviation, so this
   is internally consistent.

## CVaR (Conditional Value at Risk)

**Formula:** the Rockafellar–Uryasev linear-programming formulation of
CVaR at confidence level `α` — minimizes the expected loss in the worst
`(1-α)` tail, expressed as a convex (LP) problem rather than the naive
non-convex historical-quantile definition.

**Citation:** Rockafellar, R. T. & Uryasev, S. (2000). "Optimization of
Conditional Value-at-Risk." *Journal of Risk*, 2(3), 21-41.

**Code:** `backend/app/optimizer/solvers.py`, `RM_CODES["cvar"] = "CVaR"`.
The formulation itself matches: riskfolio-lib builds
`CVaR_L = VaR_1 + 1/(alpha·T) · Σ Z1` with `Z1 ≥ 0`,
`Z1 ≥ −X − VaR_1` (`Portfolio.py` line 2246) — this is literally the
Rockafellar–Uryasev auxiliary-variable LP, solved with CLARABEL, not a
historical quantile.

**However, the `alpha` wiring does NOT fully match the request.** This is
a real finding, not a formality:

- `rp.Portfolio.optimization()`'s signature is
  `(self, model, rm, obj, kelly, rf, l, hist)` — it takes **no `alpha`
  argument**. It reads `self.alpha`, whose constructor default is `0.05`
  (`Portfolio.py` line 295/377). `_build_portfolio` never sets
  `port.alpha`, so **every CVaR/CDaR solve runs at a fixed 5% tail
  regardless of `request.tailConfidence`.**
- `_tail_alpha(request)` (`= clip(1 − tail_confidence/100, 1e-4, 0.5)`,
  the correct 1−confidence convention) *is* correctly wired, but only
  into the two *post-solve reporting* calls:
  `realized_risk` → `rp.RiskFunctions.Sharpe_Risk(..., alpha=_tail_alpha(request))`
  and `risk_contribution_pct` → `rp.RiskFunctions.Risk_Contribution(..., alpha=...)`.
- Net effect: with `tailConfidence` at its default 95, `_tail_alpha`
  returns 0.05 and solve and reporting agree exactly. At any other
  `tailConfidence` the *reported* CVaR uses the user's tail while the
  *optimized* weights were chosen at the 5% tail. Correcting this would
  mean setting `port.alpha = _tail_alpha(request)` in `_build_portfolio`.

## CDaR (Conditional Drawdown at Risk)

**Formula:** the drawdown analogue of CVaR — expected drawdown in the
worst `(1-α)` tail of the drawdown distribution, also a convex (LP)
formulation.

**Citation:** Chekhlov, A., Uryasev, S. & Zabarankin, M. (2005).
"Drawdown Measure in Portfolio Optimization." *International Journal of
Theoretical and Applied Finance*, 8(1), 13-58.

**Code:** `backend/app/optimizer/solvers.py`, `RM_CODES["cdar"] = "CDaR"`.
riskfolio-lib constructs `risk10 = DaR + 1/(alpha·T) · Σ Zd1`
(`Portfolio.py` line 2300) — structurally the same auxiliary-variable LP
as CVaR, applied to the drawdown path instead of the return series, which
is the Chekhlov–Uryasev–Zabarankin CDaR. One documentation detail worth
recording: riskfolio-lib's own docstring specifies CDaR **of uncompounded
cumulative returns** (`Portfolio.py` line 2043), i.e. the *absolute*
drawdown of the arithmetic equity path — not the compounded percentage
drawdown that `backend/app/engine/` reports on the Drawdown tab. The two
numbers are close but not identical for long horizons, and the optimizer
never reports a CDaR figure to the UI as a drawdown percentage, so this
does not surface as an inconsistency.

Same `alpha` caveat as CVaR above: the solve uses riskfolio-lib's
default `self.alpha = 0.05`, not `request.tailConfidence`. Only the
post-solve `realized_risk` / `risk_contribution_pct` calls honor it.

## Black-Litterman Posterior Returns

**Formula:** equilibrium (implied) returns `Π = δΣw_mkt` (reverse
optimization from market-cap weights and risk aversion `δ`), then blended
with investor views via the standard BL posterior:
`E[R] = [(τΣ)⁻¹ + P'ΩP]⁻¹ [(τΣ)⁻¹Π + P'Ω⁻¹Q]`.

**Citation:** Black, F. & Litterman, R. (1992). "Global Portfolio
Optimization." *Financial Analysts Journal*, 48(5), 28-43. He, G. &
Litterman, R. (1999). "The Intuition Behind Black-Litterman Model
Portfolios." Idzorek, T. (2004). "A Step-by-Step Guide to the
Black-Litterman Model" (view-confidence-to-Ω back-solving, already saved
locally at `docs/assets/idzorek-2004-black-litterman-guide.pdf`).

**Code:** `backend/app/optimizer/black_litterman.py`. No riskfolio-lib
call is used here — the module implements the closed form directly in
numpy (its own header explains that `Portfolio.blacklitterman_stats`
exists but mutates `self.mu`/`self.cov` in place and doesn't compose with
this project's pure `(mu, sigma) → (equilibrium, posterior)` interface).

- `compute_equilibrium_returns(sigma, risk_aversion, market_weights)`
  computes `pi = risk_aversion * (sigma/100/100) @ w`, i.e. exactly
  `Π = δΣw_mkt`, returned re-scaled to percent. **Matches.**
- `risk_aversion` has **no default** — it is a required
  `Field(gt=0)` on `BlackLittermanInputs` (`optimize_schemas.py` line
  106), so `δ` is always the caller's explicit value. Likewise
  `tau: float = Field(gt=0, le=1)` is required, no default.
- `market_weights` is **not** market-cap weights: `blend_posterior` passes
  `pd.Series(1/len(proj_ids), ...)`, an equal-weighted proxy, because no
  market-cap data exists for a Thai-fund shortlist. This is a documented
  deliberate departure from Black-Litterman (1992)'s CAPM market
  portfolio, noted in the function's own docstring.
- `blend_posterior` builds `middle = inv(inv(τΣ) + P'Ω⁻¹P)` and
  `posterior = middle @ (inv(τΣ) @ π + P'Ω⁻¹Q)` (lines 73-74). Note the
  cited formula as written in this brief has a typo — the bracketed term
  is `[(τΣ)⁻¹ + P'Ω⁻¹P]⁻¹`, with `Ω⁻¹`, which is what the code does and
  what Black & Litterman (1992) / He & Litterman (1999) actually state.
  **The code is correct; the formula string above should read `P'Ω⁻¹P`.**
- `P` is built per view: absolute views set `P[row, i] = 1`; relative
  views set `P[row, i] = +1, P[row, j] = −1`. `Q[row]` is
  `adjusted_performance_pct / 100`. **Matches.**
- `Ω` is diagonal with
  `ω_k = (P_k τΣ P_k') · (1/confidence − 1)`, and `1e-8` for
  100%-confidence views (to keep `inv(Ω)` finite). This is an
  *Idzorek-style* confidence mapping — it has the right qualitative
  behavior (confidence → 1 gives ω → 0 and full view weight; confidence →
  0 gives ω → ∞ and the view is ignored) and reduces to He & Litterman's
  `Ω = diag(PτΣP')` at 50% confidence. It is **not** Idzorek (2004)'s
  actual procedure, which numerically back-solves ω from a target
  tilt (the desired posterior-weight deviation), not from a closed-form
  scalar. The code's own comment says "Idzorek (2004)-style", which is
  the honest description.
- Black-Litterman is an estimator, not an objective: `solve_for_goal`
  replaces `mu` with the posterior and then dispatches to
  `solve_mean_variance` with `obj="Sharpe"`, which is what Black &
  Litterman prescribe.

## HRP (Hierarchical Risk Parity)

**Formula:** three-stage algorithm — (1) hierarchical clustering of assets
by correlation distance, (2) quasi-diagonalization of the correlation
matrix by the clustering order, (3) recursive bisection allocating
inverse-variance weight down the resulting tree — avoiding matrix
inversion entirely (unlike mean-variance), which is HRP's stated
robustness advantage in-sample.

**Citation:** López de Prado, M. (2016). "Building Diversified Portfolios
that Outperform Out-of-Sample." *Journal of Portfolio Management*, 42(4),
59-69.

**Code:** `backend/app/optimizer/solvers.py::solve_hrp` constructs
`rp.HCPortfolio(returns=..., w_min=..., w_max=...)` and calls
`hc_port.optimization(model="HRP", codependence="pearson", rm=rm, rf=..., linkage="single")`.
Confirmed: `model="HRP"` is the three-stage López de Prado algorithm (as
opposed to `"HERC"`/`"NCO"`, riskfolio-lib's later variants);
`linkage="single"` is **single linkage**, which is the linkage López de
Prado's original paper uses; `codependence="pearson"` gives the
`d = √((1−ρ)/2)` correlation distance from the paper. `rm` is the
request's own risk measure, so the recursive-bisection step allocates
inverse-*selected-risk-measure* rather than strictly inverse-variance when
the user picks CVaR/CDaR/semi-variance — a generalization riskfolio-lib
offers beyond the paper's inverse-variance default (which is what
`rm="MV"`, the default risk measure, gives).

Two implementation notes: `w_min`/`w_max` (per-asset `pd.Series` from
`_asset_bounds`) are real `rp.HCPortfolio` constructor kwargs and are the
only constraint hook it has — `HCPortfolio` has no
`ainequality`/`binequality`, so `solve_hrp` validates group constraints
*after* solving against the identical rows `_build_portfolio` would have
fed in, raising `INFEASIBLE_CONSTRAINTS` on violation. And unlike the
mean-variance path, `solve_hrp` never receives `mu`/`sigma` at all — it
takes only `returns`, consistent with HRP not using expected returns.

## Risk Parity

**Formula:** weights such that each asset's marginal risk contribution is
equal: `wᵢ·(Σw)ᵢ = wⱼ·(Σw)ⱼ` for all i, j.

**Citation:** Maillard, S., Roncalli, T. & Teïletche, J. (2010). "The
Properties of Equally Weighted Risk Contribution Portfolios." *Journal of
Portfolio Management*, 36(4), 60-70.

**Code:** `backend/app/optimizer/solvers.py::solve_risk_parity` calls
`port.rp_optimization(model="Classic", rm=rm, rf=port.rf, b=None, hist=True)`
on the same `_build_portfolio` object. Confirmed a match: `b` is the risk
*budget* vector, and `b=None` makes riskfolio-lib use
`rb = ones(N,1)/N` (`Portfolio.py` line 3688-3690) — the equal-risk-
contribution budget, which is precisely the Maillard–Roncalli–Teïletche
ERC portfolio. riskfolio-lib's own docstring cites Roncalli for this
method; the risk-budgeting convex program it solves
(`min φ(w) − Σ bᵢ ln wᵢ`) is the standard log-barrier formulation whose
optimum satisfies the equal-marginal-contribution condition above. This
is a genuinely different algorithm from the mean-variance family, not an
inverse-volatility heuristic.

Caveat: with `rm` set to the request's risk measure, equalization is of
the *selected* risk measure's contributions; the cited paper's
`wᵢ(Σw)ᵢ` form is the `rm="MV"` case specifically. Also, the log-barrier
formulation is incompatible with hard `w ≥ lower` rows in general —
`_build_portfolio`'s `ainequality`/`binequality` are still attached here,
and `solve_risk_parity` (unlike `solve_mean_variance`) does **not**
post-validate the bounds, so a bound conflict would surface as a solver
failure (`SOLVER_NON_CONVERGENCE`) rather than `INFEASIBLE_CONSTRAINTS`.

## Risk Contribution %

**Formula:** `RCᵢ = wᵢ·(Σw)ᵢ / w'Σw`, the fraction of total portfolio
variance attributable to asset i. Sums to 100% across all holdings.

**Citation:** same as Risk Parity above (this is the underlying quantity
risk parity equalizes).

**Code:** `backend/app/optimizer/solvers.py::risk_contribution_pct` calls
`rp.RiskFunctions.Risk_Contribution(w, returns, cov=sigma/100/100, rm=..., rf=..., alpha=_tail_alpha(request))`,
then normalizes: `contributions[i] / contributions.sum() * 100`, rounded
to 2 dp.

What riskfolio-lib actually computes is **not** the closed form — it is a
central finite-difference of the risk function
(`RiskFunctions.py` lines 2552-2570): for each asset it perturbs
`w ± d_i` with `d_i = 1e-7` and returns
`wᵢ · (R(w+δᵢ) − R(w−δᵢ)) / (2 d_i)`, i.e. `wᵢ · ∂R/∂wᵢ` numerically. For
`rm="MV"` the risk function `R` it differentiates is `√(w'Σw)` (the
standard *deviation*), so the raw contribution is `wᵢ(Σw)ᵢ / √(w'Σw)`, not
`wᵢ(Σw)ᵢ / w'Σw`. **After the normalization by the sum, the two are
identical** — the `√(w'Σw)` factor cancels, and Euler's theorem on the
homogeneous-degree-1 risk function guarantees the parts sum to the whole.
So the reported percentages match the cited formula exactly for `MV`, up
to finite-difference precision, and generalize it to the other risk
measures (MSV/CVaR/CDaR) as Euler risk-contribution shares of the
selected measure. A degenerate (~zero total risk) portfolio falls back to
returning the weights themselves rather than dividing by ~0.

## Robust Optimization (Monte Carlo Resampling)

**Formula:** Michaud resampling — bootstrap-resample the return panel's
rows (with replacement) N times, re-solve the SAME objective on each
resample, average the resulting WEIGHTS across every resample that solved
successfully (not the mu/sigma inputs). Confirmed via live research
against PortfolioVisualizer's own "Robust Optimization: Yes/No" toggle
(see `docs/optimization-assumptions.md`) as the real-world technique this
matches — distinct from riskfolio-lib's own separate Worst-Case
mean-variance model, which this project does not use.

**Citation:** Michaud, R. O. (1989). "The Markowitz Optimization Enigma:
Is 'Optimized' Optimal?" *Financial Analysts Journal*, 45(1), 31-42.
Michaud, R. O. & Michaud, R. O. (2008). *Efficient Asset Management: A
Practical Guide to Stock Portfolio Optimization and Asset Allocation*
(2nd ed.), Oxford University Press — the full resampled-efficiency method.

**Code:** `backend/app/optimizer/robust.py::resample_and_solve`. All three
points confirmed:

- **Resample count is 500** — `RESAMPLE_COUNT = 500`, driving
  `for _ in range(RESAMPLE_COUNT)`. Each iteration draws
  `rng.integers(0, n_obs, size=n_obs)`, i.e. a full-length row bootstrap
  **with replacement**, from a fixed seed `RESAMPLE_SEED = 20260810` so
  the same request is byte-reproducible.
- **≥50% success threshold** — `MIN_SUCCESSFUL_FRACTION = 0.5`;
  `required = int(500 * 0.5) = 250`. Below that it falls back to a
  single-shot `solve_for_goal` on the **original** mu/sigma and returns an
  explanatory note, never a hard error. Per-resample solve failures
  (`ValueError`/`RuntimeError`) are skipped, not fatal.
- **Weights, not mu/sigma, are averaged** — each iteration recomputes
  `inputs.build_mu_sigma(request, resampled_returns)` and re-solves via
  `solvers.solve_for_goal`, accumulating the *solved weight dicts*; the
  average is `Σ weights / total_runs`, rounded to 4 dp, with the rounding
  residual placed on the largest holding so the total is exactly 100.
  Nothing averages the estimates themselves. This is Michaud's defining
  step.

One documented limitation carried in the module docstring:
`covariance_method="ewma"` depends on chronological row order, which the
bootstrap scrambles, so EWMA + robust optimization yields a covariance
estimate that no longer weights recent observations more heavily. Sample
and shrinkage covariance are unaffected.

## Verification Table

| Formula | Cited source matches code? | Notes |
| --- | --- | --- |
| Mean-Variance / Sharpe | **Yes** | `port.optimization(model="Classic", rm="MV", obj="Sharpe", rf=port.rf, l=0)`; `l=0` rules out the risk-aversion utility objective. μ/Σ assigned directly, not via `assets_stats()`. |
| Semi-Variance | **Yes, with two caveats** | `RM_CODES["semi_variance"] = "MSV"`. riskfolio-lib's `SemiDeviation` fixes the target at the sample mean `E[X]` (no MAR parameter exists or is passed), and minimizes the semi-*deviation* (square root). Argmin is unchanged by the monotone √; reported units differ and `realized_risk` correctly annualizes it as a deviation. |
| CVaR | **Yes** (`alpha` wiring was a defect, now fixed) | `RM_CODES["cvar"] = "CVaR"`; riskfolio-lib builds `VaR + 1/(αT)Σz` (`Portfolio.py:2246`) — the Rockafellar–Uryasev LP exactly. `Portfolio.optimization()` takes no `alpha` argument and reads `self.alpha` (default **0.05**), which `_build_portfolio` did not set — so the *solve* ignored `request.tailConfidence` and agreed with the reporting only at `tailConfidence = 95`. **Fixed 2026-08-11** by `port.alpha = _tail_alpha(request)` in `_build_portfolio` (`solvers.py:187`), the same helper `realized_risk`/`risk_contribution_pct` already used; regression tests in `backend/tests/test_optimizer_tail_alpha_regression.py`. See `docs/manual-verification-2026-08-11.md` Finding A. |
| CDaR | **Yes** (`alpha` wiring was a defect, now fixed) | `RM_CODES["cdar"] = "CDaR"`; `DaR + 1/(αT)Σz_d` (`Portfolio.py:2300`) is the Chekhlov–Uryasev–Zabarankin LP. Same unset-`port.alpha` defect as CVaR, fixed by the same one-line wiring on 2026-08-11. Also note riskfolio-lib defines it on *uncompounded* cumulative returns, unlike the backtest engine's compounded drawdown. |
| Black-Litterman posterior | **Yes for the math; the market portfolio and Ω are documented approximations** | `Π = δΣw_mkt` implemented literally; posterior is `[inv(τΣ) + P'Ω⁻¹P]⁻¹[inv(τΣ)π + P'Ω⁻¹Q]`, matching He & Litterman (the brief's formula string mis-typed `P'ΩP` for `P'Ω⁻¹P`; the code is the correct one). `risk_aversion` and `tau` are required schema fields (no defaults). `w_mkt` is equal-weighted, not market-cap (no cap data for Thai funds). Ω uses an Idzorek-*style* `(PτΣP')(1/conf − 1)` closed form, not Idzorek (2004)'s actual numerical back-solve. |
| HRP | **Yes** | `rp.HCPortfolio(...).optimization(model="HRP", codependence="pearson", linkage="single", rm=..., rf=...)` — single linkage and the `√((1−ρ)/2)` Pearson correlation distance are López de Prado's own choices. `rm` generalizes step 3 beyond inverse-variance when a non-MV risk measure is selected. Takes `returns` only, never μ/Σ. Group constraints are validated post-solve because `HCPortfolio` has no linear-constraint hook. |
| Risk Parity | **Yes** | `port.rp_optimization(model="Classic", rm=rm, rf=..., b=None)`; `b=None` → `rb = ones(N)/N` (`Portfolio.py:3688`), the equal-risk-contribution budget of Maillard–Roncalli–Teïletche. Solved via the standard log-barrier risk-budgeting program riskfolio-lib cites Roncalli for. The paper's `wᵢ(Σw)ᵢ` form is the `rm="MV"` case; other `rm` values equalize that measure's contributions instead. |
| Risk Contribution % | **Yes, via a numerically-equivalent route** | `rp.RiskFunctions.Risk_Contribution` is a finite-difference `wᵢ·∂R/∂wᵢ` (`d_i = 1e-7`, `RiskFunctions.py:2552-2570`), differentiating `√(w'Σw)` for MV — so raw values are `wᵢ(Σw)ᵢ/√(w'Σw)`. After `risk_contribution_pct`'s normalization by the sum, this is *identical* to the cited `wᵢ(Σw)ᵢ/w'Σw` (Euler's theorem), up to finite-difference precision. |
| Robust Optimization resampling | **Yes, all three points confirmed** | `RESAMPLE_COUNT = 500` full-length row bootstraps with replacement (fixed seed 20260810 for reproducibility); `MIN_SUCCESSFUL_FRACTION = 0.5` → needs ≥250 converged resamples or it falls back to a single-shot solve on the original μ/Σ with a note; and the averaging is over the solved **weight dicts**, not over μ/σ. Matches Michaud resampled efficiency. Known limitation: EWMA covariance is order-dependent and the bootstrap scrambles row order. |

### What could not be fully verified

- The **numerical solver path** inside riskfolio-lib is confirmed only at
  the CVXPY expression level (the LP/SOCP formulations quoted above are
  read directly from `Portfolio.py`). The subsequent CLARABEL interior-
  point solution and riskfolio-lib's internal fallback/rescaling
  (`k`-scaling for the Sharpe fractional program) were not audited
  line-by-line — the citation match rests on the objective/constraint
  expressions, which is where the cited formulas live.
- `HCPortfolio.optimization`'s recursive-bisection body was confirmed by
  its `model="HRP"` / `linkage` / `codependence` API contract and
  docstring, not by re-deriving its bisection loop against López de
  Prado's pseudocode.
- The `alpha`-wiring finding for CVaR/CDaR was a **defect in this
  project's code**, not in riskfolio-lib. It was reported here (this
  task being documentation-only) and subsequently **fixed** in Phase 4
  Task 4 — see `docs/manual-verification-2026-08-11.md`, Finding A.
- The `k`-rescaling path flagged above as unaudited turned out to contain
  a real, separate problem: riskfolio-lib's `obj="Sharpe"` falls back to a
  **degenerate** program when `(mu < 0).all()` (`Portfolio.py:3450-3461`),
  returning a dominated interior point instead of the true long-only
  optimum. Diagnosed but not fixed — it is a library-level limitation with
  no convex reformulation. See `docs/manual-verification-2026-08-11.md`,
  Finding B.
