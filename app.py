"""AstroMarket — the three Banerjee books, applied as written.   Run: streamlit run app.py"""
from __future__ import annotations
import json
from datetime import date, datetime, timedelta
from pathlib import Path
import pandas as pd
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go

import astro_core as ac
import engine as E
import calib as C
import tracker as TR

HERE = Path(__file__).parent
st.set_page_config(page_title='AstroMarket', page_icon='🪐', layout='wide')

# ---------------------------------------------------------------- vocabulary
GREEN, AMBER, RED, GREY = '#1f9d55', '#d69e2e', '#c53030', '#a0aec0'
WORD = {1: 'Up', -1: 'Down', 0: 'Neutral', None: 'No rule'}
LIGHT = {'Up': '#c6f6d5', 'Neutral': '#fefcbf', 'Down': '#fed7d7', 'No rule': '#edf2f7'}
DARK = {'Up': GREEN, 'Neutral': AMBER, 'Down': RED, 'No rule': GREY}
ARROW = {'Up': '▲', 'Neutral': '◆', 'Down': '▼', 'No rule': '·'}
HZ = {'intraday': 'Today', 'short': 'Short-term', 'long': 'Long-term'}
HZ_HELP = {'intraday': "The session's direction. Book 1: Moon transits, nakshatra-lord, opening-bell chart. Book 2: the day's muhurta. Book 3: the Ch.14 Nifty method.",
           'short': 'Book 1: Sun, Mars, Mercury, Venus transits. Book 3: Sun & Mars rule (Ch.1) and the Sun-transit sector paragraphs.',
           'long': "Book 1: Jupiter, Saturn, Rahu/Ketu and outer-planet transits, business cycle (Ch.16), gold (Ch.17), crude (Ch.18), Muhurat (Ch.19). Book 3: Saturn from Taurus (Ch.1). Read for that day's sky — when the Moon or a fast planet is part of a long-term rule, the call can change from one day to the next."}
BOOK = {1: 'Book 1 · Stock Market Astrology', 2: 'Book 2 · Investment Muhurtas', 3: 'Book 3 · Predicting the Nifty & Sensex'}


def pill(d, small=False, suffix=''):
    w = WORD[d]; fs = '12px' if small else '14px'
    return (f"<span style='background:{LIGHT[w]};color:{DARK[w]};padding:2px 10px;border-radius:12px;font-weight:600;"
            f"font-size:{fs};white-space:nowrap'>{ARROW[w]} {w}{suffix}</span>")


def books_line(bv):
    return ' '.join(f"<span title='{BOOK[k]}' style='font-size:12px;color:{DARK[WORD[bv[k]]]};white-space:nowrap'>B{k} {ARROW[WORD[bv[k]]]}</span>"
                    for k in (1, 2, 3))


def past(t, hz, d):
    r = C.record(t, hz, 'final', d)
    if not r: return "<span style='color:#a0aec0;font-size:12px'>no price history to check</span>"
    return f"<span style='color:#4a5568;font-size:12px'>such calls right {r['p']:.0%} of {r['n']:,} past times · {r['label']}</span>"


def cell(d): w = WORD[d]; return f"{ARROW[w]} {w}"
def board_style(val):
    for k in ('No rule', 'Up', 'Down', 'Neutral'):
        if isinstance(val, str) and val.endswith(k): return f'background-color:{LIGHT[k]};color:{DARK[k]};font-weight:600'
    return ''


# ---------------------------------------------------------------- settings
ss = st.session_state
ss.setdefault('exch', 'NSE/BSE Mumbai'); ss.setdefault('birth', None)
ss.setdefault('mu', json.loads((HERE / 'data' / 'muhurat.json').read_text()) if (HERE / 'data' / 'muhurat.json').exists() else [])


@st.cache_resource(show_spinner=False)
def get_engine(exch, mu, birth):
    return E.Engine(exch, muhurat=[(date.fromisoformat(a), float(b)) for a, b in mu], birth_nak=birth)
