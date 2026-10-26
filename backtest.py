"""
backtest.py — how often each book's call has matched the market in the past (information only).

The books' rules are applied exactly as in the live app (engine.py) to every past trading day; nothing is tuned to the
result. For each target / horizon / source (final call, Book 1, Book 2, Book 3) we count Up and Down calls that came
true. Scoring windows (a measurement convention, not part of any prediction): today = open→close;
short-term = 5 sessions; long-term = 40 sessions.

Outputs: data/calibration.json, data/verdict_history.parquet
  python backtest.py [start=2005-01-03]
"""
from __future__ import annotations
import json, math, sys, time as _t
from datetime import date, timedelta
from pathlib import Path
import numpy as np, pandas as pd
sys.path.insert(0, str(Path(__file__).parent))
import engine as E, data_sources as ds

HERE = Path(__file__).parent; DATA = HERE / 'data'
WINDOW = {'intraday': 1, 'short': 5, 'long': 40}
TRACK = [t for t, src in ds.PROXY.items() if src[0][2] in ('direct', 'proxy') and src[0][0] != 'yf']
SOURCES = ['final', 'b1', 'b2', 'b3']


def wilson(k, n, z=1.96):
    if n == 0: return (None, None, None)
    p = k / n; d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d; h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return p, max(0, c - h), min(1, c + h)


def history(start: date, end: date, eng=None):
    eng = eng or E.Engine()
    rows = []; d = start; t0 = _t.time()
    while d <= end:
        if d.weekday() < 5:
            r = eng.day(d)
            for t in TRACK:
                for hz in E.HORIZONS:
                    bv = r.book[(t, hz)]
                    rows.append((pd.Timestamp(d), t, hz, r.final[(t, hz)], bv[1], bv[2], bv[3]))
            eng._cache.clear()
        d += timedelta(days=1)
    print(f'history {start}..{end}: {len(rows)} rows in {_t.time() - t0:.0f}s')
    return pd.DataFrame(rows, columns=['date', 'target', 'horizon', 'final', 'b1', 'b2', 'b3'])


def score(H: pd.DataFrame):
    out = {}; joined = []
    for t in TRACK:
        rf, meta = ds.returns_frame(t)
        if rf is None: continue
        h = H[H.target == t]
        for hz in E.HORIZONS:
            x = h[h.horizon == hz].set_index('date').join(rf[[hz]].rename(columns={hz: 'ret'}), how='inner').dropna(subset=['ret'])
            x = x[x.ret != 0]
            base_up = float((x.ret > 0).mean()) if len(x) else None
            res = {}
            for s in SOURCES:
                y = x[x[s].isin([1, -1])]
                if y.empty: res[s] = dict(n=0); continue
                hit = ((y[s] > 0) == (y.ret > 0))
                k, n = int(hit.sum()), int(len(y))
                p, lo, hi = wilson(k, n)
                up = y[y[s] > 0]; dn = y[y[s] < 0]
                naive = max(base_up, 1 - base_up) if base_up is not None else None
                res[s] = dict(n=n, hits=k, p=p, lo=lo, hi=hi, n_eff=n // WINDOW[hz],
                              up_n=int(len(up)), up_p=float((up.ret > 0).mean()) if len(up) else None,
                              down_n=int(len(dn)), down_p=float((dn.ret < 0).mean()) if len(dn) else None,
                              naive=naive, coverage=float(len(y) / len(x)) if len(x) else 0)
            out.setdefault(t, {})[hz] = dict(meta=dict(source=meta['source'], key=meta['key'], quality=meta['quality']),
                                             base_up=base_up, days=int(len(x)), **res)
            xx = x.reset_index(); xx['target'] = t; xx['horizon'] = hz; joined.append(xx)
    return out, (pd.concat(joined) if joined else pd.DataFrame())


def book_windows(J):
    """Book 3 Ch.14 states its software was right on 16 of 23 days (14 Apr-15 May 2003) and 16 of 21 (14 Apr-15 May 2005)."""
    out = {}
    n = J[(J.target == 'NIFTY') & (J.horizon == 'intraday')]
    for a, b, claim in (('2003-04-14', '2003-05-15', '16/23 (70%)'), ('2005-04-14', '2005-05-15', '16/21 (76.2%)')):
        y = n[(n.date >= a) & (n.date <= b)]
        for s in ('b3', 'final'):
            z = y[y[s].isin([1, -1])]
            k = int(((z[s] > 0) == (z.ret > 0)).sum())
            out[f'{a}..{b}:{s}'] = dict(calls=int(len(z)), right=k, days=int(len(y)), book_claim=claim)
    return out


if __name__ == '__main__':
    start = date.fromisoformat(sys.argv[1]) if len(sys.argv) > 1 else date(2003, 1, 1)
    end = date.today()
    H = history(start, end)
    H.to_parquet(DATA / 'verdict_history.parquet', index=False)
    cal, J = score(H)
    cal['_book3_windows'] = book_windows(J) if len(J) else {}
    cal['_meta'] = dict(start=str(start), end=str(end), windows=WINDOW, generated=str(date.today()))
    (DATA / 'calibration.json').write_text(json.dumps(cal, indent=1, default=float))
    n = cal.get('NIFTY', {})
    for hz in E.HORIZONS:
        if hz in n: print(hz, {s: (n[hz][s].get('n'), round(n[hz][s]['p'], 3) if n[hz][s].get('p') else None) for s in SOURCES}, 'base_up', round(n[hz]['base_up'] or 0, 3))
    print(json.dumps(cal['_book3_windows'], indent=1))
