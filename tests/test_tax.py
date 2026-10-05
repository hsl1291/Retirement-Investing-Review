import numpy as np

from irasim import tax


def test_income_tax_mfj_2026():
    # 200k gross -> 167,800 taxable; 2,480 + 9,120 + 0.22*(167,800-100,800)
    assert np.isclose(tax.income_tax(200_000, "mfj"), 2_480 + 9_120 + 0.22 * 67_000)


def test_headroom_to_24_bracket():
    # top of 24% MFJ is 403,550 taxable -> gross 435,750
    assert np.isclose(tax.headroom_to_rate(150_000, 0.24, "mfj"), 435_750 - 150_000)


def test_pro_rata_kills_backdoor_with_big_ira():
    r = tax.backdoor_roth_check(806_000)
    assert r["taxable_pct"] > 0.99


def test_pro_rata_clean_when_ira_empty():
    assert tax.backdoor_roth_check(0)["taxable"] == 0


def test_rmd_age_75():
    assert tax.rmd(1_000_000, 74) == 0
    assert np.isclose(tax.rmd(1_000_000, 75), 1_000_000 / 24.6)


def test_conversion_sim_conserves_without_tax():
    prof = tax.TaxProfile(wage_income=0, retire_other_income=0, horizon_age=40, heir_rate=0.0)
    rets = np.zeros((3, 10))
    out = tax.simulate_conversions(rets, 100_000, tax.DEFAULT_STRATEGIES[0], prof)
    assert np.allclose(out["after_tax"], 100_000)
