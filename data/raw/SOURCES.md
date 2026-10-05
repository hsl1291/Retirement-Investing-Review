Bundled fallback data (public GitHub-hosted datasets, fetched 2026-10-05):

- shiller_sp500.csv   github.com/datasets/s-and-p-500  (Robert Shiller monthly S&P 500, dividends, long rate)
- gold_monthly.csv    github.com/datasets/gold-prices   (Timothy Green / World Bank monthly gold, USD/oz)
- y10_monthly.csv     github.com/datasets/bond-yields-us-10y
- cpi_monthly.csv     github.com/datasets/cpi-us

Caveats: Shiller prices are monthly AVERAGES (understate volatility, which flatters leveraged
funds); dividends are missing after 2023-06 (filled with the last known yield); there is no
T-bill series (the app refreshes TB3MS from FRED on the user's machine, otherwise uses a crude proxy).