eng = get_engine(ss['exch'], tuple(map(tuple, ss['mu'])), ss['birth'])
FKEY = (ss['exch'], tuple(map(tuple, ss['mu'])), ss['birth'])


@st.cache_data(show_spinner=False, max_entries=8)
def frame(start: date, end: date, _key):
    return eng.frame(start, end)


def next_session(d):
    while d.weekday() >= 5: d += timedelta(days=1)
    return d
TARGETS = E.TARGETS; NAME = E.TARGET_NAME

# ---------------------------------------------------------------- navigation
st.sidebar.markdown('## 🪐 AstroMarket')
page = st.sidebar.radio('Go to', ['Today', 'Month view', '12-month outlook', 'Look ahead', 'Scorecard', 'The books & rules'], label_visibility='collapsed')
st.sidebar.markdown('---')
st.sidebar.caption('▲ green = **Up** · ◆ amber = **Neutral** · ▼ red = **Down** · · grey = no rule in the books for that case.')
st.sidebar.caption('**B1 B2 B3** = what each of the three books says. The headline call is the books\' majority; when one book says Up and another Down the headline is Neutral and marked ⚖️.')
st.sidebar.caption('Calls are logged automatically every trading morning (08:00 IST) and checked every evening (20:00 IST).')

# ================================================================= TODAY
if page == 'Today':
    c0, c1 = st.columns([3, 1])
    d = c1.date_input('Date', next_session(date.today()), label_visibility='collapsed')
    c0.title(f"{d:%A, %d %B %Y}")
    r = eng.day(d)

    st.markdown('#### Market (Nifty 50)')
    cols = st.columns(3)
    for col, hz in zip(cols, E.HORIZONS):
        f = r.final[('NIFTY', hz)]; dis = r.disagree[('NIFTY', hz)]
        col.markdown(f"**{HZ[hz]}**<br>{pill(f, suffix=' ⚖️' if dis else '')}<br>{books_line(r.book[('NIFTY', hz)])}<br>{past('NIFTY', hz, f)}",
                     unsafe_allow_html=True, help=HZ_HELP[hz])

    b3 = r.b3
    with st.container(border=True):
        st.markdown(f"**Book 3 — Nifty today by the Ch.14 method:** {pill(b3['dir'], True)}", unsafe_allow_html=True)
        p = b3['parts']
        st.markdown(' · '.join(f"{p[k]['label']}: **{WORD[p[k]['dir']] if p[k]['dir'] is not None else 'not in supplied copy'}**"
                               + (f" ({p[k]['stat'][0]}/{p[k]['stat'][1]})" if p[k].get('stat') else '') for k in ('nakshatra', 'yoga', 'tithi', 'moon_sign')))
        st.caption(f"Moon {b3['avastha']} avasthā · aspects on the Moon: {', '.join(ac.EN[a] for a in b3['aspects']) or 'none'}")
        for s_ in b3['steps']: st.markdown(f"- {s_}")
        for k in p:
            if p[k].get('note'): st.caption(f"{p[k]['label']}: {p[k]['note']}")
    b2 = r.b2
    with st.container(border=True):
        up = [v for v in b2['votes'] if v['targets'] == 'ALL' and v['dir'] > 0]; dn = [v for v in b2['votes'] if v['targets'] == 'ALL' and v['dir'] < 0]
        st.markdown(f"**Book 2 — the day's muhurta:** {pill(r.book[('NIFTY', 'intraday')][2], True)} &nbsp; "
                    f"{len(up)} auspicious · {len(dn)} inauspicious factors &nbsp; <span style='color:#4a5568;font-size:13px'>"
                    f"{b2['weekday']} · {b2['tithi']} · {b2['nakshatra']} · {b2['yoga']} yoga · {b2['karana']} karana · {b2['month']} month</span>",
                    unsafe_allow_html=True)
        cA, cB = st.columns(2)
        cA.markdown('\n'.join(f"- 🟢 {v['text']} *({v['factor']})*" for v in up) or '—')
        cB.markdown('\n'.join(f"- 🔴 {v['text']} *({v['factor']})*" for v in dn) or '—')
        for v in b2['votes']:
            if v['dir'] == 0 and v['targets'] == 'ALL': st.caption(f"◆ {v['text']} ({v['factor']})")
        for n in b2['notes']: st.caption('ℹ️ ' + n)
    if r.reversal:
        st.warning('**Book 2 Ch.34 — trend-reversal window:** ' + '; '.join(x['text'] for x in r.reversal)
                   + '. The book enters on a buying-nakshatra day after a down-trend, or a selling-nakshatra day after an up-trend.', icon='🔄')
    rg = r.regime
    st.info(f"**Book 1 business cycle:** {rg['phase']} — {'active (Jupiter aspects Saturn)' if rg['active'] else 'not active (Jupiter does not aspect Saturn)'}. "
            f"{rg['desc']} {rg['detail']}", icon='🧭')
    for f in r.flags: st.caption('⚠️ ' + f)

    st.markdown('#### Timing inside the session')
    o, cl = r.open_dt, r.close_dt
    rows = []
    for w in r.windows:
        if w['end'] <= o or w['start'] >= cl: continue
        if w['kind'].startswith(('Gouri', 'Chaughadia', 'Hora')) and w['dir'] == 0: continue
        rows.append(dict(From=max(w['start'], o).strftime('%H:%M'), To=min(w['end'], cl).strftime('%H:%M'), Window=w['kind'],
                         Meaning=('Buy-side' if w['dir'] > 0 else 'Avoid buying / sell-side' if w['dir'] < 0 else 'Neutral'), Source='Book 2 ' + w['text']))
    for h in r.hora:
        if h['dir'] == 0: continue
        rows.append(dict(From=h['start'].strftime('%H:%M'), To=h['end'].strftime('%H:%M'), Window=f"Hora: {ac.EN[h['lord']]} (Book 1)",
                         Meaning=('Buy-side' if h['dir'] > 0 else 'Avoid buying / sell-side') + ' for ' + ', '.join(NAME.get(x, x) for x in h['targets'][:4]),
                         Source=f"Book 1 Ch.10 — {h['why']}"))
    T = pd.DataFrame(rows).sort_values(['From', 'Window']) if rows else pd.DataFrame()
    if len(T):
        st.dataframe(T.style.map(lambda v: f"color:{GREEN};font-weight:600" if str(v).startswith('Buy') else f"color:{RED};font-weight:600" if str(v).startswith('Avoid') else '', subset=['Meaning']),
                     hide_index=True, width='stretch', height=min(600, 40 + 35 * len(T)))
    st.caption('Timing windows say when to act on a call; they do not change the day\'s direction. Book 1 and Book 2 read the planetary hours differently (see "The books & rules").')

    st.markdown('#### All sectors & commodities')
    tab = []
    for t in TARGETS:
        row = dict(Name=NAME[t])
        for hz in E.HORIZONS:
            f = r.final[(t, hz)]; row[HZ[hz]] = ('⚖️ ' if r.disagree[(t, hz)] else '') + cell(f)
            bv = r.book[(t, hz)]
            row[f'{HZ[hz]} B1·B2·B3'] = ' '.join(ARROW[WORD[bv[k]]] for k in (1, 2, 3))
        tab.append(row)
    st.dataframe(pd.DataFrame(tab).style.map(board_style, subset=list(HZ.values())), width='stretch', height=760, hide_index=True)

    with st.expander('Why? — every rule behind any call'):
        t = st.selectbox('Pick a market', TARGETS, format_func=lambda x: NAME[x])
        for hz in E.HORIZONS:
            st.markdown(f"**{HZ[hz]}** — {pill(r.final[(t, hz)], True)} &nbsp; {books_line(r.book[(t, hz)])}", unsafe_allow_html=True)
            vs = r.votes(t, hz)
            if not vs: st.caption('No rule in the three books applies to this market on this horizon today.')
            for v in vs:
                st.markdown(f"- {'🟢' if v['dir'] > 0 else '🔴' if v['dir'] < 0 else '◆'} **B{v['book']} {v['chapter']}** — {v['text']}")
    with st.expander('Sky at the opening bell'):
        cm = r.chart_open
        st.caption(f"Moon in {ac.NAK[cm.moon_nak]} · {ac.tithi_name(cm.tithi)} · opening-bell ascendant {ac.fmt_deg(cm.asc)}")
        st.dataframe(pd.DataFrame([dict(Planet=f"{ac.EN[g]} ({ac.NAMES[g]})", Sign=ac.fmt_deg(cm[g].lon), Nakshatra=ac.NAK[cm[g].nak],
                                         Avastha=ac.avastha(cm[g].lon), Motion='retrograde' if cm[g].retro else '', Dignity=ac.dignity(g, cm[g].sign)[0])
                                    for g in ac.GRAHAS]), hide_index=True, width='stretch')

