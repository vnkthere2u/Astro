"""
engine.py — applies every rule of the rulebook to a date and produces sector / commodity /
index predictions for three horizons (intraday, short-term, long-term), timing windows
(horā, micro-daśā) and an action plan.

Rule families (book chapter → horizon):
  CH6  sector kāraka rules  : Candra→intraday, Sūrya→short, Guru→long  (book's own summary, p.24)
  CH7  transit table        : Candra→intraday; Sūrya/Maṅgala/Budha/Śukra→short; Guru/Śani/Rāhu/Ketu/outer→long
  CH8  nakṣatra-lord rules  : intraday
  CH10 horā rules           : intraday (weighted by minutes of the horā inside the session) + timing table
  CH11/14 opening-bell chart: intraday (lagna + 12 bhāvas, whole-sign from lagna at the opening bell)
  CH12 micro-daśā           : intraday timing table
  CH16 business cycle       : long (and a small short-term tilt) for all equity sectors; gold inverse (CH20)
  CH17 gold cycle           : short + long for GOLD
  CH18 crude cycle          : short + long for CRUDE / OILGAS / NATGAS
  CH19 Muhurat              : user-entered annual bias for equities
"""
from __future__ import annotations
import json, math
from dataclasses import dataclass, field
from datetime import datetime, date, time, timedelta
from functools import lru_cache
from pathlib import Path
from zoneinfo import ZoneInfo
import astro_core as ac

HERE = Path(__file__).parent
RB = json.loads((HERE / 'data' / 'rulebook.json').read_text())

SECTORS = [s for s, _ in RB['sectors']]
SECTOR_NAME = dict((s, n) for s, n in RB['sectors'])
COMMODITIES = [c for c, _ in RB['commodities']]
COMMODITY_NAME = dict((c, n) for c, n in RB['commodities'])
TARGET_NAME = {**SECTOR_NAME, **COMMODITY_NAME, 'NIFTY': 'Nifty 50 (market)'}
EQUITY = set(SECTORS)
HORIZONS = ['intraday', 'short', 'long']
HZ_LABEL = {'intraday': 'Intraday', 'short': 'Short-term (days–weeks)', 'long': 'Long-term (months)'}

# Nifty-50 composition proxy (approx. 2026 free-float weights by book sector)
NIFTY_W = {'BANK': .36, 'IT': .11, 'OILGAS': .10, 'FMCG': .07, 'AUTO': .07, 'TELECOM': .045, 'PHARMA': .04, 'INFRA': .04,
           'METAL': .035, 'POWER': .035, 'CAPGOODS': .03, 'CEMENT': .02, 'PSU': .02, 'GEMS': .015, 'PAINTS': .01, 'HEALTH': .01,
           'REALTY': .005, 'MEDIA': .002, 'AVIATION': .006}
_s = sum(NIFTY_W.values()); NIFTY_W = {k: v / _s for k, v in NIFTY_W.items()}

CH7 = {(e['graha'], e['rasi']): e for e in RB['ch7']}
CH8 = RB['ch8']
CH10 = RB['ch10']
CH14 = {(e['graha'], e['house']): e for e in RB['ch14']}
CH5 = {int(k): v for k, v in RB['ch5'].items()}
FAV = RB['favour']
CH7_HZ = {'Mo': 'intraday', 'Su': 'short', 'Ma': 'short', 'Me': 'short', 'Ve': 'short',
          'Ju': 'long', 'Sa': 'long', 'Ra': 'long', 'Ke': 'long', 'Ur': 'long', 'Ne': 'long', 'Pl': 'long'}
CH7_W = {'Mo': 1.0, 'Su': .9, 'Ma': .8, 'Me': .6, 'Ve': .6, 'Ju': 1.0, 'Sa': 1.0, 'Ra': .7, 'Ke': .7, 'Ur': .4, 'Ne': .4, 'Pl': .3}
DEFAULT_W = dict(ch6=1.0, ch7=1.0, ch8=1.2, ch10=0.8, ch11=0.6, ch14=0.7, ch16=1.0, ch17=1.2, ch18=1.2, ch19=0.5)
SCALE = {'intraday': 1.6, 'short': 1.6, 'long': 1.6}
SMOOTH = {'short': 5, 'long': 40}     # forward window in trading sessions: next week / next ~2 months
THRESH = 0.15

