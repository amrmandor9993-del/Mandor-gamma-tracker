# Gamma tracker

Logs dealer-gamma (GEX) readings for NQ, NDX, QQQ, SPX and SPY after every US close, plus QQQ daily prices.
Data lives in `data/*.csv`. The page `index.html` reads those files.

- `scripts/fetch_gamma.py` collects the day's data (ZeroGEX main source for NQ/NDX/QQQ/SPX/SPY, GEXBoard second source for NDX/QQQ, Yahoo for QQQ prices).
- `.github/workflows/daily.yml` runs it Mon-Fri: a morning snapshot (about 9:35 New York time, NQ/NDX/QQQ from ZeroGEX) and an end-of-day run (22:30 UTC). It saves the CSVs.
- If a page cannot be read, nothing is guessed: that item is skipped and the run is marked failed (GitHub emails you).

Rows from before the daily job (3 Aug to 27 Oct 2026) are regime-only, copied by hand from free newsletters (DailyMacroBrief, AdaptiveTrader, ReflectionsOfReality, moomoo, SPXGammaEdge). Each row's `notes` says which report and which day it describes. These sources use different models, so keep them separate from the ZeroGEX series when backtesting.

Modeled data, not real dealer positions. Sources are free pages and may change or block automated reads.
