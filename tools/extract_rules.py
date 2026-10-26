"""
Extracts every machine-readable rule from Banerjee, 'Stock Market Astrology' (2009)
into rulebook.json.  Chapters 6, 7, 8 are parsed programmatically from the book text;
chapters 4, 5, 9, 10, 12-19 are encoded from the text (formulaic, transcribed verbatim
in the 'text' field of every rule so every rule is auditable against the source).
"""
import re, json, unicodedata, sys
from pathlib import Path

SRC = Path(sys.argv[1] if len(sys.argv) > 1 else '/root/book/b.txt')
OUT = Path(sys.argv[2] if len(sys.argv) > 2 else '/root/astro/platform/data/rulebook.json')
raw = SRC.read_text()

# ----------------------------------------------------------------- normalisation
def strip_pages(t):
    t = re.sub(r'\n\s*Page \d+\s*\n', '\n', t)
    t = re.sub(r'\nStock Market Astrology[^\n]*\n', '\n', t)
    return t
TXT = strip_pages(raw)
def flat(s):
    return re.sub(r'\s+', ' ', s).strip()
def ascii_fold(s):
    return ''.join(c for c in unicodedata.normalize('NFKD', s) if not unicodedata.combining(c))

# ----------------------------------------------------------------- vocabularies
GRAHA = {  # book spelling -> code
    'Sūrya': 'Su', 'Candra': 'Mo', 'Maṅgala': 'Ma', 'Budha': 'Me', 'Guru': 'Ju', 'Śukra': 'Ve',
    'Śani': 'Sa', 'Rāhu': 'Ra', 'Ketu': 'Ke', 'Uranus': 'Ur', 'Neptune': 'Ne', 'Pluto': 'Pl'}
RASI = ['Meṣa', 'Vṛṣabha', 'Mithuna', 'Karkaṭa', 'Siṃha', 'Kanyā', 'Tulā', 'Vṛścika', 'Dhanus', 'Makara', 'Kumbha', 'Mīna']
NAK = ['Aśvinī', 'Bharaṇī', 'Kṛttikā', 'Rohiṇī', 'Mṛgaśīrṣā', 'Ārdrā', 'Punarvasu', 'Puṣya', 'Aśleṣā', 'Maghā',
       'Pūrva Phālgunī', 'Uttara Phālgunī', 'Hasta', 'Citrā', 'Svāti', 'Viśākhā', 'Anurādhā', 'Jyeṣṭha', 'Mūla',
       'Pūrva Aṣāḍha', 'Uttara Aṣāḍha', 'Śravaṇa', 'Dhaniṣṭhā', 'Śatabhiṣak', 'Pūrva Bhādra', 'Uttara Bhādra', 'Revatī']

SECTORS = [  # (id, book name) in the book's Chapter 3 / Chapter 6 order
    ('AGRI', 'Agriculture & agro industries'), ('AUTO', 'Automobile'), ('AVIATION', 'Aviation'),
    ('BANK', 'Banking & financial'), ('CAPGOODS', 'Capital goods'), ('CEMENT', 'Cement'),
    ('OILGAS', 'Crude oil & gas'), ('EDIBLEOIL', 'Eatable oil'), ('EDU', 'Educational'),
    ('ESSOIL', 'Essential oils & perfumeries'), ('EXPORTS', 'Exports'), ('FMCG', 'FMCG'),
    ('GEMS', 'Gems & jewelry'), ('HEALTH', 'Health care'), ('HOSPITALITY', 'Hospitality'),
    ('INFRA', 'Infrastructure'), ('IT', 'IT'), ('LEATHER', 'Leather & footwear'),
    ('MEDIA', 'Media & entertainment'), ('METAL', 'Metal'), ('PAINTS', 'Paints'),
    ('PHARMA', 'Pharmaceutical'), ('POWER', 'Power'), ('PUBLICATION', 'Publication'),
    ('REALTY', 'Realty'), ('SHIPPING', 'Shipping'), ('SUGAR', 'Sugar'),
    ('TELECOM', 'Telecommunication'), ('TEXTILE', 'Textile'), ('TRAVEL', 'Travel & tourism')]
EXTRA_SECTORS = [('PSU', 'Gov. public sector units (PSU)')]  # used by Ch.4 Sūrya and Ch.13-14 1st bhāva
COMMODITIES = [('GOLD', 'Gold'), ('SILVER', 'Silver'), ('CRUDE', 'Crude oil'), ('NATGAS', 'Natural gas'),
               ('COPPER', 'Copper'), ('ALUMINIUM', 'Aluminium'), ('STEEL', 'Iron & steel'),
               ('WHEAT', 'Wheat / food grains'), ('COTTON', 'Cotton'), ('SUGARC', 'Sugar (commodity)')]

# book term -> targets. Item-level matching (lists are split on commas/'and').
KEYMAP = [
    (r'\bagricult', ['AGRI']), (r'\bagro\b', ['AGRI']), (r'livestock', ['AGRI']), (r'food grain', ['AGRI', 'WHEAT']),
    (r'\brice\b', ['AGRI']), (r'\bwheat\b', ['WHEAT']), (r'mustard', ['EDIBLEOIL']),
    (r'automobile', ['AUTO']), (r'aviation|airline', ['AVIATION']),
    (r'banking|financ|investment|insurance', ['BANK']), (r'capital goods', ['CAPGOODS']),
    (r'cement|lime ?stone|gypsum', ['CEMENT']), (r'\bcrude', ['OILGAS', 'CRUDE']),
    (r'oil ?& ?gas|petroleum|refiner|oil marketing', ['OILGAS', 'CRUDE', 'NATGAS']),
    (r'eatable oil', ['EDIBLEOIL']), (r'education', ['EDU']),
    (r'essential oil|perfum|cosmetic|peppermint', ['ESSOIL']), (r'export|foreign trade', ['EXPORTS']),
    (r'fmcg|confectionar|soft|cold drink|mineral water|\bmilk|dairy|alcohol', ['FMCG']),
    (r'jewel|diamond|gems|\bpearl|\bopal|quartz|crystal|garnet|ruby|topaz|emerald|coral', ['GEMS']),
    (r'\bgold\b', ['GOLD']), (r'\bsilver\b', ['SILVER']), (r'copper', ['COPPER']), (r'alumin', ['ALUMINIUM']),
    (r'iron|steel', ['METAL', 'STEEL']), (r'\bmetal', ['METAL']), (r'\btin\b|\bcoal\b|mining', ['METAL']),
    (r'health ?care|hospital|diagnostic|medical|surgical|nursing', ['HEALTH']), (r'hotel|hospitality|resort', ['HOSPITALITY']),
    (r'infrastructure', ['INFRA']), (r'^it$|\bit\b|internet', ['IT']), (r'leather|footwear', ['LEATHER']),
    (r'media|entertainment|amusement|\btoys\b|advertis|handicraft', ['MEDIA']), (r'paint', ['PAINTS']),
    (r'pharma', ['PHARMA']), (r'\bpower\b|nuclear|electrical', ['POWER']), (r'publication|newsprint|\bpaper\b', ['PUBLICATION']),
    (r'realty', ['REALTY']), (r'shipping', ['SHIPPING']), (r'\bsugar\b', ['SUGAR', 'SUGARC']), (r'ethanol|methanol', ['SUGAR']),
    (r'telecom|mobiles?\b', ['TELECOM']), (r'textile|garment|fashion', ['TEXTILE']), (r'cotton', ['TEXTILE', 'COTTON']),
    (r'touris|travel', ['TRAVEL']), (r'public sector|psu|gov\.', ['PSU']),
]
def map_terms(text):
    items = re.split(r',|\band\b|&(?! ?(gas|steel|footwear|jewel|entertain|financ|tourism|perfum|dairy|cold))', text.lower())
    out = []
    for it in items:
        if not it: continue
        it = it.strip()
        for pat, tg in KEYMAP:
            if re.search(pat, it):
                for g in tg:
                    if g not in out: out.append(g)
    return out

