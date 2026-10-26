"""
book2.py — Book 2: Indrodeep Banerjee, "Investment Muhurtas" (2014).

How the book links muhurta to market direction (Ch.1, repeated in Ch.34):
  "the markets pick up during the auspicious days … the markets reflect the bearish activity during the
   inauspicious days" — so every factor the book calls good for buying / investing is an Up vote and every factor
   it calls good only for selling / profit-booking (or inauspicious for investment) is a Down vote, for that day.

Day factors (votes) — evaluated at the opening bell, the book's own practice in Ch.34 ("buy at opening"):
  Ch.3  tithi trading table ("Favourable / Unfavourable for Trading"), Dagdha/Visha/Hutashan tithi-weekday,
        Amavasya, Sankranti, eclipse, kshaya/vriddhi tithi, Galgraha tithis, month-specific prohibited tithis,
        the four ever-auspicious tithis
  Ch.4  gentle (Mon/Wed/Thu/Fri) vs cruel (Sun/Tue/Sat) weekdays, sector notes for Tuesday / Sunday
  Ch.5  nakshatra trading table (repeated in Ch.34), Panchaka, Gand-moola and Dagdha nakshatras
  Ch.6  karana; Ch.7 yoga table; Ch.16 eclipse ±3 days; Jupiter/Venus combust; Ch.17 Sankranti ±6h24m
  Ch.20 Panchaka elimination (tithi + weekday + nakshatra + ascendant, mod 9)
  Ch.21 Siddha / Sarvartha-Siddhi / Amrit-Siddhi yogas — "destroys any inauspicious yoga present"
Timing windows (shown, not voted): Rahu Kalam, Yamakandam, Gulika (Ch.9-11 tables), Gouri Panchanga (Ch.12),
  Chaughadia (Ch.13), Hora (Ch.14), Durmuhurta (Ch.33), Abhijit (Ch.21).
Ch.34: trend reversals possible from 5 days before to 5 days after any planet's change of sign
  (Sun, Mars, Mercury, Venus → short-term reversals).
Personal factors (Tara bala, Chandra bala, Janma nakshatra) need the investor's birth star — optional input.
"""
from __future__ import annotations
from datetime import datetime, timedelta, date
import astro_core as ac

WD = lambda d: (d.weekday() + 1) % 7      # 0 = Sunday … 6 = Saturday (book tables start at Sunday)
DAYN = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday']

# ---- Ch.3 tithi (1..15 within paksha; 15 = Purnima / Amavasya)
TITHI_TRADE = {1: 0, 2: 1, 3: 1, 4: -1, 5: 1, 6: 0, 7: 1, 8: -1, 9: -1, 10: 1, 11: 1, 12: 0, 13: 1, 14: -1, 15: 0}
TITHI_CLASS = {1: 'Nanda', 6: 'Nanda', 11: 'Nanda', 2: 'Bhadra', 7: 'Bhadra', 12: 'Bhadra', 3: 'Jaya', 8: 'Jaya', 13: 'Jaya',
               4: 'Rikta', 9: 'Rikta', 14: 'Rikta', 5: 'Purna', 10: 'Purna', 15: 'Purna'}
SIDDHA_DAY = {'Nanda': 5, 'Bhadra': 3, 'Jaya': 2, 'Rikta': 6, 'Purna': 4}     # weekday (0=Sun)
DAGDHA = {0: [12], 1: [11], 2: [5], 3: [3], 4: [6], 5: [8]}                   # Saturday column cut off in the book
VISHA = {0: [4], 1: [6], 2: [7], 3: [2], 4: [8], 5: [9]}
HUTASHAN = {0: [12], 1: [6], 2: [7], 3: [8], 4: [9], 5: [10]}
GALGRAHA_BOTH = {1, 7, 8, 9, 13, 14, 15}                                      # + 4th of the dark half
MONTH_BAN = {('Jyeshtha', 2), ('Ashadha', 10), ('Pausha', 11), ('Magha', 12)}  # Shukla tithis
EVER_AUSPICIOUS = {('Chaitra', 1): 'Chaitra Shukla Pratipada', ('Vaishakha', 3): 'Akshaya Tritiya',
                   ('Ashwin', 10): 'Vijaya Dashami', ('Kartika', 1): 'Kartika Shukla Pratipada'}
