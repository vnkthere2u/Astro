"""
insights.py — turns the books' calls into plain-language takeaways (the planets stay in the background).

Every sentence is derived only from the engine's Book 1 / Book 2 calls and the book rules they come from:
  market tone · sectors in favour / out of favour · where the books disagree · gold & silver · trend-reversal
  windows · times to avoid · business-cycle stance · coming shifts in the short/long-term outlook.
"""
from __future__ import annotations
from datetime import date, timedelta
import pandas as pd
import engine as E

N = E.TARGET_NAME
COMMOD = set(E.COMMODITIES)
SHORTNAME = {'Banking & financial': 'Banks', 'Crude oil & gas': 'Oil & gas', 'Gov. public sector units (PSU)': 'PSUs',
             'Media & entertainment': 'Media', 'Gems & jewelry': 'Jewellery', 'Iron & steel': 'Steel', 'Health care': 'Healthcare',
             'Pharmaceutical': 'Pharma', 'Automobile': 'Auto', 'Infrastructure': 'Infra', 'Capital goods': 'Capital goods',
             'Nifty 50 (market)': 'Nifty', 'Wheat / food grains': 'Food grains', 'Sugar (commodity)': 'Sugar (raw)',
             'Essential oils & perfumeries': 'Essential oils', 'Agriculture & agro industries': 'Agri', 'Leather & footwear': 'Leather',
             'Travel & tourism': 'Travel', 'Telecommunication': 'Telecom', 'Educational': 'Education'}
nm = lambda t: SHORTNAME.get(N[t], N[t])


def _join(xs, k=6):
    xs = list(xs)
    if not xs: return ''
    return ', '.join(xs[:k]) + (f' +{len(xs) - k} more' if len(xs) > k else '')


def daily(r, tracked=None) -> list[dict]:
    """[{icon, title, text, tone}] — tone: up / down / neutral / info / warn."""
    out = []
    sect = [t for t in (tracked or E.TARGETS) if t != 'NIFTY']
    f = lambda t, hz='intraday': r.final[(t, hz)]
    # 1. market tone today
    nifty = f('NIFTY'); ups = [t for t in sect if f(t) == 1]; dns = [t for t in sect if f(t) == -1]
    b2 = r.book[('NIFTY', 'intraday')][2]
    if nifty == 1: tone, head = 'up', 'Positive day expected'
    elif nifty == -1: tone, head = 'down', 'Weak day expected'
    else: tone, head = 'neutral', 'Mixed day expected'
    breadth = f"{len(ups)} of {len(sect)} markets lean up, {len(dns)} lean down."
    why = {1: 'The day is auspicious for buying (Book 2).', -1: 'The day is inauspicious — selling / profit-booking day (Book 2).',
           0: 'Good and bad factors of the day cancel out (Book 2).'}.get(b2, '')
    out.append(dict(icon='📈' if tone == 'up' else '📉' if tone == 'down' else '⚖️', title=head, text=f"{why} {breadth}", tone=tone))
    # 2. sectors in / out of favour today
    if ups: out.append(dict(icon='🟢', title='In favour today', text=_join(nm(t) for t in ups if t not in COMMOD), tone='up'))
    if dns: out.append(dict(icon='🔴', title='Out of favour today', text=_join(nm(t) for t in dns if t not in COMMOD), tone='down'))
    split = [t for t in sect if r.disagree[(t, 'intraday')]]
    if split: out.append(dict(icon='⚖️', title='Books disagree — stay light', text=_join(nm(t) for t in split), tone='neutral'))
    # 3. gold & silver
    for g in ('GOLD', 'SILVER'):
        s, l, d = f(g, 'short'), f(g, 'long'), f(g)
        if l == 1 and s != -1: out.append(dict(icon='🥇' if g == 'GOLD' else '🥈', title=f"{nm(g)} set to shine", text='Positive in the long term' + (' and short term.' if s == 1 else '.'), tone='up'))
        elif l == -1 and s != 1: out.append(dict(icon='🥇' if g == 'GOLD' else '🥈', title=f"{nm(g)} under pressure", text='Negative in the long term' + (' and short term.' if s == -1 else '.'), tone='down'))
        elif d in (1, -1): out.append(dict(icon='🥇' if g == 'GOLD' else '🥈', title=f"{nm(g)} today: {'up' if d == 1 else 'down'}", text='No clear multi-day signal.', tone='up' if d == 1 else 'down'))
    # 4. trend reversal
    rv = r.reversal
    if rv:
        short = [x for x in rv if x['short']]
        if short:
            buyday = next((v['dir'] for v in r.b2['votes'] if v['factor'].startswith('Nakshatra (Ch.5')), 0)
            act = ('A buying day — after a fall this is the book\'s entry point for longs.' if buyday > 0 else
                   'A selling day — after a rise this is the book\'s point to book profits / go short.' if buyday < 0 else '')
            out.append(dict(icon='🔄', title='Trend reversal window (short term)', text=f"The current short-term trend may turn around this week. {act}", tone='warn'))
        else:
            out.append(dict(icon='🔄', title='Slow trend may be turning', text='A slow planet is changing sign — larger trends can reverse over the coming weeks.', tone='warn'))
    # 5. avoid times
    o, cl = r.open_dt, r.close_dt
    bad = sorted([w for w in r.windows if w['kind'] in ('Rahu Kalam', 'Yamakandam') and w['end'] > o and w['start'] < cl], key=lambda w: w['start'])
    good = sorted([w for w in r.windows if w['kind'] in ('Abhijit', 'Gulika') and w['end'] > o and w['start'] < cl], key=lambda w: w['start'])
    if bad or good:
        t = []
        if bad: t.append('Avoid fresh buying ' + ', '.join(f"{max(w['start'], o):%H:%M}–{min(w['end'], cl):%H:%M}" for w in bad))
        if good: t.append('better entry ' + ', '.join(f"{max(w['start'], o):%H:%M}–{min(w['end'], cl):%H:%M}" for w in good))
        out.append(dict(icon='⏰', title='Timing', text='; '.join(t) + '.', tone='info'))
    # 6. business cycle stance
    rg = r.regime
    if rg['active']:
        stance = {'Fire': 'Recession phase — cash is king, rotate towards gold.', 'Earth': 'Recovery phase — good time for fresh, bottom-up investing.',
                  'Air': 'Growth phase — broad-based expansion across sectors.', 'Water': 'Boom phase — book profits gradually and hold some cash.'}[rg['element']]
        out.append(dict(icon='🧭', title='Big picture', text=stance, tone='info'))
    return out


