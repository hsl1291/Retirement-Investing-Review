import _shim  # noqa: F401
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from irasim import data, ui
from irasim.engine import Rebalance, metrics, run_backtest

ui.setup("Backtest")
under, status = ui.get_data()
ui.data_banner(status)
pf = ui.portfolio_sidebar()

STRESS = {"1973-74 stagflation": ("1973-01", "1974-12"), "2000-02 dot-com": ("2000-03", "2002-09"),
          "2008 crisis": ("2007-11", "2009-02"), "2020 COVID": ("2020-02", "2020-03"),
          "2022 stocks+bonds": ("2022-01", "2022-12")}

first = max(under.index[0], pd.Timestamp("1972-01-31"))
c1, c2 = st.columns(2)
start = c1.date_input("From", first.date(), min_value=under.index[0].date(), max_value=under.index[-1].date())
c2.caption("Gold was fixed at $35 before 1971, so UGL history is only meaningful from about 1972.")

tick = sorted(set(pf["weights"]) | {"VOO", "TLT"})
fr = ui.fund_frame(tuple(tick), pf["spread"], data.data_stamp(), str(start))
rets = fr[tick].values
reb = ui.rebalance_from(pf)
none = Rebalance("none")


def run(w: dict, rb):
    wv = np.array([w.get(t, 0.0) for t in tick])
    return run_backtest(rets, wv, rb, start_value=pf["start_value"])


series = {"Your portfolio": run(pf["weights"], reb),
          "100% S&P 500 (VOO)": run({"VOO": 1.0}, none),
          "60/40 (VOO/TLT, annual)": run({"VOO": 0.6, "TLT": 0.4}, Rebalance("calendar", 12))}
idx = pd.DatetimeIndex([fr.index[0] - pd.offsets.MonthEnd(1)]).append(fr.index)
cpi = np.concatenate([[1.0], np.cumprod(1 + fr["cpi"].values)])

real = st.toggle("Show in today's dollars (inflation-adjusted)", True)
fig = go.Figure()
for i, (n, w) in enumerate(series.items()):
    y = w / cpi if real else w
    fig.add_scatter(x=idx, y=y, name=n, line=dict(color=ui.SERIES[i], width=2),
                    hovertemplate="%{y:$,.0f}")
st.subheader("Growth of your balance (log scale)")
ui.show(ui.style(fig, logy=True, yfmt="$,.0f"))

st.subheader("Drawdowns")
fig = go.Figure()
for i, (n, w) in enumerate(series.items()):
    fig.add_scatter(x=idx, y=w / np.maximum.accumulate(w) - 1, name=n,
                    line=dict(color=ui.SERIES[i], width=2), hovertemplate="%{y:.0%}")
ui.show(ui.style(fig, yfmt=".0%"))

st.subheader("Summary")
rows = {}
for n, w in series.items():
    m = metrics(w, 12)
    rows[n] = {"CAGR": ui.pct(m["cagr"]), "Volatility": ui.pct(m["vol"]), "Max drawdown": ui.pct(m["max_dd"]),
               "Longest underwater (yrs)": f"{m['longest_underwater_yrs']:.1f}",
               "Worst 10-yr CAGR": ui.pct(m["worst_10y_cagr"]), "Ulcer index": f"{m['ulcer']*100:.1f}",
               "Ending balance (nominal)": ui.money(w[-1])}
st.dataframe(pd.DataFrame(rows).T, width="stretch")

st.subheader("Rolling 10-year CAGR")
fig = go.Figure()
for i, (n, w) in enumerate(series.items()):
    s = pd.Series(w, index=idx)
    r = (s / s.shift(120)) ** (1 / 10) - 1
    fig.add_scatter(x=idx, y=r, name=n, line=dict(color=ui.SERIES[i], width=2), hovertemplate="%{y:.1%}")
ui.show(ui.style(fig, yfmt=".0%"))

st.subheader("Stress windows (total return, peak-to-trough months)")
srows = []
for name, (a, b) in STRESS.items():
    sl = fr.loc[a:b]
    if len(sl) == 0 or sl.index[0] < fr.index[0]:
        continue
    row = {"Window": name}
    for n, (wv, rb) in {"Your portfolio": (pf["weights"], reb), "VOO": ({"VOO": 1.0}, none)}.items():
        w = np.array([wv.get(t, 0.0) for t in tick])
        row[n] = ui.pct(run_backtest(sl[tick].values, w, rb)[-1] - 1, 0)
    srows.append(row)
st.dataframe(pd.DataFrame(srows).set_index("Window"), width="stretch")
st.caption("Rebalancing costs and fund expenses are included; taxes are not (inside an IRA, rebalancing is tax-free).")
