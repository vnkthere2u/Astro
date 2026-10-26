"""
book1.py — Book 1: Indrodeep Banerjee, "Stock Market Astrology" (2009). Direction-only implementation.

Every rule returns Up / Down / Neutral votes exactly as the book words it — no strengths, weights or multipliers.
Words such as "intensify", "minimise", "strong", "weak" are kept as notes on the vote.
Horizon per the book (p.24 and Ch.15): Candra → intraday, Sūrya → short-term, Guru → long-term; Maṅgala, Budha,
Śukra (fast, Book 2 Ch.34 "short-term trend reversals") → short-term; Śani, Rāhu/Ketu and the outer planets → long-term.
Aspect convention: astro_core.casts_aspect (calibrated on Book 1's own worked examples, 36/36 in validate.py).
"Benefic / malefic aspect on graha X" uses the book's explicit good/bad aspector lists for X (Ch.8, 10, 14 —
rulebook 'favour'); "benefic / malefic to a rāśi" uses the Ch.5 lists for that rāśi.
"""
from __future__ import annotations
import json
from pathlib import Path
from datetime import timedelta
import astro_core as ac

HERE = Path(__file__).parent
RB = json.loads((HERE / 'data' / 'rulebook.json').read_text())
CH7 = {(e['graha'], e['rasi']): e for e in RB['ch7']}
CH8 = RB['ch8']; CH10 = RB['ch10']
CH14 = {(e['graha'], e['house']): e for e in RB['ch14']}
CH5 = {int(k): v for k, v in RB['ch5'].items()}
FAV = RB['favour']
CH7_HZ = {'Mo': 'intraday', 'Su': 'short', 'Ma': 'short', 'Me': 'short', 'Ve': 'short',
          'Ju': 'long', 'Sa': 'long', 'Ra': 'long', 'Ke': 'long', 'Ur': 'long', 'Ne': 'long', 'Pl': 'long'}
EQUITY = [s for s, _ in RB['sectors']]
sgn = lambda x: 1 if x > 0 else -1 if x < 0 else 0


def strength_word(x):
    a = abs(x or 0)
    return '' if a == 0 else 'weak' if a < 0.3 else 'mild' if a < 0.5 else 'moderate' if a < 0.75 else '' if a < 1 else 'strong'


class Hits(list):
    def add(self, targets, hz, d, chapter, text):
        for t in targets: self.append(dict(target=t, horizon=hz, dir=d, book=1, chapter=chapter, text=text))


def _asp(c):
    if not hasattr(c, '_b1'): c._b1 = {t: ac.aspects_on(c, t) for t in ac.GRAHAS}
    return c._b1


def ch6(c, H):
    trig = {'Mo': c['Mo'], 'Su': c['Su'], 'Ju': c['Ju']}
    A = _asp(c)
    for r in RB['ch6']:
        for hz, sides in r['horizons'].items():
            x = sides['buy']; T = trig[x['trigger_planet']]
            if not (T.sign in x['trigger_rasis'] or T.nak in x['trigger_naks']): continue
            g = sorted({f"{ac.EN[a]}→{ac.EN[k]}" for k in x['karakas'] for a in A[k] if a in FAV[k]['good']})
            b = sorted({f"{ac.EN[a]}→{ac.EN[k]}" for k in x['karakas'] for a in A[k] if a in FAV[k]['bad']})
            if not g and not b: continue
            d = sgn(len(g) - len(b))
            where = ac.RASI_EN[T.sign] if T.sign in x['trigger_rasis'] else ac.NAK[T.nak]
            H.add([r['sector']], hz, d, 'Ch.6', f"{ac.EN[x['trigger_planet']]} in {where}; kārakas {'/'.join(ac.EN[k] for k in x['karakas'])}: "
                  f"benefic aspects {', '.join(g) or 'none'} · malefic {', '.join(b) or 'none'}")


