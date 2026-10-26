# AstroMarket Terminal
A rule engine, live dashboard and Excel workbook built from Indrodeep Banerjee, *Stock Market Astrology* (2009).

## How it runs (automated, nothing to do on most days)
| When (Mon–Fri) | What happens | Where |
|---|---|---|
| 08:00 IST / 06:30 Dubai | GitHub Action `AstroMarket daily` logs today's calls for Nifty, 31 sectors and 10 commodities × 3 horizons, with confidence %, and commits them | `data/tracker/predictions.csv` |
| 20:00 IST / 18:30 Dubai | The same Action downloads the latest closing prices and settles every pending call (hit or miss) | `predictions.csv`, `data/tracker/summary.json` |
| Sunday | Rebuilds the 12-month Excel workbook | `AstroMarket_Workbook.xlsx` |

Every call is committed **before** the market opens, so the commit history is a timestamped, tamper-evident track record. To trigger a run manually, go to **Actions → AstroMarket daily → Run workflow** (mode `morning`, `evening`, `weekly` or `all`).

## Dashboard (Streamlit Community Cloud, free)
1. Go to **share.streamlit.io** and sign in with GitHub as `vnkthere2u`; authorise access to private repos when prompted.
2. Click **Create app → Deploy a public app from GitHub**, then set repository `vnkthere2u/astro`, branch `main`, main file `app.py`, and Python 3.12 under *Advanced settings*.
3. Click **Deploy**. You get a URL like `https://<name>.streamlit.app`. You can restrict viewers under *Settings → Sharing*.

The app redeploys automatically whenever the Action commits. Treat it as read-only: its "Log" and "Settle" buttons write to the cloud container's temporary disk, which is wiped on restart. The Action is the system of record.

## Will anything sleep or lose data?
- **The dashboard** (Streamlit Cloud) goes to sleep after a period with no visitors. Opening the link wakes it in about 30 seconds. It holds no data of its own, so nothing is lost.
- **The record** lives in this GitHub repo, and the GitHub Action writes it, not the app. If GitHub delays a morning run past the 09:15 IST open, those calls are kept but marked *late* and excluded from the score, so a delay can never flatter the record. A missed evening run is caught up by the next one: every pending call is scored once its prices exist.
- **Price-feed lag:** NSE data usually appears the same evening. US crude and gas data can lag 2–4 days, so those calls show "awaiting outcome" a little longer.
- **Limits:** this uses about 70 of the 2,000 free Action minutes per month. GitHub only pauses scheduled jobs in *public* repos after 60 days without activity; this repo is private and the bot commits daily.

## Your daily routine (≈3 minutes)
1. **Before 09:15 IST, open Today.**
   - Read the three Nifty views (Today / Next week / Next 2 months).
   - Read the business-cycle note.
   - Look at **Actionable calls**. These are the only calls with a historical edge, and many days there are none, by design.
   - Use **Best timing** to pick entry and exit windows.
2. **Nothing to log or settle.** The 08:00 IST job records the calls and the 20:00 IST job scores them.
3. **Once a week:** open **Scorecard** to see live accuracy vs coin-flip and benchmark, and **12-month outlook** for upcoming turning points.
4. **Each Diwali:** add the Muhurat result to `data/muhurat.json`, for example `["2026-11-08", 250]`.

## The pages
| Page | What it answers |
|---|---|
| Today | What's the view now, what's actionable, when to time it, why |
| Month view | Day-by-day boxes for every sector and commodity |
| 12-month outlook | How long each 2-month view lasts; month-by-month heat-map; cycle backdrop |
| Look ahead | The call for any future date or month, with the typical historical move |
| Scorecard | Were the calls right? (automatic) |
| About & settings | Plain-English method, evidence, advanced settings, downloads |

**Horizons:** *Today* = that session. *Next week* = average reading over the next 5 sessions. *Next 2 months* = average over the next 40 sessions; the Moon is excluded from this one, so it only changes on slow-planet events. Typical durations are 1–4 months for the 2-month view and 2–5 weeks for the next-week view.

**What gets tracked:** the Nifty view (daily; the 2-month view on Mondays), plus any *actionable* call. Actionable means Bullish or Bearish, on a sector or commodity with a reliable price series, where that call type has beaten both a coin-flip and the simple benchmark on at least 30 independent past occurrences. Expect about 2–5 rows a day.

## Running it locally instead
```bash
pip install -r requirements.txt
streamlit run app.py                 # dashboard at http://localhost:8501
python daily_job.py morning          # log today's calls
python daily_job.py evening          # settle
python daily_job.py weekly           # rebuild workbook
python backtest.py                   # refresh backtest & confidence (~1 min)
python validate.py                   # re-run the source-validation suite
```

