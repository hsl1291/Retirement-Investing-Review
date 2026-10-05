"""Live data refresh (runs on the user's machine; needs internet).

    python -m irasim.live

Writes CSVs to user/cache/: FRED TB3MS, Yahoo ^GSPC month-end closes, and actual ETF
adjusted closes (for calibrating the synthetic fund model). Every source is independent;
a failure is reported, never fatal.
"""
from __future__ import annotations

import io
import json
import sys

import pandas as pd

from .data import CACHE

ACTUAL_TICKERS = ["UPRO", "TMF", "UGL", "KMLM", "DBMF", "SSO", "VOO", "TLT"]


def _fred(series_id: str, timeout: int) -> pd.DataFrame:
    import requests

    r = requests.get(f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={series_id}", timeout=timeout)
    r.raise_for_status()
    df = pd.read_csv(io.StringIO(r.text))
    df.columns = ["date", "value"]
    df["value"] = pd.to_numeric(df["value"], errors="coerce")
    return df.dropna()


def _yahoo(tickers: list[str]) -> pd.DataFrame:
    import yfinance as yf

    df = yf.download(tickers, period="max", interval="1mo", auto_adjust=True, progress=False)
    close = df["Close"]
    if isinstance(close, pd.Series):
        close = close.to_frame(tickers[0])
    return close


def refresh(timeout: int = 30) -> dict:
    CACHE.mkdir(parents=True, exist_ok=True)
    status: dict[str, str] = {}
    try:
        _fred("TB3MS", timeout).to_csv(CACHE / "TB3MS.csv", index=False)
        status["FRED TB3MS (T-bill rate)"] = "ok"
    except Exception as e:  # noqa: BLE001 - report, don't crash
        status["FRED TB3MS (T-bill rate)"] = f"failed: {e}"
    try:
        g = _yahoo(["^GSPC"]).iloc[:, 0].dropna()
        pd.DataFrame({"date": g.index.strftime("%Y-%m-%d"), "close": g.values}).to_csv(CACHE / "gspc.csv", index=False)
        status["Yahoo ^GSPC (month-end S&P 500)"] = "ok"
    except Exception as e:  # noqa: BLE001
        status["Yahoo ^GSPC (month-end S&P 500)"] = f"failed: {e}"
    try:
        _yahoo(ACTUAL_TICKERS).to_csv(CACHE / "actuals.csv")
        status["Yahoo ETF history (calibration)"] = "ok"
    except Exception as e:  # noqa: BLE001
        status["Yahoo ETF history (calibration)"] = f"failed: {e}"
    return status


if __name__ == "__main__":
    st = refresh()
    print(json.dumps(st, indent=2))
    sys.exit(0 if all(v == "ok" for v in st.values()) else 1)
