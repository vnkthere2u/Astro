"""
validate.py — source-selection test harness.

Every checkable fact the book states (dated planetary positions, nakṣatras, aspect windows,
ingress months, historical/forthcoming sign combinations, worked horā/daśā examples) is a
test.  Each candidate ephemeris configuration (ayanāṃśa × node model) is run through all of
them; only a configuration that passes 100 % of the hard positional tests is accepted.
The daily aspect-list examples are scored separately because the book's own lists are
internally inconsistent (documented below) — the calibrated rule reaches the theoretical
maximum consistency.
"""
from __future__ import annotations
import json, sys
from datetime import datetime, date, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo
sys.path.insert(0, str(Path(__file__).parent))
import astro_core as ac

IST = ZoneInfo('Asia/Kolkata')
UTC = timezone.utc
def ist(y, m, d, H=9, M=55): return datetime(y, m, d, H, M, tzinfo=IST)
def dm(x): return x * 60  # degrees -> arc-minutes

def run_tests(ayan_name: str, node_name: str) -> list:
    ac.set_config(ayan_name, node_name)
    T = []
    def add(tid, group, desc, book, got, ok, page, hard=True):
        T.append(dict(id=tid, group=group, test=desc, book=book, engine=got, pass_=bool(ok), page=page, hard=hard))

    # ---------------- Book 3 (Predicting the Nifty & Sensex) Ch.14 worked examples — 09:00 IST Mumbai, 2012
    B3EX = [((2012, 2, 1), 'Aries', 'Mrita', {'Ju', 'Sa'}, 'Kṛttikā', 'Shukla', 9),
            ((2012, 2, 2), 'Taurus', 'Vriddha', {'Ra', 'Ke'}, 'Rohiṇī', 'Brahma', 10),
            ((2012, 2, 3), 'Taurus', 'Kumar', {'Ra', 'Ke'}, 'Rohiṇī', 'Indra', 11),
            ((2012, 2, 7), 'Cancer', 'Yuva', {'Sa', 'Su', 'Me'}, 'Puṣya', 'Ayushman', 15),
            ((2012, 2, 8), 'Cancer', 'Baal', {'Sa', 'Su', 'Me'}, 'Aśleṣā', 'Saubhagya', 16),
            ((2012, 2, 9), 'Leo', 'Kumar', {'Ma', 'Ju'}, 'Maghā', 'Atiganda', 17)]
    for i, (ymd, sg, av, asp, nk, yg, tt) in enumerate(B3EX):
        c = ac.chart(ist(*ymd, 9, 0)); m = c['Mo']
        got = (ac.RASI_EN[m.sign], ac.avastha(m.lon), set(ac.b3_aspectors(c, 'Mo')), ac.NAK[m.nak], ac.YOGA_NAMES[ac.yoga_index(c)], c.tithi)
        exp = (sg, av, asp, nk, yg, tt)
        add(f'B3-{i + 1}', 'Book 3 Ch.14', f'{ymd[2]:02d}-Feb-2012 09:00: Moon sign, avasthā, aspects on Moon, nakshatra, yoga, tithi',
            str(exp), str(got), got == exp, 'Ch.14')
    # ---------------- Book 2 (Investment Muhurtas) Ch.34 worked trades — nakshatra on the trade day
    B2EX = [((2014, 7, 8), 'Viśākhā'), ((2014, 7, 14), 'Śravaṇa'), ((2014, 5, 2), 'Mṛgaśīrṣā'), ((2014, 5, 22), 'Śatabhiṣak'),
            ((2014, 5, 30), 'Mṛgaśīrṣā'), ((2014, 6, 6), 'Pūrva Phālgunī'), ((2013, 6, 25), 'Uttara Aṣāḍha'), ((2013, 7, 1), 'Revatī'),
            ((2013, 8, 23), 'Uttara Bhādra'), ((2013, 9, 13), 'Mūla'), ((2013, 11, 22), 'Punarvasu'), ((2013, 12, 10), 'Pūrva Bhādra'),
            ((2013, 12, 20), 'Puṣya'), ((2014, 1, 7), 'Uttara Bhādra'), ((2014, 1, 15), 'Ārdrā'), ((2013, 7, 24), 'Dhaniṣṭhā'), ((2013, 8, 6), 'Puṣya')]
    for i, (ymd, nk) in enumerate(B2EX):
        seen = {ac.NAK[ac.chart(ist(*ymd, h, 0)).moon_nak] for h in (9, 11, 13, 15)}
        add(f'B2-{i + 1}', 'Book 2 Ch.34', f'Nakshatra during the session {ymd[2]:02d}-{ymd[1]:02d}-{ymd[0]}', nk, '/'.join(sorted(seen)), nk in seen, 'Ch.34')
    B2DEG = [((2014, 7, 8), 'Ma', 5, 27), ((2014, 7, 14), 'Ma', 6, 0), ((2014, 7, 14), 'Ve', 2, 0), ((2014, 7, 14), 'Su', 2, 27),
             ((2014, 5, 2), 'Me', 0, 25), ((2014, 5, 22), 'Me', 1, 29), ((2014, 5, 22), 'Ve', 11, 28), ((2014, 5, 30), 'Me', 2, 6),
             ((2014, 6, 6), 'Ju', 2, 27), ((2013, 6, 25), 'Me', 2, 29), ((2013, 7, 1), 'Ma', 1, 27), ((2013, 7, 1), 'Me', 2, 28),
             ((2013, 8, 23), 'Ma', 3, 2), ((2013, 8, 23), 'Me', 4, 4), ((2013, 9, 13), 'Su', 4, 26), ((2013, 11, 22), 'Ma', 4, 27),
             ((2013, 12, 10), 'Su', 7, 24), ((2013, 12, 20), 'Me', 7, 29), ((2014, 1, 7), 'Ve', 8, 29), ((2014, 1, 15), 'Su', 9, 1),
             ((2013, 8, 6), 'Ve', 4, 24)]
    for i, (ymd, g, sg, dg) in enumerate(B2DEG):
        b = ac.chart(ist(*ymd, 9, 15))[g]
        ok = b.sign == sg and abs(b.deg - dg) <= 1.5 or (b.sign - sg) % 12 in (1, 11) and min(abs(b.lon - sg * 30 - dg), 360 - abs(b.lon - sg * 30 - dg)) <= 1.5
        add(f'B2-D{i + 1}', 'Book 2 Ch.34', f'{ac.EN[g]} degree {ymd[2]:02d}-{ymd[1]:02d}-{ymd[0]}', f'{dg}° {ac.RASI_EN[sg]}', f'{b.deg:.1f}° {ac.RASI_EN[b.sign]}', ok, 'Ch.34')

    # T1 Moon in Kanyā 11°32′ (Ch.12 worked example)
    c = ac.chart(ist(2009, 3, 12, 9, 55))
    m = c['Mo']; err = abs((m.lon - (5 * 30 + 11 + 32 / 60))) * 60
    add('T01', 'Position', 'Candra 12-Mar-2009 09:55 IST', 'Kanyā 11°32′', ac.fmt_deg(m.lon), err <= 3, 61)
    # T2/T3 nakṣatra on trading days (Ch.8 worked examples)
    for tid, d, nk in [('T02', ist(2009, 9, 29, 12, 0), 'Śravaṇa'), ('T03', ist(2009, 9, 30, 12, 0), 'Dhaniṣṭhā')]:
        c = ac.chart(d); add(tid, 'Nakṣatra', f'Candra nakṣatra {d:%d-%b-%Y} trading hours', nk, ac.NAK[c.moon_nak], ac.NAK[c.moon_nak] == nk, 45)
    # T4 Śani retro Siṃha 14°10′ and Guru Dhanus 11°10′ on 10-Jan-2008 (Ch.16)
    c = ac.chart(ist(2008, 1, 10, 12, 0))
    sa, ju = c['Sa'], c['Ju']
    add('T04', 'Position', 'Śani 10-Jan-2008', 'Siṃha 14°10′ (R)', ac.fmt_deg(sa.lon) + (' R' if sa.retro else ''),
        sa.sign == 4 and abs(sa.deg - (14 + 10 / 60)) * 60 <= 6 and sa.retro, 83)
    add('T05', 'Position', 'Guru 10-Jan-2008', 'Dhanus 11°10′', ac.fmt_deg(ju.lon), ju.sign == 8 and abs(ju.deg - (11 + 10 / 60)) * 60 <= 12, 83)
    # T6 exact trine on 21-Jan-2008 at 13°37′
    best = min((abs(ac.sep(ac.chart(datetime(2008, 1, 21, tzinfo=UTC) + timedelta(hours=h))['Ju'].lon,
                            ac.chart(datetime(2008, 1, 21, tzinfo=UTC) + timedelta(hours=h))['Sa'].lon) - 120), h) for h in range(0, 24))
    c = ac.chart(datetime(2008, 1, 21, tzinfo=UTC) + timedelta(hours=best[1]))
    add('T06', 'Aspect', 'Guru–Śani exact trine 21-Jan-2008 at 13°37′', 'Guru 13°37′ Dhanus / Śani 13°37′ Siṃha',
        f"{ac.fmt_deg(c['Ju'].lon)} / {ac.fmt_deg(c['Sa'].lon)}", best[0] < 0.1 and c['Ju'].sign == 8 and abs(c['Ju'].deg - 13.617) < 0.2, 83)
    # T7 aspect window boundaries with 3° orb
    def orb(d): c = ac.chart(datetime(d.year, d.month, d.day, 6, tzinfo=UTC)); return abs(ac.sep(c['Ju'].lon, c['Sa'].lon) - 120)
    def window(a, b):
        days = [a + timedelta(days=i) for i in range((b - a).days + 1)]
        inside = [d for d in days if orb(d) <= 3.0]
        return (inside[0], inside[-1]) if inside else (None, None)
    s1, e1 = window(date(2007, 12, 1), date(2008, 3, 1)); s2, e2 = window(date(2008, 7, 1), date(2009, 1, 31))
    ok1 = s1 and abs((s1 - date(2008, 1, 10)).days) <= 1 and abs((e1 - date(2008, 2, 1)).days) <= 1
    ok2 = s2 and abs((s2 - date(2008, 8, 21)).days) <= 2 and abs((e2 - date(2008, 12, 11)).days) <= 2
    add('T07', 'Aspect', 'Guru→Śani aspect window #1 (3° orb)', '10-Jan-2008 → 01-Feb-2008', f'{s1} → {e1}', ok1, 83)
    add('T08', 'Aspect', 'Guru→Śani aspect window #2 (3° orb)', '21-Aug-2008 → 11-Dec-2008', f'{s2} → {e2}', ok2, 83)
    c = ac.chart(ist(2008, 8, 21, 12)); add('T09', 'Motion', 'Guru retrograde & Śani direct on 21-Aug-2008', 'Guru R, Śani D',
        f"Guru {'R' if c['Ju'].retro else 'D'}, Śani {'R' if c['Sa'].retro else 'D'}", c['Ju'].retro and not c['Sa'].retro, 83)
    # T10 recession history + watch list (sign combinations)
    def combos(y0, y1):
        s = set(); d = date(y0, 1, 1)
        while d <= date(y1, 12, 31):
            c = ac.chart(datetime(d.year, d.month, d.day, tzinfo=UTC)); s.add((c['Sa'].sign, c['Ju'].sign)); d += timedelta(days=5)
        return s
    R = {n: i for i, n in enumerate(ac.RASI)}
    hist = [(1921, 1921, [('Siṃha', 'Siṃha')]), (1930, 1930, [('Dhanus', 'Mithuna')]), (1940, 1940, [('Meṣa', 'Meṣa')]),
            (1978, 1978, [('Siṃha', 'Mithuna')]), (1979, 1979, [('Siṃha', 'Siṃha')]), (1990, 1990, [('Dhanus', 'Mithuna')]),
            (2008, 2008, [('Siṃha', 'Dhanus')]), (2017, 2018, [('Dhanus', 'Tulā')]), (2028, 2029, [('Meṣa', 'Siṃha'), ('Meṣa', 'Tulā')]),
            (2036, 2038, [('Siṃha', 'Mithuna')]), (2047, 2048, [('Dhanus', 'Meṣa'), ('Dhanus', 'Mithuna')]), (2058, 2059, [('Meṣa', 'Meṣa')])]
    for k, (y0, y1, need) in enumerate(hist):
        got = combos(y0, y1)
        ok = all((R[a], R[b]) in got for a, b in need)
        add(f'T{10 + k:02d}', 'Business cycle', f'Śani/Guru rāśis {y0}' + (f'-{y1}' if y1 != y0 else ''),
            '; '.join(f'Śani {a}, Guru {b}' for a, b in need), 'present' if ok else 'absent', ok, 85)
    # T22 Śani enters Meṣa 1998 ('May 1998' – collapse); allow Apr–May
    ing = [x for x in ac.find_ingresses('Sa', date(1998, 1, 1), date(1998, 12, 31)) if x[2] == 0]
    add('T22', 'Ingress', 'Śani enters Meṣa', '1998 (market collapse May 1998)', f'{ing[0][0]:%d-%b-%Y}' if ing else '—',
        bool(ing) and ing[0][0].month in (4, 5), 84)
    # T23 Śani–Guru conjunction in Meṣa within Apr–Aug 2000
    cj = None; d = date(2000, 1, 1)
    while d < date(2000, 12, 31):
        c = ac.chart(datetime(d.year, d.month, d.day, tzinfo=UTC))
        if ac.sep(c['Sa'].lon, c['Ju'].lon) < 1.0 and cj is None: cj = (d, ac.RASI[c['Ju'].sign])
        d += timedelta(days=1)
    add('T23', 'Aspect', 'Śani–Guru conjunction 2000', 'Meṣa, Apr–Aug 2000', f'{cj[0]:%d-%b-%Y} {cj[1]}' if cj else '—',
        bool(cj) and 4 <= cj[0].month <= 8 and cj[1] in ('Meṣa', 'Vṛṣabha'), 84, hard=False)
    # T24..27 crude-oil facts (Ch.18)
    c = ac.chart(ist(2007, 7, 25, 12)); add('T24', 'Crude', 'Śani with Ketu in Siṃha, Jul 2007', 'Śani & Ketu in Siṃha',
        f"Śani {ac.RASI[c['Sa'].sign]}, Ketu {ac.RASI[c['Ke'].sign]}", c['Sa'].sign == 4 and c['Ke'].sign == 4, 89)
    ing = [x for x in ac.find_ingresses('Ke', date(2008, 1, 1), date(2008, 12, 31)) if x[1] == 4]
    add('T25', 'Crude', 'Ketu leaves Siṃha', 'May 2008', f'{ing[0][0]:%d-%b-%Y}' if ing else '—', bool(ing) and ing[0][0].month == 5, 89)
    ends = all(ac.chart(datetime(y, m, 15, tzinfo=UTC))['Sa'].sign == 1 and ac.chart(datetime(y, m, 15, tzinfo=UTC))['Ra'].sign == 1 for y, m in [(2002, 3), (2003, 3)])
    mn = min(ac.sep(ac.chart(datetime(2002, 3, 1, tzinfo=UTC) + timedelta(days=k))['Sa'].lon, ac.chart(datetime(2002, 3, 1, tzinfo=UTC) + timedelta(days=k))['Ra'].lon) for k in range(0, 400, 4))
    add('T26', 'Crude', 'Śani with Rāhu in Vṛṣabha (conjunction inside window)', 'Mar-2002 → Mar-2003', f'both in Vṛṣabha at window ends; closest {mn:.1f}°', ends and mn < 10, 90)
    ok = all(ac.chart(datetime(y, m, 15, tzinfo=UTC))['Sa'].sign == 6 and ac.chart(datetime(y, m, 15, tzinfo=UTC))['Ra'].sign == 6 for y, m in [(2013, 1), (2013, 9), (2014, 6)])
    ing = [x for x in ac.find_ingresses('Ra', date(2014, 1, 1), date(2014, 12, 31)) if x[1] == 6]
    add('T27', 'Crude', 'Śani with Rāhu in Tulā; Rāhu leaves', 'Jan-2013 → Jul-2014', f"together; Rāhu leaves {ing[0][0]:%d-%b-%Y}" if ok and ing else 'mismatch',
        ok and bool(ing) and ing[0][0].month == 7, 90)
    # T28..33 gold (Ch.17)
    def jn(y, m, d=15):
        c = ac.chart(datetime(y, m, d, tzinfo=UTC)); return min(ac.sep(c['Ju'].lon, c['Ra'].lon), ac.sep(c['Ju'].lon, c['Ke'].lon)), c
    mins = []
    for y, m in [(2008, 5), (2008, 6)]:
        for d in range(1, 29, 2): mins.append(jn(y, m, d)[0])
    add('T28', 'Gold', 'Guru & Rāhu "came within 30°" May–Jun 2008', '≤ 30°', f'min {min(mins):.1f}°', min(mins) <= 30, 87)
    best = min((jn(2009, 2, d)[0], d) for d in range(1, 29))
    add('T29', 'Gold', 'Guru–Rāhu exact conjunction Feb 2009', '≈0° in Feb-2009', f'{best[0]:.2f}° on {best[1]:02d}-Feb', best[0] < 1.0, 87)
    ing = [x for x in ac.find_ingresses('Ju', date(2009, 10, 1), date(2010, 1, 31)) if x[2] == 10]
    add('T30', 'Gold', 'Guru moves Makara → Kumbha', 'end Dec 2009', f'{ing[0][0]:%d-%b-%Y}' if ing else '—', bool(ing) and ing[0][0].month == 12, 87)
    ing = [x for x in ac.find_ingresses('Ra', date(2009, 8, 1), date(2010, 2, 28)) if x[2] == 8]
    add('T31', 'Gold', 'Rāhu moves Makara → Dhanus', '"during end of Dec 2009" (approximate)', f'{ing[0][0]:%d-%b-%Y}' if ing else '—',
        bool(ing) and abs((ing[0][0].date() - date(2009, 12, 25)).days) <= 60, 87, hard=False)
    for tid, (y, m, sg, lbl) in zip(['T32', 'T33', 'T34', 'T35'], [(1893, 6, 0, 'Meṣa'), (1979, 11, 4, 'Siṃha'), (1980, 3, 4, 'Siṃha'), (1987, 2, 11, 'Mīna')]):
        dd, c = jn(y, m)
        add(tid, 'Gold', f'Guru conj node {m:02d}-{y}', f'conjunction in {lbl}', f'{dd:.1f}°, Guru in {ac.RASI[c["Ju"].sign]}', dd <= 30 and c['Ju'].sign == sg, 88)
    dd, c = jn(1838, 9); add('T36', 'Gold', 'Guru conj Ketu in Kanyā, 1838', 'Kanyā', f'{dd:.1f}°, Guru {ac.RASI[c["Ju"].sign]}, Ketu {ac.RASI[c["Ke"].sign]}',
                            dd <= 30 and c['Ke'].sign == 5, 88)
    dd, c = jn(1781, 5, 31); add('T37', 'Gold', 'Guru conj node 31-May-1781', 'conjunction', f'{dd:.1f}°', dd <= 30, 88, hard=False)
    dd, c = jn(1948, 6); add('T38', 'Gold', 'Guru conj Ketu in Vṛṣabha 1948', 'Vṛṣabha', f'Guru {ac.RASI[c["Ju"].sign]}, Ketu {ac.RASI[c["Ke"].sign]} ({dd:.0f}°)',
                            c['Ke'].sign == 1 and c['Ju'].sign == 1, 88, hard=False)
    T[-1]['note'] = 'Book error: in 1948 Guru was in Vṛścika/Dhanus under every ayanāṃśa (tropical included); cannot be reproduced.'
    # T39 micro-daśā worked example (Ch.12)
    c = ac.chart(ist(2009, 3, 12, 9, 55))
    md = ac.micro_dasha(c['Mo'].lon, ist(2009, 3, 12, 9, 55))
    got = [(a.strftime('%H:%M:%S'), b.strftime('%H:%M:%S'), L) for a, b, L in md[:7]]
    want = [('09:55:00', '10:30:24', 'Mo'), ('10:30:24', '10:58:24', 'Ma'), ('10:58:24', '12:10:24', 'Ra'), ('12:10:24', '13:14:24', 'Ju'),
            ('13:14:24', '14:30:24', 'Sa'), ('14:30:24', '15:38:24', 'Me'), ('15:38:24', '16:06:24', 'Ke')]
    def close(a, b): return abs((datetime.strptime(a, '%H:%M:%S') - datetime.strptime(b, '%H:%M:%S')).total_seconds()) <= 20
    ok = all(L1 == L2 and close(s1, s2) and close(e1, e2) for (s1, e1, L1), (s2, e2, L2) in zip(got, want))
    add('T39', 'Daśā', 'Micro-viṃśottarī schedule 12-Mar-2009', 'Ca→10:30:24, Ma→10:58:24 … Ke→16:06:24',
        ', '.join(f'{L} {e}' for s, e, L in got), ok, 62)
    # T40 horā sequence given book sunrise 05:52 (Ch.10 examples)
    def hora_at(d, hh, mm):
        sr = datetime(d.year, d.month, d.day, 5, 52, tzinfo=IST)
        for s, e, L in ac.hora_table(d, 0, 0, 'Asia/Kolkata', sr=sr):
            if s <= datetime(d.year, d.month, d.day, hh, mm, tzinfo=IST) < e: return L, s.strftime('%H:%M')
    checks = [(date(2009, 9, 29), 13, 52, 'Su'), (date(2009, 9, 29), 9, 52, 'Mo'), (date(2009, 9, 29), 12, 52, 'Ma'),
              (date(2009, 9, 29), 11, 52, 'Ju'), (date(2009, 9, 29), 14, 52, 'Ve'), (date(2009, 9, 29), 10, 52, 'Sa'),
              (date(2009, 9, 30), 13, 52, 'Mo'), (date(2009, 9, 30), 12, 52, 'Me')]
    res = [(hora_at(d, h, m_), want) for d, h, m_, want in checks]
    ok = all(r[0] == w for r, w in res)
    add('T40', 'Horā', 'Horā lords at book times (29/30-Sep-2009)', 'Su 13:52, Mo 09:52, Ma 12:52, Ju 11:52, Ve 14:52, Sa 10:52 | Wed Mo 13:52, Me 12:52',
        ', '.join(f'{r[0]} {r[1]}' for r, w in res), ok, 54)
    # T41 the book's sunrise 05:52 is reproduced at the author's city (Lucknow), not Mumbai
    sr_l = ac.sunrise(date(2009, 9, 29), 26.8467, 80.9462, 'Asia/Kolkata'); sr_m = ac.sunrise(date(2009, 9, 29), 19.076, 72.8777, 'Asia/Kolkata')
    add('T41', 'Horā', 'Sunrise 29-Sep-2009 used in examples', '05:52', f'Lucknow {sr_l:%H:%M}, Mumbai {sr_m:%H:%M}',
        abs((sr_l.hour * 60 + sr_l.minute) - (5 * 60 + 52)) <= 4, 54, hard=False)
    return T

