"""
book3.py — Book 3: Indrodeep Banerjee, "Predicting the Nifty & Sensex" (intraday Nifty, Sun-sign tables).

Implemented exactly as the book states / demonstrates:
  • Ch.2-13 tables (data/book3_rules.json, parsed from the book by tools/parse_book3.py): for the Sun's sign, the
    result of the Moon's sign, nakshatra, yoga and tithi — Up / Down / Neutral — including every
    "But if this Moon is aspected by / in conjunction with X then …" override, and the book's own k-of-n statistic.
  • Ch.14 worked method for the final intraday call (reproduces all six worked examples of the book):
      1. Moon in Mrita avasthā → Neutral ("fails to produce the desired results").
      2. Base = net of the nakshatra, yoga and tithi results; if they cancel, the Moon-sign result is the base.
      3. Aspects on the Moon: strengthening (Sun, Mercury, Mars, Jupiter in the book's examples) keep the base;
         weakening (Saturn, Rāhu, Ketu; Venus per the same author's Book 1) reverse it ("weak Moon fails to give the
         downside → upmove", Practicals 2-3); when both act and the weakening planet rules the Moon's nakshatra the
         call is Neutral (Practical 5); otherwise the side with more aspects decides (Practical 6).
      4. Baal / Vriddha avasthā → result stands but "in a weak sense".
  • Ch.1 short-term rule from the Sun and Mars; Ch.1 long-term rule: Saturn in Aries / Leo / Sagittarius (12th / 4th /
    8th from the Taurus ascendant of Indian markets) drags the market down; Mars aspecting houses 1,2,5,7,9,10 from
    Taurus while strengthened by benefic aspects drags prices down.
  • Ch.2-13 opening paragraph: Sun's transit through a sign aspected by listed planets → sector up / down (short-term).
Aspect convention (verified on all Ch.14 examples): astro_core.b3_aspectors.
"""
from __future__ import annotations
import json
from pathlib import Path
import astro_core as ac

HERE = Path(__file__).parent
RULES = json.loads((HERE / 'data' / 'book3_rules.json').read_text())
SIGNS_EN = ac.RASI_EN
B3_NAK = ['Aswini', 'Bharani', 'Krittika', 'Rohini', 'Mrigasira', 'Ardra', 'Punarvasu', 'Pushyami', 'Aslesha', 'Magha',
          'Purvaphalguni', 'Uttaraphalguni', 'Hasta', 'Chitra', 'Swati', 'Visakha', 'Anuradha', 'Jyeshta', 'Moola',
          'Purvashada', 'Uttarashada', 'Sravana', 'Dhanishta', 'Satabhisha', 'Purvabhadra', 'Uttarabhadra', 'Revati']
PL = {'Sun': 'Su', 'Moon': 'Mo', 'Mars': 'Ma', 'Mercury': 'Me', 'Jupiter': 'Ju', 'Venus': 'Ve', 'Saturn': 'Sa', 'Rahu': 'Ra', 'Ketu': 'Ke'}
IDX = {}
for r in RULES:
    k = r.get('key') if r['kind'] != 'sun_aspect' else (PL[r['planet'][0]] if r.get('planet') else None)
    IDX[(r['kind'], r['sun'], k)] = r

MOON_STRENGTHEN = {'Su', 'Me', 'Ma', 'Ju'}           # Ch.14 Practicals 5-7
MOON_WEAKEN = {'Sa', 'Ra', 'Ke', 'Ve'}               # Ch.14 Practicals 2-3, 5 (Sa, Ra, Ke); Venus: Book 1 FAVOUR['Mo'] bad
DIR = {'Up': 1, 'Down': -1, 'Neutral': 0}
WORD = {1: 'Up', -1: 'Down', 0: 'Neutral'}

# Ch.2-13 opening paragraphs: (sign index) -> (up aspectors, down aspectors, base direction when "up" list aspects)
# Text verified from the book; Leo and Virgo pages are missing from the supplied copy (no rule applied there).
SUN_SECTOR = {
    0: (['Mo', 'Ma', 'Ju'], ['Me', 'Ve', 'Sa', 'Ra'], 1, 1),     # Aries: positive; whereas … decline
    1: (['Mo', 'Ma', 'Ju'], ['Me', 'Sa', 'Ra'], 1, 1),
    2: (['Mo', 'Ma', 'Ju'], ['Me', 'Ve', 'Ra'], -1, -1),         # Gemini: down-slide; whereas … selling stays weak (still down)
    3: (['Mo', 'Ma', 'Ju'], ['Me', 'Ve', 'Sa', 'Ra'], 1, 1),
    6: (['Mo', 'Ma', 'Ju'], ['Me', 'Sa', 'Ra'], 1, 1),
    7: (['Mo', 'Ma', 'Ju'], ['Me', 'Ve', 'Ra'], 1, 1),
    8: (['Mo', 'Ma', 'Ju'], ['Sa', 'Ra'], 1, 1),
    9: (['Mo', 'Ma', 'Ju'], ['Me', 'Ve', 'Sa', 'Ra'], -1, -1),
    10: (['Mo', 'Ma', 'Ju'], ['Me', 'Ve', 'Sa', 'Ra'], -1, -1),
    11: (['Mo', 'Ma', 'Ju'], ['Sa', 'Ra'], 1, 1),
}
FRIENDS = ac.FRIENDS; ENEMIES = ac.ENEMIES


