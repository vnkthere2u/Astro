"""Parse Book 3 ('Predicting the Nifty & Sensex') OCR text into structured rules.
Output: data/book3_rules.json  — every statement keeps its verbatim (cleaned) text."""
import re, json, sys, difflib
from pathlib import Path
SRC = Path(sys.argv[1] if len(sys.argv) > 1 else '/root/book2/nifty.c.txt')
OUT = Path(__file__).resolve().parent.parent / 'data' / 'book3_rules.json'
SIGNS = ['Aries','Taurus','Gemini','Cancer','Leo','Virgo','Libra','Scorpio','Sagittarius','Capricorn','Aquarius','Pisces']
PLAN = ['Sun','Moon','Mars','Mercury','Jupiter','Venus','Saturn','Rahu','Ketu']
NAK = ['Aswini','Bharani','Krittika','Rohini','Mrigasira','Ardra','Punarvasu','Pushyami','Aslesha','Magha',
       'Purvaphalguni','Uttaraphalguni','Hasta','Chitra','Swati','Visakha','Anuradha','Jyeshta','Moola',
       'Purvashada','Uttarashada','Sravana','Dhanishta','Satabhisha','Purvabhadra','Uttarabhadra','Revati']
YOGA = ['Vishkumbha','Priti','Ayushman','Saubhagya','Shobhana','Atiganda','Sukarma','Dhriti','Shoola','Ganda',
        'Vriddhi','Dhruva','Vyaghata','Harshana','Vajra','Siddhi','Vyatipata','Variyan','Parigha','Shiva',
        'Siddha','Sadhya','Shubha','Shukla','Brahma','Indra','Vaidhriti']
def fz(w, opts, cut=0.6):
    w = re.sub(r'[^A-Za-z]', '', w)
    m = difflib.get_close_matches(w.capitalize(), opts, 1, cut)
    return m[0] if m else None

def is_table(l):
    s = l.strip()
    if not s: return True
    if re.search(r'\d{1,2}\s*/\s*\d{1,2}\s*/\s*\d{4}', s): return True
    if re.match(r'^(Date|Dat|Open|High|Low|Close|Gain|Trend|e|Positiv|Negativ|Positive|Negative|loss|Loss|ss|Lo)\b', s) and len(s) < 60 \
       and not re.search(r'transiting|Yoga day|Tithi|aspected', s): return True
    nd = sum(ch.isdigit() for ch in s); na = sum(ch.isalpha() for ch in s)
    return nd > na
def is_header(l):
    s = l.strip()
    return bool(re.match(r'^.{0,4}(Chapter|C\w{0,3}pter|jnafjter|\(j\\?spter)\s*\d', s) or re.search(r'Predicting.{0,6}(Nifty|Niffy|Aff/ty|N\w+)\s*&\s*Sens', s) and len(s) < 110) \
        or bool(re.match(r"^[\W\d]*Aspe\w{0,3}\s+wh\w+\s+Sun\s+[Ii]n\s+\w+[\W\d]*$", s))

lines = SRC.read_text(errors='ignore').splitlines()
keep = [l.strip() for l in lines if not is_table(l) and not is_header(l)]
text = ' '.join(keep)
text = re.sub(r'\s+', ' ', text)

TAIL = r"[\s.,]*[^:;]{0,24}?(?P<SS>[A-Za-z?][\w ]{2,12}?)\s*[:;]"
def T(n): return TAIL.replace('SS', n)
SUBJ = re.compile(
  r'(?P<num>\d{1,2}|[A-Z&*\-])?\s*[.,\-*/;]?\s*'
  r'(?:(?P<sasp>(?:S\w{1,2}|\w{0,2})\s?[IiT]n (?P<s1>\w+) aspected by (?P<p1>[\w ,]+?)\s*[:;])'
  r'|(?:Moon transiting\W{0,2}\s?through\W?\s?(?P<m>[A-Za-z][A-Za-z ]{1,16}?)J?(?P<isnak>\s*Nak\w*)?\s*' + r'(?=\W*wh|\W*Wh)' + T('s2') + r')'
  r'|(?:(?P<y>\w+) Yoga day' + T('s3') + r')'
  r'|(?:(?P<pk>Sh\w{2,3}a|Krishna)\s*\d?Paksha\s*\.?(?P<tn>\d{1,2})(?!\d)[^:;]{0,40}?T\W?[il1]\W?[t]?\W?[h^]\W?[iIl1]' + T('s4') + r'))')
