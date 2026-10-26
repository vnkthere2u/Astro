"""
engine.py — combines the three books, strictly as written.

  Book 1  Stock Market Astrology (2009)          → sectors & commodities, intraday / short / long; Nifty long (Ch.16, 19)
  Book 2  Investment Muhurtas (2014)             → the day's auspiciousness → market & every sector intraday;
                                                    timing windows; trend-reversal windows (Ch.34)
  Book 3  Predicting the Nifty & Sensex          → Nifty intraday (Ch.14 method), Nifty short / long (Ch.1),
                                                    sector short-term (Sun-transit paragraphs)

Combination — the only convention the app adds, because the books never say how to merge their votes:
  • inside one book: count its Up and Down votes for that target & horizon; more Up → Up, more Down → Down,
    equal → Neutral.  (No weights, no scores, no smoothing.)
  • across books: the same count over the books that gave a direction. If one book says Up and another Down the
    call is Neutral and flagged "books disagree".
Every vote keeps its chapter reference and the book's words, so each call can be traced.
"""
from __future__ import annotations
import json
from dataclasses import dataclass, field
from datetime import datetime, date, time, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo
import astro_core as ac, book1 as B1, book2 as B2, book3 as B3

HERE = Path(__file__).parent
RB = B1.RB
SECTORS = [s for s, _ in RB['sectors']]
COMMODITIES = [c for c, _ in RB['commodities']]
TARGET_NAME = {**dict(RB['sectors']), **dict(RB['commodities']), 'NIFTY': 'Nifty 50 (market)'}
EQUITY = set(SECTORS)
HORIZONS = ['intraday', 'short', 'long']
HZ_WORD = {'intraday': 'Today', 'short': 'Short-term', 'long': 'Long-term'}
WORD = {1: 'Up', -1: 'Down', 0: 'Neutral', None: '—'}
TARGETS = ['NIFTY'] + SECTORS + COMMODITIES
CONTRA = json.loads((HERE / 'data' / 'contradictions.json').read_text()) if (HERE / 'data' / 'contradictions.json').exists() else []


def count(dirs):
    u = sum(1 for d in dirs if d == 1); n = sum(1 for d in dirs if d == -1)
    if not u and not n: return 0 if dirs else None
    return 1 if u > n else -1 if n > u else 0


@dataclass
class DayResult:
    d: date
    exchange: str
    open_dt: datetime
    close_dt: datetime
    chart_open: ac.Chart
    hits: list                         # every vote: dict(target, horizon, dir, book, chapter, text)
    book: dict                         # (target, horizon) -> {1: dir|None, 2: …, 3: …}
    final: dict                        # (target, horizon) -> dir|None
    disagree: dict                     # (target, horizon) -> bool
    b3: dict                           # Book 3 Ch.14 detail
    b2: dict                           # Book 2 day detail
    windows: list                      # Book 2 timing windows
    hora: list                         # Book 1 Ch.10 horā rows
    dasha: list                        # Book 1 Ch.12 micro-daśā rows
    reversal: list                     # Book 2 Ch.34
    regime: dict                       # Book 1 Ch.16
    flags: list

    def call(self, t, hz): return self.final.get((t, hz))
    def votes(self, t, hz, book=None):
        return [h for h in self.hits if h['target'] == t and h['horizon'] == hz and (book is None or h['book'] == book)]