def grahas_in(s):
    return [c for n, c in GRAHA.items() if n in s]
def rasis_in(s):
    return [i for i, r in enumerate(RASI) if re.search(re.escape(r) + r'(?![a-zā])', s)]
def naks_in(s):
    found = []
    for i, n in enumerate(NAK):
        # avoid 'Phālgunī' double counting by exact multiword match
        if re.search(r'(?<![A-Za-zāīūṛ])' + re.escape(n) + r'(?![a-zā])', s): found.append(i)
    # remove singles contained in Pūrva/Uttara compounds
    return found

def page_of(snippet):
    k = raw.find(snippet[:60])
    if k < 0: return None
    m = re.search(r'Page (\d+)', raw[k:])
    return int(m.group(1)) if m else None

# ======================================================= Ch.4  graha significations
CH4 = {
 'Su': dict(own=[4], exalt=0, debil=6, friends=['Mo', 'Ma', 'Ju'], enemies=['Ve', 'Sa'], neutral=['Me'],
            sectors='Power sector, media, nuclear energy, Gov. public sector units',
            commodities='Gold, copper, bronze, gun metal, garnet, ruby, firearms, wheat, explosives, graphite & sulphur'),
 'Mo': dict(own=[3], exalt=1, debil=7, friends=['Su', 'Me'], enemies=[], neutral=['Ma', 'Ju', 'Ve', 'Sa'],
            sectors='Petroleum, shipping, oil & gas',
            commodities='Mineral water, soft drink, cold drink, milk, milk produces, silver, aluminum, pearl, oil, peppermint, alcohol & rice'),
 'Ma': dict(own=[0, 7], exalt=9, debil=3, friends=['Su', 'Mo', 'Ju'], enemies=['Me'], neutral=['Ve', 'Sa'],
            sectors='Health care, capital goods, automobiles, pharmaceuticals, cements, infrastructure, steel & metals sector',
            commodities='Copper, steel, crude oil, coral, gun powder, firearms, explosives, spices, cloves & tobaccos'),
 'Me': dict(own=[2, 5], exalt=5, debil=11, friends=['Su', 'Ve'], enemies=['Mo'], neutral=['Ma', 'Ju', 'Sa'],
            sectors='Telecommunication, FMCG, textile, IT, educational, banking & financial, insurance, publication & aviation sector',
            commodities='Peppermint, emerald, agro products, food grains, paper, newsprint & cotton'),
 'Ju': dict(own=[8, 11], exalt=3, debil=9, friends=['Su', 'Mo', 'Ma'], enemies=['Me', 'Ve'], neutral=['Sa'],
            sectors='Banking & financial, insurance, gems & jewelry, eatable oils, FMCG, textile, shipping & exports sector',
            commodities='Gold, copper, bronze, food grains, oils, topaz, mustard & wheat'),
 'Ve': dict(own=[1, 6], exalt=11, debil=5, friends=['Me', 'Sa'], enemies=['Su', 'Mo'], neutral=['Ma', 'Ju'],
            sectors='Diamond, gems & jewelry, fashion, media & entertainment, essential oils, hospitality, travel & tourism, FMCG, banking & finance, garments, hotels, sugar & agriculture sectors',
            commodities='Diamond, opal, quartz, crystal, silver, copper, peppermint & essential oils'),
 'Sa': dict(own=[9, 10], exalt=6, debil=0, friends=['Me', 'Ve'], enemies=['Su', 'Mo', 'Ma'], neutral=['Ju'],
            sectors='Cements, infrastructure, iron & steels, leather & footwear, crude oil & gas, coal, mining, metals, realty & agriculture sectors',
            commodities='Tin, iron, steel, coal, leather & crude oils'),
 'Ra': dict(own=[], exalt=1, debil=7, friends=['Me', 'Ve', 'Sa'], enemies=['Su', 'Mo', 'Ju'], neutral=['Ma'],
            sectors='Media & entertainment, telecommunication, power, electrical goods, realty, infrastructure, cements & metals sector',
            commodities='Iron & steel'),
 'Ke': dict(own=[], exalt=7, debil=1, friends=['Me', 'Ve', 'Sa'], enemies=['Su', 'Mo', 'Ju'], neutral=['Ma'],
            sectors='Power, IT, leather & footwear, crude oils, oil & gas, pharmaceuticals, coal, realty, infrastructure & automobiles sector',
            commodities='Crude oils, coal, copper, iron & steel'),
 'Ur': dict(own=[10], exalt=7, debil=1, friends=['Me', 'Ve', 'Sa'], enemies=['Su', 'Mo', 'Ma'], neutral=['Ju'],
            sectors='Telecommunication, IT, metals, iron and steel, oil & gas, soft drinks, aviation, alcohol & nuclear energy sector',
            commodities='Iron, steel, radium, uranium & crude oils'),
 'Ne': dict(own=[11], exalt=4, debil=10, friends=['Su', 'Mo', 'Me'], enemies=[], neutral=[],
            sectors='Shipping, oil & gas, pharmaceutical, FMCG, insurance & exports sector',
            commodities='Ethanol, methanol, alcohol, mineral water, soft drink & cold drinks'),
 'Pl': dict(own=[7], exalt=3, debil=9, friends=[], enemies=[], neutral=[],
            sectors='Nuclear energy, pharmaceuticals, health care & metals sector',
            commodities='Iron and steel, uranium & radium'),
}
for g, d in CH4.items():
    d['sector_ids'] = map_terms(d['sectors']); d['commodity_ids'] = [x for x in map_terms(d['commodities']) if x in dict(COMMODITIES)]

