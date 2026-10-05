# IRA Leveraged Portfolio Review — Roadmap

**Owner:** age 36, target retirement 70 (34-year horizon)
**Account:** IRA, $766k today, +$40k planned, then no further contributions
**Current allocation:** 70% UPRO / 10% KMLM / 10% UGL / 10% TMF, quarterly calendar rebalance
**Objective as stated:** highest absolute returns at age 70; volatility accepted; other retirement assets (401k, target-date funds) cover the base case

---

## Status (app v0.1.0)

| Phase | State |
|---|---|
| 1 Data layer | **Partial.** Bundled public data + live refresh (FRED T-bill, Yahoo). Live path is **untested end to end** (the dev sandbox blocks those hosts). Trend sleeve is an illustrative proxy. |
| 2 Backtest engine | Built, unit-tested. |
| 3 Monte Carlo | Built (block bootstrap, real dollars, bond-tailwind haircut). |
| 4 Tax module | Built (2026 brackets, RMD 75, pro-rata, conversion strategies). Needs your filing/income/state inputs. |
| 5 Optimizer | Built (grid search, 4 objectives, drawdown cap, leverage sweep). Real-vs-proxy calibration pending live data. |
| 6 Report/app | **Streamlit app**, zip-installable, self-updating (see README). |

**Next:** run the live refresh on your machine and check *Data and Updates → Calibration* (synthetic vs real
UPRO/TMF/UGL tracking). Do not rely on any output until tracking error is small. Replace the trend proxy
with a real series. Re-run Roth analysis with portfolio-bootstrapped returns.

## 0. Answers so far

| # | Question | Answer | Consequence |
|---|----------|--------|-------------|
| Q1 | Account type | **Traditional**; wants to understand the backdoor Roth | Tax module centers on conversions + pro-rata |
| Q2 | $40k source | **Rollover** | Lands in the Traditional IRA → increases the pro-rata problem |
| Q3 | Behavioral history | Held UPRO/TMF 70/30 through 2022 since HFEA began | Drawdown tolerance is demonstrated, not hypothetical |
| Q4 | Objective | Wants to see the optimization options | Report median / Kelly / p10 / mean side by side (§3) |
| Q5 | Broker | **Schwab** | No margin in IRA; leverage only via LETFs, return-stacked funds, or futures (Schwab allows futures in IRAs with approval) |

**Still open:**
- Q6: filing status
- Q7: current taxable income
- Q8: state now and expected state in retirement
- Q9: outside cash available to pay conversion taxes
- Q10: does your 401k accept roll-ins, and does it have a self-directed brokerage window (Schwab PCRA)?
- Q11: does your 401k allow after-tax contributions with in-plan Roth conversion (mega backdoor)?

## 0.1 Findings so far (tax; placeholder returns — see `results/roth_conversion_placeholder.txt`)