def ch7(c, H, flags, eclipse_today):
    crowd = {}
    for g in ac.GRAHAS: crowd.setdefault(c[g].sign, []).append(g)
    for s, gs in crowd.items():
        if len(gs) >= 4:
            flags.append(f"Book 1 rule 17: {len(gs)} grahas in {ac.RASI_EN[s]} ({', '.join(ac.EN[g] for g in gs)}) — neutral, directionless & volatile.")
    A = _asp(c)
    for g in ac.GRAHAS:
        B = c[g]; e = CH7.get((g, B.sign)); hz = CH7_HZ[g]
        notes = []
        if e is None: continue
        on = A[g]; w = e.get('whereas') or {}
        a1 = [a for a in on if a in e['cond_aspectors']]; a2 = [a for a in on if a in w.get('aspectors', [])]
        if e['unconditional'] and not a2:
            d = sgn(e['effect']); why = f"{ac.EN[g]} in {ac.RASI_EN[B.sign]} (stated unconditionally)"
            if strength_word(e['effect']): notes.append(strength_word(e['effect']))
        elif a1 or a2:
            d1 = sgn(e['effect']) if a1 else 0; d2 = sgn(w.get('effect') or 0) if a2 else 0
            if a1 and a2 and d1 != d2:
                d = sgn(d1 * len(a1) + d2 * len(a2))
            else:
                d = d1 if a1 else d2
            bits = []
            if a1: bits.append(f"aspected by {'/'.join(ac.EN[a] for a in a1)} → {'up' if d1 > 0 else 'down' if d1 < 0 else 'neutral'}")
            if a2: bits.append(f"by {'/'.join(ac.EN[a] for a in a2)} → {'up' if d2 > 0 else 'down' if d2 < 0 else 'neutral'}"
                               + (f" ({strength_word(w.get('effect'))})" if strength_word(w.get('effect')) else ''))
            why = f"{ac.EN[g]} in {ac.RASI_EN[B.sign]}: " + '; '.join(bits)
        else:
            # rules 1-2 (no listed aspect): dignity and benefic/malefic-to-rāśi
            dn, _ = ac.dignity(g, B.sign)
            if dn in ('exalted', 'own', 'friendly'):
                H.add(e['targets'], hz, 1, 'Ch.7 rule 1', f"{ac.EN[g]} {dn} in {ac.RASI_EN[B.sign]} → good result")
            elif dn in ('debilitated', 'inimical'):
                H.add(e['targets'], hz, 0, 'Ch.7 rule 1', f"{ac.EN[g]} {dn} in {ac.RASI_EN[B.sign]} → no good result")
            if g in CH5[B.sign]['benefics']:
                H.add(e['targets'], hz, 1, 'Ch.7 rule 2', f"{ac.EN[g]} is benefic to {ac.RASI_EN[B.sign]} → good result")
            elif g in CH5[B.sign]['malefics']:
                H.add(e['targets'], hz, -1, 'Ch.7 rule 2', f"{ac.EN[g]} is malefic to {ac.RASI_EN[B.sign]} → intensity of evil")
            continue
        # general rules as notes / the two that change the outcome (9, 17)
        ben_r = g in CH5[B.sign]['benefics']; mal_r = g in CH5[B.sign]['malefics']
        if B.retro and ben_r and d > 0: notes.append('retrograde benefic — intensified (rule 5)')
        if B.retro and mal_r and d < 0: notes.append('retrograde malefic — intensified (rule 6)')
        prev = [x for x in ac.GRAHAS if x != g and c[x].sign == (B.sign - 1) % 12]
        nxt = [x for x in ac.GRAHAS if x != g and c[x].sign == (B.sign + 1) % 12]
        mal = set(CH5[B.sign]['malefics']); ben = set(CH5[B.sign]['benefics'])
        if set(prev) & mal and set(nxt) & mal: notes.append('hemmed between malefics (rules 11-12)')
        if set(prev) & ben and set(nxt) & ben: notes.append('hemmed between benefics (rules 13-14)')
        mates = crowd.get(B.sign, [])
        if len(mates) >= 4:
            d = 0; notes.append('4+ grahas in the rāśi → neutral (rule 17)')
        if eclipse_today and g in ('Su', 'Mo', 'Ra', 'Ke'):
            if d > 0: d = 0; notes.append('in eclipse → incapable of favourable results (rule 9)')
            elif d < 0: notes.append('in eclipse → evil intensified (rule 10)')
        H.add(e['targets'], hz, d, 'Ch.7', why + (f" [{'; '.join(notes)}]" if notes else ''))


