# Retirement Investing Review

A portfolio tester and tax model for a leveraged Traditional IRA (UPRO/KMLM/UGL/TMF 70/10/10/10).
See [ROADMAP.md](ROADMAP.md).

```
pip install numpy pandas scipy pytest
python -m pytest            # engine + tax tests
python scripts/roth_analysis.py
```

`src/irasim/`
- `funds.py`: ETF definitions (leverage, expense ratio, financing spread)
- `engine.py`: leveraged-fund synthesis, rebalancing (calendar, band, none), metrics
- `montecarlo.py`: block bootstrap; grid optimizer (median / Kelly / p10 / mean objectives)
- `tax.py`: 2026 brackets, RMDs (age 75), pro-rata, Roth-conversion strategy simulation