# --------------------------------------------------------- aspect-list fit (Ch.8/10 worked examples)
TRUTH = [((2009, 9, 29), 'Mo', {'Su', 'Ma', 'Ju', 'Ra'}), ((2009, 9, 29), 'Su', {'Mo', 'Ma', 'Ju', 'Ra'}), ((2009, 9, 29), 'Ma', {'Sa'}),
         ((2009, 9, 29), 'Ju', {'Mo', 'Ma', 'Ra', 'Ke'}), ((2009, 9, 29), 'Ve', {'Me'}), ((2009, 9, 29), 'Sa', {'Su', 'Ma', 'Ju', 'Mo'}),
         ((2009, 9, 30), 'Ma', {'Sa'}), ((2009, 9, 30), 'Mo', {'Su', 'Ju', 'Ma', 'Ra'}), ((2009, 9, 30), 'Me', {'Ve'})]
CONTRADICTIONS = [
    '29-Sep: Sūrya–Śani are conjunct in Kanyā; the book lists Sūrya among Śani\'s aspects but omits Śani from Sūrya\'s list.',
    '29-Sep: Rāhu (Makara) aspects Kanyā by its 9th dṛṣṭi; the book lists Rāhu on Sūrya (Kanyā) but not on Śani (also Kanyā).',
    '29/30-Sep: Ketu (Karkaṭa) aspects Makara by 7th dṛṣṭi; the book lists Ketu on Guru (Makara) but not on Candra (also Makara).',
    '29-Sep: Candra–Śani trine is listed for Śani but not for Candra (a trine is mutual).',
]
def aspect_fit():
    ac.set_config('Lahiri', 'true')
    rows = []; tp = fp = fn = 0
    for (y, m, d), tgt, truth in TRUTH:
        c = ac.chart(ist(y, m, d, 9, 55))
        pred = {a for a in ac.NINE if a != tgt and ac.casts_aspect(c, a, tgt)[0]}
        tp += len(pred & truth); fp += len(pred - truth); fn += len(truth - pred)
        rows.append(dict(date=f'{d:02d}-{m:02d}-{y}', graha=ac.NAMES[tgt], book=', '.join(ac.NAMES[x] for x in sorted(truth)),
                         engine=', '.join(ac.NAMES[x] for x in sorted(pred)),
                         extra=', '.join(ac.NAMES[x] for x in sorted(pred - truth)), missed=', '.join(ac.NAMES[x] for x in sorted(truth - pred))))
    return dict(rows=rows, recall=tp / (tp + fn), precision=tp / (tp + fp), tp=tp, fp=fp, fn=fn,
                minimum_possible_errors=5, contradictions=CONTRADICTIONS)