class Engine:
    def __init__(self, exchange='NSE/BSE Mumbai', muhurat: list | None = None, birth_nak: int | None = None):
        ex = ac.EXCHANGES[exchange]
        self.exchange = exchange; self.lat, self.lon, self.tz = ex['lat'], ex['lon'], ex['tz']
        self.open_t, self.close_t = ex['open'], ex['close']
        self.muhurat = sorted(muhurat or [], key=lambda x: x[0]); self.birth_nak = birth_nak
        self._cache = {}

    def raw(self, d):            # kept for callers of the previous API
        return self.day(d)

    def day(self, d: date) -> DayResult:
        if d in self._cache: return self._cache[d]
        z = ZoneInfo(self.tz)
        o = datetime.combine(d, self.open_t, z); cl = datetime.combine(d, self.close_t, z)
        c = ac.chart(o, self.lat, self.lon)
        H = B1.Hits(); flags = []
        ecl_today = any(mx.astimezone(z).date() == d for _, mx in ac.eclipse_times(d.year))
        # ---------------- Book 1
        B1.ch6(c, H); B1.ch7(c, H, flags, ecl_today); B1.ch8(c, H); B1.ch11_14(c, H)
        regime = B1.ch16_19_20(c, d, H, self.muhurat); B1.ch17(c, H); B1.ch18(c, H)
        hits = list(H)
        # ---------------- Book 2
        b2 = B2.day(d, c, self.lat, self.lon, self.tz, self.birth_nak)
        for v in b2['votes']:
            tg = TARGETS if v['targets'] == 'ALL' else v['targets']
            for t in tg: hits.append(dict(target=t, horizon='intraday', dir=v['dir'], book=2, chapter=v['factor'], text=v['text']))
        # ---------------- Book 3
        b3 = B3.intraday(c)
        hits.append(dict(target='NIFTY', horizon='intraday', dir=b3['dir'], book=3, chapter='Ch.14 method',
                         text=' '.join(b3['steps'])))
        for dd, txt in B3.short_term(c): hits.append(dict(target='NIFTY', horizon='short', dir=dd, book=3, chapter='Ch.1', text=txt))
        for dd, txt in B3.long_term(c): hits.append(dict(target='NIFTY', horizon='long', dir=dd, book=3, chapter='Ch.1', text=txt))
        tbs = {s: RB['ch7'][[i for i, e in enumerate(RB['ch7']) if e['graha'] == 'Su' and e['rasi'] == s][0]]['targets'] for s in range(12)}
        for tg, dd, txt in B3.sector_short(c, tbs):
            for t in tg: hits.append(dict(target=t, horizon='short', dir=dd, book=3, chapter='Sun-transit paragraph', text=txt))
        # ---------------- combine
        book, final, dis = {}, {}, {}
        idx = {}
        for h in hits: idx.setdefault((h['target'], h['horizon'], h['book']), []).append(h['dir'])
        for t in TARGETS:
            for hz in HORIZONS:
                bv = {k: count(idx.get((t, hz, k), [])) for k in (1, 2, 3)}
                # Book 3's intraday Nifty call is one method-level result (the Ch.14 conclusion), not a count
                if t == 'NIFTY' and hz == 'intraday': bv[3] = b3['dir']
                book[(t, hz)] = bv
                dirs = [x for x in bv.values() if x in (1, -1)]
                final[(t, hz)] = count(dirs) if dirs else (0 if any(x == 0 for x in bv.values()) else None)
                dis[(t, hz)] = (1 in dirs and -1 in dirs)
        res = DayResult(d, self.exchange, o, cl, c, hits, book, final, dis, b3, b2,
                        B2.windows(d, self.lat, self.lon, self.tz), B1.hora_windows(d, self.lat, self.lon, self.tz, o, cl, c),
                        B1.dasha_windows(c, o, cl), B2.reversal_window(c), regime, flags)
        if len(self._cache) > 4000: self._cache.clear()
        self._cache[d] = res
        return res

    def frame(self, start: date, end: date, targets=None):
        """Weekday DataFrame: index date, columns (target, horizon) → +1 / -1 / 0 / NaN (no rule)."""
        import pandas as pd, numpy as np
        days = [x for x in (start + timedelta(days=i) for i in range((end - start).days + 1)) if x.weekday() < 5]
        targets = targets or TARGETS
        data = {(t, hz): [] for t in targets for hz in HORIZONS}
        for x in days:
            r = self.day(x)
            for t in targets:
                for hz in HORIZONS:
                    v = r.final[(t, hz)]; data[(t, hz)].append(np.nan if v is None else v)
        df = pd.DataFrame(data, index=pd.to_datetime(days)); df.columns = pd.MultiIndex.from_tuples(df.columns)
        return df


def is_trading_day(d: date, holidays: set | None = None) -> bool:
    return d.weekday() < 5 and (not holidays or d not in holidays)
