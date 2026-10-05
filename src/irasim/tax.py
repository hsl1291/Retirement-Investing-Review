"""Federal tax, RMD, pro-rata and Roth-conversion modeling.

Everything is in REAL (today's) dollars. Brackets are indexed to inflation by
law, so holding them constant in real terms is the natural assumption. Use
``rate_shift`` to model brackets reverting higher.

Figures are 2026 values (post-OBBBA, TCJA rates made permanent). Verify
against the IRS before relying on any single number.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

# (bracket floor of taxable income, marginal rate)
BRACKETS_2026 = {
    "single": [(0, 0.10), (12_400, 0.12), (50_400, 0.22), (105_700, 0.24),
               (201_775, 0.32), (256_225, 0.35), (640_600, 0.37)],
    "mfj": [(0, 0.10), (24_800, 0.12), (100_800, 0.22), (211_400, 0.24),
            (403_550, 0.32), (512_450, 0.35), (768_700, 0.37)],
}
STD_DEDUCTION_2026 = {"single": 16_100, "mfj": 32_200}
IRA_CONTRIB_LIMIT_2026 = 7_500

# IRS Uniform Lifetime Table (2022+), age -> divisor
UNIFORM_LIFETIME = {
    72: 27.4, 73: 26.5, 74: 25.5, 75: 24.6, 76: 23.7, 77: 22.9, 78: 22.0,
    79: 21.1, 80: 20.2, 81: 19.4, 82: 18.5, 83: 17.7, 84: 16.8, 85: 16.0,
    86: 15.2, 87: 14.4, 88: 13.7, 89: 12.9, 90: 12.2, 91: 11.5, 92: 10.8,
    93: 10.1, 94: 9.5, 95: 8.9, 96: 8.4, 97: 7.8, 98: 7.3, 99: 6.8, 100: 6.4,
}
RMD_START_AGE = 75  # SECURE 2.0, born 1960 or later


def _brackets(status: str, rate_shift: float = 0.0):
    # rate_shift raises every bracket above 12% (models "rates revert higher")
    return [(lo, r + rate_shift if r > 0.12 else r) for lo, r in BRACKETS_2026[status]]


def income_tax(ordinary_income: float, status: str = "mfj", rate_shift: float = 0.0,
               state_rate: float = 0.0) -> float:
    """Tax on gross ordinary income (standard deduction applied here)."""
    taxable = max(0.0, ordinary_income - STD_DEDUCTION_2026[status])
    br = _brackets(status, rate_shift)
    tax = 0.0
    for i, (lo, rate) in enumerate(br):
        hi = br[i + 1][0] if i + 1 < len(br) else float("inf")
        if taxable > lo:
            tax += (min(taxable, hi) - lo) * rate
    return tax + state_rate * max(0.0, ordinary_income - STD_DEDUCTION_2026[status])


def marginal_tax(base_income: float, extra: float, **kw) -> float:
    """Incremental tax from stacking ``extra`` ordinary income on ``base_income``."""
    return income_tax(base_income + extra, **kw) - income_tax(base_income, **kw)


def headroom_to_rate(base_income: float, max_rate: float, status: str = "mfj",
                     rate_shift: float = 0.0) -> float:
    """Extra gross income that can be added before the marginal rate exceeds ``max_rate``."""
    br = _brackets(status, rate_shift)
    top = None
    for i, (lo, rate) in enumerate(br):
        if rate > max_rate + 1e-9:
            top = lo
            break
    if top is None:
        return float("inf")
    taxable_now = max(0.0, base_income - STD_DEDUCTION_2026[status])
    room = top - taxable_now
    # income below the standard deduction is also free headroom
    room += max(0.0, STD_DEDUCTION_2026[status] - base_income)
    return max(0.0, room)


def rmd(balance: float, age: int, start_age: int = RMD_START_AGE) -> float:
    if age < start_age:
        return 0.0
    return balance / UNIFORM_LIFETIME.get(age, 6.4)


def pro_rata_taxable(conversion: float, after_tax_basis: float,
                     yearend_pretax_ira_balance: float) -> float:
    """Taxable part of a Roth conversion under the pro-rata rule (Form 8606).

    ``yearend_pretax_ira_balance`` is the Dec-31 value of ALL traditional, SEP
    and SIMPLE IRAs after the conversion (401k balances do NOT count).
    """
    denom = yearend_pretax_ira_balance + conversion
    if denom <= 0:
        return 0.0
    nontaxable_frac = min(1.0, after_tax_basis / denom)
    return conversion * (1 - nontaxable_frac)


# ---------------------------------------------------------------------------
# Conversion-strategy simulation
# ---------------------------------------------------------------------------

@dataclass
class TaxProfile:
    age_now: int = 36
    retire_age: int = 70
    horizon_age: int = 90            # when we score after-tax wealth
    status: str = "mfj"
    wage_income: float = 150_000     # gross ordinary income while working (real $)
    retire_other_income: float = 90_000  # SS + 401k RMDs + other, ages 70+ (real $)
    state_rate_now: float = 0.0
    state_rate_retire: float = 0.0
    rate_shift: float = 0.0          # e.g. +0.04: brackets above 12% are higher once retired
    heir_rate: float = 0.35          # tax rate on trad balance left at horizon
    side_return: float = 0.035       # real after-tax return on taxable side account


@dataclass
class ConversionStrategy:
    name: str
    fill_to_rate: float | None = None    # convert up to the top of this bracket each year
    start_age: int = 0
    stop_age: int = 200
    drawdown_trigger: float | None = None  # only convert when portfolio <= (1-x) * high-water mark
    convert_all_at_age: int | None = None


DEFAULT_STRATEGIES = [
    ConversionStrategy("No conversions"),
    ConversionStrategy("Fill 24% bracket, now to 70", fill_to_rate=0.24, stop_age=70),
    ConversionStrategy("Fill 32% bracket, now to 70", fill_to_rate=0.32, stop_age=70),
    ConversionStrategy("Fill 35% bracket, now to 70", fill_to_rate=0.35, stop_age=70),
    ConversionStrategy("Fill 24% only in 40%+ drawdowns", fill_to_rate=0.24, stop_age=70,
                       drawdown_trigger=0.40),
    ConversionStrategy("Fill 32% only in 40%+ drawdowns", fill_to_rate=0.32, stop_age=70,
                       drawdown_trigger=0.40),
    ConversionStrategy("Window: fill 32% at ages 70-74", fill_to_rate=0.32, start_age=70,
                       stop_age=75),
    ConversionStrategy("Convert everything this year", convert_all_at_age=36),
]


def simulate_conversions(real_returns: np.ndarray, trad0: float, strat: ConversionStrategy,
                         prof: TaxProfile, roth0: float = 0.0) -> dict:
    """Run one strategy along annual REAL return paths.

    real_returns: shape (n_paths, n_years) annual real returns of the IRA portfolio,
    starting at ``prof.age_now``. Taxes on conversions are paid from a taxable side
    account (which can go negative = funded from income/savings that would otherwise
    have been invested there). RMD proceeds (after tax) are added to it.
    """
    n_paths, n_years = real_returns.shape
    years = prof.horizon_age - prof.age_now
    assert n_years >= years, "need returns through horizon_age"
    trad = np.full(n_paths, float(trad0))
    roth = np.full(n_paths, float(roth0))
    side = np.zeros(n_paths)
    hwm = trad + roth
    taxes_paid = np.zeros(n_paths)
    snap = {}

    for y in range(years):
        age = prof.age_now + y
        working = age < prof.retire_age
        base = prof.wage_income if working else prof.retire_other_income
        state = prof.state_rate_now if working else prof.state_rate_retire
        # future bracket change only applies once retired (today's law applies now)
        kw = dict(status=prof.status, rate_shift=0.0 if working else prof.rate_shift, state_rate=state)

        # 1) RMD (start of year, prior year-end balance)
        r = np.array([rmd(b, age) for b in trad])
        if r.any():
            tax = np.array([marginal_tax(base, x, **kw) for x in r])
            trad -= r
            side += r - tax
            taxes_paid += tax
            base_after = base + r
        else:
            base_after = np.full(n_paths, base)

        # 2) Conversion decision
        total = trad + roth
        hwm = np.maximum(hwm, total)
        conv = np.zeros(n_paths)
        if strat.convert_all_at_age == age:
            conv = trad.copy()
        elif strat.fill_to_rate is not None and strat.start_age <= age < strat.stop_age:
            # bracket identified by today's rate; thresholds don't move with rate_shift
            room = np.array([headroom_to_rate(b, strat.fill_to_rate, prof.status) for b in base_after])
            conv = np.minimum(trad, room)
            if strat.drawdown_trigger is not None:
                in_dd = total <= (1 - strat.drawdown_trigger) * hwm
                conv = np.where(in_dd, conv, 0.0)
        if conv.any():
            tax = np.array([marginal_tax(b, c, **kw) for b, c in zip(base_after, conv)])
            trad -= conv
            roth += conv
            side -= tax
            taxes_paid += tax

        # 3) Grow
        g = real_returns[:, y]
        trad *= 1 + g
        roth *= 1 + g
        side *= 1 + prof.side_return

        if age + 1 in (prof.retire_age, 75, prof.horizon_age):
            snap[age + 1] = dict(trad=trad.copy(), roth=roth.copy(), side=side.copy())

    after_tax = roth + trad * (1 - prof.heir_rate) + side
    return dict(name=strat.name, after_tax=after_tax, trad=trad, roth=roth, side=side,
                taxes_paid=taxes_paid, snapshots=snap)


def backdoor_roth_check(trad_ira_balance: float, contribution: float = IRA_CONTRIB_LIMIT_2026) -> dict:
    """How much of a backdoor Roth conversion is taxable given existing pre-tax IRA money."""
    taxable = pro_rata_taxable(contribution, contribution, trad_ira_balance)
    return dict(contribution=contribution, taxable=taxable,
                taxable_pct=taxable / contribution, tax_free=contribution - taxable)