VERD_UP = re.compile(r'up\s?move', re.I)
VERD_DN = re.compile(r'down\s?side|(?:fall|fail|fell|rail|\(all)\s*o[rf]\b', re.I)
NEU = re.compile(r'neutral|do not produce any', re.I)
KN = re.compile(r'in (\d+) observations? out of (?:total )?(\d+)')
BUT = re.compile(r'(?:But|While) [Ii]f (?:this |the )?Moon [Ii]s (?P<rel>in conjunction with|aspected by|conjunct(?:ed)? with|associated with) (?:the )?(?P<pl>[\w ,]+?) then (?P<rest>.*?)(?=(?:But|While) [Ii]f|$)')

def verdict(s):
    a = VERD_UP.search(s); b = VERD_DN.search(s); n = NEU.search(s)
    cands = [(m.start(), v) for m, v in ((a, 'Up'), (b, 'Down'), (n, 'Neutral')) if m]
    return min(cands)[1] if cands else None
def planets(s):
    out = []
    for w in re.split(r'[ ,]+|\band\b|\bor\b', s):
        p = fz(w, PLAN, 0.6) if w and w.lower() not in ('and', 'or', 'the') else None
        if p and p not in out: out.append(p)
    return out, (' or ' in s and ' and ' not in s and 'any' in s or 'or' in s.split())

ms = list(SUBJ.finditer(text)); rules = []
for i, m in enumerate(ms):
    body = text[m.end(): ms[i+1].start() if i + 1 < len(ms) else len(text)]
    body = body[:3000]
    head, *_ = re.split(r'(?:But|While) [Ii]f', body, maxsplit=1) + ['']
    r = dict(num=m['num'], text=(m.group(0) + body).strip()[:240])
    if m['sasp']:
        r.update(kind='sun_aspect', sun=fz(m['s1'], SIGNS), planet=planets(m['p1'])[0])
    elif m['m']:
        if m['isnak'] or fz(m['m'].replace(' ',''), NAK, 0.75):
            r.update(kind='nakshatra', sun=fz(m['s2'].split()[-1], SIGNS), key=fz(m['m'].replace(' ',''), NAK, 0.5))
        else:
            r.update(kind='moon_sign', sun=fz(m['s2'].split()[-1], SIGNS), key=fz(m['m'].replace(' ',''), SIGNS))
    elif m['y']:
        r.update(kind='yoga', sun=fz(m['s3'].split()[-1], SIGNS), key=fz(m['y'], YOGA, 0.5))
    else:
        r.update(kind='tithi', sun=fz(m['s4'].split()[-1], SIGNS), key=(15 if m['pk'] == 'Krishna' else 0) + int(m['tn']))
    r['verdict'] = verdict(head)
    k = KN.search(head); r['stat'] = [int(k[1]), int(k[2])] if k else None
    conds = []
    for b in BUT.finditer(body):
        pl, _ = planets(b['pl']); rest = b['rest']
        kk = KN.search(rest)
        conds.append(dict(rel='conj' if 'conj' in b['rel'] or 'assoc' in b['rel'] else 'aspect', planets=pl,
                          any_of=True, verdict=verdict(rest), stat=[int(kk[1]), int(kk[2])] if kk else None,
                          text=b.group(0)[:200]))
    r['conds'] = conds
    if not r.get('sun') and rules: r['sun'] = rules[-1]['sun']
    rules.append(r)

# de-dup: keep first per (kind,sun,key/planet)
seen = {}; final = []
for r in rules:
    k = (r['kind'], r['sun'], str(r.get('key')) + str(r.get('planet')))
    if k in seen: continue
    seen[k] = 1; final.append(r)
CH14 = [('nakshatra','Capricorn','Krittika','Down',1), ('nakshatra','Capricorn','Pushyami','Up',5),
        ('nakshatra','Capricorn','Aslesha','Neutral',6), ('nakshatra','Capricorn','Magha','Up',7),
        ('tithi','Capricorn',16,'Up',6), ('tithi','Capricorn',17,'Down',7), ('moon_sign','Capricorn','Cancer','Up',5)]
have = {(r['kind'], r['sun'], r.get('key')) for r in final}
for kind, sun, key, v, pr in CH14:
    if (kind, sun, key) not in have:
        final.append(dict(num=None, kind=kind, sun=sun, key=key, verdict=v, stat=None, conds=[],
                          text=f"Quoted in Ch.14 Practical {pr} (page of Ch.11 missing from the supplied copy)", source='ch14'))
OUT.write_text(json.dumps(final, indent=1, ensure_ascii=False))
from collections import Counter
c = Counter((r['kind'], r['sun']) for r in final)
exp = dict(sun_aspect=7, moon_sign=12, nakshatra=27, yoga=27, tithi=30)
for s in SIGNS:
    print(s.ljust(12), ' '.join(f"{k}:{c[(k, s)]}/{exp[k]}" for k in exp))
print('total', len(final), 'no-verdict', sum(r['verdict'] is None for r in final))
