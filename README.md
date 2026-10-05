# Leveraged IRA Review

A local app for reviewing a leveraged Traditional-IRA portfolio (UPRO / KMLM / UGL / TMF) held to
retirement: historical backtest, Monte Carlo to age 70, portfolio optimizer, and the tax side
(backdoor Roth pro-rata, Roth conversions, RMDs). Runs on your computer; nothing is uploaded.
Roadmap: [ROADMAP.md](ROADMAP.md). **Modeling tool, not tax or investment advice.**

## Install (from the ZIP)

1. Install **Python 3.11 or newer** from <https://www.python.org/downloads/>
   (Windows: tick *Add python.exe to PATH*).
2. On GitHub: **Code → Download ZIP** (make sure the branch selector shows the branch you want),
   then unzip anywhere.
3. Run the installer once:
   - Windows: double-click **install.bat**
   - Mac/Linux: `./install.sh`
   It creates a private environment, installs dependencies, and downloads live market data.
4. Start the app: **run.bat** (Windows) or `./run.sh` (Mac/Linux). It opens in your browser.

## Updates

Every start, the launcher checks GitHub and installs the newest version of the app (zip installs
download the branch zip; git clones run `git pull --ff-only`). Your saved settings and data live
in `user/` and are never overwritten. You can also check or apply updates from the app
(**Data and Updates**), or switch the tracked repo/branch there.

- Private repo? Add a GitHub token under *Update settings* (or `user/config.json`).
- Auto-update runs code from the tracked branch on your machine: only track a repo you control.
- Skip updating for one run: `run.bat --no-update` / `./run.sh --no-update`.

## Develop

```
pip install -r requirements.txt pytest
python -m pytest                 # engine, tax, updater, and headless smoke tests of every page
python run.py --no-update        # start the app
```

`src/irasim/`: `funds.py` (ETF definitions) · `engine.py` (leveraged-fund synthesis, rebalancing, metrics) ·
`montecarlo.py` (block bootstrap, optimizer) · `tax.py` (2026 brackets, RMDs, pro-rata, conversions) ·
`data.py` / `live.py` (market data) · `updater.py` · `ui.py`. Pages are in `app/`.

## Data caveats

Without a live refresh the app uses bundled public data with a crude T-bill proxy and monthly-average
S&P prices; leverage looks better than it is. The app shows a banner while in that mode.
The KMLM sleeve is an illustrative trend proxy until a real series is added.
