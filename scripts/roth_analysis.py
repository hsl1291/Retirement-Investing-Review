"""Roth conversion strategy comparison under assumed return distributions.

Placeholder returns until the Phase-1 data layer is live: annual REAL portfolio
returns are lognormal with the given geometric mean and volatility. Rerun with
bootstrapped paths from the real backtest once available.

    python scripts/roth_analysis.py
"""
import sys
from dataclasses import replace
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from irasim import tax  # noqa: E402

TRAD0 = 766_000 + 40_000  # current IRA + planned rollover
N_PATHS = 2000
SCENARIOS = {  # name: (real geometric mean, annual vol)
    "bear (3% real)": (0.03, 0.40),
    "base (7% real)": (0.07, 0.40),
    "bull (11% real)": (0.11, 0.40),
}


def lognormal_paths(geo, vol, n_paths, n_years, seed=0):
    rng = np.random.default_rng(seed)
    return np.exp(np.log1p(geo) + vol * rng.standard_normal((n_paths, n_years))) - 1


def fmt(x):
    return f"${x/1e6:6.2f}M"


def run(prof: tax.TaxProfile, label: str):
    years = prof.horizon_age - prof.age_now
    print(f"\n=== {label} ===")
    for sname, (geo, vol) in SCENARIOS.items():
        paths = lognormal_paths(geo, vol, N_PATHS, years)
        base = tax.simulate_conversions(paths, TRAD0, tax.DEFAULT_STRATEGIES[0], prof)
        print(f"\n  {sname}: after-tax real wealth at {prof.horizon_age}, vs no conversions")
        print(f"  {'strategy':38s} {'p10':>9s} {'median':>9s} {'p90':>9s}  {'win%':>5s}  {'med tax paid':>12s}")
        for st in tax.DEFAULT_STRATEGIES:
            o = tax.simulate_conversions(paths, TRAD0, st, prof)
            a = o["after_tax"]
            win = np.mean(a > base["after_tax"]) if st is not tax.DEFAULT_STRATEGIES[0] else np.nan
            print(f"  {st.name:38s} {fmt(np.percentile(a,10))} {fmt(np.median(a))} {fmt(np.percentile(a,90))}"
                  f"  {win*100:5.0f}  {fmt(np.median(o['taxes_paid']))}")


if __name__ == "__main__":
    print("Backdoor Roth with $806k pre-tax IRA:", tax.backdoor_roth_check(TRAD0))
    print("Backdoor Roth with IRA rolled into 401k:", tax.backdoor_roth_check(0))
    base = tax.TaxProfile()
    run(base, "MFJ, $150k wages, $90k other retirement income, no state tax")
    run(replace(base, wage_income=300_000), "MFJ, $300k wages")
    run(replace(base, rate_shift=0.04), "MFJ, $150k wages, brackets +4pts in future")