# ================================================================= MONTH VIEW
elif page == 'Month view':
    st.title('Month view')
    st.caption('One box per day for every market. Green = Up, amber = Neutral, red = Down, grey = no rule; faded = weekend. Hover a box for details.')
    c1, c2 = st.columns([1, 2])
    m0 = c1.date_input('Month', date.today().replace(day=1)).replace(day=1)
    hz = c2.radio('Horizon', E.HORIZONS, format_func=lambda x: HZ[x], horizontal=True)
    end = (m0 + timedelta(days=32)).replace(day=1) - timedelta(days=1)
    days = [m0 + timedelta(days=i) for i in range((end - m0).days + 1)]
    with st.spinner('Reading the month…'):
        F = frame(m0, end, FKEY)

    def grid(targets):
        head = ''.join(f"<th style='font-size:10px;padding:1px;color:{'#bbb' if d.weekday() >= 5 else '#333'}'>{d.day}<br>{'MTWTFSS'[d.weekday()]}</th>" for d in days)
        body = []
        for t in targets:
            cells = []
            for d in days:
                if d.weekday() >= 5:
                    cells.append("<td style='background:#f1f1f1;width:20px;height:18px'></td>"); continue
                v = F.loc[pd.Timestamp(d), (t, hz)]; w = WORD[None if pd.isna(v) else int(v)]
                cells.append(f"<td title='{NAME[t]} · {d:%a %d %b}: {w}' style='background:{DARK[w]};width:20px;height:18px'></td>")
            body.append(f"<tr><td style='font-size:12px;white-space:nowrap;padding-right:8px'>{NAME[t]}</td>{''.join(cells)}</tr>")
        return f"<div style='overflow-x:auto'><table style='border-collapse:separate;border-spacing:2px'><tr><th></th>{head}</tr>{''.join(body)}</table></div>"
    st.markdown('**Market & sectors**'); st.markdown(grid(['NIFTY'] + E.SECTORS), unsafe_allow_html=True)
    st.markdown('**Commodities**'); st.markdown(grid(E.COMMODITIES), unsafe_allow_html=True)
    st.markdown('#### Key planetary dates this month')
    ev = []
    for g in ['Su', 'Ma', 'Me', 'Ju', 'Ve', 'Sa', 'Ra']:
        for tt, a, b in ac.find_ingresses(g, m0 - timedelta(days=1), end):
            if m0 <= tt.date() <= end: ev.append((tt.date(), f'{ac.EN[g]} moves into {ac.RASI_EN[b]} — Book 2 reversal window ±5 days'))
    prev = None
    for d in days:
        c = ac.chart(datetime(d.year, d.month, d.day, 6, tzinfo=ac.timezone.utc)); rs = {g: c[g].retro for g in ['Me', 'Ve', 'Ma', 'Ju', 'Sa']}
        if prev:
            for g in rs:
                if rs[g] != prev[g]: ev.append((d, f"{ac.EN[g]} turns {'retrograde' if rs[g] else 'direct'}"))
        prev = rs
    for k, mx in ac.eclipse_times(m0.year):
        if m0 <= mx.astimezone(ac.IST).date() <= end: ev.append((mx.astimezone(ac.IST).date(), f'{k.title()} eclipse — Book 2: no buying ±3 days'))
    for dd, e in sorted(ev): st.markdown(f"- **{dd:%a %d %b}** — {e}")
    if not ev: st.caption('No sign changes, stations or eclipses this month.')