def _apply(rule, asp, conj):
    """Base verdict of a table entry plus any 'But if…' override that is active today."""
    if rule is None: return None, None, 'page not in the supplied copy of the book'
    v = DIR.get(rule['verdict']); note = None; act = []
    for cnd in rule['conds']:
        pool = conj if cnd['rel'] == 'conj' else asp
        hit = [p for p in cnd['planets'] if PL.get(p) in pool]
        if hit and cnd['verdict']:
            act.append((DIR[cnd['verdict']], f"Moon {'conjunct' if cnd['rel'] == 'conj' else 'aspected by'} {'/'.join(hit)} → {cnd['verdict']}"
                        + (f" ({cnd['stat'][0]}/{cnd['stat'][1]} in the book)" if cnd.get('stat') else '')))
    if act:
        ds = {a for a, _ in act}
        v = act[0][0] if len(ds) == 1 else 0
        note = 'but ' + '; '.join(t for _, t in act) + ('' if len(ds) == 1 else ' — the book\'s overrides conflict → Neutral')
    return v, rule.get('stat'), note


def intraday(c) -> dict:
    """Nifty intraday per Book 3 Ch.14. c = chart at the opening bell."""
    sun = SIGNS_EN[c['Su'].sign]; mo = c['Mo']
    asp = ac.b3_aspectors(c, 'Mo'); conj = ac.b3_conjunct(c, 'Mo')
    av = ac.avastha(mo.lon)
    parts = {}
    for kind, key, label in (('nakshatra', B3_NAK[mo.nak], f"Nakshatra {ac.NAK[mo.nak]}"),
                             ('yoga', ac.YOGA_NAMES[ac.yoga_index(c)], f"Yoga {ac.YOGA_NAMES[ac.yoga_index(c)]}"),
                             ('tithi', c.tithi, f"Tithi {ac.tithi_name(c.tithi)}"),
                             ('moon_sign', SIGNS_EN[mo.sign], f"Moon in {SIGNS_EN[mo.sign]}")):
        v, stat, note = _apply(IDX.get((kind, sun, key)), asp, conj)
        parts[kind] = dict(label=label, dir=v, stat=stat, note=note)
    sun_asp = [dict(planet=p, dir=DIR.get(IDX[('sun_aspect', sun, p)]['verdict']), stat=IDX[('sun_aspect', sun, p)]['stat'])
               for p in ac.b3_aspectors(c, 'Su') if ('sun_aspect', sun, p) in IDX]
    strong = [a for a in asp if a in MOON_STRENGTHEN]; weak = [a for a in asp if a in MOON_WEAKEN]
    steps = []
    if av == 'Mrita':
        final = 0; steps.append('Moon in Mrita avasthā — "fails to produce the desired results" → Neutral (Ch.1, Practical 1).')
    else:
        P = sum(parts[k]['dir'] or 0 for k in ('nakshatra', 'yoga', 'tithi'))
        base = (1 if P > 0 else -1) if P else (parts['moon_sign']['dir'] or 0)
        steps.append(f"Nakshatra/yoga/tithi net {P:+d} → base {WORD[base]}" + ('' if P else f" (tie → Moon-sign result {WORD[base]})"))
        lord = ac.DASHA_ORDER[mo.nak % 9]
        if not base:
            final = 0; steps.append('No directional base → Neutral.')
        elif weak and not strong:
            final = -base; steps.append(f"Only weakening aspects on Moon ({', '.join(ac.EN[x] for x in weak)}) — weak Moon cannot deliver the base → {WORD[final]} (Practicals 2-3).")
        elif strong and not weak:
            final = base; steps.append(f"Strengthening aspects on Moon ({', '.join(ac.EN[x] for x in strong)}) → {WORD[final]} (Practical 7).")
        elif strong and weak:
            if lord in weak:
                final = 0; steps.append(f"{ac.EN[lord]} aspects the Moon and rules its nakshatra — very strong weakening → Neutral (Practical 5).")
            elif len(strong) > len(weak):
                final = base; steps.append(f"{len(strong)} strengthening vs {len(weak)} weakening aspects → {WORD[final]} (Practical 6).")
            elif len(weak) > len(strong):
                final = -base; steps.append(f"{len(weak)} weakening vs {len(strong)} strengthening aspects → {WORD[final]}.")
            else:
                final = 0; steps.append('Equal strengthening and weakening aspects → Neutral.')
        else:
            final = base; steps.append('No aspect on the Moon → base stands.')
        if av in ('Baal', 'Vriddha'): steps.append(f"Moon in {av} avasthā — result “in a weak sense”.")
    return dict(dir=final, avastha=av, aspects=asp, parts=parts, steps=steps, sun_aspects=sun_asp,
                weak=av in ('Baal', 'Vriddha'))