1. **The backdoor Roth is dead while the IRA holds pre-tax money.** Pro-rata makes 99.1% of a $7,500 backdoor conversion taxable with $806k in the IRA. The only clean fix is to roll the IRA *into a 401k* (401k balances don't count for pro-rata). That only keeps this strategy alive if the 401k has a brokerage window that allows UPRO/TMF/UGL/KMLM.
2. **Backdoor Roth is small potatoes anyway:** $7.5k/yr vs an $806k balance. The real decisions are (a) partial conversions of the big IRA and (b) a mega backdoor in the 401k, if offered.
3. **Converting with taxes paid from outside cash is economically the same as adding outside money to this leveraged strategy, sheltered forever.** It raised median after-tax real wealth at 90 by about 30% (7% real scenario) to about 60% (11% real), and won in 62–80% of paths. In a 3% real world it lost about 63% of the time, because you prepaid tax on money that later evaporated. It is a bet on the strategy, not free money.
4. **Drawdown-triggered conversion is not a free lunch** (correcting my earlier framing). Its median is about the same as converting now; it improves the bad tail and gives up the good tail. Without mean reversion, a dollar converted in a crash has the same expected future as any other dollar.
5. **Waiting to convert at 70–74 is the worst of the active options** when returns are good. By then RMDs and balances force top-bracket income regardless.
6. **Never pay conversion tax from the IRA before 59½.** Withheld tax counts as an early distribution and gets the 10% penalty on top.

## 1. Phase 1 — Data layer

> **Blocked:** the environment's network policy denies fred.stlouisfed.org, query1/query2.finance.yahoo.com, mba.tuck.dartmouth.edu, www.aqr.com. Monthly Shiller S&P/CPI/10y and monthly gold are cached in `data/raw/` from GitHub-hosted public datasets, but there is no T-bill or trend series, so no backtest numbers yet.

**Goal:** return series for every candidate asset that are long enough and honest enough to test a 34-year hold.

- **Actual ETF history:** UPRO (2009), TMF (2009), UGL (2008), KMLM (2020). Together they cover only about 16 years, all in a low-rate regime. That is not enough on its own.
- **Synthetic extensions (the core work):**
  - Daily leveraged series = `L × underlying daily total return − (L−1) × (T-bill + spread) − expense ratio`, compounded daily.
  - Underlyings: S&P 500 total return (daily from 1928 via Ken French/CRSP proxies), long Treasuries (20+yr yield series from FRED → total return), gold (LBMA from 1968), and trend (the KFA MLM Index back to 1988, plus SG Trend and AQR TSMOM research series for a longer cross-check).
  - **Calibration:** fit the financing spread so that synthetic UPRO, TMF, and UGL track the real funds over the years where both exist. Report the tracking error.
- **Rates and inflation:** T-bill (FRED DTB3), CPI. These feed the borrowing cost and the real-dollar outputs.
- **Deliverable:** a `data/` cache plus a validation report (synthetic vs actual, per fund).

> ⚠️ Key bias to correct: most of the 2009–2021 backtests that made this portfolio popular ran at near-zero rates. With T-bills at about 4%, UPRO's built-in borrowing (2× notional) costs roughly 8–9% a year on that sleeve, which is about 6 points of drag on the whole portfolio. The tester must model financing explicitly, not just replay ETF prices.

## 2. Phase 2 — Backtest engine

- Daily simulation, any weights, any rebalance rule:
  - calendar (monthly / quarterly / annual)
  - threshold bands (e.g. 5/25 absolute/relative)
  - none (buy and hold)
- Cash flows: $766k at t0, then the $40k on a schedule set by Q2.
- Costs: expense ratios, financing, and a bid-ask/slippage estimate per rebalance.
- **Metrics:** CAGR, real CAGR, volatility, max drawdown and drawdown duration, Ulcer index, Sortino, worst 1/5/10-year windows, and time underwater.
- **Stress windows, replayed explicitly:** 1929–32, 1966–82 (stagflation), 1973–74, 2000–02, 2008, 2020, 2022 (a stock *and* bond crash with fast rate hikes, the scenario that breaks the UPRO/TMF hedge).

## 3. Phase 3 — Forward Monte Carlo (the part that actually answers "at 70")

Historical backtests give you one path. A 34-year leveraged bet needs a distribution.

- **Method:** stationary block bootstrap of joint monthly returns (keeps cross-asset correlation and volatility clustering), plus a regime-conditioned variant that oversamples high-rate and inflationary periods.
- **Output at age 70:** the full distribution of terminal wealth in nominal and real dollars:
  - mean, median, and the 5th / 10th / 25th / 75th / 90th percentiles
  - P(ending below the starting $806k in real terms)
  - P(drawdown > 80% at any point)
  - P(underperforming plain 100% S&P / VOO)
- **Why it matters:** the mean and median separate with leverage. Past roughly Kelly-optimal leverage (about 1.5–2× on equities at today's financing costs), extra leverage *raises* the mean through a few huge paths and *lowers* the median. Your current mix is about 2.1× S&P, plus 0.3× long Treasuries, 0.2× gold, and 0.1× trend, so about 2.7× total gross exposure. The tester will show where it sits on that curve.

## 4. Phase 4 — Tax and timing module

Inside an IRA, rebalancing, distributions, and turnover create **no current tax**, so the quarterly rebalance is tax-free. The tax questions are all about the account wrapper and the exit.

| Topic | Model |
|-------|-------|
| Account type (Q1) | Traditional: every dollar out is ordinary income. Roth: tax-free with no RMDs. |
| Early access | 10% penalty before 59½. Not relevant if you hold to 70, but it is modeled as a constraint. |
| RMDs | Born 1990 → RMDs start at **75** (SECURE 2.0). Uniform Lifetime Table. Project the RMD dollars and marginal bracket each year from 75 on. |
| **Roth conversion strategy (if Traditional)** | Highest-value lever in the whole project. Leveraged portfolios have deep drawdowns, and converting shares *during* a 50–70% drawdown moves future recovery into the Roth tax-free. Model: (a) no conversions, (b) fixed annual conversions to fill a bracket, (c) drawdown-triggered conversions, (d) a conversion window from ages 70–75. |
| Contribution path (Q2) | Annual limits, Roth income phase-outs, backdoor Roth and the pro-rata rule (a large Traditional IRA breaks the backdoor), and rollover mechanics. |
| UGL (K-1 commodity pool) in an IRA | Check UBTI exposure (futures gains are generally excluded) and broker restrictions. Low expected impact, but verify it rather than assume. |
| Heirs | 10-year rule for non-spouse beneficiaries. Traditional vs Roth inheritance value. |
| Bracket assumptions | Current brackets, the post-2025 law, and a "brackets revert higher" scenario. |
| **Primary output** | After-tax wealth at 70 and at 75, plus the after-tax value of RMDs. Compare every portfolio on after-tax, real dollars, not pre-tax nominal. |

## 5. Phase 5 — Candidate portfolios to test against yours

The baseline is your current mix. Every candidate faces the same data, costs, and taxes.

| ID | Portfolio | Hypothesis |
|----|-----------|------------|
| B0 | 100% VOO | The null hypothesis. Leverage has to beat this after costs. |
| B1 | **70 UPRO / 10 KMLM / 10 UGL / 10 TMF, quarterly** | Your current mix. |
| B2 | Same mix with threshold-band rebalancing | Is calendar timing leaving money on the table? |
| C1 | 55 UPRO / 15 KMLM / 15 UGL / 15 TMF | Less leverage, possibly a *higher median*. |
| C2 | SSO (2×) based, sized to a similar equity notional | Less volatility decay than 3× daily reset. |
| C3 | TMF → shorter-duration leveraged Treasuries (TYD) or a mix | 2022 showed long duration is a weak hedge against inflation shocks. |
| C4 | KMLM → blended trend (KMLM + DBMF / CTA) | Single-manager risk. KMLM has had long flat stretches. |
| C5 | Return-stacked / capital-efficient core (NTSX, GDE, RSST, RSSB) plus a UPRO satellite | Leverage at lower embedded cost, without 3× daily reset. |
| C6 | Leverage sweep: equity 1.0× → 3.0× in 0.1 steps, diversifier sleeve held constant | Finds the median-maximizing leverage under today's rates. |
| C7 | Optimizer: max median (or max 10th-percentile) terminal real after-tax wealth, with constraints | The "is there a more efficient portfolio?" answer. |

Guardrail: an optimizer will overfit to 2009–2021. All optimization runs on the bootstrap distribution, with out-of-sample and high-rate regime checks.

## 6. Phase 6 — Report

- Interactive page: the allocation editor, efficient frontier (median vs 10th percentile), terminal wealth fan chart, drawdown chart, and tax comparison.
- A written recommendation with a clear verdict: keep, adjust, or replace, and why.
- A one-page "rules card": rebalance rule, drawdown conversion trigger, and the conditions under which you would *de-lever* (pre-committed, not decided in a panic).

## 7. Tech stack

- Python 3.12, `pandas`, `numpy`, `scipy`, `yfinance` / FRED / Ken French loaders, `pytest`
- `src/` engine, `notebooks/` exploration, `tests/` (cost-model and rebalance correctness, synthetic-vs-actual tracking)
- Report as a static HTML artifact

## 8. Order of work

1. ~~Answer Q1–Q5~~ ✅; Q6–Q11 open
2. Phase 1 data + calibration ← most of the honesty lives here
3. Phase 2 engine + tests
4. Phase 3 Monte Carlo
5. Phase 4 tax module
6. Phase 5 candidate runs
7. Phase 6 report + recommendation
