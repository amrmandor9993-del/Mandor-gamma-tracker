# Gamma tracker

Logs dealer-gamma (GEX) readings for NQ, NDX, QQQ, SPX and SPY after every US close, plus QQQ daily prices.
Data lives in `data/*.csv`. The page `index.html` reads those files.

- `scripts/fetch_gamma.py` collects the day's data (ZeroGEX main source for NQ/NDX/QQQ/SPX/SPY, GEXBoard second source for NDX/QQQ, Yahoo for QQQ prices).
- `.github/workflows/daily.yml` runs it Mon-Fri at 22:30 UTC and saves the CSVs.
- If a page cannot be read, nothing is guessed: that item is skipped and the run is marked failed (GitHub emails you).

Modeled data, not real dealer positions. Sources are free pages and may change or block automated reads.
