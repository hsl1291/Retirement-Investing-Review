"""Forward simulation (stationary block bootstrap) and portfolio optimization.

All candidate portfolios are evaluated on the SAME bootstrapped paths (common
random numbers), so differences between them are not sampling noise.
"""
from __future__ import annotations

import itertools

import numpy as np
import pandas as pd

from .engine import Rebalance, run_backtest


def block_bootstrap(rows: np.ndarray, n_paths: int, horizon: int, mean_block: int = 24,
                    seed: int = 0) -> np.ndarray:
    """Politis-Romano stationary bootstrap over time rows.

    rows: (T, k) historical joint returns. Returns (n_paths, horizon, k).
    """
    rng = np.random.default_rng(seed)
    T = rows.shape[0]
    idx = np.empty((n_paths, horizon), dtype=int)
    idx[:, 0] = rng.integers(0, T, n_paths)
    p = 1.0 / mean_block
    for t in range(1, horizon):
        jump = rng.random(n_paths) < p
        idx[:, t] = np.where(jump, rng.integers(0, T, n_paths), (idx[:, t - 1] + 1) % T)
    return rows[idx]


def summarize_terminal(wealth: np.ndarray, start: float, real_benchmark: np.ndarray | None = None) -> dict:
    term = wealth[:, -1]
    peak = np.maximum.accumulate(wealth, axis=1)
    mdd = (wealth / peak - 1).min(1)
    out = dict(
        mean=term.mean(), median=np.median(term),
        p05=np.percentile(term, 5), p10=np.percentile(term, 10), p25=np.percentile(term, 25),
        p75=np.percentile(term, 75), p90=np.percentile(term, 90),
        mean_log=np.mean(np.log(np.maximum(term, 1e-9) / start)),
        p_loss=np.mean(term < start),
        p_dd_over_80=np.mean(mdd < -0.80),
        median_max_dd=np.median(mdd),
    )
    if real_benchmark is not None:
        out["p_beat_benchmark"] = np.mean(term > real_benchmark[:, -1])
    return out


OBJECTIVES = {
    # Long-horizon median ~ exp(horizon * mean log return): maximizing mean_log is Kelly
    "median": lambda s: s["median"],
    "kelly": lambda s: s["mean_log"],
    "p10": lambda s: s["p10"],
    "mean": lambda s: s["mean"],  # shown for contrast; rewards ruinous leverage
}


def simplex_grid(n_assets: int, step: float, bounds=None):
    k = int(round(1 / step))
    for combo in itertools.product(range(k + 1), repeat=n_assets - 1):
        s = sum(combo)
        if s > k:
            continue
        w = np.array(list(combo) + [k - s]) * step
        if bounds is not None and any(not (lo - 1e-9 <= x <= hi + 1e-9) for x, (lo, hi) in zip(w, bounds)):
            continue
        yield w


def optimize(paths: np.ndarray, tickers, step: float = 0.05, reb: Rebalance | None = None,
             objective: str = "median", max_p_dd80: float | None = None, bounds=None,
             start: float = 1.0, flows=None, top: int = 10, deflator: np.ndarray | None = None,
             progress=None):
    """Grid search over weights on bootstrapped fund-return paths (n_paths, T, n_assets).

    deflator (n_paths, T+1) converts nominal wealth to real before scoring.
    progress(i, n) is called after each candidate.
    """
    reb = reb or Rebalance()
    grid = list(simplex_grid(len(tickers), step, bounds))
    results = []
    for i, w in enumerate(grid):
        wealth = run_backtest(paths, w, reb, start_value=start, flows=flows)
        if deflator is not None:
            wealth = wealth / deflator
        s = summarize_terminal(wealth, start)
        if progress:
            progress(i + 1, len(grid))
        if max_p_dd80 is not None and s["p_dd_over_80"] > max_p_dd80:
            continue
        results.append((OBJECTIVES[objective](s), dict(zip(tickers, np.round(w, 3))), s))
    results.sort(key=lambda x: -x[0])
    return results[:top]


def simulate_portfolio(fund_rets: pd.DataFrame, weights: dict, reb: Rebalance, n_paths: int,
                       years: int, mean_block: int = 24, start: float = 1.0, seed: int = 0) -> dict:
    """Bootstrap joint monthly fund returns + CPI and run one portfolio.

    fund_rets must contain a 'cpi' column plus one column per fund. Returns nominal and real
    wealth (n_paths, months+1), the deflator, and annual real returns (n_paths, years).
    """
    tick = [c for c in fund_rets.columns if c != "cpi"]
    rows = fund_rets[tick + ["cpi"]].values
    months = years * 12
    paths = block_bootstrap(rows, n_paths, months, mean_block, seed)
    w = np.array([weights.get(t, 0.0) for t in tick], float)
    w = w / w.sum()
    wealth = run_backtest(paths[:, :, :-1], w, reb, start_value=start)
    defl = np.concatenate([np.ones((n_paths, 1)), np.cumprod(1 + paths[:, :, -1], axis=1)], axis=1)
    real = wealth / defl
    ys = real[:, ::12]
    return dict(wealth=wealth, real=real, deflator=defl, annual_real=ys[:, 1:] / ys[:, :-1] - 1,
                tickers=tick)
