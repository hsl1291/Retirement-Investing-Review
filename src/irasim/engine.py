"""Backtest engine: fund return synthesis, rebalancing, metrics.

Works on any periodicity (daily or monthly) given ``periods_per_year``.

Leveraged daily-reset funds:
  * with DAILY underlying data the fund return is computed exactly:
        r_f = sum_k L_k r_k - (gross - 1)(cash + spread)/ppy - ER/ppy
  * with MONTHLY data, daily compounding is approximated by subtracting the
    volatility-decay term  (L^2 - L)/2 * sigma^2_month, where the intramonth
    variance is estimated from an EWMA of monthly returns. That is the
    standard continuous-time result for a daily-rebalanced leveraged position.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from .funds import FUNDS, Fund


def fund_returns(under: pd.DataFrame, fund: Fund, periods_per_year: int,
                 ewma_halflife: int = 12) -> pd.Series:
    cash = under["cash"]
    lev = fund.gross
    borrow = max(0.0, lev - 1.0)
    fin = cash + fund.spread / periods_per_year
    if fund.daily_reset and periods_per_year < 200:
        # Daily-reset product on coarse data: log V = L log(1+r) - (L^2-L)/2 * var - (L-1) log(1+f).
        # (Plain L*r would only capture the decay from the coarse period's own squared return.)
        assert len(fund.exposures) == 1, "daily-reset synthesis supports one underlying"
        (u, L), = fund.exposures.items()
        x = under[u]
        # Intramonth variance proxy: EWMA of past squared returns minus the squared long-run
        # mean (drift inflates m^2 but not the sum of daily r^2). Avoids small-sample EWM-var bias.
        mu2 = x.expanding().mean().shift(1).fillna(x.mean()) ** 2
        var = ((x * x).ewm(halflife=ewma_halflife).mean().shift(1).fillna((x * x).mean()) - mu2).clip(lower=0)
        r = (1 + x) ** L * np.exp(-(L * L - L) / 2.0 * var) / (1 + fin) ** borrow - 1
    else:
        r = sum(L * under[u] for u, L in fund.exposures.items()) - borrow * fin
    return r - fund.expense_ratio / periods_per_year


def build_fund_returns(under: pd.DataFrame, tickers, periods_per_year: int,
                       funds: dict | None = None) -> pd.DataFrame:
    funds = funds or FUNDS
    return pd.DataFrame({t: fund_returns(under, funds[t], periods_per_year) for t in tickers})


@dataclass
class Rebalance:
    kind: str = "calendar"          # calendar | band | none
    every: int = 3                   # periods between calendar rebalances (3 = quarterly on monthly data)
    abs_band: float = 0.05           # band: rebalance if |w - target| > abs_band ...
    rel_band: float = 0.25           # ... or |w/target - 1| > rel_band
    cost_bps: float = 5.0            # cost per unit of traded notional


def run_backtest(rets: np.ndarray, weights: np.ndarray, reb: Rebalance,
                 start_value: float = 1.0, flows: np.ndarray | None = None) -> np.ndarray:
    """Vectorised over paths.

    rets: (n_paths, n_periods, n_assets) or (n_periods, n_assets)
    flows: optional (n_periods,) cash added at the start of each period (allocated at target)
    returns: wealth (n_paths, n_periods + 1)
    """
    single = rets.ndim == 2
    if single:
        rets = rets[None]
    n_paths, T, n = rets.shape
    w = np.asarray(weights, float)
    hold = np.tile(w * start_value, (n_paths, 1))
    wealth = np.empty((n_paths, T + 1))
    wealth[:, 0] = start_value
    cost = reb.cost_bps / 1e4
    for t in range(T):
        if flows is not None and flows[t]:
            hold += w * flows[t]
        hold *= 1.0 + rets[:, t, :]
        hold = np.maximum(hold, 0.0)  # a leveraged sleeve cannot go below zero
        total = hold.sum(1)
        if reb.kind != "none":
            if reb.kind == "calendar":
                do = np.full(n_paths, (t + 1) % reb.every == 0)
            else:
                cw = hold / np.maximum(total[:, None], 1e-12)
                dev = np.abs(cw - w)
                rel = dev / np.where(w > 0, w, np.inf)
                do = ((dev > reb.abs_band) | (rel > reb.rel_band)).any(1)
            if do.any():
                target = total[:, None] * w
                traded = np.abs(target - hold).sum(1) * cost
                total_after = total - traded
                hold = np.where(do[:, None], total_after[:, None] * w, hold)
        wealth[:, t + 1] = hold.sum(1)
    return wealth[0] if single else wealth


def metrics(wealth: np.ndarray, periods_per_year: int) -> dict:
    """Metrics for a single wealth path (1-D)."""
    w = np.asarray(wealth, float)
    r = w[1:] / w[:-1] - 1
    yrs = len(r) / periods_per_year
    cagr = (w[-1] / w[0]) ** (1 / yrs) - 1 if w[-1] > 0 else -1.0
    peak = np.maximum.accumulate(w)
    dd = w / peak - 1
    ulcer = np.sqrt(np.mean(dd ** 2))
    vol = r.std() * np.sqrt(periods_per_year)
    down = r[r < 0]
    sortino = (r.mean() * periods_per_year) / (down.std() * np.sqrt(periods_per_year)) if len(down) > 1 else np.nan
    # longest time underwater, in years
    uw, longest = 0, 0
    for x in dd:
        uw = uw + 1 if x < 0 else 0
        longest = max(longest, uw)
    win = 10 * periods_per_year
    worst10 = (np.min(w[win:] / w[:-win]) ** (1 / 10) - 1) if len(w) > win else np.nan
    return dict(cagr=cagr, vol=vol, max_dd=dd.min(), ulcer=ulcer, sortino=sortino,
                longest_underwater_yrs=longest / periods_per_year, worst_10y_cagr=worst10,
                terminal_multiple=w[-1] / w[0])
