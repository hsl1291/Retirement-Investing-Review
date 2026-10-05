import _shim  # noqa: F401
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from irasim import data, tax, ui
from irasim.montecarlo import simulate_portfolio

ui.setup("Taxes and Roth")
under, status = ui.get_data()
pf = ui.portfolio_sidebar()

st.caption("2026 federal brackets, in today's dollars. State tax is a flat rate you choose. "
           "Not tax advice; confirm figures with the IRS and a CPA before acting.")

# ---------------------------------------------------------------- backdoor
st.header("1. Backdoor Roth and the pro-rata rule")
c1, c2, c3 = st.columns(3)
bal = c1.number_input("Pre-tax IRA balance at year-end ($)", 0.0, 1e9, 806_000.0, step=10_000.0,
                      help="ALL traditional, SEP and SIMPLE IRAs. 401k balances do not count.")
basis = c2.number_input("After-tax basis already in IRAs ($)", 0.0, 1e7, 0.0, step=1_000.0)
contrib = c3.number_input("Backdoor contribution ($)", 0.0, 20_000.0, float(tax.IRA_CONTRIB_LIMIT_2026), step=500.0)
t_now = tax.pro_rata_taxable(contrib, basis + contrib, bal)
t_clean = tax.pro_rata_taxable(contrib, basis + contrib, 0)
m1, m2 = st.columns(2)
m1.metric("Taxable portion of the conversion", f"${t_now:,.0f}", f"{t_now / contrib * 100:.1f}% of ${contrib:,.0f}" if contrib else None,
          delta_color="inverse")
m2.metric("If the IRA were rolled into a 401k first", f"${t_clean:,.0f} taxable")
st.markdown(
    "- **Why it fails for you today:** the IRS treats all pre-tax IRA money as one pool, so a clean "
    "$7,500 after-tax contribution converts mostly taxable.\n"
    "- **The only clean fix** is rolling the IRA into a 401k (not counted in pro-rata), which only helps if "
    "that 401k offers a brokerage window (Schwab PCRA) that holds these funds.\n"
    "- **Bigger lever:** a *mega backdoor Roth* (after-tax 401k contributions + in-plan Roth conversion), "
    "if your plan allows it, and converting the large IRA itself (below).\n"
    "- Paying conversion tax from the IRA itself before 59½ triggers the 10% early-withdrawal penalty on the "
    "withheld amount. Pay it from outside cash.")

# ---------------------------------------------------------------- conversions
st.header("2. Roth conversion strategies")
a, b, c, d = st.columns(4)
age = a.number_input("Age now", 18, 69, 36)
ret = b.number_input("Retire at", 50, 80, 70)
hor = c.number_input("Score wealth at age", 75, 100, 90)
status_ = d.selectbox("Filing status", ["mfj", "single"], format_func=lambda s: {"mfj": "Married filing jointly", "single": "Single"}[s])
e, f, g, h = st.columns(4)
wage = e.number_input("Taxable income now ($)", 0.0, 5e6, 150_000.0, step=10_000.0)
oth = f.number_input("Other retirement income at 70+ ($/yr, real)", 0.0, 1e6, 90_000.0, step=5_000.0,
                     help="Social Security, 401k withdrawals, pension.")
st_now = g.number_input("State tax now (%)", 0.0, 15.0, 0.0, step=0.5) / 100
st_ret = h.number_input("State tax in retirement (%)", 0.0, 15.0, 0.0, step=0.5) / 100
i, j, k = st.columns(3)
shift = i.number_input("Future bracket increase (pts above 12%)", 0.0, 15.0, 0.0, step=1.0) / 100
heir = j.number_input("Heirs' tax rate on leftover Traditional", 0.0, 50.0, 35.0, step=1.0) / 100
n_paths = k.select_slider("Paths", [100, 300, 500, 1000], 300)

st.subheader("Return assumptions")
src = st.radio("Pre-retirement returns", ["Bootstrap of your portfolio (Monte Carlo page settings)", "Assumed lognormal"],
               horizontal=True)
l1, l2, l3, l4 = st.columns(4)
geo = l1.number_input("Pre-retirement real geometric return (%)", -5.0, 25.0, 7.0, step=0.5) / 100
vol = l2.number_input("Pre-retirement volatility (%)", 5.0, 80.0, 40.0, step=1.0) / 100
pgeo = l3.number_input("Post-retirement real return (%)", -2.0, 12.0, 4.0, step=0.5,
                       help="After you stop running the leveraged mix; e.g. a balanced portfolio.") / 100
pvol = l4.number_input("Post-retirement volatility (%)", 3.0, 40.0, 12.0, step=1.0) / 100

prof = tax.TaxProfile(age_now=age, retire_age=ret, horizon_age=hor, status=status_, wage_income=wage,
                      retire_other_income=oth, state_rate_now=st_now, state_rate_retire=st_ret,
                      rate_shift=shift, heir_rate=heir)
years, pre = hor - age, ret - age
rng = np.random.default_rng(7)

if st.button("Run conversion analysis", type="primary"):
    with st.spinner("Simulating…"):
        if src.startswith("Bootstrap"):
            tick = tuple(sorted(pf["weights"]))
            fr = ui.fund_frame(tick, pf["spread"], data.data_stamp(), "1972-01-01", pf["bond_haircut"])
            sim = simulate_portfolio(fr, pf["weights"], ui.rebalance_from(pf), n_paths, pre, 24, pf["start_value"])
            pre_r = sim["annual_real"]
        else:
            pre_r = np.exp(np.log1p(geo) + vol * rng.standard_normal((n_paths, pre))) - 1
        post_r = np.exp(np.log1p(pgeo) + pvol * rng.standard_normal((n_paths, years - pre))) - 1
        paths = np.hstack([pre_r, post_r])
        base = None
        rows, meds = [], {}
        for st_ in tax.DEFAULT_STRATEGIES:
            o = tax.simulate_conversions(paths, pf["start_value"], st_, prof)
            if base is None:
                base = o["after_tax"]
            a_ = o["after_tax"]
            rows.append({"Strategy": st_.name, "10th pct": ui.money(np.percentile(a_, 10)),
                         "Median": ui.money(np.median(a_)), "90th pct": ui.money(np.percentile(a_, 90)),
                         "Beats no-conversion": "-" if st_ is tax.DEFAULT_STRATEGIES[0] else ui.pct(float(np.mean(a_ > base)), 0),
                         "Median tax paid": ui.money(np.median(o["taxes_paid"]))})
            meds[st_.name] = float(np.median(a_))
    st.dataframe(pd.DataFrame(rows).set_index("Strategy"), width="stretch")
    fig = go.Figure(go.Bar(x=list(meds.values()), y=list(meds), orientation="h", marker_color=ui.SERIES[0],
                           hovertemplate="%{x:$,.0f}"))
    fig.update_yaxes(autorange="reversed")
    ui.show(ui.style(fig, height=340, yfmt=None))
    st.markdown(
        f"After-tax **real** wealth at {hor}, assuming heirs pay {heir*100:.0f}% on leftover Traditional money. "
        "Conversion tax is paid from a taxable side account that earns 3.5% real (negative balance = money "
        "taken from savings/income). **Conversions are a bet on the strategy:** paying tax now on money that "
        "later shrinks loses; on money that grows, it wins. The *Beats no-conversion* column shows how often.")