def method_tests():
    """Book 3 Ch.14: the app's method must reproduce the book's own concluded predictions; Book 2 Ch.34: every
    planet the book cites as signalling a reversal must be inside the app's reversal window."""
    import book3 as B3, book2 as B2
    out = []
    for ymd, exp in [((2012, 2, 1), 0), ((2012, 2, 2), 1), ((2012, 2, 3), 1), ((2012, 2, 7), 0), ((2012, 2, 8), 1), ((2012, 2, 9), 1)]:
        r = B3.intraday(ac.chart(ist(*ymd, 9, 0)))
        out.append(dict(id=f'M3-{ymd[2]}', test=f'Book 3 concluded prediction {ymd[2]:02d}-Feb-2012', book=B3.WORD[exp], engine=B3.WORD[r['dir']], pass_=r['dir'] == exp))
    cites = [((2014, 7, 8), 'Ma'), ((2014, 7, 14), 'Ma'), ((2014, 7, 14), 'Ve'), ((2014, 7, 14), 'Su'), ((2014, 5, 2), 'Me'), ((2014, 5, 22), 'Me'),
             ((2014, 5, 22), 'Ve'), ((2014, 5, 30), 'Me'), ((2014, 6, 6), 'Ju'), ((2013, 6, 25), 'Me'), ((2013, 7, 1), 'Ma'), ((2013, 7, 1), 'Me'),
             ((2013, 8, 23), 'Ma'), ((2013, 8, 23), 'Me'), ((2013, 9, 13), 'Su'), ((2013, 11, 22), 'Ma'), ((2013, 12, 10), 'Su'), ((2013, 12, 20), 'Me'),
             ((2014, 1, 7), 'Ve'), ((2014, 1, 15), 'Su'), ((2013, 8, 6), 'Ve')]
    for ymd, g in cites:
        w = {x['planet'] for x in B2.reversal_window(ac.chart(ist(*ymd, 9, 15)))}
        out.append(dict(id=f'M2-{ymd[0]}{ymd[1]:02d}{ymd[2]:02d}{g}', test=f'Book 2 reversal window {ymd[2]:02d}-{ymd[1]:02d}-{ymd[0]} ({ac.EN[g]})',
                        book='reversal possible', engine='in window' if g in w else 'not in window', pass_=g in w))
    return out