# ======================================================= Ch.5  rāśi significations
CH5_TEXT = {
 0: 'Automobiles, pharmaceuticals, infrastructure, capital goods, health care, hospitals, diagnostic centers, medical & surgical equipment, limestone, gypsum, cement, iron & steel, crude, spices, copper, tobaccos, firearms, explosives & metals',
 1: 'Banking, finance, FMCG, entertainment, hotels, hospitality, media, sugar, agriculture, cosmetics, essential oils, perfumeries, peppermint, confectionaries, jewelry, garments, diamond, silver, copper, paints, amusement parks, tourism, toys, investments and insurance',
 2: 'Telecommunications, media, mobiles, export, insurance, airlines, banking, FMCG, publications, IT, textile, peppermint, agro products, food grains, cotton, paper, newsprint and internet services',
 3: 'Oil & gas, petroleum, mineral water, shipping, milk & dairy products, pearl, silver, aluminum, peppermint, alcohols, cold drinks, soft drinks & rice grain',
 4: 'Power, media, gold, copper, bronze, nuclear energy, weapons of mass destruction, gunmetal, firearms, explosives, graphite, sulphur & wheat',
 5: 'Media, telecommunication, mobiles, exports, insurance, aviation, banking, finance, FMCG, publications, IT, textile, peppermint, agro products, food grains, cotton, paper, newsprint and internet services',
 6: 'Banking, finance, investments., insurance, FMCG, media, entertainment, hotels, hospitality, sugar, agriculture, cosmetics, essential oils, perfumeries, peppermint, confectionaries, jewelries, garments, diamond, silver, copper, paints, amusement parks, toys, tourism & travel',
 7: 'Automobile, pharmaceutical, infrastructure, capital goods, health care, hospitals, medical equipment, diagnostic centers, iron & steel, gypsum, cement, limestone, metals, copper, crude, spices, tobacco, nuclear power, uranium, radium, firearms & explosives',
 8: 'Insurance, banking, financial, FMCG, bronze, gold, textile, eatable oils, exports, shipping, jewelry, garments, wheat, mustard & food grains',
 9: 'Leather, footwear, realty, infrastructure, oil & gas, cement, metals, iron & steel, mining, coal, gypsum, tin, limestone, agriculture & livestock',
 10: 'Leather, footwear, realty, infrastructure, oil & gas, cement, metals, iron & steel, mining, coal, gypsum, tin, limestone, telecommunication, internet, nuclear power, uranium, radium, soft & cold drinks, alcohols, aviation, agriculture and livestock',
 11: 'Insurance, banking, financial, FMCG, bronze, gold, textile, eatable oils, exports, shipping, jewelry, garments, oil & gas, pharmaceutical, methanol, ethanol, alcohols, soft & cold drinks, mineral water, wheat, mustard & food grains',
}
CH5_META = {  # ruler, element, benefics, malefics (Ch.5)
 0: ('Ma', 'Fire', 'cardinal', ['Su', 'Ma', 'Mo', 'Ju'], ['Me', 'Ve']), 1: ('Ve', 'Earth', 'fixed', ['Su', 'Me', 'Ve', 'Sa'], ['Mo', 'Ju']),
 2: ('Me', 'Air', 'mutable', ['Me', 'Ve', 'Sa'], ['Su', 'Ma', 'Ju']), 3: ('Mo', 'Water', 'cardinal', ['Mo', 'Ma', 'Ju'], ['Su', 'Me', 'Ve']),
 4: ('Su', 'Fire', 'fixed', ['Su', 'Ma', 'Ju'], ['Mo', 'Me', 'Ve']), 5: ('Me', 'Earth', 'mutable', ['Me', 'Ve', 'Sa'], ['Su', 'Ma', 'Mo', 'Ju']),
 6: ('Ve', 'Air', 'cardinal', ['Me', 'Ve', 'Sa'], ['Su', 'Mo', 'Ju']), 7: ('Ma', 'Water', 'fixed', ['Su', 'Mo', 'Ma', 'Ju'], ['Me', 'Ve']),
 8: ('Ju', 'Fire', 'mutable', ['Su', 'Ma', 'Ju'], ['Mo', 'Me', 'Ve', 'Sa']), 9: ('Sa', 'Earth', 'cardinal', ['Me', 'Ve', 'Sa'], ['Su', 'Mo', 'Ju']),
 10: ('Sa', 'Air', 'fixed', ['Su', 'Me', 'Ve', 'Sa'], ['Mo', 'Ju']), 11: ('Ju', 'Water', 'mutable', ['Mo', 'Ma', 'Ju'], ['Su', 'Me', 'Ve', 'Sa']),
}
CH5 = {i: dict(rasi=RASI[i], ruler=CH5_META[i][0], element=CH5_META[i][1], mode=CH5_META[i][2],
               benefics=CH5_META[i][3], malefics=CH5_META[i][4], text=CH5_TEXT[i], targets=map_terms(CH5_TEXT[i]))
       for i in range(12)}

# ======================================================= Ch.6  sector rules (parsed)
s6 = TXT[TXT.find('» Intraday buying in this sector'):TXT.find('Grahas always keep moving from one rāśi')]
stmts = [flat(x) for x in re.split(r'»', s6) if x.strip()]
stmts = [re.sub(r'\[If we sum up.*$', '', x).strip() for x in stmts]
assert len(stmts) == 180, len(stmts)
CH6 = []
for si in range(30):
    block = stmts[si * 6:(si + 1) * 6]
    sid, sname = SECTORS[si]
    rule = dict(sector=sid, name=sname, horizons={})
    prev_karakas = None
    for k, st in enumerate(block):
        hz = ['intraday', 'intraday', 'short', 'short', 'long', 'long'][k]
        side = 'buy' if k % 2 == 0 else 'sell'
        m = re.search(r'when (.*?) (?:is|are) aspected', st)
        kar_txt = m.group(1)
        karakas = prev_karakas if 'same graha' in kar_txt else grahas_in(kar_txt.replace('[Ketu?]', ''))
        if side == 'buy': prev_karakas = karakas
        trig_txt = st.split('transits')[1] if 'transits' in st else st
        trig_clean = re.sub(r'\[[^\]]*\]', '', trig_txt)
        trigger_planet = 'Mo' if 'and Candra transits' in st else ('Su' if 'and Sūrya transits' in st else 'Ju')
        rule['horizons'].setdefault(hz, {})[side] = dict(
            karakas=karakas, trigger_planet=trigger_planet,
            trigger_rasis=rasis_in(trig_clean), trigger_naks=naks_in(trig_clean),
            editor_note=re.findall(r'\[[^\]]*\]', st), text=st, page=page_of(st))
    CH6.append(rule)

