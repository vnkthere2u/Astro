"""
astro_core.py — ephemeris layer for the Banerjee Stock-Market-Astrology engine.

Source of truth: Swiss Ephemeris (pyswisseph; JPL-DE-based, Moshier fallback when no
ephemeris files are installed — sub-arcsecond for planets in 1800-2400).  Sidereal zodiac
with N.C. Lahiri ayanāṃśa (the book: "all my calculations ... N.C. Lahiri ephemeris").
Node type and every other convention are selected by validate.py against the book's own
worked examples; see CONFIG below.
"""
from __future__ import annotations
import math
from dataclasses import dataclass, field
from datetime import datetime, date, time, timedelta, timezone
from functools import lru_cache
from zoneinfo import ZoneInfo
import swisseph as swe

# ------------------------------------------------------------------ configuration
CONFIG = dict(
    ayanamsa=swe.SIDM_LAHIRI,
    node=swe.TRUE_NODE,          # validated: true node matches 'Ketu changed rāśi in May 2008' and 'Guru–Rāhu within 30° in Jun 2008'
    hora_mode='equal60',         # book Fig.1 / worked examples: 60-minute horās from sunrise
    sunrise_disc='center',       # Hindu sunrise: centre of disc, with refraction
)
AYANAMSA_CHOICES = {'Lahiri': swe.SIDM_LAHIRI, 'Raman': swe.SIDM_RAMAN, 'Krishnamurti': swe.SIDM_KRISHNAMURTI,
                    'Fagan-Bradley': swe.SIDM_FAGAN_BRADLEY, 'Tropical': None}
NODE_CHOICES = {'true': swe.TRUE_NODE, 'mean': swe.MEAN_NODE}

GRAHAS = ['Su', 'Mo', 'Ma', 'Me', 'Ju', 'Ve', 'Sa', 'Ra', 'Ke', 'Ur', 'Ne', 'Pl']
NINE = GRAHAS[:9]
SWE_ID = {'Su': swe.SUN, 'Mo': swe.MOON, 'Ma': swe.MARS, 'Me': swe.MERCURY, 'Ju': swe.JUPITER, 'Ve': swe.VENUS,
          'Sa': swe.SATURN, 'Ur': swe.URANUS, 'Ne': swe.NEPTUNE, 'Pl': swe.PLUTO}
NAMES = {'Su': 'Sūrya', 'Mo': 'Candra', 'Ma': 'Maṅgala', 'Me': 'Budha', 'Ju': 'Guru', 'Ve': 'Śukra', 'Sa': 'Śani',
         'Ra': 'Rāhu', 'Ke': 'Ketu', 'Ur': 'Uranus', 'Ne': 'Neptune', 'Pl': 'Pluto'}
EN = {'Su': 'Sun', 'Mo': 'Moon', 'Ma': 'Mars', 'Me': 'Mercury', 'Ju': 'Jupiter', 'Ve': 'Venus', 'Sa': 'Saturn',
      'Ra': 'Rahu', 'Ke': 'Ketu', 'Ur': 'Uranus', 'Ne': 'Neptune', 'Pl': 'Pluto'}
RASI = ['Meṣa', 'Vṛṣabha', 'Mithuna', 'Karkaṭa', 'Siṃha', 'Kanyā', 'Tulā', 'Vṛścika', 'Dhanus', 'Makara', 'Kumbha', 'Mīna']
RASI_EN = ['Aries', 'Taurus', 'Gemini', 'Cancer', 'Leo', 'Virgo', 'Libra', 'Scorpio', 'Sagittarius', 'Capricorn', 'Aquarius', 'Pisces']
ELEMENT = ['Fire', 'Earth', 'Air', 'Water'] * 3
NAK = ['Aśvinī', 'Bharaṇī', 'Kṛttikā', 'Rohiṇī', 'Mṛgaśīrṣā', 'Ārdrā', 'Punarvasu', 'Puṣya', 'Aśleṣā', 'Maghā',
       'Pūrva Phālgunī', 'Uttara Phālgunī', 'Hasta', 'Citrā', 'Svāti', 'Viśākhā', 'Anurādhā', 'Jyeṣṭha', 'Mūla',
       'Pūrva Aṣāḍha', 'Uttara Aṣāḍha', 'Śravaṇa', 'Dhaniṣṭhā', 'Śatabhiṣak', 'Pūrva Bhādra', 'Uttara Bhādra', 'Revatī']