@dataclass
class Contribution:
    family: str; rule: str; horizon: str; value: float; text: str

@dataclass
class DayResult:
    d: date
    exchange: str
    open_dt: datetime
    close_dt: datetime
    chart_open: ac.Chart
    chart_mid: ac.Chart
    scores: dict                 # target -> horizon -> score (-1..1)
    contrib: dict                # target -> list[Contribution]
    hora: list                   # rows for timing
    dasha: list
    regime: dict
    flags: list
    nak_change: datetime | None

    def composite(self, target, mix=(0.5, 0.3, 0.2)):
        s = self.scores.get(target, {})
        return mix[0] * s.get('intraday', 0) + mix[1] * s.get('short', 0) + mix[2] * s.get('long', 0)

def rag(x, th=THRESH):
    return 'G' if x > th else ('R' if x < -th else 'A')

class Engine:
    def __init__(self, exchange='NSE/BSE Mumbai', open_time: time | None = None, close_time: time | None = None,
                 weights: dict | None = None, muhurat: list | None = None, sunrise_override: dict | None = None):
        ex = ac.EXCHANGES[exchange]
        self.exchange = exchange
        self.lat, self.lon, self.tz = ex['lat'], ex['lon'], ex['tz']
        self.open_t = open_time or ex['open']; self.close_t = close_time or ex['close']
        self.W = {**DEFAULT_W, **(weights or {})}
        self.muhurat = sorted(muhurat or [], key=lambda x: x[0])   # [(date, points_change)]
        self.sunrise_override = sunrise_override or {}
        self._cache = {}

    # ------------------------------------------------------------ stabilised view
    def raw(self, d: date) -> 'DayResult':
        r = self._cache.get(d)
        if r is None:
            r = self._cache[d] = self.day(d)
        return r

    @staticmethod
    def sessions(d: date, n: int) -> list:
        out, x = [], d
        while len(out) < n:
            if x.weekday() < 5: out.append(x)
            x += timedelta(days=1)
        return out

    def view(self, d: date) -> 'DayResult':
        """Scores as shown to the user. Intraday = that day's sky. Short / long = average of the daily
        readings over the next 5 / 40 sessions, so a 'next 2 months' call only changes when a slow planet
        changes rāśi, stations, or forms / leaves an aspect — not because of the Moon."""
        import copy
        r = self.raw(d)
        sc = {t: {'intraday': v['intraday']} for t, v in r.scores.items()}
        for hz, n in SMOOTH.items():
            rs = [self.raw(x) for x in self.sessions(d, n)]
            for t in sc: sc[t][hz] = sum(x.scores[t][hz] for x in rs) / n
        v = copy.copy(r); v.raw_scores = r.scores; v.scores = sc
        return v

    def frame(self, start: date, end: date, targets=None):
        """Weekday DataFrame of stabilised scores: index date, columns (target, horizon)."""
        import pandas as pd
        days = [x for x in (start + timedelta(days=i) for i in range((end - start).days + 1)) if x.weekday() < 5]
        ext = self.sessions(end + timedelta(days=1), max(SMOOTH.values()))
        alld = days + ext
        targets = targets or list(self.raw(start).scores)
        raw = {(t, hz): [self.raw(x).scores[t][hz] for x in alld] for t in targets for hz in HORIZONS}
        df = pd.DataFrame(raw, index=pd.to_datetime(alld))
        df.columns = pd.MultiIndex.from_tuples(df.columns)
        out = df.copy()
        for hz, n in SMOOTH.items():
            cols = [c for c in df.columns if c[1] == hz]
            out[cols] = df[cols][::-1].rolling(n, min_periods=1).mean()[::-1]
        return out.loc[pd.to_datetime(days)]

    # ------------------------------------------------------------ helpers
    @staticmethod
    def _asp(c: ac.Chart, slow=False):
        """Aspect matrix. slow=True drops Candra as an aspecting graha: the Moon's aspects change every
        few hours, so they belong to the intraday horizon only (book: Candra→intraday, Sūrya→short, Guru→long)."""
        if not hasattr(c, '_asp'):
            c._asp = ac.aspect_matrix(c)
            c._asp_slow = {t: {a: v for a, v in d.items() if a != 'Mo'} for t, d in c._asp.items()}
        return c._asp_slow if slow else c._asp

    def _q(self, c, karaka, good=None, bad=None, slow=False):
        A = self._asp(c, slow)[karaka]
        good = FAV[karaka]['good'] if good is None else good
        bad = FAV[karaka]['bad'] if bad is None else bad
        g = sum(s for a, (h, s) in A.items() if a in good)
        b = sum(s for a, (h, s) in A.items() if a in bad)
        return g - b, g, b

    def _add(self, out, targets, fam, rule, hz, val, text, w=1.0):
        if abs(val) < 1e-9: return
        for t in targets:
            out.setdefault(t, []).append(Contribution(fam, rule, hz, val * w, text))

    # ------------------------------------------------------------ main
    def day(self, d: date) -> DayResult:
        z = ZoneInfo(self.tz)
        o = datetime.combine(d, self.open_t, z); cl = datetime.combine(d, self.close_t, z)
        mid = o + (cl - o) / 2
        c_open = ac.chart(o, self.lat, self.lon)
        c_mid = ac.chart(mid)
        contrib: dict = {}
        flags = []
        self._ch6(c_mid, contrib)
        self._ch7(c_mid, contrib, flags)
        self._ch8(c_mid, contrib)
        hora_rows = self._ch10(d, o, cl, c_mid, contrib)
        self._ch11_14(c_open, contrib)
        regime = self._ch16(c_mid, contrib)
        self._ch17(c_mid, d, contrib)
        self._ch18(c_mid, d, contrib)
        self._ch19(d, contrib)
        dasha = self._ch12(c_open, o, cl)
        # nakṣatra change inside session
        c_close = ac.chart(cl)
        nak_change = None
        if c_close.moon_nak != c_open.moon_nak:
            lo, hi = o, cl
            for _ in range(20):
                m = lo + (hi - lo) / 2
                if ac.chart(m).moon_nak == c_open.moon_nak: lo = m
                else: hi = m
            nak_change = hi
            flags.append(f"Candra moves {ac.NAK[c_open.moon_nak]} → {ac.NAK[c_close.moon_nak]} at {hi:%H:%M} — intraday rules switch.")
        scores = {}
        for t in list(SECTORS) + COMMODITIES:
            cs = contrib.get(t, [])
            scores[t] = {hz: math.tanh(sum(x.value for x in cs if x.horizon == hz) / SCALE[hz]) for hz in HORIZONS}
        scores['NIFTY'] = {hz: sum(NIFTY_W[k] * scores[k][hz] for k in NIFTY_W) * 1.6 for hz in HORIZONS}
        scores['NIFTY'] = {hz: max(-1, min(1, v)) for hz, v in scores['NIFTY'].items()}
        return DayResult(d, self.exchange, o, cl, c_open, c_mid, scores, contrib, hora_rows, dasha, regime, flags, nak_change)

    # ------------------------------------------------------------ CH6
    def _ch6(self, c, out):
        trig = {'Mo': c['Mo'], 'Su': c['Su'], 'Ju': c['Ju']}
        for r in RB['ch6']:
            for hz, sides in r['horizons'].items():
                for side in ('buy', 'sell'):
                    x = sides[side]
                    T = trig[x['trigger_planet']]
                    active = T.sign in x['trigger_rasis'] or T.nak in x['trigger_naks']
                    if not active: continue
                    qs = [self._q(c, k, slow=(hz != 'intraday'))[0] for k in x['karakas']]
                    q = sum(qs) / len(qs) if qs else 0
                    q = max(-1.5, min(1.5, q))
                    if (side == 'buy' and q > 0) or (side == 'sell' and q < 0):
                        why = (f"{ac.NAMES[x['trigger_planet']]} in {'%s' % ac.RASI[T.sign] if T.sign in x['trigger_rasis'] else ac.NAK[T.nak]}"
                               f"; kārakas {'/'.join(ac.NAMES[k] for k in x['karakas'])} net {'benefic' if q > 0 else 'malefic'} aspect {q:+.2f}")
                        self._add(out, [r['sector']], 'CH6', f"6:{r['sector']}:{hz}:{side}", hz, q, why, self.W['ch6'])

    # ------------------------------------------------------------ CH7 (+ general rules 1-17)
    def _ch7(self, c, out, flags):
        crowd = ac.crowding(c)
        ecl = ac.eclipse_near(c.dt)
        for sgn, gs in crowd.items():
            if len(gs) >= 4:
                flags.append(f"{len(gs)} grahas in {ac.RASI[sgn]} ({', '.join(ac.NAMES[g] for g in gs)}) — rule 17: directionless & volatile for {ac.RASI[sgn]} sectors.")
        if ecl: flags.append(f"{ecl[0].title()} eclipse on {ecl[1]:%d-%b-%Y} — rules 9/10 applied.")
        for g in ac.GRAHAS:
            B = c[g]; e = CH7.get((g, B.sign))
            if not e: continue
            A = self._asp(c, slow=(g != 'Mo'))[g]
            m1 = sum(s for a, (h, s) in A.items() if a in e['cond_aspectors'])
            w = e.get('whereas') or {}
            m2 = sum(s for a, (h, s) in A.items() if a in w.get('aspectors', []))
            dig_name, dig = ac.dignity(g, B.sign)
            if e['unconditional']:
                v = e['effect'] * (1 - min(m2, 1)) + (w.get('effect') or 0) * min(m2, 1)
                why = f"{ac.NAMES[g]} in {ac.RASI[B.sign]} (unconditional {e['effect']:+.2f})"
            elif m1 == 0 and m2 == 0:
                v = 0.3 * dig
                why = f"{ac.NAMES[g]} in {ac.RASI[B.sign]}, no qualifying aspect → rule 1 ({dig_name})"
            else:
                v = e['effect'] * min(m1, 1) + (w.get('effect') or 0) * min(m2, 1)
                bits = []
                if m1: bits.append(f"aspected by {'/'.join(ac.NAMES[a] for a in A if a in e['cond_aspectors'])} → {e['effect']:+.2f}")
                if m2: bits.append(f"by {'/'.join(ac.NAMES[a] for a in A if a in w.get('aspectors', []))} → {w.get('effect', 0):+.2f}")
                why = f"{ac.NAMES[g]} in {ac.RASI[B.sign]}: " + '; '.join(bits)
            # general transit rules
            ben = g in ac.NATURAL_BENEFIC and not (g == 'Mo' and not c.waxing)
            if B.retro:
                if ben and v > 0: v *= 1.25; why += ' · retro benefic ×1.25'
                if not ben and v < 0: v *= 1.25; why += ' · retro malefic ×1.25'
            hem = ac.hemmed(c, g); fav = dig >= 0.4
            if hem == 'malefic': v = v * (0.5 if (fav and v > 0) else 1.3 if (not fav and v < 0) else 1); why += ' · pāpa-kartari'
            if hem == 'benefic': v = v * (1.3 if (fav and v > 0) else 0.7 if (not fav and v < 0) else 1); why += ' · śubha-kartari'
            mates = crowd.get(B.sign, [])
            if len(mates) >= 4: v *= 0.3; why += ' · 4+ grahas: volatile'
            else:
                nb = sum(1 for x in mates if x in ac.NATURAL_BENEFIC); nm = sum(1 for x in mates if x in ac.NATURAL_MALEFIC)
                if nb >= 2 and v > 0: v *= 1.2
                if nm >= 2 and v < 0: v *= 1.2
            if ecl and g in ('Su', 'Mo', 'Ra', 'Ke'):
                v = 0 if v > 0 else v * 1.3
            v = max(-1.3, min(1.3, v))
            self._add(out, e['targets'], 'CH7', f"7:{g}:{B.sign}", CH7_HZ[g], v, why, self.W['ch7'] * CH7_W[g])

    # ------------------------------------------------------------ CH8
    def _ch8(self, c, out):
        r = CH8[c.moon_nak]; L = r['lord']
        A = self._asp(c)[L]; Am = self._asp(c)['Mo']
        mp = sum(s for a, (h, s) in A.items() if a in r['pos']['aspectors'])
        mn = sum(s for a, (h, s) in A.items() if a in r['neg']['aspectors'])
        cp = sum(s for a, (h, s) in Am.items() if a in r['pos']['moon_confirm']) if L != 'Mo' else 0
        cn = sum(s for a, (h, s) in Am.items() if a in r['neg']['moon_confirm']) if L != 'Mo' else 0
        v = mp * (1 + 0.5 * min(cp, 1)) - mn * (1 + 0.5 * min(cn, 1))
        v = max(-1.5, min(1.5, v))
        why = (f"{r['nakshatra']} day, lord {ac.NAMES[L]}: favourable aspects {mp:.2f}, unfavourable {mn:.2f}"
               + (f"; Candra confirm +{cp:.2f}/−{cn:.2f}" if L != 'Mo' else ''))
        self._add(out, r['pos']['targets'], 'CH8', f"8:{c.moon_nak}", 'intraday', v, why, self.W['ch8'])

    # ------------------------------------------------------------ CH10 horā
    def _ch10(self, d, o, cl, c, out):
        sr = self.sunrise_override.get(d)
        rows = ac.hora_table(d, self.lat, self.lon, self.tz, sr=sr)
        sess = (cl - o).total_seconds()
        table = []
        for s, e, L in rows:
            ov = (min(e, cl) - max(s, o)).total_seconds()
            if ov <= 0: continue
            rule = CH10.get(L)
            q, g, b = self._q(c, L, rule['good'], rule['bad'])
            sig = 'BUY before / during' if q > 0.05 else ('SELL during' if q < -0.05 else 'neutral')
            table.append(dict(start=max(s, o), end=min(e, cl), lord=L, q=round(q, 2), signal=sig, targets=rule['targets'], text=rule['text']))
            if abs(q) > 0.05:
                self._add(out, rule['targets'], 'CH10', f"10:{L}", 'intraday', max(-1.2, min(1.2, q)) * ov / sess,
                          f"{ac.NAMES[L]} horā {max(s, o):%H:%M}-{min(e, cl):%H:%M}: net aspect {q:+.2f}", self.W['ch10'])
        return table

    # ------------------------------------------------------------ CH11/13/14 opening bell
    def _ch11_14(self, c, out):
        lag = int(c.asc // 30)
        # lagna aspects (sign-based dṛṣṭi + conjunction)
        ben = mal = 0.0; who = []
        for g in ac.NINE:
            h = ac.house_from(c[g].sign, lag)
            if h in ({1, 7, 5, 9} | set(ac.VEDIC_DRISHTI.get(g, ()))):
                wt = ac.ASPECT_TYPE_WEIGHT.get(h, .75)
                if g in ac.NATURAL_BENEFIC and not (g == 'Mo' and not c.waxing): ben += wt; who.append('+' + ac.NAMES[g])
                elif g in ac.NATURAL_MALEFIC or g == 'Mo': mal += wt; who.append('−' + ac.NAMES[g])
        v = max(-1.2, min(1.2, 0.5 * (ben - mal)))
        self._add(out, CH5[lag]['targets'], 'CH11', f"11:{lag}", 'intraday', v,
                  f"Opening lagna {ac.RASI[lag]} {c.asc % 30:.1f}°; aspects {' '.join(who) or 'none'}", self.W['ch11'])
        for g in ac.GRAHAS:
            h = (c[g].sign - lag) % 12 + 1
            e = CH14.get((g, h))
            if not e: continue
            A = self._asp(c)[g]
            gs = sum(s for a, (hh, s) in A.items() if a in e['good'])
            bs = sum(s for a, (hh, s) in A.items() if a in e['bad'])
            hw = e['house_weight']
            base = f"{ac.NAMES[g]} in bhāva {h}"
            if e['mixed'] and gs:
                mag = min(gs, 1)
                self._add(out, e['mixed']['up'], 'CH14', f"14:{g}:{h}", 'intraday', 0.8 * mag, base + ' (favourably aspected: up)', self.W['ch14'] * hw)
                self._add(out, e['mixed']['down'], 'CH14', f"14:{g}:{h}", 'intraday', e['mixed'].get('down_mag', -0.75) * mag, base + ' (same: down)', self.W['ch14'] * hw)
                if bs and e['bad_effect']:
                    self._add(out, e['targets'], 'CH14', f"14:{g}:{h}", 'intraday', e['bad_effect'] * min(bs, 1), base + ' (afflicted)', self.W['ch14'] * hw)
                continue
            if e['unconditional'] is not None:
                v = e['unconditional']
                if bs and e['bad_effect'] is not None: v = e['bad_effect']
                why = base + (' (unconditional' + (', afflicted' if bs else '') + ')')
            else:
                v = (e['effect'] or 0) * min(gs, 1) + (e['bad_effect'] or 0) * min(bs, 1)
                why = base + f": benefic {gs:.2f} / malefic {bs:.2f}"
            self._add(out, e['targets'], 'CH14', f"14:{g}:{h}", 'intraday', v, why, self.W['ch14'] * hw)

    # ------------------------------------------------------------ CH12 daśā timing
    def _ch12(self, c, o, cl):
        rows = []
        for s, e, L in ac.micro_dasha(c['Mo'].lon, o, cl):
            if s >= cl: break
            q = self._q(c, L)[0]
            tg = RB['ch4'][L]['sector_ids'] + RB['ch4'][L]['commodity_ids']
            rows.append(dict(start=s, end=min(e, cl), lord=L, q=round(q, 2), targets=tg,
                             signal='positive momentum' if q > 0.05 else 'negative momentum' if q < -0.05 else 'mixed'))
        return rows

    # ------------------------------------------------------------ CH16 business cycle (+CH20)
    def regime_at(self, c):
        sa, ju = c['Sa'], c['Ju']
        el = ac.ELEMENT[sa.sign]
        name, desc, val = RB['ch16']['phases'][el]
        deg = ac.degree_aspect(c, 'Ju', 'Sa', (0, 120, 180), RB['ch16']['trigger_orb_deg'])
        h = ac.house_from(ju.sign, sa.sign)
        sign_asp = h in (1, 5, 7, 9)
        if el == 'Air': sign_asp = h in (1, 5, 9); deg = deg if (deg and deg[0] in (0, 120)) else None
        if deg: state, mult = 'TRIGGERED', 1.0
        elif sign_asp: state, mult = 'ACTIVE', 0.6
        elif el == 'Fire' and ju.sign % 2 == 0: state, mult = 'WATCH (Guru in odd rāśi)', 0.35
        else: state, mult = 'DORMANT (no Guru aspect)', 0.15
        return dict(element=el, phase=name, desc=desc, state=state, value=val * mult,
                    detail=f"Śani {ac.fmt_deg(sa.lon)}{' R' if sa.retro else ''}, Guru {ac.fmt_deg(ju.lon)}{' R' if ju.retro else ''}"
                           + (f"; exact {deg[0]}° within {deg[1]:.2f}°" if deg else ''))

    def _ch16(self, c, out):
        r = self.regime_at(c)
        v = r['value']
        if r['phase'].startswith('Over-expansion'):
            v_long = v * (0.5 if 'TRIG' in r['state'] else 1.0)   # book: boom = take profits
        else:
            v_long = v
        txt = f"Business cycle: {r['phase']} [{r['state']}] — {r['detail']}"
        self._add(out, list(EQUITY), 'CH16', 'cycle', 'long', v_long, txt, self.W['ch16'])
        self._add(out, list(EQUITY), 'CH16', 'cycle', 'short', v_long * 0.25, txt, self.W['ch16'])
        if r['phase'] == 'Recession' and r['value'] < -0.3:
            self._add(out, ['GOLD', 'SILVER'], 'CH20', 'stocks↔gold', 'long', -v_long * 0.6, 'Ch.20: equities collapsing → flight to gold', self.W['ch16'])
        return r

    # ------------------------------------------------------------ CH17 gold
    def _ch17(self, c, d, out):
        ju = c['Ju']
        parts = []; v = 0.0
        dn, dg = ac.dignity('Ju', ju.sign); v += 0.5 * dg; parts.append(f"Guru {dn} in {ac.RASI[ju.sign]} {0.5 * dg:+.2f}")
        if ac.combust(c, 'Ju'): v -= 0.5; parts.append('Guru asta (combust) −0.50')
        else: v += 0.15; parts.append('Guru udita +0.15')
        A = self._asp(c, slow=True)['Ju']
        sm = sum(s for a, (h, s) in A.items() if a == 'Su')
        if sm: v += 0.4 * min(sm, 1.5); parts.append(f"aspected by Sūrya +{0.4 * min(sm, 1.5):.2f}")
        sr, sk = ac.sep(ju.lon, c['Ra'].lon), ac.sep(ju.lon, c['Ke'].lon)
        sn = min(sr, sk)
        c2 = ac.chart(c.dt + timedelta(days=5))
        sn2 = min(ac.sep(c2['Ju'].lon, c2['Ra'].lon), ac.sep(c2['Ju'].lon, c2['Ke'].lon))
        if sn <= 30:
            k = 0.3 + 0.9 * (1 - sn / 30); v += k; parts.append(f"Guru–{'Rāhu' if sr < sk else 'Ketu'} within {sn:.0f}° (hyper-inflation) +{k:.2f}")
            if ju.retro and sn2 > sn: v -= 0.6; parts.append('Guru retro, separating from node −0.60')
        elif sn <= 45 and sn2 > sn and ju.retro:
            v -= 0.5; parts.append(f'Guru retro separating from node ({sn:.0f}°) −0.50')
        if ju.retro: parts.append('Guru retrograde')
        v = max(-1.5, min(1.8, v))
        txt = 'Gold cycle: ' + '; '.join(parts)
        self._add(out, ['GOLD'], 'CH17', 'gold', 'long', v, txt, self.W['ch17'])
        self._add(out, ['GOLD'], 'CH17', 'gold', 'short', v * 0.6, txt, self.W['ch17'])
        self._add(out, ['GEMS'], 'CH17', 'gold', 'long', v * 0.4, txt, self.W['ch17'])

    # ------------------------------------------------------------ CH18 crude
    def _ch18(self, c, d, out):
        sa = c['Sa']; parts = []; v = 0.0
        sr, sk = ac.sep(sa.lon, c['Ra'].lon), ac.sep(sa.lon, c['Ke'].lon)
        sn = min(sr, sk); node = 'Rāhu' if sr < sk else 'Ketu'
        c_prev = ac.chart(c.dt - timedelta(days=20))
        sn_prev = min(ac.sep(c_prev['Sa'].lon, c_prev['Ra'].lon), ac.sep(c_prev['Sa'].lon, c_prev['Ke'].lon))
        same_sign = sa.sign in (c['Ra'].sign, c['Ke'].sign)
        if same_sign or sn <= 12:
            k = 0.4 + 0.8 * max(0, 1 - sn / 30); v += k; parts.append(f"Śani–{node} conjunction ({sn:.0f}°) → crude soars +{k:.2f}")
        elif sn <= 40 and sn > sn_prev:
            v -= 0.8; parts.append(f"Śani separating from {node} ({sn:.0f}°) → crude plunges −0.80")
        if ac.ELEMENT[sa.sign] == 'Fire': v += 0.2; parts.append('Śani in fiery rāśi (hot) +0.20')
        nodes_water = [n for n in ('Ra', 'Ke') if ac.ELEMENT[c[n].sign] == 'Water']
        if nodes_water: v -= 0.2; parts.append(f"{'/'.join(ac.NAMES[n] for n in nodes_water)} in watery rāśi (cooling) −0.20")
        bq = 0
        for g in ('Sa', 'Ur', 'Ne'):
            bq += self._q(c, g, slow=True)[0]
        bq = max(-1, min(1, bq / 3)); v += 0.4 * bq
        parts.append(f"Śani/Uranus/Neptune aspect balance {0.4 * bq:+.2f}")
        v = max(-1.5, min(1.5, v))
        txt = 'Crude cycle: ' + '; '.join(parts)
        for t, k in (('CRUDE', 1.0), ('NATGAS', 0.6), ('OILGAS', 0.5)):
            self._add(out, [t], 'CH18', 'crude', 'long', v * k, txt, self.W['ch18'])
            self._add(out, [t], 'CH18', 'crude', 'short', v * k * 0.6, txt, self.W['ch18'])

    # ------------------------------------------------------------ CH19 Muhurat
    def _ch19(self, d, out):
        prev = [m for m in self.muhurat if m[0] <= d and (d - m[0]).days <= 370]
        if not prev: return
        md, pts = prev[-1]
        sgn = 1 if pts > 0 else -1 if pts < 0 else 0
        txt = f"Dīpāvali Muhurat {md:%d-%b-%Y}: {pts:+} pts → {'bullish' if sgn > 0 else 'bearish'} Samvat year"
        self._add(out, list(EQUITY), 'CH19', 'muhurat', 'long', 0.5 * sgn, txt, self.W['ch19'])
        self._add(out, list(EQUITY), 'CH19', 'muhurat', 'short', 0.25 * sgn, txt, self.W['ch19'])

# ====================================================================== action plan
def action_plan(r: DayResult, conf=None, top=4) -> dict:
    conf = conf or (lambda t, hz, s: None)
    def lst(hz, pool, sign):
        xs = [(t, r.scores[t][hz]) for t in pool]
        xs = [x for x in xs if (x[1] > THRESH if sign > 0 else x[1] < -THRESH)]
        xs.sort(key=lambda x: -sign * x[1])
        return [dict(target=t, name=TARGET_NAME[t], score=round(s, 2), conf=conf(t, hz, s)) for t, s in xs[:top]]
    plan = dict(
        intraday_long=lst('intraday', SECTORS, +1), intraday_short=lst('intraday', SECTORS, -1),
        swing_long=lst('short', SECTORS, +1), swing_short=lst('short', SECTORS, -1),
        position_long=lst('long', SECTORS, +1), position_avoid=lst('long', SECTORS, -1),
        commodities=[dict(target=t, name=TARGET_NAME[t], intraday=round(r.scores[t]['intraday'], 2), short=round(r.scores[t]['short'], 2),
                          long=round(r.scores[t]['long'], 2), call=rag(r.composite(t))) for t in COMMODITIES],
        nifty={hz: round(r.scores['NIFTY'][hz], 2) for hz in HORIZONS},
    )
    win = []
    for h in r.hora:
        if h['signal'] != 'neutral':
            win.append(f"{h['start']:%H:%M}–{h['end']:%H:%M} {ac.NAMES[h['lord']]} horā: {h['signal']} — {h['text']}")
    plan['hora_windows'] = win
    plan['dasha_windows'] = [f"{x['start']:%H:%M}–{x['end']:%H:%M} {ac.NAMES[x['lord']]} daśā: {x['signal']} ({', '.join(TARGET_NAME.get(t, t) for t in x['targets'][:5])})"
                             for x in r.dasha]
    notes = list(r.flags)
    reg = r.regime
    notes.append(f"Business-cycle regime: {reg['phase']} [{reg['state']}]. {reg['desc']}")
    if reg['phase'].startswith('Over-expansion') and 'TRIG' in reg['state']:
        notes.append('Book guidance for this regime: book profits progressively, keep cash ready, avoid fresh leverage.')
    if reg['phase'] == 'Recession' and reg['state'] in ('TRIGGERED', 'ACTIVE'):
        notes.append('Book guidance: "Cash is King" — stay out / hedge; rotate toward gold (Ch.20).')
    plan['notes'] = notes
    return plan

# ====================================================================== range helpers
def is_trading_day(d: date, holidays: set | None = None) -> bool:
    return d.weekday() < 5 and (not holidays or d not in holidays)

def run_range(eng: Engine, start: date, end: date, trading_only=False, holidays=None):
    d = start; out = []
    while d <= end:
        if not trading_only or is_trading_day(d, holidays):
            out.append(eng.day(d))
        d += timedelta(days=1)
    return out
