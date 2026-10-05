import _shim  # noqa: F401
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from irasim import data, ui
from irasim.montecarlo import simulate_portfolio, summarize_terminal

ui.setup("Monte Carlo to retirement")
under, status = ui.get_data()
ui.data_banner(status)
pf = ui.portfolio_sidebar()

c1, c2, c3, c4 = st.columns(4)
age = c1.number_input("Your age now", 18, 69, 36)
ret_age = c2.number_input("Retirement age", 50, 80, 70)
paths = c3.select_slider("Simulated paths", [200, 500, 1000, 2000], 500)
block = c4.slider("Mean block length (months)", 6, 60, 24,
                  help="Longer blocks preserve more of the history's volatility clustering and "
                       "multi-year regimes (e.g. 2000-02, 2022).")
pool_start = st.slider("Resample history from year", 1955, 2010, 1972)
years = int(ret_age - age)

tick = sorted(set(pf["weights"]) | {"VOO"})
fr = ui.fund_frame(tuple(tick), pf["spread"], data.data_stamp(), f"{pool_start}-01-01", pf["bond_haircut"])


@st.cache_data(show_spinner="Simulating…")
def sim(weights: tuple, reb_name: str, cost: float, start_value: float, years: int, n: int, block: int, fr_key):
    reb = ui.rebalance_from({"rebalance": reb_name, "cost_bps": cost})
    fr_ = ui.fund_frame(*fr_key)
    mine = simulate_portfolio(fr_, dict(weights), reb, n, years, block, start_value)
    voo = simulate_portfolio(fr_, {"VOO": 1.0}, ui.rebalance_from({"rebalance": "Never (buy & hold)", "cost_bps": 0}),
                             n, years, block, start_value)  # same seed -> same paths (common random numbers)
    return mine, voo


key = (tuple(tick), pf["spread"], data.data_stamp(), f"{pool_start}-01-01", pf["bond_haircut"])
mine, voo = sim(tuple(pf["weights"].items()), pf["rebalance"], pf["cost_bps"], pf["start_value"], years,
                paths, block, key)
st.session_state["mc_annual_real"] = mine["annual_real"]
st.caption(f"{len(fr)} months of history in the pool ({fr.index[0].date()} to {fr.index[-1].date()}); "
           f"{paths} paths x {years} years. All results in today's dollars unless noted.")

x = np.arange(years * 12 + 1) / 12 + age
fig = go.Figure()
for i, (name, d) in enumerate({"Your portfolio": mine, "100% S&P 500": voo}.items()):
    col = ui.SERIES[i]
    q = np.percentile(d["real"], [10, 25, 50, 75, 90], axis=0)
    fig.add_scatter(x=x, y=q[0], line=dict(width=0), showlegend=False, hoverinfo="skip")
    fig.add_scatter(x=x, y=q[4], line=dict(width=0), fill="tonexty", showlegend=False, hoverinfo="skip",
                    fillcolor="rgba(42,120,214,.12)" if i == 0 else "rgba(235,104,52,.12)")
    fig.add_scatter(x=x, y=q[2], name=f"{name}: median (band = 10th-90th pct)", line=dict(color=col, width=2),
                    hovertemplate="%{y:$,.0f}")
fig.add_hline(y=pf["start_value"], line=dict(color=ui.INK2, dash="dot", width=1))
ui.show(ui.style(fig, logy=True, yfmt="$,.0f", height=460))

st.subheader(f"Outcome at age {ret_age}")
rows = {}
for name, d in {"Your portfolio": mine, "100% S&P 500": voo}.items():
    s = summarize_terminal(d["real"], pf["start_value"])
    rows[name] = {"Mean": ui.money(s["mean"]), "Median": ui.money(s["median"]), "10th pct": ui.money(s["p10"]),
                  "25th pct": ui.money(s["p25"]), "75th pct": ui.money(s["p75"]), "90th pct": ui.money(s["p90"]),
                  "P(ends below start, real)": ui.pct(s["p_loss"]), "P(drawdown > 80%)": ui.pct(s["p_dd_over_80"]),
                  "Median worst drawdown": ui.pct(s["median_max_dd"], 0)}
rows["Your portfolio"]["P(beats S&P 500)"] = ui.pct(
    float(np.mean(mine["real"][:, -1] > voo["real"][:, -1])))
st.dataframe(pd.DataFrame(rows).T, width="stretch")

st.markdown(
    "**How to read this:** compare *Mean* with *Median*. A large gap means the average is carried by a "
    "few extreme paths. A leveraged portfolio's typical outcome is the median, and the 10th percentile "
    "is what a bad-luck retiree gets. The bootstrap only knows the history it samples, so a regime "
    "that has not happened (e.g. 1970s-style inflation with 2020s leverage costs) is not represented.")