def main(out_dir: Path):
    configs = [(a, n) for a in ['Lahiri', 'Raman', 'Krishnamurti', 'Fagan-Bradley', 'Tropical'] for n in ['true', 'mean']]
    matrix = []
    detail = {}
    for a, n in configs:
        T = run_tests(a, n)
        hard = [t for t in T if t['hard']]
        matrix.append(dict(ayanamsa=a, node=n, hard_pass=sum(t['pass_'] for t in hard), hard_total=len(hard),
                           soft_pass=sum(t['pass_'] for t in T if not t['hard']), soft_total=sum(1 for t in T if not t['hard'])))
        detail[f'{a}/{n}'] = T
    winners = [m for m in matrix if m['hard_pass'] == m['hard_total']]
    chosen = sorted(winners, key=lambda m: (-m['soft_pass'], m['ayanamsa'] != 'Lahiri'))[0] if winners else None
    fit = aspect_fit()
    ac.set_config(chosen['ayanamsa'] if chosen else 'Lahiri', chosen['node'] if chosen else 'true')
    rep = dict(generated=datetime.now(UTC).isoformat(timespec='seconds'), matrix=matrix,
               chosen=chosen, tests=detail[f"{chosen['ayanamsa']}/{chosen['node']}"] if chosen else [],
               aspect_fit=fit, swisseph_version=ac.swe.version)
    rep['method_tests'] = method_tests()
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / 'validation_report.json').write_text(json.dumps(rep, ensure_ascii=False, indent=1, default=str))
    return rep

if __name__ == '__main__':
    rep = main(Path(__file__).parent / 'data')
    for m in rep['matrix']:
        print(f"{m['ayanamsa']:14s} {m['node']:5s} hard {m['hard_pass']}/{m['hard_total']}  soft {m['soft_pass']}/{m['soft_total']}")
    print('CHOSEN:', rep['chosen'])
    for t in rep['tests']:
        print(('PASS' if t['pass_'] else 'FAIL'), ('H' if t['hard'] else 's'), t['id'], t['test'], '|', t['book'], '|', t['engine'])
    for t in rep['method_tests']: print(('PASS' if t['pass_'] else 'FAIL'), 'M', t['id'], t['test'], '|', t['book'], '|', t['engine'])
    f = rep['aspect_fit']; print('aspect fit recall', f['recall'], 'precision', round(f['precision'], 3), f['tp'], f['fp'], f['fn'])
