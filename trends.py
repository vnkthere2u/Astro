"""
trends.py — watches the live track record and flags a book/market/horizon whose hit-rate becomes statistically meaningful.

A record counts as a meaningful trend when, using only calls logged BEFORE the open (mode 'live'):
  • it has at least MIN_N independent calls (short-term calls overlap, so only every 5th is counted; long-term every 40th),
  • the 95% Wilson lower bound of its hit-rate is at least 60%, and
  • its hit-rate beats the simple benchmark (always calling whichever direction happened more often) by 5 points.
Each trend is announced once on Telegram; if it later falls below the bar, a "faded" note follows.
"""
from __future__ import annotations
import json, math
from pathlib import Path
import pandas as pd
import tracker as TR, engine as E

STATE = TR.TDIR / 'trends.json'
MIN_N = 20
STEP = {'intraday': 1, 'short': 5, 'long': 40}
HZW = {'intraday': 'Today', 'short': 'Short-term', 'long': 'Long-term'}


def wilson_lo(k, n, z=1.96):
    if n == 0: return 0.0
    p = k / n; d = 1 + z * z / n
    return ((p + z * z / (2 * n)) - z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))) / d


def records():
    df = TR.load()
    s = df[(df['mode'] == 'live') & (df.status == 'scored') & df.actual_ret.notna() & (df.actual_ret != 0)]
    out = []
    for (t, hz), g in s.groupby(['target', 'horizon']):
        g = g.sort_values('date')
        for b, nm in (('book1', 'Book 1'), ('book2', 'Book 2'), ('view', 'Combined')):
            y = g[g[b].isin(['Up', 'Down'])].iloc[::STEP[hz]]
            n = len(y)
            if n == 0: continue
            k = int(((y[b] == 'Up') == (y.actual_ret > 0)).sum())
            up = (y.actual_ret > 0).mean(); naive = max(up, 1 - up)
            out.append(dict(key=f'{t}|{hz}|{b}', target=t, horizon=hz, book=nm, k=k, n=n, p=k / n, lo=wilson_lo(k, n), naive=naive,
                            meaningful=n >= MIN_N and wilson_lo(k, n) >= 0.60 and k / n >= naive + 0.05))
    return out


def check(send):
    st = json.loads(STATE.read_text()) if STATE.exists() else {}
    msgs = []
    for r in records():
        was = st.get(r['key'], {}).get('meaningful', False)
        if r['meaningful'] and not was:
            msgs.append(f"🎯 <b>Meaningful trend found</b>\n{r['book']} · {E.TARGET_NAME[r['target']]} · {HZW[r['horizon']]}: "
                        f"right {r['k']}/{r['n']} ({r['p']:.0%}) on on-time calls — benchmark {r['naive']:.0%}, "
                        f"95% confidence it is at least {r['lo']:.0%}.")
        elif was and not r['meaningful']:
            msgs.append(f"📉 <b>Trend faded</b>\n{r['book']} · {E.TARGET_NAME[r['target']]} · {HZW[r['horizon']]}: now {r['k']}/{r['n']} ({r['p']:.0%}).")
        st[r['key']] = dict(meaningful=r['meaningful'], k=r['k'], n=r['n'])
    for m in msgs:
        if not send(m): return
    STATE.write_text(json.dumps(st, indent=0))
    print(f'trends: {len(msgs)} notification(s)')
