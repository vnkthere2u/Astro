# AstroMarket
A rule engine and live dashboard that apply, strictly as written, the rules of three books by Indrodeep Banerjee:

| | Book | Drives |
|---|---|---|
| B1 | *Stock Market Astrology* (2009) | sectors & commodities on all horizons; Nifty long-term (Ch.16 business cycle, Ch.19 Muhurat); horā timing |
| B2 | *Investment Muhurtas* (2014) | the day's muhurta for the market and every sector; Rahu Kalam / Yamakandam / Gulika / Gouri / Chaughadia / Durmuhurta / Abhijit; trend-reversal windows (Ch.34) |
| B3 | *Predicting the Nifty & Sensex* | Nifty today by the Ch.14 method; Nifty short/long (Ch.1); sector short-term (Sun-transit paragraphs) |

Every vote is Up / Down / Neutral with its chapter and the book's words. Inside a book: more Up → Up, more Down → Down,
equal → Neutral. Across books: same count; Up vs Down → Neutral, flagged "books disagree". No weights, scores, smoothing
or accuracy filters. Contradictions between and inside the books are listed in `data/contradictions.json` and on the
*The books & rules* page.

## Runs by itself
| When | What | Where |
|---|---|---|
| Mon–Fri 08:00 IST | logs the books' call for every tracked market × 3 horizons (all calls, whatever their past accuracy) | `data/tracker/predictions.csv` |
| Mon–Fri 20:00 IST | scores every call whose horizon has ended | same file + `summary.json` |
| every 3 hours | opens the Streamlit app in a headless browser and presses "wake up" if it is asleep | `.github/workflows/keepalive.yml` |

The keep-alive job reads the app address from `data/app_url.txt` (or the `APP_URL` repository variable).

## Files
- `astro_core.py` — Swiss Ephemeris, Lahiri, true node; panchanga (tithi, yoga, karana, lunar month, avasthā)
- `book1.py`, `book2.py`, `book3.py` — each book's rules; `engine.py` — combination
- `data/rulebook.json` (Book 1), `data/book3_rules.json` (Book 3 tables, parsed by `tools/parse_book3.py`)
- `validate.py` — 80/80 dated positions from the three books; 27/27 worked examples (Book 3 Ch.14, Book 2 Ch.34)
- `backtest.py` — historical hit-rates (information only)

```bash
pip install -r requirements.txt
streamlit run app.py
python daily_job.py morning | evening | paper
python validate.py ; python backtest.py
```