# ---- Ch.5 nakshatra (0 = Ashwini)
NAK_TRADE = [-1, -1, -1, 1, 1, -1, 1, 1, -1, -1, -1, 1, 1, -1, 1, -1, 1, -1, -1, -1, 1, 1, -1, -1, -1, 1, -1]
PANCHAKA = {22, 23, 24, 25, 26}
GANDMOOLA = {0, 8, 9, 17, 18, 26}
DAGDHA_NAK = {0: 1, 1: 13, 2: 20, 3: 22, 4: 11, 5: 17, 6: 26}               # weekday -> nakshatra
SARVARTHA = {0: {12, 7, 8, 11, 20, 25}, 1: {4, 3, 7, 16, 21}, 2: {0, 2, 8, 25}, 3: {15, 16, 2, 3, 4, 12},
             4: {7, 0, 6, 16, 26}, 5: {21, 0, 6, 16, 26}, 6: {3, 14, 21}}
AMRIT_SIDDHI = {0: 12, 1: 4, 2: 0, 3: 15, 4: 7, 5: 26, 6: 3}
MOVABLE_NAK = {6, 14, 21, 22, 23}
# ---- Ch.7 yoga (0 = Vishkumbha)
YOGA_BAD = {0, 5, 8, 9, 12, 14, 16, 18, 26}
# ---- Ch.6 karana
KARANA_DIR = {'Shakuni': 1, 'Chatushpada': 1, 'Kintughna': 1, 'Bava': 1, 'Balava': 1, 'Kaulava': 1, 'Gara': 1,
              'Naga': -1, 'Vanija': -1, 'Vishti': -1, 'Taitila': 0}
KARANA_TEXT = {'Vanija': 'selling is more profitable than buying', 'Vishti': 'forbidden for all major investments',
               'Naga': 'good for selling / profit booking', 'Taitila': 'for churning an existing portfolio'}
# ---- Ch.9-11 eighth-of-day tables (1-based part number, Sunday first) — read from the book's tables
GULIKA = [7, 6, 5, 4, 3, 2, 1]
RAHU = [8, 2, 7, 5, 6, 4, 3]
YAMA = [5, 4, 3, 2, 1, 6, 7]
GOURI_DAY = [['Udit', 'Labha', 'Visha', 'Amrit', 'Shubha', 'Dana', 'Amrit', 'Roga'],
             ['Amrit', 'Visha', 'Udit', 'Labha', 'Shora', 'Shubha', 'Amrit', 'Dana'],
             ['Roga', 'Udit', 'Shora', 'Labha', 'Amrit', 'Udit', 'Visha', 'Dana'],
             ['Visha', 'Amrit', 'Shubha', 'Udit', 'Shora', 'Labha', 'Dana', 'Amrit'],
             ['Udit', 'Visha', 'Shora', 'Labha', 'Amrit', 'Roga', 'Kalah', 'Roga'],
             ['Roga', 'Shora', 'Amrit', 'Visha', 'Labha', 'Shubha', 'Dana', 'Amrit'],
             ['Visha', 'Amrit', 'Roga', 'Udit', 'Shubha', 'Labha', 'Dana', 'Labha']]
GOURI_GOOD = {'Amrit', 'Udit', 'Labha', 'Shubha', 'Dana'}; GOURI_BAD = {'Visha', 'Shora', 'Roga'}
CHAUGHADIA_DAY = [['Udwega', 'Chara', 'Laabh', 'Amrit', 'Kaala', 'Shubh', 'Roga', 'Udwega'],
                  ['Amrit', 'Kaala', 'Shubh', 'Roga', 'Udwega', 'Chara', 'Laabh', 'Amrit'],
                  ['Roga', 'Udwega', 'Chara', 'Laabh', 'Amrit', 'Kaala', 'Shubh', 'Roga'],
                  ['Laabh', 'Amrit', 'Kaala', 'Shubh', 'Roga', 'Udwega', 'Chara', 'Laabh'],
                  ['Shubh', 'Roga', 'Udwega', 'Chara', 'Laabh', 'Amrit', 'Kaala', 'Shubh'],
                  ['Chara', 'Laabh', 'Amrit', 'Kaala', 'Shubh', 'Roga', 'Udwega', 'Chara'],
                  ['Kaala', 'Shubh', 'Roga', 'Udwega', 'Chara', 'Laabh', 'Amrit', 'Kaala']]