# ================================================================= 12-MONTH OUTLOOK
elif page == '12-month outlook':
    st.title('12-month outlook')
    s0 = st.date_input('Start', date.today().replace(day=1)).replace(day=1)
    e0 = (s0 + timedelta(days=366)).replace(day=1) - timedelta(days=1)
    with st.spinner('Working through 12 months of planetary positions…'):
        F = frame(s0, e0, FKEY)
    hz = st.radio('Horizon', ['long', 'short', 'intraday'], format_func=lambda x: HZ[x], horizontal=True)
    st.markdown('#### Daily calls across the year')
    st.caption('Each stripe is one trading day — exactly the books\' call for that day. Long stretches of one colour mean the deciding planets stay put; '
               'frequent changes mean a fast planet (often the Moon) is part of the rule.')
    pick = st.multiselect('Show', TARGETS, default=['NIFTY', 'BANK', 'IT', 'OILGAS', 'PHARMA', 'METAL', 'FMCG', 'AUTO', 'REALTY', 'GOLD', 'SILVER', 'CRUDE'], format_func=lambda x: NAME[x])
    segs = []
    for t in pick:
        calls = F[(t, hz)].map(lambda v: WORD[None if pd.isna(v) else int(v)]); start = calls.index[0]; cur = calls.iloc[0]
        for ts, w in calls.items():
            if w != cur: segs.append(dict(Market=NAME[t], Start=start, End=ts, Call=cur)); start, cur = ts, w
        segs.append(dict(Market=NAME[t], Start=start, End=calls.index[-1] + pd.Timedelta(days=1), Call=cur))
    if segs:
        G = pd.DataFrame(segs)
        fig = px.timeline(G, x_start='Start', x_end='End', y='Market', color='Call', color_discrete_map=DARK,
                          category_orders={'Market': [NAME[t] for t in pick], 'Call': ['Up', 'Neutral', 'Down', 'No rule']})
        fig.update_layout(height=60 + 28 * len(pick), margin=dict(l=0, r=0, t=10, b=0), legend_title_text='')
        st.plotly_chart(fig, width='stretch')
    st.markdown('#### Month by month — share of trading days Up vs Down')
    M = F.xs(hz, axis=1, level=1).copy(); M.index = pd.to_datetime(M.index)
    up = (M == 1).resample('MS').mean(); dn = (M == -1).resample('MS').mean()
    net = (up - dn).T.reindex(TARGETS)
    lab = pd.DataFrame({c: [f"▲{u:.0%} ▼{v:.0%}" for u, v in zip(up[c], dn[c])] for c in up.columns}, index=up.index).T.reindex(TARGETS)
    net.index = [NAME[t] for t in net.index]; net.columns = [c.strftime('%b %y') for c in net.columns]
    fig = go.Figure(go.Heatmap(z=net.values, x=net.columns, y=net.index, zmin=-1, zmax=1, text=lab.values, texttemplate='%{text}', textfont=dict(size=9),
                               colorscale=[[0, RED], [0.4, '#f6ad55'], [0.5, '#fefcbf'], [0.6, '#9ae6b4'], [1, GREEN]],
                               colorbar=dict(title='more Down ⟵ ⟶ more Up', tickvals=[-1, 0, 1], ticktext=['all Down', 'balanced', 'all Up']),
                               hovertemplate='%{y} · %{x}: %{text}<extra></extra>'))
    fig.update_layout(height=1100, margin=dict(l=0, r=0, t=10, b=0), yaxis_autorange='reversed')
    st.plotly_chart(fig, width='stretch')
    st.markdown('#### Book 1 business cycle by month')
    rows = []
    for m in pd.date_range(s0, e0, freq='MS'):
        rr = eng.day(next_session(m.date() + timedelta(days=14)))
        rows.append(dict(Month=m.strftime('%b %Y'), Phase=rr.regime['phase'], Active='yes' if rr.regime['active'] else 'no', Detail=rr.regime['detail']))
    st.dataframe(pd.DataFrame(rows), hide_index=True, width='stretch')