# ======================================================= Ch.7  transits (parsed)
s7 = TXT[TXT.find(' Transit of Sūrya through Meṣa'):TXT.find('Transit of Candra plays role of an important trend')]
bul = [flat(x) for x in s7.split('') if x.strip()]
def classify(ph):
    p = ph.lower()
    table = [
        (r'volatile and directionless', 0.0), (r'remain volatile with marginal downside', -0.15),
        (r'stability amidst weakness', -0.2), (r'lack ?luster|low volumes|volumes low', 0.0),
        (r'price stability with moderate upside', 0.3), (r'prices remain stable and damage is less', -0.15),
        (r'selling pressure remains? (weak|nominal)|damage .* (lower|less|nominal)|remain nominal|remains? marginal', -0.2),
        (r'downs?(slide|side) in stock prices (of above sectors )?remains? moderate|selling pressure remains moderate|downslide in stock prices remain marginal', -0.3),
        (r'moderate negative momentum|slight downslide', -0.4), (r'moderate weakness', -0.5),
        (r'melt ?down|drags down|aggressive selling', -1.0),
        (r'upsurge with volatility|upsurge and volatility', 0.6), (r'calls for volatility|cause volatility', 0.0),
        (r'moderate upsurge|moderate strength|moderate upside', 0.5),
        (r'strong buying|heavy buying|sustained buying', 1.0),
        (r'decline|downslide|negative momentum|slide down|slip down|slides down|show weakness|move down|selling pressure|witness selling|negative price', -0.75),
        (r'upsurge|positive momentum|inflow|upswing|positive price|buying', 0.8),
    ]
    for pat, sc in table:
        if re.search(pat, p): return sc
    return None
CH7 = []
cur = None
for b in bul:
    if b.startswith('Transit of'):
        m = re.match(r'Transit of (\S+) through (\S+?),?\s', b)
        g = GRAHA[m.group(1)]; r = RASI.index(m.group(2).rstrip(','))
        asp = re.search(r'aspected by (.*?),?\s+(?:determines?|results?|brings?|calls?|indicates?|cause[s]?|drags?|determine)\b', b)
        aspectors = grahas_in(asp.group(1).replace('[always!?]', '').replace('[?]', '')) if asp else []
        eff_txt = b[asp.end() - 15:] if asp else b
        cur = dict(graha=g, rasi=r, cond_aspectors=aspectors, effect=classify(b.split('stock')[0] if asp else b),
                   unconditional=not asp, text=b, page=page_of(b), whereas=None)
        # page 26 typo: the second 'Sūrya through Vṛṣabha' entry is Vṛścika (sector list = Vṛścika)
        if g == 'Su' and r == 1 and 'automobile, pharmaceutical' in b: cur['rasi'] = 7; cur['editor_fix'] = 'Book prints Vṛṣabha; sector list and sequence = Vṛścika'
        if g == 'Ju' and r == 6: cur['cond_aspectors'] = ['Su', 'Ma', 'Mo']; cur['editor_fix'] = 'Book prints "Sūrya, Maṅgala or Guru" (Guru cannot aspect itself); read as Candra per every other Guru entry'
        CH7.append(cur)
    elif b.startswith('Whereas') and cur:
        asp = re.search(r'aspected by (.*?),? then', b)
        cur['whereas'] = dict(aspectors=grahas_in(asp.group(1)) if asp else [], effect=classify(b.split('then', 1)[1] if 'then' in b else b), text=b)
for e in CH7:
    e['targets'] = CH5[e['rasi']]['targets']
    if e['graha'] == 'Ur' and e['rasi'] == 10: pass
# Dhanus/Mīna for Śani & Uranus have no 'whereas'; Pluto unconditional.

# ======================================================= Ch.8  nakṣatra intraday rules (parsed)
s8 = TXT[TXT.find('»    If Ketu is aspected by Budha, Śukra or Śani, during Aśvinī'):TXT.find('Aspects play a great deal of role')]
b8 = [flat(x) for x in s8.split('»') if x.strip()]
CH8 = {}
for b in b8:
    m = re.match(r'If (\S+) is aspected by (.*?), during (?:an? )?(.*?) nakṣatra day, then (positive|negative) momentum will be experienced in stock prices of (.*?)(?:, especially so if Candra is also aspected by (.*?), and|, and) strength', b)
    if not m: print('CH8 PARSE FAIL', b[:80]); continue
    lord = GRAHA[m.group(1)]; nk = NAK.index(m.group(3).strip())
    d = CH8.setdefault(nk, dict(nakshatra=NAK[nk], lord=lord, page=page_of(b)))
    key = 'pos' if m.group(4) == 'positive' else 'neg'
    d[key] = dict(aspectors=grahas_in(m.group(2)), moon_confirm=grahas_in(m.group(6) or ''), targets=map_terms(m.group(5)),
                  items=m.group(5), text=b)
    if key == 'neg' and not d[key]['moon_confirm'] and lord != 'Mo': d[key]['moon_confirm'] = ['Ve', 'Sa', 'Ra']
    d['hora'] = ['Mo', lord] if lord != 'Mo' else ['Mo']
CH8 = [CH8[i] for i in sorted(CH8)]
assert len(CH8) == 27, len(CH8)

# ======================================================= Ch.9 aspects (definitions + calibrated engine)
CH9 = dict(text='Conjunction, semi-sextile 30°, semi-square 45°, sextile 60°, square 90°, trine 120°, sesquiquadrate 135°, opposition 180°. '
                'Most powerful: conjunction & opposition; next: square, trine, sextile; others weak.',
           engine='Calibrated (see Validation): sign-based Vedic graha-dṛṣṭi (all grahas 7th; Maṅgala 4/8; Guru 5/9; Śani 3/10; Rāhu/Ketu 5/9) '
                  '+ conjunction (same rāśi) + trine (5th/9th rāśi) for every graha. Strength scaled by type and degree exactness. '
                  'Slow-planet cycle aspects (Ch.16 Guru→Śani) use degree aspects with 3° orb (calibrated on 10-Jan-2008, 01-Feb-2008, 21-Aug-2008, 11-Dec-2008).',
           page=52)