## What is computed (every rule traceable to the book)
| Book | Rule family | Horizon | Implementation |
|---|---|---|---|
| Ch.4–5 | Graha / rāśi significations, friendships, dignities | mapping | `rulebook.json` → `ch4`, `ch5` |
| Ch.6 | 30 sectors × kārakas × trigger rāśis/nakṣatras (180 statements) | Candra→intraday, Sūrya→short, Guru→long | parsed from text |
| Ch.7 | 12 grahas × 12 rāśis with aspect conditions (144) plus general rules 1–17 (dignity, retrograde, kartari, crowding, eclipse) | by graha speed | parsed + modifiers |
| Ch.8 | 27 nakṣatra-lord rules with Candra confirmation | intraday | parsed |
| Ch.9 | Aspects | all | calibrated (see validation) |
| Ch.10 | Horā strategy (60-minute horās from sunrise, Fig.1) | intraday + timing | |
| Ch.11–14 | Opening-bell chart: lagna + 12 grahas × 12 bhāvas (144) | intraday | encoded table |
| Ch.12 | Micro-viṃśottarī daśā from Candra at the opening bell | timing | reproduces the book's worked example to the second |
| Ch.16 | Business cycle: Śani element × Guru aspect (3° trigger orb) | long | |
| Ch.17 | Gold: Guru dignity, combustion, Sūrya/Candra aspects, Guru–node conjunction or separation | short / long | |
| Ch.18 | Crude: Śani–node conjunction or separation, fiery/watery placement | short / long | |
| Ch.19 | Dīpāvali Muhurat | annual bias | user input |
| Ch.20 | Stocks ↔ gold rotation in a recession regime | long | |

Each rule adds a signed contribution (−1…+1 scale) to the sectors and commodities it names. Contributions are summed per horizon and squashed with tanh to a score from −1 to +1. A score above +0.15 is UP (green), below −0.15 is DOWN (red), and anything between is NEUTRAL (amber); the threshold is adjustable. Every score can be decomposed into its rule-by-rule drivers ("Why?").

## Source selection (your 100% match requirement)
Ten ephemeris configurations (Lahiri, Raman, KP, Fagan-Bradley, Tropical × true/mean node) were run through 36 hard tests taken from facts printed in the book: dated positions, nakṣatras, aspect windows, ingress months, the 7 historical and 5 forecast recession placements, the gold and crude conjunctions, and the worked horā and daśā examples. **Swiss Ephemeris + Lahiri + true node is the only configuration that passes 36/36.** Tropical passes 11/36.

The two soft failures are errors in the book itself: it places Jupiter–Ketu in Vṛṣabha in 1948, which no zodiac can reproduce, and its 05:52 sunrise matches neither Mumbai nor Lucknow.

The book's daily aspect lists contradict each other in 4 places, so no consistent rule can match all of them. The adopted rule (Vedic graha-dṛṣṭi plus trine within classical orbs) gets 23 of the 24 listed aspects.

The price feeds are NSE index EOD data via GitHub `BennyThadikaran/eod2_data` (compiled from NSE bhavcopies, updated daily) and EIA crude/gas via `datasets/*`. They pass integrity checks for OHLC consistency, gaps and duplicates. When Yahoo Finance is reachable, the app also cross-checks them against it.

## What the backtest says (read this)
2012-02-21 → 2026-10-23, threshold ±0.15:

| Horizon | Directional hit-rate (direct-quality series) | Naive majority call |
|---|---|---|
| Intraday (open→close) | **50.5%** (95% CI 50.0–51.0, n = 34,257) | 53.5% |
| Short (5 sessions) | **50.0%** | 51.6% |
| Long (63 sessions) | **47.1%** | ≈ 60% (markets mostly rose) |

- **Out-of-sample** (2020+) results are no better than in-sample (2012–19).
- **Walk-forward re-weighting** of rule families (fit 2012–19, test 2020+) adds no robust edge (`data/walkforward.json`).
- **Long-run tests:**
  - Gold cycle, 1971+: 58.5% 12-month hit vs 61.5% naive.
  - Crude cycle, 1986+: 44%.
  - Business cycle, S&P 500 since 1871: the only directionally consistent result. "Recession, triggered" months were followed by −4.5% average 12-month returns vs +6.5% for all months. That's about 40 months, i.e. only a handful of independent episodes.
- **The book's own forecasts:** crude "> $250" in 2013–14 (actual: fell to $45), and the 2017–18 "recession" (actual: Nifty +29% in 2017, +3% in 2018).

The **confidence %** shown next to every call is the shrunk empirical hit-rate of comparable past calls (same target, horizon and strength bucket), shown with its naive benchmark. Expect values near 50%. That's the honest number.

## Files
`astro_core.py` ephemeris, aspects, horā, daśā, lagna · `extract_rules.py` → `data/rulebook.json` · `engine.py` rule application and action plan · `validate.py` source-selection tests · `data_sources.py` feeds · `backtest.py` / `walkforward.py` / `calib.py` confidence · `tracker.py` prediction log · `app.py` dashboard · `build_excel.py` workbook.

Mapping of sectors without an NSE index is listed in `data_sources.PROXY` and marked direct, proxy or weak. Treat weak-proxy accuracy as indicative only.

*Research and educational tool, not investment advice.*
