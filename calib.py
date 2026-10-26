"""calib.py — past hit-rates of each book's calls (information only; never changes or filters a prediction)."""
from __future__ import annotations
import json
from pathlib import Path

HERE = Path(__file__).parent
_CAL = None


def cal():
    global _CAL
    if _CAL is None:
        p = HERE / 'data' / 'calibration.json'
        _CAL = json.loads(p.read_text()) if p.exists() else {}
    return _CAL


def record(t, hz, source='final', d=None) -> dict | None:
    """Hit-rate of past calls of this kind. d = +1 / -1 picks the Up-only or Down-only record."""
    r = cal().get(t, {}).get(hz, {}).get(source)
    if not r or not r.get('n'): return None
    if d == 1 and r.get('up_n'): p, n = r['up_p'], r['up_n']
    elif d == -1 and r.get('down_n'): p, n = r['down_p'], r['down_n']
    else: p, n = r['p'], r['n']
    lo, hi = r['lo'], r['hi']
    if hi is not None and hi < 0.5: label = 'worse than chance so far'
    elif lo is not None and lo > 0.5 and p >= (r.get('naive') or 0.5): label = 'better than chance so far'
    else: label = 'not distinguishable from chance'
    return dict(p=p, n=n, all_p=r['p'], all_n=r['n'], lo=lo, hi=hi, naive=r.get('naive'), label=label)


def pct(t, hz, source='final', d=None):
    r = record(t, hz, source, d)
    return None if r is None else round(100 * r['p'])
