"""
daily_job.py — unattended daily operation (GitHub Actions).

  python daily_job.py evening   # score today, send the evening check, log TOMORROW's calls, refresh the 12-month outlook
  python daily_job.py morning   # make sure today's calls are logged; send the morning alert (once per day)
  python daily_job.py paper     # rebuild the reconstructed baseline for the last 90 days
  python daily_job.py outlook   # rebuild data/outlook.csv only

The books' calls depend only on the sky, so the next session's calls are logged the evening before — well ahead of the
09:15 IST open even when GitHub runs a scheduled job hours late. Every alert is sent once per date, whichever
scheduled run gets there first. Rows logged after the open are marked 'late' and excluded from the score.
"""
from __future__ import annotations
import json, sys
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo
import pandas as pd
sys.path.insert(0, str(Path(__file__).parent))
import engine as E, tracker as TR, alerts as A, book2 as B2, astro_core as ac

HERE = Path(__file__).parent
IST = ZoneInfo('Asia/Kolkata')
MUHURAT_FILE = HERE / 'data' / 'muhurat.json'
OUTLOOK = HERE / 'data' / 'outlook.csv'
OPEN_IST = (9, 15)
ARW = {'Up': '🟢▲', 'Down': '🔴▼', 'Neutral': '🟡◆', 'No rule': '⚪'}
_ENG = None


def engine():
    global _ENG
    if _ENG is None:
        mu = [(date.fromisoformat(a), float(b)) for a, b in json.loads(MUHURAT_FILE.read_text())] if MUHURAT_FILE.exists() else []
        _ENG = E.Engine(muhurat=mu)
    return _ENG


def now_ist(): return datetime.now(IST)


def next_session(d: date) -> date:
    while d.weekday() >= 5: d += timedelta(days=1)
    return d


def log(d: date):
    n = now_ist()
    late = d < n.date() or (d == n.date() and (n.hour, n.minute) >= OPEN_IST)
    k = TR.log_predictions(engine(), d, mode='late' if late else 'live')
    print(f"logged {k} calls for {d}{' (late)' if late else ''}")


# ------------------------------------------------------------------ messages
def morning_text(d: date) -> str:
    r = engine().day(d); W = E.WORD
    nf = r.final[('NIFTY', 'intraday')]; bv = r.book[('NIFTY', 'intraday')]
    L = [f"🪐 <b>AstroMarket — {d:%a %d %b %Y}</b>",
         f"<b>Nifty today:</b> {ARW[TR.VIEW[nf]]} {TR.VIEW[nf]}  (Book 1 {TR.VIEW[bv[1]]} · Book 2 {TR.VIEW[bv[2]]})", '']
    for k, nm in ((1, 'Book 1 — sectors'), (2, 'Book 2 — muhurta')):
        up = [E.TARGET_NAME[t] for t in TR.TRACKABLE if t != 'NIFTY' and r.book[(t, 'intraday')][k] == 1]
        dn = [E.TARGET_NAME[t] for t in TR.TRACKABLE if t != 'NIFTY' and r.book[(t, 'intraday')][k] == -1]
        L.append(f"<b>{nm}:</b> ▲ {len(up)} up · ▼ {len(dn)} down")
        if up: L.append('  ▲ ' + ', '.join(up))
        if dn: L.append('  ▼ ' + ', '.join(dn))
    dis = [E.TARGET_NAME[t] for t in TR.TRACKABLE if r.disagree[(t, 'intraday')]]
    if dis: L.append(f"⚖️ Books disagree (shown Neutral): {', '.join(dis)}")
    b2 = r.b2
    L += ['', f"<b>Muhurta:</b> {b2['weekday']} · {b2['tithi']} · {b2['nakshatra']} · {b2['yoga']} yoga · {b2['karana']} karana"]
    for v in b2['votes']:
        if v['targets'] == 'ALL' and v['dir']: L.append(f"{'🟢' if v['dir'] > 0 else '🔴'} {v['text']}")
    o, cl = r.open_dt, r.close_dt
    win = [w for w in r.windows if w['kind'] in ('Rahu Kalam', 'Yamakandam', 'Gulika', 'Abhijit') and w['end'] > o and w['start'] < cl]
    if win:
        L += ['', '<b>Timing (Book 2):</b>'] + [f"{max(w['start'], o):%H:%M}–{min(w['end'], cl):%H:%M} {w['kind']} — {w['text']}" for w in win]
    if r.reversal: L += ['', '🔄 <b>Reversal window (Ch.34):</b> ' + '; '.join(x['text'] for x in r.reversal)]
    return '\n'.join(L)


