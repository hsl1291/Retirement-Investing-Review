import _shim  # noqa: F401
import pandas as pd
import streamlit as st

from irasim import data, live, ui, updater
from irasim.funds import FUNDS

ui.setup("Data and Updates")
under, status = ui.get_data()

st.header("App updates")
cfg = updater.config()
st.write(f"Version **{ui.VERSION}** · install type **{'git clone' if updater.is_git_clone() else 'zip install'}** · "
         f"tracking `{cfg['repo']}` @ `{cfg['branch']}`")
c1, c2 = st.columns(2)
if c1.button("Check for updates"):
    res = updater.check()
    if res["error"]:
        st.error(f"Could not check: {res['error']}")
    elif res["update_available"]:
        st.info(f"Update available ({(res['local'] or 'unknown')[:7]} → {res['remote'][:7]}).")
    else:
        st.success("You're up to date.")
if c2.button("Update now"):
    res = updater.update()
    (st.success if res["ok"] else st.error)(res["message"])
    if res["ok"] and res["requirements_changed"]:
        st.warning("Dependencies changed: close the app and start it again with run.bat / run.sh.")
    elif res["ok"]:
        st.info("Restart the app (close and reopen it) to load the new version.")
with st.expander("Update settings"):
    repo = st.text_input("GitHub repo (owner/name)", cfg["repo"])
    branch = st.text_input("Branch", cfg["branch"])
    auto = st.checkbox("Check for updates automatically when the app starts", cfg["auto_update"])
    token = st.text_input("GitHub token (only for a private repo)", cfg.get("github_token", ""), type="password")
    if st.button("Save update settings"):
        updater.save_config(repo=repo, branch=branch, auto_update=auto, github_token=token)
        st.success("Saved to user/config.json")

st.header("Market data")
st.write(f"**Price source:** {status['price_source']}  \n**Cash source:** {status['cash_source']}  \n"
         f"**Range:** {status['start']} to {status['end']}")
if st.button("Refresh live data (needs internet)"):
    with st.spinner("Downloading…"):
        res = live.refresh()
    for k, v in res.items():
        (st.success if v == "ok" else st.error)(f"{k}: {v}")
    st.cache_data.clear()
    st.info("Reload the page to use the new data.")

st.subheader("Calibration: synthetic fund model vs the real ETFs")
cal = data.calibration(under, FUNDS)
if cal is None:
    st.info("Available after a live data refresh. This is the check that the leveraged-fund model "
            "reproduces UPRO / TMF / UGL / KMLM; trust the Monte Carlo only if tracking error is small. "
            "KMLM here is a proxy, so expect a gap until a real trend series is added.")
else:
    fmt = cal.copy()
    for c in ["actual_cagr", "synthetic_cagr", "actual_vol", "synthetic_vol", "tracking_error"]:
        fmt[c] = (fmt[c] * 100).round(1).astype(str) + "%"
    fmt["correlation"] = fmt["correlation"].round(3)
    st.dataframe(fmt, width="stretch")

st.subheader("Fund assumptions")
st.dataframe(pd.DataFrame([{"ticker": f.ticker, "exposure": f.exposures, "expense ratio": f"{f.expense_ratio*100:.2f}%",
                            "daily reset": f.daily_reset, "K-1": f.k1, "note": f.note} for f in FUNDS.values()])
             .set_index("ticker"), width="stretch")
st.caption("Expense ratios are approximate. Verify against current prospectuses.")