def ahead(F: pd.DataFrame, today: date, days=45) -> list[dict]:
    """Coming shifts from the pre-computed outlook: sector rotation and gold/silver turns."""
    if F is None or F.empty: return []
    out = []
    F = F[(F.date >= pd.Timestamp(today)) & (F.date <= pd.Timestamp(today + timedelta(days=days)))]
    for hz, label in (('long', 'long-term'), ('short', 'short-term')):
        turn_up, turn_dn = [], []
        for t, g in F.groupby('target'):
            s = g.sort_values('date')[hz]
            if s.isna().all(): continue
            first = s.iloc[0]; ch = s[s != first].dropna()
            if ch.empty: continue
            when = g.loc[ch.index[0], 'date']; new = ch.iloc[0]
            if new == 1 and first != 1: turn_up.append((when, t))
            if new == -1 and first != -1: turn_dn.append((when, t))
        if turn_up or turn_dn:
            parts = []
            if turn_up: parts.append('turning positive: ' + ', '.join(f"{nm(t)} ({w:%d %b})" for w, t in sorted(turn_up)[:6]))
            if turn_dn: parts.append('turning negative: ' + ', '.join(f"{nm(t)} ({w:%d %b})" for w, t in sorted(turn_dn)[:6]))
            out.append(dict(icon='🔁', title=f"Rotation ahead ({label}, next {days} days)", text='; '.join(parts) + '.', tone='info'))
    return out


def outlook_summary(F: pd.DataFrame, t: str) -> str:
    """One-line read of a market's next 12 months."""
    g = F[F.target == t].sort_values('date')
    if g.empty: return ''
    bits = []
    for hz, label in (('short', 'Short term'), ('long', 'Long term')):
        s = g[hz].dropna()
        if s.empty: bits.append(f"{label}: no rule"); continue
        up, dn = (s == 1).mean(), (s == -1).mean()
        mood = 'mostly positive' if up >= 0.6 else 'mostly negative' if dn >= 0.6 else 'leaning positive' if up > dn + 0.15 else 'leaning negative' if dn > up + 0.15 else 'mixed'
        # best stretch
        m = g.assign(m=g.date.dt.to_period('M')).groupby('m')[hz].apply(lambda x: (x == 1).mean() - (x == -1).mean())
        best = m.idxmax(); worst = m.idxmin()
        extra = f" — strongest {best.strftime('%b')}, weakest {worst.strftime('%b')}" if m.max() - m.min() > 0.3 else ''
        bits.append(f"{label}: {mood}{extra}")
    return ' · '.join(bits)