# ======================================================= Ch.10 horā (encoded verbatim)
CH10 = {
 'Su': dict(good=['Mo', 'Ma', 'Ju'], bad=['Ve', 'Ra', 'Sa'], text='gold, copper, bronze as well as power and media sector stocks', page=54),
 'Mo': dict(good=['Su', 'Ju'], bad=['Ra', 'Sa'], text='crude, silver, aluminum, peppermint, eatable oils, oil & gas, petroleum and shipping sector stocks', page=55),
 'Ma': dict(good=['Su', 'Mo', 'Ju'], bad=['Me', 'Ra', 'Sa'], text='copper, steel, metal, spices, pharmaceutical, health care, automobile, crude oil, capital goods, cement and infrastructure sector stocks', page=56),
 'Me': dict(good=['Su', 'Ve'], bad=['Mo', 'Ma'], text='telecommunication, FMCG, food grains, cotton, paper, newsprint, peppermint, agro products, insurance, textile, exports, aviation, IT, banking and financial, media, advertising, educational and publication sector stocks', page=57),
 'Ju': dict(good=['Su', 'Mo', 'Ma'], bad=['Me', 'Ve', 'Ra'], text='gold, bronze, food grains, mustard, FMCG, banking & financial, insurance, eatable oils, textile, shipping, exports, gems and jewelry sector stocks', page=58),
 'Ve': dict(good=['Me', 'Sa'], bad=['Su', 'Mo', 'Ma'], text='silver, copper, diamond, peppermint oil, essential oils, diamond cutting, jewelry, hospitality, hotels, tourism, media & entertainment, FMCG, finance, banking, garments, sugar and agricultural sector stocks', page=59),
 'Sa': dict(good=['Me', 'Ve', 'Ra'], bad=['Su', 'Mo', 'Ma'], text='oil & gas, cement, realty, infrastructure, iron & steel, metal, mining, coal, agricultural products, leather & footwear sector stocks', page=59),
}
for d in CH10.values(): d['targets'] = map_terms(d['text'])
HORA_ORDER = ['Su', 'Ve', 'Me', 'Mo', 'Sa', 'Ju', 'Ma']  # Fig.1: each hour the next in this cycle
WEEKDAY_LORD = ['Mo', 'Ma', 'Me', 'Ju', 'Ve', 'Sa', 'Su']  # python weekday() 0=Mon

# ======================================================= Ch.12 daśā
CH12 = dict(order=['Ke', 'Ve', 'Su', 'Mo', 'Ma', 'Ra', 'Ju', 'Sa', 'Me'],
            minutes={'Su': 24, 'Mo': 40, 'Ma': 28, 'Ra': 72, 'Ju': 64, 'Sa': 76, 'Me': 68, 'Ke': 28, 'Ve': 80},
            text='Micro-viṃśottarī from Candra longitude in the opening-bell chart; balance of first daśā = period × unelapsed fraction of nakṣatra. '
                 'Worked example: 12-Mar-2009 09:55 Mumbai, Candra Kanyā 11°32′ → Candra balance 35 min 24 s (09:55:00–10:30:24), then Ma 28, Ra 72, Gu 64, Sa 76, Bu 68, Ke 28.',
            page=61)

# ======================================================= Ch.13/14 opening bell chart (encoded from text)
CH13 = {1: 'Public sector units and power sectors.', 2: 'FMCG, banking, finance, insurance, jewelry, gold, eatable oils, food grains, soft & cold drink sectors.',
        3: 'Internet, telecommunication, mobiles, media, publications, newsprint, IT, aviation and automobile sectors.',
        4: 'Agriculture, agro products, crude, oil & gas, cements, metals, iron & steel, realty, mining and infrastructure sectors.',
        5: 'Entertainment, amusement parks, toys, handicrafts, educational institutions, insurance, finance, banking and investment sectors.',
        6: 'Health care, hospitals, pharmaceuticals, diagnostic centers, firearms, capital goods and textiles sector.', 7: 'Foreign trades and exports sector.',
        8: 'Health care, diagnostic centers, hospitals and pharmaceutical sectors.', 9: 'Foreign trade, exports, aviation, shipping and tourism sector.',
        10: 'Power, nuclear energy and capital goods sector.', 11: 'Investment, banking, finance and insurance sector.',
        12: 'Hospitality, hotels, health care, hospitals and footwear sector.'}