def evening_text(d: date) -> str | None:
    df = TR.load()
    x = df[(df['date'] == pd.Timestamp(d)) & (df.horizon == 'intraday') & (df['mode'].isin(['live', 'late']))]
    if x.empty: return None
    import data_sources as ds
    nse = {t for t, v in ds.PROXY.items() if v[0][0] == 'eod2'}
    if ((x.status == 'pending') & x.target.isin(nse)).any(): return None   # NSE prices not in yet (US commodities may lag)
    s = x[x.status == 'scored']
    if s.empty: return None
    up = lambda col: s[s[col].isin(['Up', 'Down'])]
    L = [f"📊 <b>AstroMarket — close check {d:%a %d %b %Y}</b>"]
    for col, nm in (('book1', 'Book 1'), ('book2', 'Book 2'), ('view', 'Combined')):
        y = up(col)
        if len(y):
            ok = ((y[col] == 'Up') == (y.actual_ret > 0)).sum()
            L.append(f"<b>{nm}:</b> {ok}/{len(y)} right ({ok / len(y):.0%})")
        else:
            L.append(f"<b>{nm}:</b> no Up/Down calls today")
    n = s[s.target == 'NIFTY']
    if len(n):
        rr = n.iloc[0]; L.append(f"Nifty: called {rr['view']}, moved {rr['actual_ret'] * 100:+.2f}%")
    rows = []
    for _, r in s.sort_values('actual_ret', ascending=False).iterrows():
        mk = lambda v: ('✅' if (v == 'Up') == (r.actual_ret > 0) else '❌') if v in ('Up', 'Down') else '·'
        rows.append(f"{r['name'][:18]:18s} {r.actual_ret * 100:+5.2f}%  B1 {mk(r.book1)}  B2 {mk(r.book2)}")
    L += ['', '<pre>' + '\n'.join(rows) + '</pre>']
    if (x['mode'] == 'late').any(): L.append('(these calls were logged after the open, so they are excluded from the long-run score)')
    return '\n'.join(L)


# ------------------------------------------------------------------ jobs
def morning():
    d = now_ist().date()
    if d.weekday() >= 5: print('weekend'); return
    log(d)
    if A.once(f'morning:{d}'):
        if not A.send(morning_text(d)): A.unmark(f'morning:{d}')


def evening():
    import data_sources as ds
    try:
        print('NSE rows added:', ds.update_nse_ext(date(2026, 10, 24), now_ist().date()))
    except Exception as e:
        print('NSE update failed:', e)
    n = TR.settle(); s = TR.stats(modes=('live',)); p = TR.stats(modes=('paper',))
    (TR.TDIR / 'summary.json').write_text(json.dumps(dict(updated=now_ist().isoformat(timespec='minutes'), scored_now=n, live=s,
                                                          paper_baseline=p), indent=1, default=float))
    print(f'scored {n}')
    today = now_ist().date()
    for d in sorted({today - timedelta(days=i) for i in range(0, 4)}):     # catch up a missed evening
        if d.weekday() >= 5: continue
        t = evening_text(d)
        if t and A.once(f'evening:{d}'):
            if not A.send(t): A.unmark(f'evening:{d}')
    nxt = next_session(today + timedelta(days=1))
    log(nxt)
    outlook()


def outlook(days=372):
    start = now_ist().date(); end = start + timedelta(days=days)
    rows = []; eng = engine(); d = start
    while d <= end:
        if d.weekday() < 5:
            r = eng.day(d)
            for t in E.TARGETS:
                rows.append((d.isoformat(), t, r.final[(t, 'short')], r.final[(t, 'long')], r.book[(t, 'short')][1], r.book[(t, 'long')][1]))
            eng._cache.clear()
        d += timedelta(days=1)
    pd.DataFrame(rows, columns=['date', 'target', 'short', 'long', 'b1_short', 'b1_long']).to_csv(OUTLOOK, index=False)
    print(f'outlook {start}..{end}: {len(rows)} rows')


def paper(days=90):
    df = TR.load()
    if len(df): TR.save(df[df['mode'] != 'paper'])
    end = now_ist().date() - timedelta(days=1)
    print('paper baseline rebuilt;', TR.paper_history(engine(), end - timedelta(days=days), end), 'calls scored')


if __name__ == '__main__':
    mode = sys.argv[1] if len(sys.argv) > 1 else 'evening'
    {'morning': morning, 'evening': evening, 'paper': paper, 'outlook': outlook}[mode]()
