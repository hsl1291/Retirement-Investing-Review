"""Streamlit helpers shared by all pages: data caching, sidebar portfolio, chart styling."""
from __future__ import annotations

import json
import sys
from dataclasses import replace
from pathlib import Path

import numpy as np
import pandas as pd
import streamlit as st

from . import data
from .engine import Rebalance, build_fund_returns
from .funds import CURRENT_PORTFOLIO, FUNDS

ROOT = Path(__file__).resolve().parents[2]
PROFILE = ROOT / "user" / "profile.json"
VERSION = (ROOT / "VERSION").read_text().strip() if (ROOT / "VERSION").exists() else "dev"

# validated reference palette (dataviz skill): categorical order is fixed, never cycled
SERIES = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#4a3aa7", "#e34948"]
SURFACE, INK, INK2, GRID = "#fcfcfb", "#0b0b0b", "#52514e", "#e6e5e1"

REBAL = {
    "Monthly": ("calendar", 1), "Quarterly": ("calendar", 3), "Semiannual": ("calendar", 6),
    "Annual": ("calendar", 12), "5/25 bands (checked monthly)": ("band", 1),
    "Never (buy & hold)": ("none", 1),
}


def setup(title: str):
    st.set_page_config(page_title=f"{title} · Long Haul", page_icon="📈", layout="wide")
    st.title(title)


def money(x: float) -> str:
    a = abs(x)
    if a >= 1e9:
        return f"${x/1e9:,.2f}B"
    if a >= 1e6:
        return f"${x/1e6:,.2f}M"
    return f"${x/1e3:,.0f}k"


def pct(x: float, d: int = 1) -> str:
    return f"{x*100:.{d}f}%"


# ---------------------------------------------------------------- data
@st.cache_data(show_spinner="Loading market data…")
def load_data(stamp: float):
    return data.load()


def get_data():
    return load_data(data.data_stamp())


def data_banner(status: dict):
    if not status.get("live"):
        st.warning(
            "**Offline data mode.** T-bill rates are a crude proxy, so leverage financing costs "
            "are unreliable, and S&P prices are monthly averages (understates volatility, which "
            "flatters leveraged funds). Run **Data & Updates → Refresh live data** for real numbers.")
    st.caption(f"Trend sleeve: {status['trend_source']}")


@st.cache_data(show_spinner=False)
def fund_frame(tickers: tuple, spread: float | None, stamp: float, start: str, bond_haircut: float = 0.0):
    """Monthly fund returns + cpi. bond_haircut (decimal/yr) is subtracted from Treasury returns
    to model 'the 1982-2020 fall in yields does not repeat'."""
    under, _ = load_data(stamp)
    if bond_haircut:
        under = under.copy()
        under["ltt"] -= bond_haircut / 12
        under["itt"] -= bond_haircut / 12
    funds = FUNDS if spread is None else {k: replace(v, spread=spread) for k, v in FUNDS.items()}
    fr = build_fund_returns(under, list(tickers), 12, funds)
    fr["cpi"] = under["cpi"]
    return fr.loc[start:].dropna()


# ---------------------------------------------------------------- profile
def load_profile() -> dict:
    try:
        return json.loads(PROFILE.read_text())
    except (OSError, ValueError):
        return {}


def save_profile(d: dict) -> None:
    PROFILE.parent.mkdir(exist_ok=True)
    PROFILE.write_text(json.dumps(d, indent=2))


def portfolio_sidebar(with_start=True) -> dict:
    """Portfolio editor shared by every page (state survives page switches)."""
    prof = st.session_state.get("portfolio") or load_profile().get("portfolio") or {
        "weights": dict(CURRENT_PORTFOLIO), "rebalance": "Quarterly", "cost_bps": 5.0,
        "start_value": 806_000.0, "spread": None, "bond_haircut": 0.0}
    sb = st.sidebar
    sb.header("Portfolio")
    tickers = sb.multiselect("Funds", list(FUNDS), default=list(prof["weights"]))
    weights = {}
    for t in tickers:
        weights[t] = sb.number_input(f"{t} %", 0.0, 100.0, float(prof["weights"].get(t, 0.0) * 100),
                                     step=5.0) / 100
    tot = sum(weights.values())
    if not tickers:
        sb.error("Pick at least one fund.")
        st.stop()
    if abs(tot - 1) > 1e-6:
        sb.warning(f"Weights sum to {tot*100:.0f}%. They will be normalized.")
    names = list(REBAL)
    reb_name = sb.selectbox("Rebalance", names, index=names.index(prof["rebalance"]))
    cost = sb.number_input("Trading cost (bps per $ traded)", 0.0, 100.0, float(prof["cost_bps"]), step=1.0)
    start = prof["start_value"]
    if with_start:
        start = sb.number_input("Starting balance ($)", 0.0, 1e9, float(prof["start_value"]), step=10_000.0)
    spread = sb.number_input("Financing spread over T-bills (%/yr)", 0.0, 3.0,
                             float((prof["spread"] if prof["spread"] is not None else 0.005) * 100),
                             step=0.1) / 100
    hc = sb.number_input("Bond return haircut for forecasts (%/yr)", 0.0, 6.0,
                         float(prof.get("bond_haircut", 0.0) * 100), step=0.5,
                         help="Applies to Monte Carlo / Optimizer / Taxes, not the historical Backtest. "
                              "Treasuries gained roughly 3-4%/yr from falling yields in 1982-2020; "
                              "2-3 here asks 'what if that tailwind doesn't repeat?'") / 100
    out = {"weights": {t: w / tot for t, w in weights.items()}, "rebalance": reb_name,
           "cost_bps": cost, "start_value": start, "spread": spread, "bond_haircut": hc}
    st.session_state["portfolio"] = out
    if sb.button("Save as my default"):
        save_profile({**load_profile(), "portfolio": out})
        sb.success("Saved to user/profile.json")
    return out


def rebalance_from(pf: dict) -> Rebalance:
    kind, every = REBAL[pf["rebalance"]]
    return Rebalance(kind, every, cost_bps=pf["cost_bps"])


# ---------------------------------------------------------------- charts
def style(fig, height=420, logy=False, yfmt=None):
    fig.update_layout(
        template=None, paper_bgcolor=SURFACE, plot_bgcolor=SURFACE, height=height,
        font=dict(color=INK2, size=13), hovermode="x unified",
        legend=dict(orientation="h", y=-0.18, x=0, font=dict(color=INK)),
        margin=dict(l=10, r=10, t=30, b=10))
    fig.update_xaxes(showgrid=False, linecolor=GRID, tickcolor=GRID)
    fig.update_yaxes(gridcolor=GRID, zeroline=False, automargin=True, type="log" if logy else "linear",
                     tickformat=yfmt)
    return fig


def show(fig):
    st.plotly_chart(fig, theme=None, width="stretch")