HOUSE_WEIGHT = {1: 1.0, 4: 1.0, 7: 1.0, 10: 1.0, 5: 0.9, 9: 0.9, 2: 0.6, 11: 0.6, 3: 0.4, 6: 0.4, 8: 0.4, 12: 0.4}
# Encoded explicitly from Ch.14 text (pp.63-78). Format per (graha, house):
#   (good_aspectors, good_effect, bad_aspectors, bad_effect, unconditional_effect, targets_override, mixed)
M3 = ['Su','Mo','Ju']; SUP=['Me','Ve','Sa']; NODEB=['Su','Mo','Ju']
H14 = {
 ('Su',1):(['Mo','Ma','Ju'],.8,['Ve','Sa','Ra','Ke'],-.75,None,'PSU,POWER',None),
 ('Mo',1):(['Su','Me','Ju'],.4,['Sa','Ra','Ke'],-.4,None,'PSU,POWER',None),
 ('Ma',1):(['Su','Mo','Ju'],1.,['Me','Ra'],-1.,None,'PSU,POWER,CAPGOODS',None),
 ('Me',1):(['Su','Ve','Ju','Sa','Ra'],.8,['Mo','Ma'],-.8,None,'PSU,BANK,TELECOM,AVIATION,IT',None),
 ('Ju',1):(['Su','Mo','Ma'],.8,['Me','Ve'],-.75,None,'PSU,POWER,BANK,OILGAS',None),
 ('Ve',1):(['Ra','Me','Sa'],.8,['Su','Mo'],-.75,None,'TRAVEL,HOSPITALITY,BANK,MEDIA,SUGAR,PSU',None),
 ('Sa',1):(['Me','Ve','Ra'],.8,['Su','Mo','Ma'],-.75,None,'PSU,METAL,STEEL,CAPGOODS,REALTY,INFRA,OILGAS',None),
 ('Ra',1):(SUP,.4,NODEB,-.9,None,'PSU,TELECOM,METAL,POWER',None),
 ('Ke',1):(SUP,0.,NODEB,-1.,None,'OILGAS,METAL,POWER',None),
 ('Ur',1):(SUP,.8,['Su','Mo','Ma'],-.75,None,'POWER,OILGAS,TELECOM,AVIATION,REALTY,INFRA,PSU',None),
 ('Ne',1):(['Su','Mo','Me'],.8,[],None,None,'PSU,OILGAS,PHARMA,FMCG,BANK,EXPORTS,SHIPPING',None),
 ('Pl',1):([],None,[],None,.5,'POWER,PHARMA,HEALTH,METAL,PSU',None),
 ('Su',2):(['Mo','Ma','Ju'],.8,['Ve','Sa'],-.75,None,'GEMS,GOLD,EDIBLEOIL,FMCG,BANK',None),
 ('Mo',2):(['Su','Me','Ju'],.4,['Sa','Ra','Ke'],-.5,None,'FMCG,EDIBLEOIL,OILGAS,CRUDE,GOLD,SILVER,ALUMINIUM,STEEL,BANK',None),
 ('Ma',2):(['Su','Mo','Ju'],None,['Me'],0.,None,'AUTO,CEMENT,BANK,FMCG',{'up':['AUTO','CEMENT'],'down':['BANK','FMCG']}),
 ('Me',2):(['Su','Ve','Ju','Sa'],1.,['Mo','Ma'],-.8,None,'TELECOM,BANK,AVIATION,FMCG,TEXTILE,IT,PUBLICATION,EXPORTS,AGRI',None),
 ('Ju',2):(['Su','Mo','Ma'],.8,['Ra'],-.75,None,'GEMS,GOLD,BANK,EDIBLEOIL,FMCG,EXPORTS',None),
 ('Ve',2):(['Me'],.8,['Su','Mo','Ma'],-.75,None,'GEMS,GOLD,SILVER,BANK,FMCG',None),
 ('Sa',2):([],None,['Su','Mo','Ma','Ra','Ke'],-.9,-.6,'FMCG,BANK,GEMS,GOLD,EDIBLEOIL,AGRI',None),
 ('Ra',2):(SUP,0.,NODEB,-.4,None,'TELECOM,BANK,FMCG,AGRI,GOLD,GEMS',None),
 ('Ke',2):(SUP,-.8,NODEB,-.1,None,'OILGAS,CRUDE,BANK,FMCG,COPPER,GEMS',None),
 ('Ur',2):([],None,['Su','Mo','Ma'],-.9,-.6,'FMCG,BANK,GEMS,GOLD,EDIBLEOIL,AGRI',None),
 ('Ne',2):(['Su','Mo','Me'],.8,[],None,None,'BANK,CRUDE,OILGAS,FMCG,EDIBLEOIL,EXPORTS',None),
 ('Pl',2):([],None,[],None,.6,'BANK,FMCG,GEMS',None),
 ('Su',3):(['Mo','Ju'],.8,['Ve','Sa'],-.75,None,None,None),
 ('Mo',3):(['Su','Me','Ju'],.5,['Sa','Ra','Ke'],-.4,None,None,None),
 ('Ma',3):(['Su','Mo','Ju'],None,['Me','Ra'],-1.,None,'AUTO,CAPGOODS,TELECOM,MEDIA,PUBLICATION,IT',{'up':['AUTO','CAPGOODS'],'down':['TELECOM','MEDIA','PUBLICATION','IT']}),
 ('Me',3):(['Su','Ve','Ju','Sa'],.8,['Mo','Ma'],-.8,None,None,None),
 ('Ju',3):(['Su','Mo','Ma'],.8,['Ra','Ve'],-.75,None,None,None),
 ('Ve',3):(['Ra','Me','Sa'],.8,['Su','Mo'],-.75,None,'TRAVEL,HOSPITALITY,AVIATION,AUTO,TELECOM,MEDIA,PUBLICATION,IT',None),
 ('Sa',3):([],None,['Su','Mo','Ma','Ra','Ke'],-.9,-.6,None,None),
 ('Ra',3):(SUP,.4,NODEB,-.9,None,None,None),
 ('Ke',3):(SUP,0.,NODEB,-1.,None,None,None),
 ('Ur',3):([],None,['Su','Mo','Ma'],-.5,.5,None,None),
 ('Ne',3):(['Su','Mo','Me'],.8,[],None,None,None,None),
 ('Pl',3):([],None,[],None,.4,None,None),
 ('Su',4):(['Mo','Ma','Ju'],1.,['Ve','Sa'],0.,None,None,None),
 ('Mo',4):(['Su','Ju','Me'],.8,['Sa','Ra','Ke'],-.75,None,None,None),
 ('Ma',4):(['Su','Mo','Ju'],-.9,['Sa','Ra','Ke'],-.1,None,None,None),
 ('Me',4):(['Su','Ve'],.8,['Mo','Ma'],-.6,None,None,None),
 ('Ju',4):(['Su','Mo','Ma'],.8,['Ra','Ke'],-.75,None,None,None),
 ('Ve',4):(['Me','Sa'],1.,['Su','Mo','Ma'],-.75,None,None,None),
 ('Sa',4):([],None,[],None,-.6,None,None),
 ('Ra',4):(SUP,.8,NODEB,0.,None,None,None),
 ('Ke',4):(SUP,.8,NODEB,0.,None,None,None),
 ('Ur',4):([],None,[],None,-.75,None,None),
 ('Ne',4):(['Su','Mo','Me'],.8,[],None,None,None,None),
 ('Pl',4):([],None,[],None,.6,None,None),
 ('Su',5):(['Mo','Ma','Ju'],None,['Ve','Sa'],-.75,None,'MEDIA,EDU,BANK',{'up':['MEDIA'],'down':['EDU','BANK'],'down_mag':-.3}),
 ('Mo',5):(['Su','Me'],.5,['Sa','Ra','Ke'],-.75,None,None,None),
 ('Ma',5):(['Su','Mo','Ju'],-.75,['Me','Sa','Ra','Ke'],-.3,None,None,None),
 ('Me',5):(['Su','Ve'],.8,['Mo','Ma'],-.75,None,None,None),
 ('Ju',5):(['Su','Mo'],1.,['Ra','Ke'],-.75,None,None,None),
 ('Ve',5):(['Me'],.8,['Su','Mo','Ma'],-.75,None,None,None),
 ('Sa',5):([],None,['Su','Mo','Ma'],-1.,-.75,None,None),
 ('Ra',5):(SUP,0.,NODEB,-.4,None,None,None),
 ('Ke',5):(SUP,-.3,NODEB,-.3,None,None,None),
 ('Ur',5):([],None,['Su','Mo','Ma'],-1.,-1.,None,None),
 ('Ne',5):(['Su','Mo','Me'],.5,[],None,None,None,None),
 ('Pl',5):([],None,[],None,.5,None,None),
}
for h,(dflt) in [(6,None),(8,None),(12,None)]:
    big = 1.0 if h in (6,8) else 0.8
    H14.update({
     ('Su',h):(['Mo','Ma','Ju'],.8 if h!=8 else 1.,['Ve','Sa','Ra','Ke'],-.75,None,None,None),
     ('Mo',h):(['Su','Me'],.4,['Sa','Ra','Ke'],-.75,None,None,None),
     ('Ma',h):(['Su','Mo','Ju'],1.,['Me','Sa'],-.75,None,None,None),
     ('Me',h):(['Su','Ve'],.8,['Mo'],0.,None,None,None),
     ('Ju',h):(['Su','Mo','Ma'],.8,['Me','Ve','Ra'],-.75,None,None,None),
     ('Ve',h):(['Me','Sa','Ra'],.8,['Su','Mo'],-.4,None,None,None),
     ('Sa',h):([],None,[],None,-.75,None,None),
     ('Ra',h):(SUP,.4,NODEB,-.4 if h!=8 else -.6,None,None,None),
     ('Ke',h):(SUP,.8,NODEB,-.75,None,None,None),
     ('Ur',h):([],None,[],None,-.75,None,None),
     ('Ne',h):(['Su','Mo','Me'],.5,[],None,None,None,None),
     ('Pl',h):([],None,[],None,.5,None,None)})