def _rel(g, sign):
    """friendly / enemy sign for graha g per its friends & enemies (Book 1 Ch.4, same author)."""
    lord = ac.SIGN_LORD[sign]
    if lord == g or sign == ac.EXALT.get(g) or lord in FRIENDS.get(g, []): return 'friendly'
    if lord in ENEMIES.get(g, []) or sign == ac.DEBIL.get(g): return 'enemy'
    return None


def short_term(c) -> list:
    """Ch.1: aspects on Sun and Mars → short-term trend. Returns hits [(dir, text)]."""
    out = []
    for g in ('Su', 'Ma'):
        rel = _rel(g, c[g].sign)
        asp = ac.b3_aspectors(c, g)
        fr = [a for a in asp if a in FRIENDS.get(g, [])]; en = [a for a in asp if a in ENEMIES.get(g, [])]
        if not rel or not (fr or en): continue
        good = len(fr) > len(en); bad = len(en) > len(fr)
        if not (good or bad): continue
        if rel == 'friendly' and good: d, t = 1, 'friendly sign + friendly aspects → buying spree'
        elif rel == 'enemy' and good: d, t = -1, 'enemy sign + benefic aspects → selling pressure'
        elif rel == 'friendly' and bad: d, t = 0, 'friendly sign + malefic aspects → dull, occasionally negative'
        else: d, t = 0, 'enemy sign + malefic aspects → flat & directionless'
        who = ', '.join(ac.EN[a] for a in (fr if good else en))
        out.append((d, f"{ac.EN[g]} in {SIGNS_EN[c[g].sign]} ({rel} sign), aspected by {who}: {t} (Book 3 Ch.1)"))
    # Mars aspecting houses 1,2,5,7,9,10 from Taurus while strengthened by benefic aspects
    ma = c['Ma']; houses = {(ma.sign + h - 1) % 12 for h in (4, 7, 8)}
    hit = sorted(((s - 1) % 12 + 1 for s in houses if ((s - 1) % 12 + 1) in (1, 2, 5, 7, 9, 10)))
    ben = [a for a in ac.b3_aspectors(c, 'Ma') if a in FRIENDS['Ma']]
    if hit and ben:
        out.append((-1, f"Mars aspects house(s) {', '.join(map(str, hit))} from Taurus and is strengthened by {', '.join(ac.EN[a] for a in ben)} → prices dragged down (Book 3 Ch.1)"))
    return out


def long_term(c) -> list:
    s = c['Sa'].sign
    if s in (0, 4, 8):
        h = {0: 12, 4: 4, 8: 8}[s]
        return [(-1, f"Saturn in {SIGNS_EN[s]} ({h}th from the Taurus ascendant of Indian markets) → selling pressure, recessionary (Book 3 Ch.1)")]
    return []


def sector_short(c, targets_by_sign) -> list:
    """Ch.2-13 opening paragraph for the Sun's sign. Returns [(targets, dir, text)]."""
    s = c['Su'].sign
    if s not in SUN_SECTOR: return []
    up, dn, d_up, d_dn = SUN_SECTOR[s]
    asp = ac.b3_aspectors(c, 'Su')
    a = [x for x in asp if x in up]; b = [x for x in asp if x in dn]
    out = []
    if a: out.append((targets_by_sign[s], d_up, f"Sun in {SIGNS_EN[s]} aspected by {', '.join(ac.EN[x] for x in a)} (Book 3 Ch.{s + 2} opening)"))
    if b: out.append((targets_by_sign[s], -1, f"Sun in {SIGNS_EN[s]} aspected by {', '.join(ac.EN[x] for x in b)} → selling pressure (Book 3 Ch.{s + 2} opening)"))
    return out