def ch8(c, H):
    r = CH8[c.moon_nak]; L = r['lord']; A = _asp(c)
    p = [a for a in A[L] if a in r['pos']['aspectors']]; n = [a for a in A[L] if a in r['neg']['aspectors']]
    if not p and not n: return
    d = sgn(len(p) - len(n))
    cp = [a for a in A['Mo'] if a in r['pos']['moon_confirm']] if L != 'Mo' else []
    cn = [a for a in A['Mo'] if a in r['neg']['moon_confirm']] if L != 'Mo' else []
    note = ''
    if d > 0 and cp: note = f" — especially so: Candra aspected by {'/'.join(ac.EN[a] for a in cp)}"
    if d < 0 and cn: note = f" — especially so: Candra aspected by {'/'.join(ac.EN[a] for a in cn)}"
    H.add(r['pos']['targets'], 'intraday', d, 'Ch.8',
          f"{r['nakshatra']} day, lord {ac.EN[L]} aspected by {', '.join(ac.EN[a] for a in p + n)}{note}")


def ch11_14(c, H):
    lag = int(c.asc // 30); A = _asp(c)
    ben = set(CH5[lag]['benefics']); mal = set(CH5[lag]['malefics'])
    on = []
    for g in ac.NINE:
        h = ac.house_from(c[g].sign, lag)
        if h in ({1, 7} | set(ac.VEDIC_DRISHTI.get(g, ()))): on.append(g)
    b = [g for g in on if g in ben]; m = [g for g in on if g in mal]
    if b or m:
        H.add(CH5[lag]['targets'], 'intraday', sgn(len(b) - len(m)), 'Ch.11',
              f"Opening lagna {ac.RASI_EN[lag]}; benefic aspects {', '.join(ac.EN[x] for x in b) or 'none'} · malefic {', '.join(ac.EN[x] for x in m) or 'none'}")
    for g in ac.GRAHAS:
        h = (c[g].sign - lag) % 12 + 1; e = CH14.get((g, h))
        if not e: continue
        gs = [a for a in A[g] if a in e['good']]; bs = [a for a in A[g] if a in e['bad']]
        base = f"{ac.EN[g]} in bhāva {h} of the opening chart"
        if e['mixed'] and gs:
            H.add(e['mixed']['up'], 'intraday', 1, 'Ch.14', base + f", favourably aspected ({'/'.join(ac.EN[a] for a in gs)})")
            H.add(e['mixed']['down'], 'intraday', -1, 'Ch.14', base + f", favourably aspected ({'/'.join(ac.EN[a] for a in gs)}) — these fall")
            if bs and e['bad_effect']: H.add(e['targets'], 'intraday', sgn(e['bad_effect']), 'Ch.14', base + ' — afflicted')
            continue
        if e['unconditional'] is not None:
            d = sgn(e['bad_effect']) if (bs and e['bad_effect'] is not None) else sgn(e['unconditional'])
            H.add(e['targets'], 'intraday', d, 'Ch.14', base + (' (afflicted)' if bs else ' (stated unconditionally)'))
        elif gs or bs:
            d = sgn((sgn(e['effect'] or 0) * len(gs)) + (sgn(e['bad_effect'] or 0) * len(bs)))
            H.add(e['targets'], 'intraday', d, 'Ch.14', base + f": benefic {', '.join(ac.EN[a] for a in gs) or 'none'} · malefic {', '.join(ac.EN[a] for a in bs) or 'none'}")


def regime(c) -> dict:
    """Ch.16: Śani's element + Guru's conjunction / trine / opposition on Śani (sign-based, i.e. Guru's 1/5/7/9)."""
    sa, ju = c['Sa'], c['Ju']; el = ac.ELEMENT[sa.sign]
    name, desc, val = RB['ch16']['phases'][el]
    h = ac.house_from(ju.sign, sa.sign)
    active = h in (1, 5, 7, 9) if el != 'Air' else h in (1, 5, 9)        # Air phase: conjunction or trine only
    exact = ac.degree_aspect(c, 'Ju', 'Sa', (0, 120, 180) if el != 'Air' else (0, 120), RB['ch16']['trigger_orb_deg'])
    d = {'Fire': -1, 'Earth': 1, 'Air': 1, 'Water': 1}[el] if active else None
    return dict(element=el, phase=name, desc=desc, active=active, exact=exact, dir=d,
                detail=f"Saturn {ac.fmt_deg(sa.lon)}, Jupiter {ac.fmt_deg(ju.lon)}"
                       + (f"; exact {exact[0]}° (±{exact[1]:.1f}°)" if exact else ''))


def ch16_19_20(c, d, H, muhurat):
    r = regime(c)
    if r['active']:
        txt = f"Business cycle: {r['phase']} — Saturn in a {r['element']} sign aspected by Jupiter. {r['desc']}"
        H.add(EQUITY + ['NIFTY'], 'long', r['dir'], 'Ch.16', txt)
        if r['element'] == 'Fire':
            H.add(['GOLD'], 'long', 1, 'Ch.20', 'Equities collapsing (recession phase) → gold rises (Ch.20)')
    prev = [m for m in muhurat if m[0] <= d and (d - m[0]).days <= 370]
    if prev:
        md, pts = prev[-1]
        if pts: H.add(EQUITY + ['NIFTY'], 'long', sgn(pts), 'Ch.19', f"Dīpāvali Muhurat {md:%d-%b-%Y} closed {pts:+} → {'bullish' if pts > 0 else 'bearish'} Samvat year")
    return r


def ch17(c, H):
    ju = c['Ju']; A = _asp(c)
    dn, _ = ac.dignity('Ju', ju.sign)
    if dn in ('exalted', 'own', 'friendly'): H.add(['GOLD'], 'long', 1, 'Ch.17', f"Jupiter {dn} in {ac.RASI_EN[ju.sign]} → gold strong")
    elif dn in ('debilitated', 'inimical'): H.add(['GOLD'], 'long', -1, 'Ch.17', f"Jupiter {dn} in {ac.RASI_EN[ju.sign]} → gold weak")
    if ac.combust(c, 'Ju'): H.add(['GOLD'], 'long', -1, 'Ch.17', 'Jupiter asta (combust) → gold demand and price fall')
    else: H.add(['GOLD'], 'long', 1, 'Ch.17', 'Jupiter udita (visible) → gold demand and price rise')
    sm = [a for a in A['Ju'] if a in ('Su', 'Mo')]
    if sm: H.add(['GOLD'], 'long', 1, 'Ch.17', f"Jupiter aspected by {'/'.join(ac.EN[a] for a in sm)} → favourable for gold")
    sr, sk = ac.sep(ju.lon, c['Ra'].lon), ac.sep(ju.lon, c['Ke'].lon); sn = min(sr, sk); node = 'Rāhu' if sr < sk else 'Ketu'
    if sn <= 30:
        c2 = ac.chart(c.dt + timedelta(days=1))
        sn2 = min(ac.sep(c2['Ju'].lon, c2['Ra'].lon), ac.sep(c2['Ju'].lon, c2['Ke'].lon))
        if ju.retro and sn2 > sn:
            H.add(['GOLD'], 'long', -1, 'Ch.17', f"Jupiter retrograde, separating from {node} ({sn:.0f}°) → gold falls (2008 example)")
        else:
            H.add(['GOLD'], 'long', 1, 'Ch.17', f"Jupiter within 30° of {node} ({sn:.0f}°) → hyper-inflationary surge in gold")
    elif any(a in ('Ra', 'Ke') for a in A['Ju']):
        H.add(['GOLD'], 'long', 1, 'Ch.17', 'Jupiter aspected by Rāhu/Ketu → good for gold (hyper-inflation)')


def ch18(c, H):
    sa = c['Sa']; T = ['CRUDE']
    same = [n for n in ('Ra', 'Ke') if c[n].sign == sa.sign]
    if same:
        H.add(T, 'long', 1, 'Ch.18', f"Saturn conjunct {'/'.join(ac.EN[n] for n in same)} in {ac.RASI_EN[sa.sign]} → crude soars")
    else:
        adj = [n for n in ('Ra', 'Ke') if abs(((c[n].sign - sa.sign + 6) % 12) - 6) == 1]
        if adj:
            c2 = ac.chart(c.dt + timedelta(days=1))
            n = adj[0]
            if ac.sep(c2['Sa'].lon, c2[n].lon) > ac.sep(sa.lon, c[n].lon):
                H.add(T, 'long', -1, 'Ch.18', f"{ac.EN[n]} separated from conjunction with Saturn → crude plunges from peak")
    if ac.ELEMENT[sa.sign] == 'Fire': H.add(T, 'long', 1, 'Ch.18', f"Saturn in fiery {ac.RASI_EN[sa.sign]} keeps crude 'bubbling hot'")
    for n in ('Ra', 'Ke'):
        if ac.ELEMENT[c[n].sign] == 'Water': H.add(T, 'long', -1, 'Ch.18', f"{ac.EN[n]} in watery {ac.RASI_EN[c[n].sign]} 'cools' crude")
    A = _asp(c)
    for g in ('Sa', 'Ur', 'Ne', 'Ra', 'Ke', 'Mo'):
        good = [a for a in A[g] if a in FAV[g]['good']]; bad = [a for a in A[g] if a in FAV[g]['bad']]
        if good or bad:
            H.add(T, 'intraday' if g == 'Mo' else 'long', sgn(len(good) - len(bad)), 'Ch.18',
                  f"{ac.EN[g]} aspected by {', '.join(ac.EN[a] for a in good + bad)} → crude {'up' if len(good) > len(bad) else 'down' if len(bad) > len(good) else 'mixed'}")


def hora_windows(d, lat, lon, tz, o, cl, c):
    rows = []; A = _asp(c)
    for s, e, L in ac.hora_table(d, lat, lon, tz):
        if e <= o or s >= cl: continue
        r = CH10[L]
        g = [a for a in A[L] if a in r['good']]; b = [a for a in A[L] if a in r['bad']]
        dd = sgn(len(g) - len(b)) if (g or b) else 0
        rows.append(dict(start=max(s, o), end=min(e, cl), lord=L, dir=dd, targets=r['targets'], text=r['text'],
                         why=f"{ac.EN[L]} aspected by {', '.join(ac.EN[a] for a in g + b) or 'none'}"))
    return rows


def dasha_windows(c, o, cl):
    out = []; A = _asp(c)
    for s, e, L in ac.micro_dasha(c['Mo'].lon, o, cl):
        if s >= cl: break
        g = [a for a in A[L] if a in FAV[L]['good']]; b = [a for a in A[L] if a in FAV[L]['bad']]
        tg = RB['ch4'][L]['sector_ids'] + RB['ch4'][L]['commodity_ids']
        out.append(dict(start=s, end=min(e, cl), lord=L, dir=sgn(len(g) - len(b)), targets=tg))
    return out
