"""
tracker.py — the scorecard's memory.

What gets logged each trading morning (before the open, automatically):
  • the Nifty view for today / next week (every day) and next 2 months (Mondays only — it changes slowly)
  • every sector / commodity call that is ACTIONABLE: direction is Bullish or Bearish AND that kind of call
    historically beat the simple benchmark on enough independent occurrences (calib.actionable)
Neutral and 'no proven edge' calls are shown in the app but not logged — they are information, not trades.

Rows are never edited after logging. The evening job fills in what actually happened.
mode: live = logged before the open · late = logged after the open (kept, excluded from the score)
      paper = reconstructed history used as a baseline (clearly separated)
"""
from __future__ import annotations
from datetime import date, datetime, timedelta
from pathlib import Path
import numpy as np, pandas as pd
import engine as E, data_sources as ds, calib as C

HERE = Path(__file__).parent
TDIR = HERE / 'data' / 'tracker'; TDIR.mkdir(parents=True, exist_ok=True)
LOG = TDIR / 'predictions.csv'
COLS = ['logged_at', 'mode', 'date', 'target', 'name', 'horizon', 'view', 'strength', 'score', 'confidence', 'tier',
        'why', 'actual_ret', 'outcome', 'correct', 'status', 'settled_at']
HZ_SESSIONS = {'intraday': 1, 'short': 5, 'long': 40}
HZ_WORD = {'intraday': 'Today', 'short': 'Next week', 'long': 'Next 2 months'}
TEXT = ['logged_at', 'mode', 'target', 'name', 'horizon', 'view', 'strength', 'tier', 'why', 'outcome', 'status', 'settled_at']
TRACKABLE = [t for t, src in ds.PROXY.items() if src[0][2] in ('direct', 'proxy') and src[0][0] != 'yf']

def view_word(s):
    return 'Bullish' if s > E.THRESH else 'Bearish' if s < -E.THRESH else 'Neutral'
def strength_word(s):
    a = abs(s); return '—' if a <= E.THRESH else 'Mild' if a < 0.3 else 'Moderate' if a < 0.5 else 'Strong'

def _types(df):
    df = df.copy()
    for c in COLS:
        if c not in df: df[c] = np.nan
    for c in TEXT: df[c] = df[c].astype(object)
    for c in ['score', 'confidence', 'actual_ret', 'correct']: df[c] = pd.to_numeric(df[c], errors='coerce')
    df['date'] = pd.to_datetime(df['date'])
    return df[COLS]

def load() -> pd.DataFrame:
    return _types(pd.read_csv(LOG)) if LOG.exists() else _types(pd.DataFrame(columns=COLS))

def save(df):
    df.sort_values(['date', 'horizon', 'target']).to_csv(LOG, index=False)

def todays_calls(eng: E.Engine, d: date):
    """The calls the app presents as actionable for date d (plus the Nifty view)."""
    v = eng.view(d); out = []
    for hz in E.HORIZONS:
        s = v.scores['NIFTY'][hz]
        if not (hz == 'long' and d.weekday() != 0):
            out.append(('NIFTY', hz, s, C.confidence('NIFTY', hz, s)))
        for t in TRACKABLE:
            if t == 'NIFTY': continue
            s = v.scores[t][hz]; cf = C.confidence(t, hz, s)
            if C.actionable(cf): out.append((t, hz, s, cf))
    return v, out

def log_predictions(eng: E.Engine, d: date, mode='live') -> int:
    df = load()
    have = set(zip(df['date'].dt.date, df['target'], df['horizon'])) if len(df) else set()
    v, calls = todays_calls(eng, d); new = []
    for t, hz, s, cf in calls:
        if (d, t, hz) in have: continue
        drivers = sorted((c for c in v.contrib.get(t, []) if c.horizon == hz), key=lambda c: -abs(c.value))[:2]
        new.append(dict(logged_at=datetime.now().isoformat(timespec='seconds'), mode=mode, date=pd.Timestamp(d), target=t,
                        name=E.TARGET_NAME[t], horizon=hz, view=view_word(s), strength=strength_word(s), score=round(s, 4),
                        confidence=(cf or {}).get('p'), tier=(cf or {}).get('tier', '—'),
                        why=' | '.join(c.text[:90] for c in drivers), status='pending'))
    if new:
        df = _types(pd.concat([df, _types(pd.DataFrame(new))], ignore_index=True)) if len(df) else _types(pd.DataFrame(new))
        save(df)
    return len(new)

def settle(local_dir=None) -> int:
    df = load()
    if df.empty: return 0
    pend = df[df.status == 'pending']; n = 0
    for t in pend.target.unique():
        rf, meta = ds.returns_frame(t, local_dir=local_dir)
        if rf is None: continue
        idx = rf.index; last = idx.max()
        for i, row in pend[pend.target == t].iterrows():
            dt = row['date']
            if dt not in idx:
                if dt < last - pd.Timedelta(days=4): df.loc[i, 'status'] = 'market closed'
                continue
            pos = idx.get_loc(dt)
            if pos + HZ_SESSIONS[row['horizon']] - 1 >= len(idx): continue
            ret = rf.loc[dt, row['horizon']]
            if pd.isna(ret): continue
            df.loc[i, 'actual_ret'] = float(ret)
            df.loc[i, 'outcome'] = 'Up' if ret > 0 else 'Down' if ret < 0 else 'Flat'
            df.loc[i, 'correct'] = np.nan if row['view'] == 'Neutral' else float((ret > 0) == (row['view'] == 'Bullish'))
            df.loc[i, 'status'] = 'scored'; df.loc[i, 'settled_at'] = datetime.now().isoformat(timespec='seconds'); n += 1
    save(df); return n

def paper_history(eng: E.Engine, start: date, end: date, local_dir=None):
    d = start
    while d <= end:
        if d.weekday() < 5: log_predictions(eng, d, mode='paper')
        d += timedelta(days=1)
    return settle(local_dir)

def scored(df=None, modes=('live',)):
    df = load() if df is None else df
    s = df[(df.status == 'scored') & (df['mode'].isin(modes)) & df.correct.notna()].copy()
    return s

def stats(df=None, modes=('live',)) -> dict:
    s = scored(df, modes)
    if s.empty: return dict(n=0)
    out = dict(n=int(len(s)), hit=float(s.correct.mean()))
    out['by_horizon'] = {hz: dict(n=int(len(g)), hit=float(g.correct.mean()),
                                  naive=float(max((g.actual_ret > 0).mean(), (g.actual_ret < 0).mean())))
                         for hz, g in s.groupby('horizon')}
    out['actionable'] = dict(n=int((s.target != 'NIFTY').sum()), hit=float(s[s.target != 'NIFTY'].correct.mean()) if (s.target != 'NIFTY').any() else None)
    out['nifty'] = dict(n=int((s.target == 'NIFTY').sum()), hit=float(s[s.target == 'NIFTY'].correct.mean()) if (s.target == 'NIFTY').any() else None)
    return out

def running(df=None, modes=('live',)) -> pd.DataFrame:
    s = scored(df, modes)
    if s.empty: return pd.DataFrame()
    g = s.groupby('date').agg(calls=('correct', 'size'), right=('correct', 'sum')).reset_index()
    g['cumulative'] = g.right.cumsum() / g.calls.cumsum()
    return g