DASHA_ORDER = ['Ke', 'Ve', 'Su', 'Mo', 'Ma', 'Ra', 'Ju', 'Sa', 'Me']           # nakṣatra lords, Aśvinī→
DASHA_MIN = {'Su': 24, 'Mo': 40, 'Ma': 28, 'Ra': 72, 'Ju': 64, 'Sa': 76, 'Me': 68, 'Ke': 28, 'Ve': 80}  # Ch.12 Fig.3
HORA_CYCLE = ['Su', 'Ve', 'Me', 'Mo', 'Sa', 'Ju', 'Ma']                      # Ch.10 Fig.1
WEEKDAY_LORD = ['Mo', 'Ma', 'Me', 'Ju', 'Ve', 'Sa', 'Su']                    # Mon..Sun
NAK_SPAN = 360 / 27

# dignity (Ch.4): own, exaltation, debilitation rāśi indices; friends/enemies
OWN = {'Su': [4], 'Mo': [3], 'Ma': [0, 7], 'Me': [2, 5], 'Ju': [8, 11], 'Ve': [1, 6], 'Sa': [9, 10],
       'Ra': [], 'Ke': [], 'Ur': [10], 'Ne': [11], 'Pl': [7]}
EXALT = {'Su': 0, 'Mo': 1, 'Ma': 9, 'Me': 5, 'Ju': 3, 'Ve': 11, 'Sa': 6, 'Ra': 1, 'Ke': 7, 'Ur': 7, 'Ne': 4, 'Pl': 3}
DEBIL = {k: (v + 6) % 12 for k, v in EXALT.items()}
FRIENDS = {'Su': ['Mo', 'Ma', 'Ju'], 'Mo': ['Su', 'Me'], 'Ma': ['Su', 'Mo', 'Ju'], 'Me': ['Su', 'Ve'], 'Ju': ['Su', 'Mo', 'Ma'],
           'Ve': ['Me', 'Sa'], 'Sa': ['Me', 'Ve'], 'Ra': ['Me', 'Ve', 'Sa'], 'Ke': ['Me', 'Ve', 'Sa'], 'Ur': ['Me', 'Ve', 'Sa'],
           'Ne': ['Su', 'Mo', 'Me'], 'Pl': []}
ENEMIES = {'Su': ['Ve', 'Sa'], 'Mo': [], 'Ma': ['Me'], 'Me': ['Mo'], 'Ju': ['Me', 'Ve'], 'Ve': ['Su', 'Mo'], 'Sa': ['Su', 'Mo', 'Ma'],
           'Ra': ['Su', 'Mo', 'Ju'], 'Ke': ['Su', 'Mo', 'Ju'], 'Ur': ['Su', 'Mo', 'Ma'], 'Ne': [], 'Pl': []}
SIGN_LORD = ['Ma', 'Ve', 'Me', 'Mo', 'Su', 'Me', 'Ve', 'Ma', 'Ju', 'Sa', 'Sa', 'Ju']
NATURAL_BENEFIC = {'Ju', 'Ve', 'Me', 'Mo'}           # Ch.11 / Ch.7 rules 2,5,6,11-16 (Moon benefic when waxing)
NATURAL_MALEFIC = {'Sa', 'Ma', 'Ra', 'Ke', 'Su'}

# Vedic graha-dṛṣṭi houses (counted inclusively from the aspecting graha)
VEDIC_DRISHTI = {'Ma': (4, 7, 8), 'Ju': (5, 7, 9), 'Sa': (3, 7, 10), 'Ra': (5, 7, 9), 'Ke': (5, 7, 9)}
ASPECT_TYPE_WEIGHT = {1: 1.0, 7: 1.0, 4: 0.85, 8: 0.85, 3: 0.85, 10: 0.85, 5: 0.75, 9: 0.75}
MOIETY = {'Su': 15, 'Mo': 12, 'Ma': 7.5, 'Me': 7, 'Ju': 9, 'Ve': 7, 'Sa': 9, 'Ra': 9, 'Ke': 9, 'Ur': 5, 'Ne': 5, 'Pl': 5}  # Lilly