# ================================================================= LOOK AHEAD
elif page == 'Look ahead':
    st.title('Look ahead')
    st.caption('Pick a future date or month to see what the books say and how often such calls have been right in the past.')
    c1, c2 = st.columns(2)
    mode = c1.radio('Look at', ['A date', 'A month'], horizontal=True)
    t = c2.selectbox('Market', TARGETS, format_func=lambda x: NAME[x])
    if mode == 'A date':
        d = st.date_input('Date', next_session(date.today() + timedelta(days=30)))
        r = eng.day(d)
        cols = st.columns(3)
        for col, hz in zip(cols, E.HORIZONS):
            f = r.final[(t, hz)]
            col.markdown(f"**{HZ[hz]}**<br>{pill(f, suffix=' ⚖️' if r.disagree[(t, hz)] else '')}<br>{books_line(r.book[(t, hz)])}<br>{past(t, hz, f)}",
                         unsafe_allow_html=True, help=HZ_HELP[hz])
        for hz in E.HORIZONS:
            vs = [v for v in r.votes(t, hz) if v['dir'] != 0]
            if vs:
                st.markdown(f"**{HZ[hz]} — rules that apply**")
                for v in vs[:12]: st.markdown(f"- {'🟢' if v['dir'] > 0 else '🔴'} B{v['book']} {v['chapter']} — {v['text']}")
    else:
        m = st.date_input('Month', (date.today().replace(day=1) + timedelta(days=32)).replace(day=1)).replace(day=1)
        e = (m + timedelta(days=32)).replace(day=1) - timedelta(days=1)
        F = frame(m, e, FKEY)
        for hz in E.HORIZONS:
            s = F[(t, hz)]
            n = s.notna().sum() or 1
            st.markdown(f"**{HZ[hz]}** — ▲ Up {(s == 1).sum() / n:.0%} of trading days · ◆ Neutral {(s == 0).sum() / n:.0%} · ▼ Down {(s == -1).sum() / n:.0%}")
            st.markdown(' '.join(f"<span title='{ix:%a %d %b}: {WORD[None if pd.isna(v) else int(v)]}' style='display:inline-block;width:22px;height:22px;margin:1px;"
                                 f"background:{DARK[WORD[None if pd.isna(v) else int(v)]]};color:white;font-size:10px;text-align:center;line-height:22px'>{ix.day}</span>"
                                 for ix, v in s.items()), unsafe_allow_html=True)