CH_GOOD = {'Amrit', 'Shubh', 'Laabh'}; CH_BAD = {'Udwega', 'Roga', 'Kaala'}
HORA_DIR = {'Su': -1, 'Mo': 1, 'Ma': -1, 'Me': 1, 'Ju': 1, 'Ve': 1, 'Sa': -1}
DURMUHURTA_DAY = {1, 2, 4, 10, 11, 12, 15}


def _v(out, d, factor, text, targets='ALL'):
    out.append(dict(dir=d, factor=factor, text=text, targets=targets))


def day(d: date, c_open, lat, lon, tz, birth_nak: int | None = None) -> dict:
    """All Book 2 factors for trading date d. c_open = chart at the opening bell (with ascendant)."""
    w = WD(d); t30 = c_open.tithi; t = (t30 - 1) % 15 + 1; shukla = t30 <= 15
    nk = c_open.moon_nak; yg = ac.yoga_index(c_open); kr = ac.karana(c_open)
    month = ac.lunar_month(c_open.dt)
    votes = []; notes = []
    tname = ac.tithi_name(t30)
    # ----- tithi
    td = TITHI_TRADE[t] if not (t == 15) else 0
    _v(votes, td, 'Tithi (Ch.3 trading table)', f"{tname}: {'buying' if td > 0 else 'selling' if td < 0 else 'neutral'} tithi")
    if t30 == 30: _v(votes, -1, 'Amavasya (Ch.3a)', 'Amavasya — only selling / profit booking advisable')
    cls = TITHI_CLASS[t]
    if SIDDHA_DAY[cls] == w:
        siddha = True; _v(votes, 1, 'Siddha yoga (Ch.21)', f"{cls} tithi on {DAYN[w]} — Siddha yoga, destroys inauspicious yogas")
    else: siddha = False
    for tab, nm in ((DAGDHA, 'Dagdha'), (VISHA, 'Visha'), (HUTASHAN, 'Hutashan')):
        if t in tab.get(w, []): _v(votes, -1, f'{nm} tithi (Ch.3)', f"{tname} on {DAYN[w]} is {nm} — selling / short selling advisable", 'yoga-dosha')
    if t in GALGRAHA_BOTH or (not shukla and t == 4):
        _v(votes, -1, 'Galgraha tithi (Ch.3j)', f"{tname} is Galgraha — only selling / profit booking advisable")
    if shukla and (month, t) in MONTH_BAN:
        _v(votes, -1, 'Month-prohibited tithi (Ch.3k-n)', f"Shukla {t} in {month} — avoid investment, selling advisable")
    if shukla and (month, t) in EVER_AUSPICIOUS:
        _v(votes, 1, 'Ever-auspicious tithi (Ch.3)', f"{EVER_AUSPICIOUS[(month, t)]} — the whole tithi is auspicious")
    # kshaya / vriddhi (tithi at sunrise today vs tomorrow)
    sr = ac.sunrise(d, lat, lon, tz); sr2 = ac.sunrise(d + timedelta(days=1), lat, lon, tz)
    a, b = ac.chart(sr).tithi, ac.chart(sr2).tithi
    gap = (b - a) % 30
    if gap == 2: _v(votes, -1, 'Kshaya tithi (Ch.3a)', 'a tithi is skipped today (kshaya) — only selling advisable')
    if gap == 0: _v(votes, -1, 'Vriddhi tithi (Ch.3a)', 'the same tithi prevails at two sunrises (vriddhi) — only selling advisable')
    # ----- weekday
    if w in (1, 3, 4, 5): _v(votes, 1, 'Weekday (Ch.4)', f"{DAYN[w]} is a gentle day — auspicious for investing")
    else: _v(votes, -1, 'Weekday (Ch.4)', f"{DAYN[w]} is a cruel day — selling / profit booking advisable")
    if w == 2: _v(votes, 1, 'Tuesday sectors (Ch.4)', 'Tuesday favourable for pharma, crude, metals, capital goods, automobiles',
                  ['PHARMA', 'HEALTH', 'CRUDE', 'OILGAS', 'METAL', 'STEEL', 'CAPGOODS', 'AUTO'])
    if w == 0: _v(votes, 1, 'Sunday (Ch.4)', 'Sunday favourable for gold ornaments and garments', ['GOLD', 'GEMS', 'TEXTILE'])
    if w == 4: notes.append('Thursday: auspicious for the educational sector (Ch.4).')
    if w == 1 and shukla: notes.append('Waxing Moon on a Monday: good for speculation and financial matters (Ch.4).')
    # ----- nakshatra
    nd = NAK_TRADE[nk]
    _v(votes, nd, 'Nakshatra (Ch.5 / Ch.34 trading table)', f"{ac.NAK[nk]}: favourable for {'buying' if nd > 0 else 'selling'}")
    if nk in PANCHAKA: _v(votes, -1, 'Panchaka nakshatra (Ch.5)', f"{ac.NAK[nk]} is a Panchaka nakshatra — investments avoided")
    if nk in GANDMOOLA: _v(votes, -1, 'Gand-moola nakshatra (Ch.5)', f"{ac.NAK[nk]} is Gand-moola — stock-market investment avoided")
    if DAGDHA_NAK[w] == nk: _v(votes, -1, 'Dagdha nakshatra (Ch.5)', f"{ac.NAK[nk]} on {DAYN[w]} is Dagdha — investment prohibited", 'yoga-dosha')
    if nk == 7 and w == 4: _v(votes, 1, 'Guru-Pushya (Ch.1)', 'Pushya on Thursday — gold demand and prices rise', ['GOLD'])
    if shukla and month == 'Vaishakha' and t == 3: _v(votes, 1, 'Akshaya Tritiya (Ch.1)', 'Akshaya Tritiya — gold prices rise', ['GOLD'])
    if nk in MOVABLE_NAK: _v(votes, 1, 'Movable nakshatra (Ch.5)', f"{ac.NAK[nk]} is movable — favourable for automobile sector", ['AUTO'])
    sarv = nk in SARVARTHA[w]; amrit = AMRIT_SIDDHI[w] == nk
    if amrit: _v(votes, 1, 'Amrit-Siddhi yoga (Ch.21)', f"{DAYN[w]} + {ac.NAK[nk]} — Amrit-Siddhi yoga, ensures profit")
    elif sarv: _v(votes, 1, 'Sarvartha-Siddhi yoga (Ch.21)', f"{DAYN[w]} + {ac.NAK[nk]} — Sarvartha-Siddhi yoga, ensures profit")
    # ----- yoga
    yd = -1 if yg in YOGA_BAD else 1
    _v(votes, yd, 'Yoga (Ch.7 table)', f"{ac.YOGA_NAMES[yg]} yoga: {'bad' if yd < 0 else 'good'} for investment", 'yoga-dosha' if yd < 0 else 'ALL')
    # ----- karana
    _v(votes, KARANA_DIR[kr], 'Karana (Ch.6)', f"{kr} karana" + (f" — {KARANA_TEXT[kr]}" if kr in KARANA_TEXT else ' — good for buying'))
    # ----- tithi-specific sectors
    if t == 5: _v(votes, 1, 'Panchami (Ch.3)', 'Panchami favourable for pharma / health care', ['PHARMA', 'HEALTH'])
    if t == 7: _v(votes, 1, 'Saptami (Ch.3)', 'Saptami favourable for travel, airlines, automobiles', ['TRAVEL', 'AVIATION', 'AUTO'])
    if t == 14: _v(votes, 1, 'Chaturdashi (Ch.3)', 'Chaturdashi good for pharma / industrial chemicals', ['PHARMA'])
    # ----- eclipse / sankranti / combustion
    o = c_open.dt; cl = o + timedelta(hours=6, minutes=15)
    for kind, mx in ac.eclipse_times(o.year) + ac.eclipse_times(o.year + 1) + ac.eclipse_times(o.year - 1):
        mx = mx.astimezone(o.tzinfo)
        pre, post = (timedelta(hours=12), timedelta(hours=6)) if kind == 'solar' else (timedelta(hours=9), timedelta(hours=4, minutes=30))
        if mx - pre <= cl and o <= mx + post:
            _v(votes, -1, 'Eclipse (Ch.3a / Ch.16)', f"{kind} eclipse {mx:%d-%b %H:%M} overlaps the session — only selling advisable")
        elif abs((mx.date() - d).days) <= 3:
            _v(votes, -1, 'Eclipse ±3 days (Ch.16)', f"within 3 days of the {kind} eclipse of {mx:%d-%b} — major investments prohibited")
    for tt, a_, b_ in ac.find_ingresses('Su', d - timedelta(days=2), d + timedelta(days=1)):
        tt = tt.astimezone(o.tzinfo)
        if tt - timedelta(hours=6, minutes=24) <= cl and o <= tt + timedelta(hours=6, minutes=24):
            _v(votes, -1, 'Sankranti (Ch.3a / Ch.17)', f"Sun enters {ac.RASI_EN[b_]} at {tt:%d-%b %H:%M} — avoid buying ±6h24m")
    for g in ('Ju', 'Ve'):
        if ac.combust(c_open, g): _v(votes, -1, f"{ac.EN[g]} combust (Ch.16)", f"{ac.EN[g]} is combust (set) — major investments prohibited")
    # ----- Ch.20 Panchaka elimination at the opening bell
    lag = int(c_open.asc // 30) + 1 if c_open.asc is not None else None
    if lag:
        rem = (t30 + (w + 1) + (nk + 1) + lag) % 9
        good = rem in (0, 3, 5, 7)
        names = {1: 'Mrityu', 2: 'Agni', 4: 'Raja', 6: 'Chora', 8: 'Roga'}
        _v(votes, 1 if good else -1, 'Panchaka elimination (Ch.20)',
           f"tithi {t30} + weekday {w + 1} + nakshatra {nk + 1} + ascendant {lag} → remainder {rem}: "
           + ('free of Panchaka' if good else f"{names[rem]} Panchaka — avoid investing"))
    # ----- Ch.21 auspicious yogas destroy inauspicious yogas
    if siddha or sarv or amrit:
        for x in votes:
            if x['targets'] == 'yoga-dosha' and x['dir'] < 0:
                x['dir'] = 0; x['text'] += ' — cancelled by Siddha / Sarvartha / Amrit-Siddhi yoga (Ch.21)'
    for x in votes:
        if x['targets'] == 'yoga-dosha': x['targets'] = 'ALL'
    # ----- slow-down months
    if month in ('Bhadrapada', 'Pausha'): notes.append(f"{month} month: reduced business activity; at times reversals (Ch.1).")
    if month == 'Bhadrapada' and not shukla: notes.append('Pitru Paksha: reduced business activity; at times reversals (Ch.1).')
    # ----- personal
    if birth_nak is not None:
        n = (nk - birth_nak) % 27 + 1; r = n % 9
        tb = r in (2, 4, 6, 8, 0)
        _v(votes, 1 if tb else -1, 'Tara bala (Ch.8, personal)', f"count {n} from your birth star → remainder {r}: {'favourable' if tb else 'avoid investing'}")
        if nk == birth_nak: _v(votes, -1, 'Janma nakshatra (Ch.5, personal)', 'your birth star — avoid major investments')
    return dict(votes=votes, notes=notes, tithi=tname, nakshatra=ac.NAK[nk], yoga=ac.YOGA_NAMES[yg], karana=kr,
                weekday=DAYN[w], month=month, siddha=siddha, sarvartha=sarv, amrit=amrit)


def windows(d: date, lat, lon, tz) -> list:
    """Intraday timing windows from sunrise–sunset (Ch.9-14, 21, 33)."""
    w = WD(d); sr = ac.sunrise(d, lat, lon, tz); ss = ac.sunset(d, lat, lon, tz)
    L = (ss - sr) / 8; M = (ss - sr) / 15
    part = lambda k: (sr + L * (k - 1), sr + L * k)
    out = []
    out.append(dict(kind='Rahu Kalam', start=part(RAHU[w])[0], end=part(RAHU[w])[1], dir=-1, text='no investment (Ch.10)'))
    out.append(dict(kind='Yamakandam', start=part(YAMA[w])[0], end=part(YAMA[w])[1], dir=-1, text='investment fails (Ch.11)'))
    out.append(dict(kind='Gulika', start=part(GULIKA[w])[0], end=part(GULIKA[w])[1], dir=1, text='buying allowed, do not sell / short (Ch.9)'))
    for k in range(8):
        g = GOURI_DAY[w][k]; s, e = part(k + 1)
        out.append(dict(kind=f'Gouri: {g}', start=s, end=e, dir=1 if g in GOURI_GOOD else -1 if g in GOURI_BAD else 0, text='Ch.12'))
        ch = CHAUGHADIA_DAY[w][k]
        out.append(dict(kind=f'Chaughadia: {ch}', start=s, end=e, dir=1 if ch in CH_GOOD else -1 if ch in CH_BAD else 0,
                        text='Ch.13' + (' — medium, good for trading' if ch == 'Chara' else '')))
    for k in range(1, 16):
        s, e = sr + M * (k - 1), sr + M * k
        bad = k in DURMUHURTA_DAY or (k == 8 and w in (1, 5)) or (k == 14 and w == 0)
        if bad: out.append(dict(kind='Durmuhurta', start=s, end=e, dir=-1, text=f'day muhurta {k} inauspicious (Ch.33)'))
        if k == 8 and not bad: out.append(dict(kind='Abhijit', start=s, end=e, dir=1, text='victorious — ideal to initiate investments (Ch.21)'))
    for s, e, lord in ac.hora_table(d, lat, lon, tz)[:13]:
        out.append(dict(kind=f'Hora: {ac.EN[lord]}', start=s, end=e, dir=HORA_DIR[lord], text='Ch.14'))
    return out


def reversal_window(c) -> list:
    """Ch.34: "trend reversals are visible any time from before five days to after five days of change in zodiacal sign
    of any planet … during the period of change of sign the planet happens to be in Mrita and Bala awastha".
    A planet is in the window if either statement holds: (a) its sign change is within 5 days, or (b) it is in Mrita /
    Baal avasthā, reading its degree in whole degrees as the book quotes them (0°-6° or 24°-30° of the sign).
    Together these reproduce all 21 planet citations in the book's ten Ch.34 trades. Moon excluded (never cited)."""
    out = []; d = c.dt.date()
    for g in ('Su', 'Ma', 'Me', 'Ve', 'Ju', 'Sa', 'Ra'):
        b = c[g]; w = round(b.deg)
        why = None
        if w <= 6 or w >= 24:
            why = f"{w}° {ac.RASI_EN[b.sign]} ({'Baal/Mrita'} avasthā)"
        else:
            for tt, a_, b_ in ac.find_ingresses(g, d - timedelta(days=6), d + timedelta(days=6)):
                dd = (tt.date() - d).days
                if abs(dd) <= 5:
                    why = f"{w}° {ac.RASI_EN[b.sign]}, {'enters ' + ac.RASI_EN[b_] + ' in ' + str(dd) + ' day(s)' if dd >= 0 else 'entered ' + ac.RASI_EN[b_] + ' ' + str(-dd) + ' day(s) ago'}"
                    break
        if why:
            out.append(dict(planet=g, deg=b.deg, sign=b.sign, short=g in ('Su', 'Ma', 'Me', 'Ve'),
                            text=f"{ac.EN[g]} {why} — trend reversal possible" + (' (short-term)' if g in ('Su', 'Ma', 'Me', 'Ve') else '')))
    return out