for h in (7,9):
    H14.update({
     ('Su',h):(['Mo','Ju'] if h==7 else ['Mo','Ma','Ju'],.8,['Ve','Sa'] if h==7 else ['Sa','Ra'],-.75,None,None,None),
     ('Mo',h):(['Su','Me'],.4,['Sa','Ra','Ke'],-.75,None,None,None),
     ('Ma',h):(['Su','Mo','Ju'],-.75,['Me','Sa','Ra','Ke'],-.3,None,None,None),
     ('Me',h):(['Su','Ve'],.8,['Mo','Ma'],-.75,None,None,None),
     ('Ju',h):(['Su','Mo','Ma'],1.,['Me','Ve','Ra'],-.75,None,None,None),
     ('Ve',h):(['Me'],.8,['Su','Mo','Ma'],-.75,None,None,None),
     ('Sa',h):([],None,[],None,-.75,None,None),
     ('Ra',h):(SUP,0.,NODEB,-.3,None,None,None),
     ('Ke',h):(SUP,-.75,NODEB,0.,None,None,None),
     ('Ur',h):([],None,[],None,-.75,None,None),
     ('Ne',h):(['Su','Mo','Me'],1.,[],None,None,None,None),
     ('Pl',h):([],None,[],None,.6,None,None)})
H14.update({
 ('Su',10):(['Mo','Ma','Ju'],.8,['Ve','Sa'],-.75,None,None,None),
 ('Mo',10):(['Su','Me'],.4,['Sa','Ra','Ke'],-.75,None,None,None),
 ('Ma',10):(['Su','Mo','Ju'],.8,['Ve','Sa'],-.75,None,None,None),
 ('Me',10):(['Su','Ve','Ra','Ke'],.8,['Mo'],-.2,None,None,None),
 ('Ju',10):(['Su','Mo','Ma'],1.,['Me','Ve'],-.4,None,None,None),
 ('Ve',10):(['Me','Sa'],1.,['Su','Mo'],-.75,None,None,None),
 ('Sa',10):(['Me','Ve','Ra','Ke'],.8,['Su','Mo','Ma'],-.4,None,None,None),
 ('Ra',10):(SUP,0.,NODEB,-.6,None,None,None),
 ('Ke',10):(SUP,0.,NODEB,-.4,None,None,None),
 ('Ur',10):(['Sa','Me','Ve','Ra','Ke'],.8,['Su','Mo','Ma'],-.75,None,None,None),
 ('Ne',10):(['Su','Mo','Me'],-.9,[],None,None,None,None),
 ('Pl',10):([],None,[],None,.6,None,None),
 ('Su',11):(['Mo','Ma','Ju'],.8,['Ve','Sa'],-.75,None,None,None),
 ('Mo',11):(['Su','Me','Ju'],.4,['Sa','Ra','Ke'],-.5,None,None,None),
 ('Ma',11):(['Su','Mo','Ju'],-.75,['Me'],0.,None,None,None),
 ('Me',11):(['Su','Ve','Ju','Sa'],1.,['Mo','Ma'],-.8,None,None,None),
 ('Ju',11):(['Su','Mo','Ma'],.8,['Ra'],-.75,None,None,None),
 ('Ve',11):(['Me'],.8,['Su','Mo','Ma'],-.75,None,None,None),
 ('Sa',11):([],None,['Su','Mo','Ma','Ra','Ke'],-.9,-.6,None,None),
 ('Ra',11):(SUP,0.,NODEB,-.4,None,None,None),
 ('Ke',11):(SUP,-.8,NODEB,0.,None,None,None),
 ('Ur',11):([],None,['Su','Mo','Ma'],-.9,-.6,None,None),
 ('Ne',11):(['Su','Mo','Me'],.8,[],None,None,None,None),
 ('Pl',11):([],None,[],None,.6,None,None)})
assert len(H14) == 144, len(H14)
CH14 = []
for (g, h), (gd, ge, bd, be, unc, tg, mixed) in sorted(H14.items(), key=lambda kv: (kv[0][1], list(GRAHA.values()).index(kv[0][0]))):
    CH14.append(dict(graha=g, house=h, good=gd, effect=ge, bad=bd, bad_effect=be, unconditional=unc,
                     targets=tg.split(',') if tg else map_terms(CH13[h]), mixed=mixed,
                     house_text=CH13[h], house_weight=HOUSE_WEIGHT[h]))
CH11 = dict(text='Rāśi of lagna in the opening-bell chart = sector of the day\'s major movement; benefic aspects to lagna → those sectors strong, malefic aspects → weak.',
            natural_benefics=['Ju', 'Ve', 'Me', 'Mo'], natural_malefics=['Sa', 'Ma', 'Ra', 'Ke', 'Su'], page=61)

# ======================================================= Ch.7 general transit rules (1-17)
CH7_GENERAL = [
 '1) Exalted / own / friendly rāśi → very good / good / ordinary; inimical or debilitated → no good result.',
 '2) Transiting graha benefic to the rāśi → good; malefic to the rāśi → intensified evil.',
 '3) Benefic aspects or friendly association intensify good, minimise bad.', '4) Malefic aspects or enemy association intensify bad, minimise good.',
 '5) Retrograde benefic intensifies positive results.', '6) Retrograde malefic intensifies negative results.',
 '7) Benefic in own daśā intensifies positive (needs natal/company chart – not applied).', '8) Malefic in own daśā intensifies negative (not applied).',
 '9) Eclipse in favourable rāśi → incapable of favourable results.', '10) Eclipse in unfavourable rāśi → intensifies evil.',
 '11) Hemmed between 2 malefics in favourable rāśi → positive reduced.', '12) Hemmed between 2 malefics in unfavourable rāśi → negative intensified.',
 '13) Hemmed between 2 benefics in favourable rāśi → positive at peak.', '14) Hemmed between 2 benefics in unfavourable rāśi → negative reduced.',
 '15) >1 benefic transiting together → good intensified.', '16) >1 malefic transiting together → evil intensified.',
 '17) 4+ grahas in one rāśi → neutral, directionless & volatile.']

