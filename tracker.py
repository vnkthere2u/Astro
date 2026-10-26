"""
tracker.py — the scorecard's memory.

Every trading morning (before the open, automatically) the job logs the books' call for every tracked market,
for all three horizons, exactly as the app shows it — including Neutral calls — together with each book's own
verdict. Nothing is filtered by past accuracy. Rows are never edited; the evening job fills in what happened.
Neutral calls are kept in the log but have no right/wrong (they are excluded from hit-rates).

mode: live = logged before the open · late = logged after the open (kept, excluded from the score)
      paper = reconstructed history (baseline, shown separately)
Scoring windows: today = open→close, short-term = 5 sessions, long-term = 40 sessions.
"""
from __future__ import annotations
from datetime import date, datetime, timedelta
from pathlib import Path
import numpy as np, pandas as pd
import engine as E, data_sources as ds, calib as C

HERE = Path(__file__).parent
TDIR = HERE / 'data' / 'tracker'; TDIR.mkdir(parents=True, exist_ok=True)
LOG = TDIR / 'predictions.csv'
COLS = ['logged_at', 'mode', 'date', 'target', 'name', 'horizon', 'view', 'book1', 'book2', 'book3', 'disagree',
        'past_hit_pct', 'why', 'actual_ret', 'outcome', 'correct', 'status', 'settled_at']
HZ_SESSIONS = {'intraday': 1, 'short': 5, 'long': 40}
HZ_WORD = {'intraday': 'Today', 'short': 'Short-term', 'long': 'Long-term'}
TEXT = ['logged_at', 'mode', 'target', 'name', 'horizon', 'view', 'book1', 'book2', 'book3', 'why', 'outcome', 'status', 'settled_at']
TRACKABLE = [t for t, src in ds.PROXY.items() if src[0][2] in ('direct', 'proxy') and src[0][0] != 'yf']
VIEW = {1: 'Up', -1: 'Down', 0: 'Neutral', None: 'No rule'}


def _types(df):
    df = df.copy()
    for c in COLS:
        if c not in df: df[c] = np.nan
    for c in TEXT: df[c] = df[c].astype(object)
    for c in ['past_hit_pct', 'actual_ret', 'correct']: df[c] = pd.to_numeric(df[c], errors='coerce')
    df['disagree'] = df['disagree'].astype(object)
    df['date'] = pd.to_datetime(df['date'])
    return df[COLS]


def load() -> pd.DataFrame:
    if not LOG.exists(): return _types(pd.DataFrame(columns=COLS))
    df = pd.read_csv(LOG)
    if 'book1' not in df.columns:        # log from the earlier (score-based) version → archive it, start clean
        LOG.rename(TDIR / 'predictions_v1_archive.csv')
        return _types(pd.DataFrame(columns=COLS))
    return _types(df)


def save(df):
    df.sort_values(['date', 'horizon', 'target']).to_csv(LOG, index=False)


def todays_calls(eng: E.Engine, d: date):
    r = eng.day(d); out = []
    for t in TRACKABLE:
        for hz in E.HORIZONS:
            out.append((t, hz, r.final[(t, hz)], r.book[(t, hz)], r.disagree[(t, hz)]))
    return r, out


def log_predictions(eng: E.Engine, d: date, mode='live') -> int:
    df = load()
    have = set(zip(df['date'].dt.date, df['target'], df['horizon'])) if len(df) else set()
    r, calls = todays_calls(eng, d); new = []
    for t, hz, f, bv, dis in calls:
        if (d, t, hz) in have: continue
        votes = [h for h in r.votes(t, hz) if h['dir'] in (1, -1)]
        why = ' | '.join(f"B{h['book']} {h['chapter']}: {h['text'][:80]}" for h in votes[:3])
        new.append(dict(logged_at=datetime.now().isoformat(timespec='seconds'), mode=mode, date=pd.Timestamp(d), target=t,
                        name=E.TARGET_NAME[t], horizon=hz, view=VIEW[f], book1=VIEW[bv[1]], book2=VIEW[bv[2]], book3=VIEW[bv[3]],
                        disagree=bool(dis), past_hit_pct=C.pct(t, hz, 'final', f), why=why, status='pending' if f in (1, -1) else 'no call'))
    if new:
        nd = _types(pd.DataFrame(new))
        df = _types(pd.concat([df, nd], ignore_index=True)) if len(df) else nd
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
            df.loc[i, 'correct'] = float((ret > 0) == (row['view'] == 'Up')) if ret != 0 else np.nan
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
    return df[(df.status == 'scored') & (df['mode'].isin(modes)) & df.correct.notna()].copy()


def stats(df=None, modes=('live',)) -> dict:
    s = scored(df, modes)
    if s.empty: return dict(n=0)
    out = dict(n=int(len(s)), hit=float(s.correct.mean()))
    out['by_horizon'] = {hz: dict(n=int(len(g)), hit=float(g.correct.mean()),
                                  naive=float(max((g.actual_ret > 0).mean(), (g.actual_ret < 0).mean())))
                         for hz, g in s.groupby('horizon')}
    out['nifty'] = {hz: dict(n=int(len(g)), hit=float(g.correct.mean())) for hz, g in s[s.target == 'NIFTY'].groupby('horizon')}
    by_book = {}
    for b in ('book1', 'book2', 'book3'):
        x = s[s[b].isin(['Up', 'Down'])]
        if len(x): by_book[b] = dict(n=int(len(x)), hit=float(((x[b] == 'Up') == (x.actual_ret > 0)).mean()))
    out['by_book'] = by_book
    return out


def running(df=None, modes=('live',)) -> pd.DataFrame:
    s = scored(df, modes)
    if s.empty: return pd.DataFrame()
    g = s.groupby('date').agg(calls=('correct', 'size'), right=('correct', 'sum')).reset_index()
    g['cumulative'] = g.right.cumsum() / g.calls.cumsum()
    return g
