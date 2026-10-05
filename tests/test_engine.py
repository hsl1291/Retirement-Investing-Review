import numpy as np
import pandas as pd

from irasim.engine import Rebalance, fund_returns, run_backtest
from irasim.funds import FUNDS


def _gbm_daily(n_days, mu=0.08, sigma=0.20, seed=1):
    rng = np.random.default_rng(seed)
    return np.exp((mu - sigma**2 / 2) / 252 + sigma / np.sqrt(252) * rng.standard_normal(n_days)) - 1


def test_monthly_leverage_approx_is_unbiased_vs_daily_exact():
    # Monthly data cannot see each month's realized intramonth variance, so single
    # paths are noisy; the approximation must be unbiased on average.
    diffs = []
    for seed in range(40):
        days = _gbm_daily(21 * 12 * 20, seed=seed)
        exact = np.log1p(fund_returns(pd.DataFrame({"spx": days, "cash": 0.0}), FUNDS["UPRO"], 252)).sum()
        monthly = (1 + days).reshape(-1, 21).prod(1) - 1
        approx = np.log1p(fund_returns(pd.DataFrame({"spx": monthly, "cash": 0.0}), FUNDS["UPRO"], 12)).sum()
        diffs.append((approx - exact) / 20)
    assert abs(np.mean(diffs)) < 0.005  # < 0.5%/yr average bias


def test_vol_decay_makes_3x_lose_on_flat_choppy_market():
    r = np.tile([0.05, -0.0476190476], 500)  # underlying ends flat
    df = pd.DataFrame({"spx": r, "cash": 0.0})
    upro = np.prod(1 + fund_returns(df, FUNDS["UPRO"], 252).values)
    assert upro < 0.5


def test_calendar_rebalance_restores_weights():
    rets = np.array([[0.10, -0.05], [0.20, 0.00], [0.00, 0.00]])
    w = run_backtest(rets, [0.5, 0.5], Rebalance("calendar", every=2, cost_bps=0))
    # after period 2 rebalanced; period 3 flat -> wealth unchanged
    assert np.isclose(w[2], w[3])
    assert np.isclose(w[1], 0.5 * 1.1 + 0.5 * 0.95)


def test_no_rebalance_is_buy_and_hold():
    rets = np.array([[0.10, -0.05], [0.10, -0.05]])
    w = run_backtest(rets, [0.5, 0.5], Rebalance("none"))
    assert np.isclose(w[-1], 0.5 * 1.1**2 + 0.5 * 0.95**2)
