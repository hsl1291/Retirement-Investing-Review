"""Fund definitions: each tradable ETF is a leveraged (or not) claim on underlying series.

Underlying series names (columns expected in the returns frame):
    spx   S&P 500 total return
    ltt   20+yr Treasury total return
    itt   7-10yr Treasury total return
    gold  spot gold
    trend managed-futures / trend index (net of its own fees -> use fee_in_index=True)
    cash  T-bill return (also the financing rate)

Expense ratios are approximate; verify before relying on them. ``spread`` is the
financing spread over T-bills on the borrowed notional. It is calibrated against
the real funds in Phase 1 (placeholder default 0.5%/yr).
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Fund:
    ticker: str
    exposures: dict  # underlying -> leverage multiple, e.g. {"spx": 3.0}
    expense_ratio: float
    daily_reset: bool = True
    spread: float = 0.005
    k1: bool = False   # issues a K-1 (commodity pool)
    note: str = ""

    @property
    def gross(self) -> float:
        return sum(self.exposures.values())


FUNDS = {f.ticker: f for f in [
    Fund("VOO", {"spx": 1.0}, 0.0003, daily_reset=False),
    Fund("SSO", {"spx": 2.0}, 0.0089),
    Fund("UPRO", {"spx": 3.0}, 0.0091),
    Fund("TLT", {"ltt": 1.0}, 0.0015, daily_reset=False),
    Fund("UBT", {"ltt": 2.0}, 0.0095),
    Fund("TMF", {"ltt": 3.0}, 0.0101),
    Fund("TYD", {"itt": 3.0}, 0.0101),
    Fund("GLDM", {"gold": 1.0}, 0.0010, daily_reset=False),
    Fund("UGL", {"gold": 2.0}, 0.0095, k1=True),
    Fund("KMLM", {"trend": 1.0}, 0.0090, daily_reset=False, note="single-manager trend"),
    Fund("DBMF", {"trend": 1.0}, 0.0085, daily_reset=False, note="replicator; proxied by trend index"),
    # Capital-efficient / return-stacked: not daily-reset 3x, futures-based overlays
    Fund("NTSX", {"spx": 0.9, "itt": 0.6}, 0.0020, daily_reset=False),
    Fund("GDE", {"spx": 0.9, "gold": 0.9}, 0.0020, daily_reset=False),
    Fund("RSSB", {"spx": 1.0, "itt": 1.0}, 0.0036, daily_reset=False,
         note="actually global equity; proxied by spx"),
    Fund("RSST", {"spx": 1.0, "trend": 1.0}, 0.0095, daily_reset=False),
]}

CURRENT_PORTFOLIO = {"UPRO": 0.70, "KMLM": 0.10, "UGL": 0.10, "TMF": 0.10}
