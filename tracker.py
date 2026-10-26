"""
tracker.py — immutable prediction log + reconciliation against realised prices.

• log_predictions(): appends the engine's calls for a trading date BEFORE the outcome is known.
  Rows are never overwritten (first write wins) so the record cannot be curve-fitted afterwards.
• settle(): fills realised returns once the horizon has elapsed and the data feed has the prices.
• stats(): hit-rates (overall / by horizon / by target / rolling), vs naive majority-direction benchmark.
Storage: data/tracker/predictions.csv (plain CSV — portable, Excel-readable).
"""
from __future__ import annotations
import json, math
from datetime import date, datetime, timedelta
from pathlib import Path
import numpy as np, pandas as pd
import engine as E, data_sources as ds

HERE = Path(__file__).parent
TDIR = HERE / 'data' / 'tracker'; TDIR.mkdir(parents=True, exist_ok=True)
LOG = TDIR / 'predictions.csv'
COLS = ['logged_at', 'mode', 'date', 'target', 'horizon', 'score', 'call', 'confidence', 'naive', 'basis',
        'actual_ret', 'actual_call', 'hit', 'status', 'settled_at']
HZ_SESSIONS = {'intraday': 1, 'short': 5, 'long': 63}

def load() -> pd.DataFrame:
    if LOG.exists():
        df = pd.read_csv(LOG, parse_dates=['date'])
        for c in COLS:
            if c not in df: df[c] = np.nan
        return _types(df[COLS])
    return _types(pd.DataFrame(columns=COLS))

TEXT = ['logged_at', 'mode', 'target', 'horizon', 'call', 'basis', 'actual_call', 'status', 'settled_at']
def _types(df):
    df = df.copy()
    for c in TEXT: df[c] = df[c].astype(object)
    for c in ['score', 'confidence', 'naive', 'actual_ret', 'hit']: df[c] = pd.to_numeric(df[c], errors='coerce')
    return df

def save(df: pd.DataFrame):
    df.sort_values(['date', 'target', 'horizon']).to_csv(LOG, index=False)

def log_predictions(eng: E.Engine, d: date, conf_fn=None, mode='live', targets=None) -> int:
    df = load()
    have = set(zip(pd.to_datetime(df['date']).dt.date, df['target'], df['horizon'])) if len(df) else set()
    r = eng.day(d); new = []
    for t in (targets or (['NIFTY'] + E.SECTORS + E.COMMODITIES)):
        for hz in E.HORIZONS:
            if (d, t, hz) in have: continue
            s = r.scores[t][hz]
            cf = conf_fn(t, hz, s) if conf_fn else None
            new.append(dict(logged_at=datetime.now().isoformat(timespec='seconds'), mode=mode, date=pd.Timestamp(d), target=t, horizon=hz,
                            score=round(s, 4), call=E.rag(s), confidence=(cf or {}).get('p'), naive=(cf or {}).get('naive'),
                            basis=None, actual_ret=np.nan, actual_call=None, hit=np.nan, status='pending', settled_at=None))
    if new:
        df = _types(pd.concat([df, _types(pd.DataFrame(new, columns=COLS))], ignore_index=True) if len(df) else pd.DataFrame(new, columns=COLS))
        save(df)
    return len(new)

def settle(local_dir=None) -> int:
    df = load()
    if df.empty: return 0
    pend = df[df.status == 'pending']
    n = 0
    for t in pend.target.unique():
        rf, meta = ds.returns_frame(t, local_dir=local_dir)
        if rf is None: continue
        idx = rf.index
        for i, row in pend[pend.target == t].iterrows():
            dt = pd.Timestamp(row['date'])
            if dt not in idx:
                if dt < idx.max() - pd.Timedelta(days=5) and dt.weekday() < 5:
                    df.loc[i, 'status'] = 'no-session'
                continue
            pos = idx.get_loc(dt); need = HZ_SESSIONS[row['horizon']] - 1
            if pos + need >= len(idx): continue
            ret = rf.loc[dt, row['horizon']]
            if pd.isna(ret): continue
            df.loc[i, 'actual_ret'] = float(ret)
            df.loc[i, 'actual_call'] = 'G' if ret > 0 else 'R' if ret < 0 else 'A'
            df.loc[i, 'hit'] = np.nan if row['call'] == 'A' else float((ret > 0) == (row['call'] == 'G'))
            df.loc[i, 'basis'] = meta.get('intraday_basis') if row['horizon'] == 'intraday' else f"{HZ_SESSIONS[row['horizon']]} sessions"
            df.loc[i, 'status'] = 'settled'; df.loc[i, 'settled_at'] = datetime.now().isoformat(timespec='seconds')
            n += 1
    save(df)
    return n

def backfill(eng: E.Engine, start: date, end: date, conf_fn=None, local_dir=None):
    """Paper-trade history (clearly flagged mode='backfill') so the tracker has a baseline."""
    d = start
    while d <= end:
        if d.weekday() < 5: log_predictions(eng, d, conf_fn, mode='backfill')
        d += timedelta(days=1)
    return settle(local_dir)

def stats(df: pd.DataFrame | None = None, mode: str | None = None) -> dict:
    df = load() if df is None else df
    s = df[(df.status == 'settled') & (df.call != 'A')].copy()
    if mode: s = s[s['mode'] == mode]
    if s.empty: return dict(n=0)
    s['hit'] = s['hit'].astype(float)
    out = dict(n=int(len(s)), hit=float(s.hit.mean()))
    out['by_horizon'] = {hz: dict(n=int(len(g)), hit=float(g.hit.mean()),
                                  naive=float(max((g.actual_ret > 0).mean(), (g.actual_ret < 0).mean())))
                         for hz, g in s.groupby('horizon')}
    out['by_target'] = {t: dict(n=int(len(g)), hit=float(g.hit.mean())) for t, g in s.groupby('target')}
    out['by_call'] = {c: dict(n=int(len(g)), hit=float(g.hit.mean()), mean_ret=float(g.actual_ret.mean())) for c, g in s.groupby('call')}
    return out

def daily_accuracy(df: pd.DataFrame | None = None, horizon='intraday') -> pd.DataFrame:
    df = load() if df is None else df
    s = df[(df.status == 'settled') & (df.call != 'A') & (df.horizon == horizon)].copy()
    if s.empty: return pd.DataFrame()
    s['hit'] = s['hit'].astype(float)
    g = s.groupby('date').agg(calls=('hit', 'size'), hit=('hit', 'mean')).reset_index()
    g['cum_hit'] = (g.hit * g.calls).cumsum() / g.calls.cumsum()
    g['roll20'] = g.hit.rolling(20, min_periods=5).mean()
    return g
