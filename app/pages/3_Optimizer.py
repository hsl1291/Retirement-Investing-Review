import _shim  # noqa: F401
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from irasim import data, ui
from irasim.engine import run_backtest
from irasim.funds import FUNDS
from irasim.montecarlo import OBJECTIVES, block_bootstrap, optimize, summarize_terminal

ui.setup("Optimizer")
under, status = ui.get_data()
ui.data_banner(status)
pf = ui.portfolio_sidebar()

st.markdown(
    "Searches mixes on the **same** bootstrapped paths and scores them on **real** (inflation-adjusted) "
    "terminal wealth. Pick what 'best' means: the *median* (typical outcome) and the *10th percentile* "
    "(bad luck) are the honest targets; *mean* is shown for contrast and rewards ruinous leverage.")

c1, c2, c3 = st.columns(3)
universe = c1.multiselect("Funds to consider", list(FUNDS), default=list(pf["weights"]) or ["UPRO"])
step = c2.select_slider("Weight step", [0.25, 0.2, 0.1, 0.05], 0.1)
objective = c3.selectbox("Optimize for", list(OBJECTIVES), index=0,
                         format_func=lambda k: {"median": "Median real wealth", "kelly": "Mean log wealth (Kelly)",
                                                "p10": "10th-percentile real wealth", "mean": "Mean (contrast only)"}[k])
c4, c5, c6, c7 = st.columns(4)
years = c4.number_input("Years to retirement", 5, 50, 34)
n_paths = c5.select_slider("Paths", [100, 200, 300, 500], 200)
dd_cap = c6.slider("Max P(drawdown > 80%)", 0, 100, 100, help="100 = no constraint") / 100
max_w = c7.slider("Max weight in any one fund (%)", 10, 100, 100) / 100
pool_start = st.slider("Resample history from year", 1955, 2010, 1972)

if len(universe) < 2:
    st.info("Choose at least two funds.")
    st.stop()

tick = tuple(sorted(set(universe) | set(pf["weights"])))
fr = ui.fund_frame(tick, pf["spread"], data.data_stamp(), f"{pool_start}-01-01", pf["bond_haircut"])
months = int(years) * 12
reb = ui.rebalance_from(pf)
start = pf["start_value"]

rows = fr[list(tick) + ["cpi"]].values
paths = block_bootstrap(rows, n_paths, months, 24, seed=1)
rets = paths[:, :, :-1]
defl = np.concatenate([np.ones((n_paths, 1)), np.cumprod(1 + paths[:, :, -1], axis=1)], axis=1)
ix = [tick.index(t) for t in universe]
sub = rets[:, :, ix]


def fmt_row(w, s):
    return {**{t: f"{w.get(t,0)*100:.0f}%" for t in universe}, "Median": ui.money(s["median"]),
            "10th pct": ui.money(s["p10"]), "Mean": ui.money(s["mean"]),
            "P(DD>80%)": ui.pct(s["p_dd_over_80"], 0), "P(< start)": ui.pct(s["p_loss"], 0)}


cur_w = np.array([pf["weights"].get(t, 0.0) for t in universe])
cur_w = cur_w / cur_w.sum() if cur_w.sum() else cur_w
cur = summarize_terminal(run_backtest(sub, cur_w, reb, start) / defl, start)

if st.button("Run optimizer", type="primary"):
    bar = st.progress(0.0, "Searching…")
    res = optimize(sub, universe, step, reb, objective, dd_cap if dd_cap < 1 else None,
                   bounds=[(0, max_w)] * len(universe), start=start, deflator=defl, top=10,
                   progress=lambda i, n: bar.progress(i / n, f"Searching… {i}/{n}"))
    bar.empty()
    if not res:
        st.warning("No mix satisfied the constraints. Relax the drawdown cap or the max weight.")
    else:
        table = {"Your current mix": fmt_row({t: pf['weights'].get(t, 0) for t in universe}, cur)}
        for k, (_, w, s) in enumerate(res):
            table[f"#{k+1}"] = fmt_row(w, s)
        st.subheader("Top mixes")
        st.dataframe(pd.DataFrame(table).T, width="stretch")
        st.caption("Real (today's) dollars at retirement. Differences between neighbouring rows are within "
                   "simulation noise; look for the *region* the winners share, not the single best row.")

st.subheader("Leverage sweep")
eq = st.selectbox("Equity fund to dial", universe, index=0)
others = [t for t in universe if t != eq]
if others:
    base = np.array([pf["weights"].get(t, 0.0) for t in others])
    base = base / base.sum() if base.sum() else np.ones(len(others)) / len(others)
    xs = np.arange(0, 101, 5) / 100
    med, p10, p90, mean = [], [], [], []
    for a in xs:
        w = np.zeros(len(universe))
        w[universe.index(eq)] = a
        for t, b in zip(others, base):
            w[universe.index(t)] = (1 - a) * b
        s = summarize_terminal(run_backtest(sub, w, reb, start) / defl, start)
        med.append(s["median"]); p10.append(s["p10"]); p90.append(s["p90"]); mean.append(s["mean"])
    fig = go.Figure()
    for i, (n, y) in enumerate({"Median": med, "10th percentile": p10, "90th percentile": p90, "Mean": mean}.items()):
        fig.add_scatter(x=xs, y=y, name=n, line=dict(color=ui.SERIES[i], width=2), hovertemplate="%{y:$,.0f}")
    fig.update_xaxes(title=f"Weight in {eq}", tickformat=".0%")
    ui.show(ui.style(fig, logy=True, yfmt="$,.0f"))
    st.caption(f"Remaining weight is split across {', '.join(others)} in your current proportions. "
               "Where the *median* line peaks is the growth-optimal equity weight on these paths; "
               "beyond it, extra leverage only helps the mean and the 90th percentile.")