IST = ZoneInfo('Asia/Kolkata')
EXCHANGES = {
    'NSE/BSE Mumbai': dict(lat=19.0760, lon=72.8777, tz='Asia/Kolkata', open=time(9, 15), close=time(15, 30)),
    'MCX Mumbai (commodities)': dict(lat=19.0760, lon=72.8777, tz='Asia/Kolkata', open=time(9, 0), close=time(23, 30)),
    'Lucknow (author, book examples)': dict(lat=26.8467, lon=80.9462, tz='Asia/Kolkata', open=time(9, 55), close=time(15, 30)),
    'DFM/ADX UAE': dict(lat=25.2048, lon=55.2708, tz='Asia/Dubai', open=time(10, 0), close=time(15, 0)),
    'NYSE New York': dict(lat=40.7069, lon=-74.0113, tz='America/New_York', open=time(9, 30), close=time(16, 0)),
    'LSE London': dict(lat=51.5145, lon=-0.0886, tz='Europe/London', open=time(8, 0), close=time(16, 30)),
}

def set_config(ayanamsa='Lahiri', node='true'):
    CONFIG['ayanamsa'] = AYANAMSA_CHOICES[ayanamsa]
    CONFIG['node'] = NODE_CHOICES[node]
    positions_jd.cache_clear()

# ------------------------------------------------------------------ time helpers
def to_jd(dt: datetime) -> float:
    if dt.tzinfo is None: dt = dt.replace(tzinfo=timezone.utc)
    u = dt.astimezone(timezone.utc)
    return swe.julday(u.year, u.month, u.day, u.hour + u.minute / 60 + u.second / 3600 + u.microsecond / 3.6e9)

def from_jd(jd: float, tz=timezone.utc) -> datetime:
    y, m, d, h = swe.revjul(jd)
    base = datetime(y, m, d, tzinfo=timezone.utc) + timedelta(hours=h)
    return base.astimezone(tz)

def sep(a: float, b: float) -> float:
    d = abs(a - b) % 360
    return min(d, 360 - d)