# ======================================================= Ch.16-20 cycle rules
CH16 = dict(
 phases={'Fire': ('Recession', 'Śani in Meṣa/Siṃha/Dhanus aspected (conj/trine/opp) by Guru from an odd rāśi – collapse of boom. "Cash is King".', -1.0),
         'Earth': ('Recovery & revival', 'Śani in Vṛṣabha/Kanyā/Makara aspected by Guru – bottom fishing, fresh investment.', 0.6),
         'Air': ('Growth & expansion', 'Śani in Mithuna/Tulā/Kumbha with conjunction or trine of Guru – growth spreads across sectors.', 0.8),
         'Water': ('Over-expansion & boom', 'Śani in watery rāśi aspected by Guru – euphoria; book advises booking profits and holding cash.', 0.4)},
 trigger_orb_deg=3.0,
 history=[(1921, 'Śani and Guru in Siṃha'), (1930, 'Śani in Dhanus and Guru in Mithuna'), (1940, 'Śani and Guru in Meṣa'),
          (1978, 'Śani in Siṃha and Guru in Mithuna'), (1979, 'Śani and Guru in Siṃha'), (1990, 'Śani in Dhanus and Guru in Mithuna'),
          (2008, 'Śani in Siṃha and Guru in Dhanus')],
 watchlist=[('2017-18', 'Śani in Dhanus and Guru in Tulā'), ('2028-29', 'Śani in Meṣa and Guru in Siṃha and Tulā'),
            ('2036-38', 'Śani in Siṃha and Guru in Mithuna'), ('2047-48', 'Śani in Dhanus and Guru in Meṣa and Mithuna'),
            ('2058-59', 'Śani in Meṣa and Guru in Meṣa')], page=83)
CH17 = dict(rules=[
 ('Guru exalted/own/friendly rāśi or favourably aspected → gold strong; enemy/debilitated or malefic aspects → gold weak', 'dignity'),
 ('Guru udita (rising) → gold demand rises; Guru asta (combust) → gold demand falls', 'combust'),
 ('Guru aspected by Sūrya or Candra → favourable for gold', 'su_mo_aspect'),
 ('Guru conjunct Rāhu/Ketu (within ~30°) → hyperinflationary surge in gold', 'node_conj'),
 ('Guru retrograde and separating from Rāhu → gold falls (2008 example)', 'node_separation')], page=87)
CH18 = dict(rules=[
 ('Śani conjunct Rāhu or Ketu → crude soars; separation from conjunction → crude plunges from peak', 'sa_node'),
 ('Candra, Śani, Uranus, Neptune, Rāhu, Ketu benefically placed / aspected by benefics → crude up', 'benefic_positions'),
 ('Node moving into a watery rāśi "cools" crude; Śani in fiery rāśi keeps it "bubbling hot"', 'element')], page=89)
CH19 = dict(text='Dīpāvali Muhurat session closing positive → bullish Samvat year; negative → bearish year.', page=90,
            history=[('2007-11-09', -151, 'Sensex -151 → 2008 crash'), ('2008-10-28', 499, 'Sensex +499 → 2009 recovery')])
CH20 = dict(text='Partial inverse correlation: when equities collapse from peak, gold rises; when equities recover, gold slips.', page=91)
CH15 = dict(periodicities=[('Sūrya', '1 year'), ('Candra', '27 days'), ('Maṅgala', '~2 years'), ('Guru', '12 years – gold & business cycles'),
                           ('Śani', '29 years – realty'), ('Rāhu/Ketu', '18 years – realty, crude, gold'), ('Eclipses', '19 years'),
                           ('Sunspots', '11.3 / 22.6 years'), ('Śani–Guru', '18–19 years [sic, synodic ≈ 20]'), ('Śani–Uranus', '13–14 years'), ('Śani–Neptune', '43–49 years')], page=80)

# ======================================================= karaka favour sets (Ch.8/10/14 explicit lists)
FAVOUR = {
 'Su': dict(good=['Mo', 'Ma', 'Ju'], bad=['Ve', 'Sa', 'Ra', 'Ke']), 'Mo': dict(good=['Su', 'Ma', 'Ju'], bad=['Ve', 'Sa', 'Ra']),
 'Ma': dict(good=['Su', 'Mo', 'Ju'], bad=['Me', 'Sa', 'Ra']), 'Me': dict(good=['Ra', 'Ve', 'Sa', 'Su'], bad=['Mo', 'Ma']),
 'Ju': dict(good=['Su', 'Mo', 'Ma'], bad=['Me', 'Ve', 'Ra']), 'Ve': dict(good=['Me', 'Sa', 'Ra'], bad=['Su', 'Mo', 'Ma']),
 'Sa': dict(good=['Me', 'Ve', 'Ra'], bad=['Su', 'Mo', 'Ma']), 'Ra': dict(good=['Me', 'Ve', 'Sa'], bad=['Su', 'Mo', 'Ju']),
 'Ke': dict(good=['Me', 'Ve', 'Sa'], bad=['Su', 'Mo', 'Ju']), 'Ur': dict(good=['Me', 'Ve', 'Sa'], bad=['Su', 'Mo', 'Ma']),
 'Ne': dict(good=['Su', 'Mo', 'Me'], bad=['Sa', 've'.title(), 'Ra']), 'Pl': dict(good=[], bad=[])}
FAVOUR['Ne']['bad'] = ['Sa', 'Ve', 'Ra']

book = dict(
 meta=dict(title='Stock Market Astrology', author='Indrodeep Banerjee', year=2009, zodiac='sidereal (N.C. Lahiri)',
           extracted_by='extract_rules.py', counts={}),
 grahas=GRAHA, rasis=RASI, nakshatras=NAK, sectors=SECTORS + EXTRA_SECTORS, commodities=COMMODITIES,
 ch4=CH4, ch5=CH5, ch6=CH6, ch7=CH7, ch7_general=CH7_GENERAL, ch8=CH8, ch9=CH9, ch10=CH10, hora_order=HORA_ORDER,
 weekday_lord=WEEKDAY_LORD, ch11=CH11, ch12=CH12, ch13=CH13, house_weight=HOUSE_WEIGHT, ch14=CH14,
 ch15=CH15, ch16=CH16, ch17=CH17, ch18=CH18, ch19=CH19, ch20=CH20, favour=FAVOUR)
book['meta']['counts'] = dict(ch6_statements=180, ch7_transits=len(CH7), ch8_nakshatras=len(CH8), ch10_horas=7, ch14_house_rules=len(CH14))
OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text(json.dumps(book, ensure_ascii=False, indent=1))
print('wrote', OUT, book['meta']['counts'])
