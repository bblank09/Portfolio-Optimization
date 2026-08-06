from typing import Any

import numpy as np
import pandas as pd

# Computed statistics never land on exactly 0.0: pct_change on float NAVs leaves
# last-bit residue (a constant +10% series yields a std of ~1e-16). Guarding
# ratio denominators with `== 0` therefore never fires and the ratio explodes to
# ~1e15. Anything below this tolerance is economically indistinguishable from
# zero, so treat it as degenerate.
DEGENERACY_TOLERANCE = 1e-12


def annualized_return(returns: pd.Series, periods_per_year: int) -> float:
    clean = returns.dropna()
    if clean.empty:
        return 0.0
    years = len(clean) / periods_per_year
    clean_values = clean.to_numpy(dtype=float)
    total_return = float(np.prod(1.0 + clean_values))
    return total_return ** (1 / years) - 1


def annualized_volatility(returns: pd.Series, periods_per_year: int) -> float:
    clean = returns.dropna()
    # ddof=1 (Bessel) is the unbiased sample estimator and matches the ddof used
    # by cov/var in beta_alpha, so Sharpe and beta rest on the same statistics.
    if len(clean) < 2:
        return 0.0
    return float(clean.std(ddof=1) * np.sqrt(periods_per_year))


def downside_deviation(returns: pd.Series, periods_per_year: int, minimum_acceptable_return: float = 0.0) -> float:
    clean = returns.dropna()
    downside = np.minimum(clean - minimum_acceptable_return, 0)
    return float(np.sqrt(np.mean(np.square(downside))) * np.sqrt(periods_per_year))


def sharpe_ratio(returns: pd.Series, risk_free_rate: float, periods_per_year: int) -> float | None:
    volatility = annualized_volatility(returns, periods_per_year)
    if volatility <= DEGENERACY_TOLERANCE:
        return None
    return float((annualized_return(returns, periods_per_year) - risk_free_rate) / volatility)


def sortino_ratio(returns: pd.Series, risk_free_rate: float, periods_per_year: int) -> float | None:
    downside = downside_deviation(returns, periods_per_year)
    if downside <= DEGENERACY_TOLERANCE:
        return None
    return float((annualized_return(returns, periods_per_year) - risk_free_rate) / downside)


def max_drawdown(values: pd.Series) -> float:
    clean = values.dropna()
    if clean.empty:
        return 0.0
    return float((clean / clean.cummax() - 1).min())


def drawdown_series(values: pd.Series) -> pd.Series:
    clean = values.dropna()
    return clean / clean.cummax() - 1


def rolling_correlation(asset_returns: pd.DataFrame, window: int) -> list[dict[str, Any]]:
    """Rolling Pearson correlation for every unordered pair of held assets.

    The static end-of-run correlation matrix (diversification_table) hides
    regime changes -- two funds can average a low correlation over years while
    having moved in lockstep during the exact period that mattered. A rolling
    window surfaces that. Returns one row per (pair, date) once the window is
    full; correlation against a zero-variance window is undefined (0/0 -> NaN)
    and reported as None rather than leaking a NaN float.
    """
    columns = list(asset_returns.columns)
    rows: list[dict[str, Any]] = []
    for left_index, left in enumerate(columns):
        for right in columns[left_index + 1 :]:
            series = asset_returns[left].rolling(window).corr(asset_returns[right]).dropna()
            for index, value in series.items():
                rows.append(
                    {
                        "date": index,
                        "asset_a": left,
                        "asset_b": right,
                        "correlation": float(value) if np.isfinite(value) else None,
                    }
                )
    return rows


def historical_var(returns: pd.Series, confidence: float, min_observations: int = 3) -> float | None:
    """Historical (non-parametric) Value at Risk, as a positive loss magnitude.

    The (1 - confidence) percentile of observed period returns is the largest
    loss expected `confidence` of the time (e.g. 95% VaR = 3% means no more
    than a 3% loss is expected in 95% of periods). Requires at least
    `min_observations` clean returns for the percentile to be meaningful.
    """
    clean = returns.dropna()
    if len(clean) < min_observations:
        return None
    percentile = float(np.percentile(clean.to_numpy(dtype=float), (1 - confidence) * 100))
    return max(0.0, -percentile)


def calmar_ratio(returns: pd.Series, values: pd.Series, periods_per_year: int) -> float | None:
    drawdown = abs(max_drawdown(values))
    if drawdown <= DEGENERACY_TOLERANCE:
        return None
    return float(annualized_return(returns, periods_per_year) / drawdown)


def beta_alpha(
    portfolio: pd.Series,
    benchmark: pd.Series,
    risk_free_rate: float,
    periods_per_year: int,
) -> tuple[float, float]:
    aligned = pd.concat([portfolio, benchmark], axis=1).dropna()
    aligned.columns = ["portfolio", "benchmark"]
    variance = aligned["benchmark"].var(ddof=1)
    degenerate = not np.isfinite(variance) or variance <= DEGENERACY_TOLERANCE
    beta = 0.0 if degenerate else float(aligned["portfolio"].cov(aligned["benchmark"]) / variance)
    port_cagr = annualized_return(aligned["portfolio"], periods_per_year)
    bench_cagr = annualized_return(aligned["benchmark"], periods_per_year)
    alpha = port_cagr - (risk_free_rate + beta * (bench_cagr - risk_free_rate))
    return beta, float(alpha)


def tracking_error(portfolio: pd.Series, benchmark: pd.Series, periods_per_year: int) -> float:
    aligned = pd.concat([portfolio, benchmark], axis=1).dropna()
    if len(aligned) < 2:
        return 0.0
    active_returns = aligned.iloc[:, 0] - aligned.iloc[:, 1]
    return float(active_returns.std(ddof=1) * np.sqrt(periods_per_year))


def information_ratio(portfolio: pd.Series, benchmark: pd.Series, periods_per_year: int) -> float | None:
    te = tracking_error(portfolio, benchmark, periods_per_year)
    if te <= DEGENERACY_TOLERANCE:
        return None
    active_return = annualized_return(portfolio, periods_per_year) - annualized_return(benchmark, periods_per_year)
    return float(active_return / te)


def correlation(portfolio: pd.Series, benchmark: pd.Series) -> float | None:
    aligned = pd.concat([portfolio, benchmark], axis=1).dropna()
    if len(aligned) < 2:
        return None
    # Correlation divides by each series' standard deviation, so it is
    # undefined (0/0 -> NaN) when either side has no variance.
    value = float(aligned.iloc[:, 0].corr(aligned.iloc[:, 1]))
    return None if not np.isfinite(value) else value