def fmt_deg(lon: float) -> str:
    s = int(lon // 30); d = lon % 30
    return f"{RASI[s]} {int(d):02d}°{int(round((d % 1) * 60)) % 60:02d}′"

# ------------------------------------------------------------------ positions
@lru_cache(maxsize=200_000)
def positions_jd(jd: float, ayan=None, node=None) -> dict:
    ayan = CONFIG['ayanamsa'] if ayan is None else ayan
    node = CONFIG['node'] if node is None else node
    flags = swe.FLG_SPEED | swe.FLG_MOSEPH if False else swe.FLG_SPEED
    if ayan is not None:
        swe.set_sid_mode(ayan); flags |= swe.FLG_SIDEREAL
    out = {}
    for g, pid in SWE_ID.items():
        x = swe.calc_ut(jd, pid, flags)[0]
        out[g] = (x[0] % 360, x[3])
    x = swe.calc_ut(jd, node, flags)[0]
    out['Ra'] = (x[0] % 360, x[3]); out['Ke'] = ((x[0] + 180) % 360, x[3])
    return out

@dataclass
class Body:
    code: str; lon: float; speed: float
    @property
    def sign(self): return int(self.lon // 30)
    @property
    def deg(self): return self.lon % 30
    @property
    def retro(self): return self.speed < 0 and self.code not in ('Ra', 'Ke')
    @property
    def nak(self): return int(self.lon // NAK_SPAN)
    @property
    def pada(self): return int((self.lon % NAK_SPAN) // (NAK_SPAN / 4)) + 1

@dataclass
class Chart:
    dt: datetime
    bodies: dict
    asc: float | None = None
    def __getitem__(self, k): return self.bodies[k]
    @property
    def moon_nak(self): return self.bodies['Mo'].nak
    @property
    def tithi(self):  # 1..30
        return int(((self.bodies['Mo'].lon - self.bodies['Su'].lon) % 360) // 12) + 1
    @property
    def waxing(self): return self.tithi <= 15

def chart(dt: datetime, lat: float | None = None, lon: float | None = None, ayan=None, node=None) -> Chart:
    jd = to_jd(dt)
    jd_r = round(jd, 6)
    p = positions_jd(jd_r, ayan, node)
    c = Chart(dt=dt, bodies={g: Body(g, *p[g]) for g in GRAHAS})
    if lat is not None:
        c.asc = ascendant(jd, lat, lon, ayan)
    return c

def ascendant(jd: float, lat: float, lon: float, ayan=None) -> float:
    ayan = CONFIG['ayanamsa'] if ayan is None else ayan
    if ayan is None:
        return swe.houses(jd, lat, lon, b'W')[1][0] % 360
    swe.set_sid_mode(ayan)
    return swe.houses_ex(jd, lat, lon, b'W', swe.FLG_SIDEREAL)[1][0] % 360

# ------------------------------------------------------------------ dignity / strength (Ch.4, Ch.7 rule 1)
def dignity(g: str, sign: int) -> tuple[str, float]:
    if sign == EXALT.get(g): return 'exalted', 1.0
    if sign in OWN.get(g, []): return 'own', 0.75
    if sign == DEBIL.get(g): return 'debilitated', -1.0
    lord = SIGN_LORD[sign]
    if lord in FRIENDS.get(g, []): return 'friendly', 0.4
    if lord in ENEMIES.get(g, []): return 'inimical', -0.5
    return 'neutral', 0.0

def combust(c: Chart, g: str) -> bool:
    orb = {'Mo': 12, 'Ma': 17, 'Me': 14, 'Ju': 11, 'Ve': 10, 'Sa': 15}.get(g)
    return orb is not None and sep(c[g].lon, c['Su'].lon) < orb

# ------------------------------------------------------------------ aspects (Ch.9, calibrated by validate.py)
def house_from(a_sign: int, b_sign: int) -> int:
    return (b_sign - a_sign) % 12 + 1

def casts_aspect(c: Chart, a: str, b: str) -> tuple[bool, int, float]:
    """Does graha a aspect graha b?  (calibrated in validate.py against the book's worked examples)
    1. Vedic graha-dṛṣṭi, sign based: conjunction (same rāśi), 7th for all, Maṅgala 4/8, Guru 5/9, Śani 3/10, Rāhu/Ketu 5/9.
    2. Trine (Ch.9, 120°) for every graha, degree based within the classical moiety orb (mean of both grahas' moieties).
    returns (bool, house_count, strength 0..1)."""
    if a == b or {a, b} == {'Ra', 'Ke'}: return (False, 0, 0.0)
    A, B = c[a], c[b]
    h = house_from(A.sign, B.sign)
    d = (B.lon - A.lon) % 360
    if h in ({1, 7} | set(VEDIC_DRISHTI.get(a, ()))):
        exact = (h - 1) * 30
        dev = min(abs(d - exact), 360 - abs(d - exact))
        return (True, h, ASPECT_TYPE_WEIGHT.get(h, 0.75) * (1 - 0.5 * min(dev, 30) / 30))
    dev = abs(sep(A.lon, B.lon) - 120)
    orb = (MOIETY[a] + MOIETY[b]) / 2
    if dev <= orb:
        return (True, 5 if h in (4, 5, 6) else 9, 0.75 * (1 - 0.5 * dev / orb))
    return (False, h, 0.0)

def aspects_on(c: Chart, target: str, pool=NINE + ['Ur', 'Ne', 'Pl']) -> dict:
    out = {}
    for a in pool:
        ok, h, s = casts_aspect(c, a, target)
        if ok: out[a] = (h, round(s, 3))
    return out

def aspect_matrix(c: Chart) -> dict:
    return {t: aspects_on(c, t) for t in GRAHAS}

def degree_aspect(c: Chart, a: str, b: str, angles=(0, 120, 180), orb=3.0):
    s = sep(c[a].lon, c[b].lon)
    for A in angles:
        if abs(s - A) <= orb: return A, abs(s - A)
    return None

# ------------------------------------------------------------------ hemming / crowding (Ch.7 rules 11-17)
def hemmed(c: Chart, g: str) -> str | None:
    s = c[g].sign
    prev = {x for x in NINE if x != g and c[x].sign == (s - 1) % 12}
    nxt = {x for x in NINE if x != g and c[x].sign == (s + 1) % 12}
    if prev & NATURAL_MALEFIC and nxt & NATURAL_MALEFIC: return 'malefic'
    if prev & NATURAL_BENEFIC and nxt & NATURAL_BENEFIC: return 'benefic'
    return None

def crowding(c: Chart) -> dict:
    cnt = {}
    for g in NINE:
        cnt.setdefault(c[g].sign, []).append(g)
    return cnt

# ------------------------------------------------------------------ sunrise, horā (Ch.10)
def sunrise(d: date, lat: float, lon: float, tz: str) -> datetime:
    z = ZoneInfo(tz)
    start = datetime(d.year, d.month, d.day, 0, 0, tzinfo=z)
    jd0 = to_jd(start)
    flag = swe.CALC_RISE | (swe.BIT_DISC_CENTER if CONFIG['sunrise_disc'] == 'center' else 0)
    res = swe.rise_trans(jd0, swe.SUN, flag, (lon, lat, 0), 1013.25, 15)
    return from_jd(res[1][0], z)

def hora_table(d: date, lat: float, lon: float, tz: str, sr: datetime | None = None, mode=None) -> list:
    mode = mode or CONFIG['hora_mode']
    sr = sr or sunrise(d, lat, lon, tz)
    first = WEEKDAY_LORD[d.weekday()]
    i0 = HORA_CYCLE.index(first)
    rows = []
    if mode == 'equal60':
        for k in range(24):
            st = sr + timedelta(hours=k)
            rows.append((st, st + timedelta(hours=1), HORA_CYCLE[(i0 + k) % 7]))
    else:  # proportional day/night horās
        sr2 = sunrise(d + timedelta(days=1), lat, lon, tz)
        z = ZoneInfo(tz)
        jd0 = to_jd(sr)
        ss = from_jd(swe.rise_trans(jd0, swe.SUN, swe.CALC_SET | swe.BIT_DISC_CENTER, (lon, lat, 0), 1013.25, 15)[1][0], z)
        dl = (ss - sr) / 12; nl = (sr2 - ss) / 12
        for k in range(12): rows.append((sr + dl * k, sr + dl * (k + 1), HORA_CYCLE[(i0 + k) % 7]))
        for k in range(12): rows.append((ss + nl * k, ss + nl * (k + 1), HORA_CYCLE[(i0 + 12 + k) % 7]))
    return rows

# ------------------------------------------------------------------ micro-viṃśottarī (Ch.12)
def micro_dasha(moon_lon: float, start: datetime, until: datetime | None = None) -> list:
    nk = int(moon_lon // NAK_SPAN)
    lord = DASHA_ORDER[nk % 9]
    frac_left = 1 - (moon_lon % NAK_SPAN) / NAK_SPAN
    out = []
    t = start
    bal = timedelta(minutes=DASHA_MIN[lord] * frac_left)
    out.append((t, t + bal, lord)); t += bal
    i = DASHA_ORDER.index(lord)
    until = until or start + timedelta(hours=16)
    while t < until:
        i = (i + 1) % 9; L = DASHA_ORDER[i]
        e = t + timedelta(minutes=DASHA_MIN[L]); out.append((t, e, L)); t = e
    return out

# ------------------------------------------------------------------ eclipses (Ch.7 rules 9-10, Ch.15)
@lru_cache(maxsize=64)
def eclipses_in_year(year: int) -> tuple:
    out = []
    jd = swe.julday(year, 1, 1, 0); end = swe.julday(year + 1, 1, 1, 0)
    t = jd
    while True:
        r = swe.sol_eclipse_when_glob(t, swe.FLG_SWIEPH, 0)
        if r[1][0] > end: break
        out.append(('solar', r[1][0])); t = r[1][0] + 10
    t = jd
    while True:
        r = swe.lun_eclipse_when(t, swe.FLG_SWIEPH, 0)
        if r[1][0] > end: break
        out.append(('lunar', r[1][0])); t = r[1][0] + 10
    return tuple(sorted(out, key=lambda x: x[1]))

def eclipse_near(dt: datetime, window_days=3):
    jd = to_jd(dt)
    for y in (dt.year - 1, dt.year, dt.year + 1):
        for kind, t in eclipses_in_year(y):
            if abs(t - jd) <= window_days: return kind, from_jd(t)
    return None

# ------------------------------------------------------------------ ingress search
def find_ingresses(g: str, start: date, end: date, step_days=1.0):
    out = []; d = datetime(start.year, start.month, start.day, tzinfo=timezone.utc)
    prev = chart(d)[g].sign
    while d.date() <= end:
        d2 = d + timedelta(days=step_days); s = chart(d2)[g].sign
        if s != prev:
            lo, hi = d, d2
            for _ in range(30):
                mid = lo + (hi - lo) / 2
                if chart(mid)[g].sign == prev: lo = mid
                else: hi = mid
            out.append((hi, prev, s))
            prev = s
        d = d2
    return out

# ================================================================== additions for Books 2 & 3
# Book 3 ('Predicting the Nifty & Sensex') aspect convention — verified 6/6 against its Ch.14 worked examples:
# sign-based Vedic graha-dṛṣṭi; conjunction counts as an aspect; Rāhu/Ketu aspect only by conjunction / 7th.
B3_DRISHTI = {'Ma': (4, 7, 8), 'Ju': (5, 7, 9), 'Sa': (3, 7, 10), 'Ra': (7,), 'Ke': (7,)}

def b3_aspectors(c: Chart, target: str) -> list:
    out = []
    for a in NINE:
        if a == target: continue
        h = house_from(c[a].sign, c[target].sign)
        if h == 1 or h in B3_DRISHTI.get(a, (7,)):
            out.append(a)
    return out

def b3_conjunct(c: Chart, target: str) -> list:
    return [a for a in NINE if a != target and c[a].sign == c[target].sign]

AVASTHA = ['Baal', 'Kumar', 'Yuva', 'Vriddha', 'Mrita']   # 6° bands from 0° in odd signs; reversed in even signs
def avastha(lon: float) -> str:
    s = int(lon // 30); d = lon % 30
    i = min(int(d // 6), 4)
    return AVASTHA[i] if s % 2 == 0 else AVASTHA[4 - i]

YOGA_NAMES = ['Vishkumbha', 'Priti', 'Ayushman', 'Saubhagya', 'Shobhana', 'Atiganda', 'Sukarma', 'Dhriti', 'Shoola',
              'Ganda', 'Vriddhi', 'Dhruva', 'Vyaghata', 'Harshana', 'Vajra', 'Siddhi', 'Vyatipata', 'Variyan', 'Parigha',
              'Shiva', 'Siddha', 'Sadhya', 'Shubha', 'Shukla', 'Brahma', 'Indra', 'Vaidhriti']
def yoga_index(c: Chart) -> int:                      # 0..26
    return int(((c['Su'].lon + c['Mo'].lon) % 360) // NAK_SPAN)

KARANA_MOVABLE = ['Bava', 'Balava', 'Kaulava', 'Taitila', 'Gara', 'Vanija', 'Vishti']
def karana(c: Chart) -> str:
    k = int(((c['Mo'].lon - c['Su'].lon) % 360) // 6)  # 0..59
    if k == 0: return 'Kintughna'
    if k >= 57: return ['Shakuni', 'Chatushpada', 'Naga'][k - 57]
    return KARANA_MOVABLE[(k - 1) % 7]

TITHI_NAMES = ['Pratipada', 'Dwitiya', 'Tritiya', 'Chaturthi', 'Panchami', 'Shashthi', 'Saptami', 'Ashtami', 'Navami',
               'Dashami', 'Ekadashi', 'Dwadashi', 'Trayodashi', 'Chaturdashi']
def tithi_name(t: int) -> str:                        # t = 1..30
    if t == 15: return 'Shukla Purnima'
    if t == 30: return 'Krishna Amavasya'
    return ('Shukla ' if t <= 15 else 'Krishna ') + TITHI_NAMES[(t - 1) % 15]

def sunset(d: date, lat: float, lon: float, tz: str) -> datetime:
    z = ZoneInfo(tz)
    jd0 = to_jd(datetime(d.year, d.month, d.day, 0, 0, tzinfo=z))
    flag = swe.CALC_SET | (swe.BIT_DISC_CENTER if CONFIG['sunrise_disc'] == 'center' else 0)
    return from_jd(swe.rise_trans(jd0, swe.SUN, flag, (lon, lat, 0), 1013.25, 15)[1][0], z)

LUNAR_MONTHS = ['Chaitra', 'Vaishakha', 'Jyeshtha', 'Ashadha', 'Shravana', 'Bhadrapada', 'Ashwin', 'Kartika',
                'Margashirsha', 'Pausha', 'Magha', 'Phalguna']
def lunar_month(dt: datetime) -> str:
    """Amānta month: named from the Sun's rāśi at the new moon that began the month (Sun in Mīna → Chaitra)."""
    c = chart(dt)
    back = ((c['Mo'].lon - c['Su'].lon) % 360) / 12.19     # ≈ days since new moon
    t = dt - timedelta(days=back)
    for _ in range(40):                                   # refine to the conjunction
        cc = chart(t); el = (cc['Mo'].lon - cc['Su'].lon) % 360
        if el > 180: el -= 360
        if abs(el) < 1e-4: break
        t -= timedelta(days=el / 12.19)
    return LUNAR_MONTHS[(chart(t)['Su'].sign + 1) % 12]

def eclipse_times(year: int) -> list:
    """[(kind, max_dt_utc)] for the year (solar & lunar)."""
    return [(k, from_jd(t)) for k, t in eclipses_in_year(year)]