# ================================================================= SCORECARD
elif page == 'Scorecard':
    st.title('Scorecard — were the calls right?')
    st.info('This runs by itself. Every trading morning at 08:00 IST the books\' call for every tracked market and horizon is logged before the open — '
            'whatever its past accuracy; every evening at 20:00 IST it is checked against actual prices. Logged calls are never edited afterwards. '
            'Neutral calls are logged but have no right/wrong.', icon='⚙️')
    df = TR.load()
    incl = st.toggle('Include reconstructed history (paper record) for context', value=not (df['mode'] == 'live').any())
    modes = ('live', 'paper') if incl else ('live',)
    S = TR.stats(df, modes)
    pending = int(((df.status == 'pending') & df['mode'].isin(modes)).sum())
    k = st.columns(4)
    k[0].metric('Calls checked', f"{S.get('n', 0):,}", help='Up/Down calls whose outcome is known.')
    k[1].metric('Right', f"{S['hit']:.0%}" if S.get('n') else '—', help='Coin-flip = 50%.')
    nv = None
    if S.get('n'):
        nv = sum(b['naive'] * b['n'] for b in S['by_horizon'].values()) / sum(b['n'] for b in S['by_horizon'].values())
        k[2].metric('Simple benchmark', f'{nv:.0%}', help='How often you would be right by always predicting whichever direction actually happened more often in those same windows.')
    k[3].metric('Awaiting outcome', f'{pending}')
    if S.get('n'):
        if S['n'] < 60: st.caption('Fewer than 60 calls checked — too early to judge.')
        g = TR.running(df, modes)
        fig = go.Figure(go.Scatter(x=g.date, y=g.cumulative, line=dict(color='#1a365d', width=3), name='Cumulative % right'))
        fig.add_hline(y=0.5, line_dash='dot', annotation_text='coin-flip'); fig.add_hline(y=nv, line_dash='dash', line_color=AMBER, annotation_text='benchmark')
        fig.update_layout(height=300, yaxis_tickformat='.0%', yaxis_range=[0.2, 0.8], margin=dict(l=0, r=0, t=10, b=0))
        st.plotly_chart(fig, width='stretch')
        a, b = st.columns(2)
        a.dataframe(pd.DataFrame([dict(Horizon=HZ[h], Checked=x['n'], Right=f"{x['hit']:.0%}", Benchmark=f"{x['naive']:.0%}") for h, x in S['by_horizon'].items()]), hide_index=True, width='stretch')
        b.dataframe(pd.DataFrame([dict(Book=BOOK[int(k_[-1])], Checked=x['n'], Right=f"{x['hit']:.0%}") for k_, x in S.get('by_book', {}).items()]), hide_index=True, width='stretch')
    st.markdown('#### Recent calls')
    sub = df[df['mode'].isin(modes + ('late',))].sort_values(['date', 'horizon'], ascending=[False, True]).head(400).copy()
    if sub.empty:
        st.caption('The first live calls appear after the next 08:00 IST run.')
    else:
        def res(r):
            if r['mode'] == 'late': return '⚪ logged late — not counted'
            if r['status'] == 'no call': return '— neutral / no rule'
            if r['status'] == 'pending': return f"⏳ result on {(r['date'] + pd.tseries.offsets.BDay(TR.HZ_SESSIONS[r['horizon']] - 1)):%d %b}"
            if r['status'] != 'scored': return '— market closed'
            return ('✅ right' if r['correct'] == 1 else '❌ wrong' if r['correct'] == 0 else '— flat') + f" (actual {r['actual_ret'] * 100:+.2f}%)"
        sub['Result'] = sub.apply(res, axis=1)
        sub['Call'] = sub['view'].map(lambda v: f"{ARROW.get(v, '')} {v}")
        sub['Books'] = sub.apply(lambda r: f"{ARROW.get(r['book1'], '·')} {ARROW.get(r['book2'], '·')} {ARROW.get(r['book3'], '·')}", axis=1)
        out = sub[['date', 'name', 'horizon', 'Call', 'Books', 'Result']].rename(columns={'date': 'Date', 'name': 'Market', 'horizon': 'Horizon', 'Books': 'B1 B2 B3'})
        out['Horizon'] = out['Horizon'].map(HZ); out['Date'] = out['Date'].dt.strftime('%d %b %Y')
        st.dataframe(out.style.map(board_style, subset=['Call']), hide_index=True, width='stretch', height=520)
        st.download_button('Download full log (CSV)', TR.LOG.read_bytes(), 'astro_predictions.csv')

