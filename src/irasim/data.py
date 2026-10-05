"""Market data: bundled public datasets + optional live refresh -> monthly underlying returns.

Output columns (monthly, decimal returns, month-end index):
    spx   S&P 500 total return        ltt  20+yr Treasury total return (from yield)
    itt   7-10yr Treasury total ret.  gold gold spot
    trend illustrative trend-following proxy (NOT the real KMLM index)
    cash  T-bill return (also the financing rate)
    cpi   monthly CPI inflation

With live data (``irasim.live.refresh``): real T-bill rates (FRED TB3MS) and month-end S&P
prices (Yahoo ^GSPC). Without: a crude T-bill proxy and Shiller monthly-average prices; the
status dict says which, and the UI shows a banner.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "data" / "raw"
CACHE = ROOT / "user" / "cache"

LTT_YIELD_PREMIUM = 0.004   # 20y yield ~ 10y yield + 40bp (proxy)
LTT_DURATION, LTT_CONVEXITY = 16.5, 300.0
ITT_DURATION, ITT_CONVEXITY = 7.5, 70.0
ME = pd.offsets.MonthEnd(0)


def _month_end(idx) -> pd.DatetimeIndex:
    return pd.DatetimeIndex(pd.to_datetime(idx)) + ME


def _shiller() -> pd.DataFrame:
    df = pd.read_csv(RAW / "shiller_sp500.csv", parse_dates=["Date"])
    df.index = _month_end(df["Date"])
    # dividends are 0.0 after the last published value: carry the last yield forward
    dy = (df["Dividend"] / df["SP500"]).where(df["Dividend"] > 0).ffill()
    return pd.DataFrame({"price": df["SP500"], "dy": dy})


def _series_csv(name: str, date_col: str, val_col: str) -> pd.Series:
    df = pd.read_csv(RAW / name)
    s = pd.Series(df[val_col].values, index=_month_end(df[date_col].astype(str).str[:7] + "-01"))
    return s[~s.index.duplicated(keep="last")]


def _bond_return(y: pd.Series, duration: float, convexity: float) -> pd.Series:
    """Monthly total return of a constant-maturity bond from its yield series (decimal)."""
    dy = y.diff()
    return y.shift(1) / 12 - duration * dy + 0.5 * convexity * dy ** 2


TREND_HAIRCUT = 0.05  # annual; the raw proxy (~13%/yr) is far above published managed-futures results


def _trend_proxy(assets: pd.DataFrame, cash: pd.Series, target_vol=0.15, lookback=12,
                 haircut: float = TREND_HAIRCUT) -> pd.Series:
    """Illustrative time-series-momentum: 12m sign x vol-targeted position in each asset."""
    ex = assets.sub(cash, axis=0)
    sig = np.sign(ex.rolling(lookback).sum().shift(1))
    vol = ex.rolling(12).std().shift(1) * np.sqrt(12)
    pos = sig * (target_vol / vol).clip(upper=3.0)
    return cash + (pos * ex).mean(axis=1, skipna=False) - haircut / 12


def load_cached_live() -> dict:
    out = {}
    f = CACHE / "TB3MS.csv"
    if f.exists():
        df = pd.read_csv(f)
        out["tb3ms"] = pd.Series(df["value"].values, index=_month_end(df["date"]))
    f = CACHE / "gspc.csv"
    if f.exists():
        df = pd.read_csv(f)
        out["gspc"] = pd.Series(df["close"].values, index=_month_end(df["date"]))
    return out


def build(live: dict | None = None) -> tuple[pd.DataFrame, dict]:
    live = live or {}
    sh = _shiller()
    price = sh["price"]
    status = {"price_source": "Shiller monthly averages (understates volatility)",
              "cash_source": "CRUDE PROXY (10y yield - 1.5%): financing costs unreliable. "
                             "Run a live data refresh."}
    if "gspc" in live and len(live["gspc"]) > 24:
        price = live["gspc"].combine_first(price)
        status["price_source"] = "Yahoo ^GSPC month-end closes (1927+), Shiller before"
    spx = price.pct_change() + sh["dy"].shift(1).reindex(price.index).ffill() / 12

    y10 = _series_csv("y10_monthly.csv", "Date", "Rate") / 100
    if "tb3ms" in live and len(live["tb3ms"]) > 24:
        cash = (live["tb3ms"] / 100 / 12)
        status["cash_source"] = "FRED TB3MS (3-month T-bill), live"
        status["live"] = True
    else:
        cash = ((y10 - 0.015).clip(lower=0.0) / 12)
        status["live"] = False
    ltt = _bond_return(y10 + LTT_YIELD_PREMIUM, LTT_DURATION, LTT_CONVEXITY)
    itt = _bond_return(y10, ITT_DURATION, ITT_CONVEXITY)

    g = _series_csv("gold_monthly.csv", "Date", "Price")
    gold = g.pct_change()
    cpi_idx = _series_csv("cpi_monthly.csv", "Date", "Index")
    cpi = cpi_idx.pct_change()

    df = pd.DataFrame({"spx": spx, "ltt": ltt, "itt": itt, "gold": gold, "cash": cash, "cpi": cpi})
    df = df.dropna()
    df["trend"] = _trend_proxy(df[["spx", "ltt", "gold"]], df["cash"])
    df = df.dropna()
    status["start"] = str(df.index[0].date())
    status["end"] = str(df.index[-1].date())
    status["trend_source"] = "ILLUSTRATIVE PROXY (12m momentum on stocks/bonds/gold, minus a 5%/yr haircut so it lands near published trend results), not the KMLM index"
    return df, status


def load() -> tuple[pd.DataFrame, dict]:
    return build(load_cached_live())


def data_stamp() -> float:
    """Cache-busting key: newest mtime among cache files."""
    try:
        return max((p.stat().st_mtime for p in CACHE.glob("*.csv")), default=0.0)
    except OSError:
        return 0.0


def calibration(under: pd.DataFrame, funds: dict, tickers=("UPRO", "TMF", "UGL", "KMLM", "DBMF", "SSO")):
    """Synthetic vs actual fund monthly returns over their common history (needs live refresh)."""
    from .engine import fund_returns

    f = CACHE / "actuals.csv"
    if not f.exists():
        return None
    px = pd.read_csv(f, index_col=0, parse_dates=True)
    px.index = _month_end(px.index)
    rows = []
    for t in tickers:
        if t not in px.columns or t not in funds:
            continue
        act = px[t].pct_change().dropna()
        syn = fund_returns(under, funds[t], 12)
        j = pd.concat([act, syn], axis=1, keys=["act", "syn"]).dropna()
        if len(j) < 12:
            continue
        yrs = len(j) / 12
        rows.append(dict(
            fund=t, months=len(j),
            actual_cagr=(1 + j.act).prod() ** (1 / yrs) - 1,
            synthetic_cagr=(1 + j.syn).prod() ** (1 / yrs) - 1,
            actual_vol=j.act.std() * np.sqrt(12), synthetic_vol=j.syn.std() * np.sqrt(12),
            correlation=j.act.corr(j.syn), tracking_error=(j.act - j.syn).std() * np.sqrt(12)))
    return pd.DataFrame(rows).set_index("fund") if rows else None
