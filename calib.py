"""calib.py — turns calibration.json into confidence % and expected-move projections."""
from __future__ import annotations
import json, math
from pathlib import Path
import pandas as pd
import engine as E

HERE = Path(__file__).parent
_CAL = None; _J = None
PRIOR_N = 50   # shrinkage toward 50 % (empirical-Bayes style)

def cal():
    global _CAL
    if _CAL is None:
        p = HERE / 'data' / 'calibration.json'
        _CAL = json.loads(p.read_text()) if p.exists() else {}
    return _CAL

def joined():
    global _J
    if _J is None:
        p = HERE / 'data' / 'backtest_joined.parquet'
        _J = pd.read_parquet(p) if p.exists() else pd.DataFrame()
    return _J

def bucket(s):
    a = abs(s)
    for lo, hi, name in E_BUCKETS:
        if lo <= a < hi: return name
    return None
E_BUCKETS = [(0.15, 0.30, 'weak'), (0.30, 0.50, 'moderate'), (0.50, 1.01, 'strong')]

def confidence(target: str, hz: str, score: float) -> dict | None:
    """Shrunk empirical hit-rate of calls like this one (same target, horizon, strength bucket)."""
    c = cal()
    if not c or abs(score) <= E.THRESH: return None
    b = bucket(score)
    t = c.get('targets', {}).get(target, {}).get('horizons', {}).get(hz)
    src = 'target'
    if t and t['buckets'].get(b, {}).get('n', 0) >= 30:
        k, n = t['buckets'][b]['hits'], t['buckets'][b]['n']; naive = t['all'].get('naive_hit')
    else:
        o = c.get('overall', {}).get(f'{hz}|all|{b}')
        if not o: return None
        k, n = o['hits'], o['n']; naive = None; src = 'pooled'
    p = (k + PRIOR_N / 2) / (n + PRIOR_N)
    z = 1.96; ph = k / n if n else 0.5
    d = 1 + z * z / n; cc = (ph + z * z / (2 * n)) / d; h = z * math.sqrt(ph * (1 - ph) / n + z * z / (4 * n * n)) / d
    return dict(p=round(p, 3), raw=round(ph, 3), lo=round(cc - h, 3), hi=round(cc + h, 3), n=n, bucket=b, naive=naive, source=src)

def expected_move(target: str, hz: str, score: float) -> dict | None:
    """Historical distribution of returns on days with a call in the same bucket & direction."""
    J = joined()
    if J.empty: return None
    a = J[(J.target == target) & (J.hz == hz)]
    if a.empty: return None
    if abs(score) <= E.THRESH:
        m = a[a.score.abs() <= E.THRESH]
    else:
        b = bucket(score); lo, hi = [(x, y) for x, y, n in E_BUCKETS if n == b][0]
        m = a[(a.score.abs() >= lo) & (a.score.abs() < hi) & ((a.score > 0) == (score > 0))]
    if len(m) < 20: return None
    return dict(n=int(len(m)), mean=float(m.ret.mean()), median=float(m.ret.median()), p25=float(m.ret.quantile(.25)),
                p75=float(m.ret.quantile(.75)), up=float((m.ret > 0).mean()), all_mean=float(a.ret.mean()))

def conf_fn(t, hz, s):
    return confidence(t, hz, s)