# ================================================================= BOOKS & RULES
else:
    st.title('The books & rules')
    st.markdown('''
The app applies only the rules of three books by Indrodeep Banerjee, as written:

| | Book | What it drives in the app |
|---|---|---|
| **B1** | *Stock Market Astrology* (2009) | Sectors and commodities on all three horizons; Nifty long-term via the business cycle (Ch.16) and Dīpāvali Muhurat (Ch.19); planetary-hour timing (Ch.10) |
| **B2** | *Investment Muhurtas* (2014) | The day's muhurta for the market and every sector (the book: *markets pick up on auspicious days and turn bearish on inauspicious days*); Rahu Kalam, Yamakandam, Gulika, Gouri, Chaughadia, Durmuhurta, Abhijit, horā timing; trend-reversal windows (Ch.34) |
| **B3** | *Predicting the Nifty & Sensex* | Nifty today by the book's own Ch.14 method (nakshatra, yoga, tithi and Moon-sign tables for the Sun's sign, Moon aspects and avasthā); Nifty short- and long-term (Ch.1); sector short-term (Sun-transit paragraphs) |

**How votes are combined** — the books never say how to merge one another, so the app uses the plainest rule: inside a book, more Up rules than Down → Up, more Down → Down, equal → Neutral; across books the same count, and if one book says Up while another says Down the call is **Neutral ⚖️**. No weights, scores or smoothing.
''')
    st.markdown('#### Where the books contradict each other (or themselves)')
    for c_ in E.CONTRA:
        with st.expander(f"{c_['id']}. {c_['topic']} — {c_['books']}"):
            st.markdown(c_['detail']); st.caption('In the app: ' + c_['app'])
    cal = C.cal()
    if cal.get('NIFTY'):
        st.markdown('#### How the books\' calls have matched the Nifty (Feb 2012 onward)')
        rows = []
        for hz in E.HORIZONS:
            x = cal['NIFTY'][hz]
            for s_, nm in (('final', 'Headline call'), ('b1', 'Book 1'), ('b2', 'Book 2'), ('b3', 'Book 3')):
                y = x.get(s_, {})
                if y.get('n'): rows.append(dict(Horizon=HZ[hz], Source=nm, Calls=f"{y['n']:,}", Right=f"{y['p']:.1%}", Benchmark=f"{y['naive']:.1%}"))
        st.dataframe(pd.DataFrame(rows), hide_index=True, width='stretch')
        st.caption('Shown for information only — it never changes or filters a call. Benchmark = always predicting the direction that occurred more often.')
    with st.expander('Checks that the calculations match the books'):
        vr = HERE / 'data' / 'validation_report.json'
        if vr.exists():
            v = json.loads(vr.read_text()); m = v['chosen']
            st.write(f"Positions: {m['hard_pass']} of {m['hard_total']} dated facts from the three books reproduced. "
                     f"Methods: {sum(t['pass_'] for t in v.get('method_tests', []))} of {len(v.get('method_tests', []))} worked examples reproduced.")
            st.dataframe(pd.DataFrame(v['tests'] + v.get('method_tests', []))[['test', 'book', 'engine', 'pass_']].rename(
                columns={'test': 'Check', 'book': 'Book says', 'engine': 'App computes', 'pass_': 'Match'}), hide_index=True, width='stretch')
    with st.expander('Settings'):
        ex = st.selectbox('Market location (opening-bell chart, sunrise-based windows)', list(ac.EXCHANGES), index=list(ac.EXCHANGES).index(ss['exch']))
        bn = st.selectbox('Your birth nakshatra (optional — adds Book 2 Tara bala)', [None] + list(range(27)), index=0 if ss['birth'] is None else ss['birth'] + 1,
                          format_func=lambda i: '— not set —' if i is None else ac.NAK[i])
        mu = st.text_area('Dīpāvali Muhurat-session results (date, points) — Book 1 Ch.19 annual signal', '\n'.join(f'{a}, {b:g}' for a, b in ss['mu']))
        if st.button('Apply'):
            parsed = []
            for ln in mu.strip().splitlines():
                try: a, b = ln.split(','); parsed.append([date.fromisoformat(a.strip()).isoformat(), float(b)])
                except Exception: pass
            ss['exch'], ss['mu'], ss['birth'] = ex, parsed, bn; st.cache_data.clear(); st.rerun()
        st.caption('To make a Muhurat entry permanent for the automatic daily runs, add it to data/muhurat.json in the GitHub repo.')
