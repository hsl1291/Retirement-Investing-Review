import _shim  # noqa: F401  (makes irasim importable)
import streamlit as st

from irasim import tax, ui, updater

ui.setup("Leveraged IRA Review")
under, status = ui.get_data()
ui.data_banner(status)

st.markdown(
    """
**What this is:** a tester for a Traditional-IRA leveraged portfolio (UPRO / KMLM / UGL / TMF) held to age 70,
with the tax side (backdoor Roth, conversions, RMDs) modeled alongside it. Use the pages in the sidebar:

| Page | Question it answers |
|---|---|
| **Backtest** | How would this mix have done historically, with real financing costs? |
| **Monte Carlo** | What's the *distribution* of outcomes at age 70, in today's dollars? |
| **Optimizer** | Is there a more efficient mix? Where does leverage stop helping the median? |
| **Taxes and Roth** | Backdoor Roth (pro-rata), conversion strategies, RMDs |
| **Roadmap** | Project plan and open questions |
| **Data and Updates** | Refresh market data, check for app updates |
""")

c1, c2, c3 = st.columns(3)
bd = tax.backdoor_roth_check(806_000)
c1.metric("Backdoor Roth with $806k pre-tax IRA", f"{bd['taxable_pct']*100:.1f}% taxable",
          help="Pro-rata rule: every pre-tax IRA dollar counts. Only a 401k roll-in clears it.")
c2.metric("RMDs begin at age", tax.RMD_START_AGE, help="SECURE 2.0, born 1960 or later.")
c3.metric("App version", ui.VERSION)

st.info(
    "**Read this before trusting any number.** Backtests of leveraged ETFs are dominated by the "
    "interest-rate regime and by volatility data quality. The synthetic fund model is approximate "
    "(see *Data and Updates → Calibration* once live data is loaded), and a historical bootstrap "
    "cannot know about regimes that never happened. Treat outputs as a way to compare options, "
    "not as forecasts. This is a modeling tool, not tax or investment advice.")

with st.expander("Update status"):
    cfg = updater.config()
    st.write(f"Tracking `{cfg['repo']}` @ `{cfg['branch']}`. Use **Data and Updates** to check or apply updates.")
