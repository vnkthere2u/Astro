"""AstroMarket — daily astro-market views, outlook and scorecard.   Run: streamlit run app.py"""
from __future__ import annotations
import json
from datetime import date, datetime, time, timedelta
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

# ---------------------------------------------------------------- vocabulary (no letters, no jargon)
GREEN, AMBER, RED = '#1f9d55', '#d69e2e', '#c53030'
LIGHT = {'Bullish': '#c6f6d5', 'Neutral': '#fefcbf', 'Bearish': '#fed7d7'}
DARK = {'Bullish': GREEN, 'Neutral': AMBER, 'Bearish': RED}
ARROW = {'Bullish': '▲', 'Neutral': '◆', 'Bearish': '▼'}
HZ = {'intraday': 'Today', 'short': 'Next week', 'long': 'Next 2 months'}
HZ_HELP = {'intraday': "That session's open-to-close bias, from the Moon, nakshatra, opening-bell chart and planetary hours.",
           'short': 'Average view over the next 5 sessions, from Sun, Mars, Mercury and Venus transits.',
           'long': 'Average view over the next 40 sessions (~2 months), from Jupiter, Saturn, Rahu/Ketu, the business-cycle, gold and crude cycles. Changes only when a slow planet changes sign, turns, or forms/leaves an aspect.'}
EDGE = {'High': ('Strong edge', '#1a365d'), 'Medium': ('Tradeable — modest edge', '#2b6cb0'),
        'Low': ('No proven edge', '#718096'), 'Unproven': ('Too little history', '#a0aec0'), None: ('—', '#a0aec0')}

def view(s): return TR.view_word(s)
def strength(s): return TR.strength_word(s)
def pill(s, small=False):
    v = view(s); st_ = strength(s)
    txt = f"{ARROW[v]} {v}" + (f" · {st_}" if v != 'Neutral' else '')
    fs = '12px' if small else '14px'
    return f"<span style='background:{LIGHT[v]};color:{DARK[v]};padding:2px 10px;border-radius:12px;font-weight:600;font-size:{fs}'>{txt}</span>"
def edge_txt(cf):
    if not cf: return "<span style='color:#a0aec0'>—</span>"
    lab, col = EDGE[cf['tier']]
    bench = f" vs {cf['naive']:.0%} benchmark" if cf.get('naive') else ''
    return f"<span style='color:{col};font-size:12px'>{lab} · right {cf['p']:.0%} of the time historically{bench}</span>"
def cell_text(s): v = view(s); return f"{ARROW[v]} {v}" + (f" ({strength(s)})" if v != 'Neutral' else '')
def board_style(val):
    for k in LIGHT:
        if isinstance(val, str) and k in val: return f'background-color:{LIGHT[k]};color:{DARK[k]};font-weight:600'
    return ''

# ---------------------------------------------------------------- settings (kept in About → Advanced)
ss = st.session_state
ss.setdefault('exch', 'NSE/BSE Mumbai'); ss.setdefault('thr', 0.15)
ss.setdefault('mu', json.loads((HERE / 'data' / 'muhurat.json').read_text()) if (HERE / 'data' / 'muhurat.json').exists() else [])
E.THRESH = ss['thr']

@st.cache_resource(show_spinner=False)
def get_engine(exch, mu):
    return E.Engine(exch, muhurat=[(date.fromisoformat(a), float(b)) for a, b in mu])
eng = get_engine(ss['exch'], tuple(map(tuple, ss['mu'])))

@st.cache_data(show_spinner=False, max_entries=8)
def frame(start: date, end: date, _key):
    return eng.frame(start, end)
FKEY = (ss['exch'], tuple(map(tuple, ss['mu'])))

def next_session(d):
    while d.weekday() >= 5: d += timedelta(days=1)
    return d
TARGETS = ['NIFTY'] + E.SECTORS + E.COMMODITIES
NAME = E.TARGET_NAME

def run_info(F, t, d, hz='long'):
    """Since when the current call has held, and when it next changes (from the stabilised series)."""
    s = F[(t, hz)]; calls = s.map(view); ts = pd.Timestamp(d)
    if ts not in calls.index: return None, None
    cur = calls.loc[ts]
    before = calls.loc[:ts][::-1]; ch = before[before != cur]
    since = before.index[0] if ch.empty else calls.loc[ch.index[0]:].index[1]
    after = calls.loc[ts:]; ch2 = after[after != cur]
    nxt = None if ch2.empty else ch2.index[0]
    return since.date(), (nxt.date() if nxt is not None else None)

# ---------------------------------------------------------------- navigation
st.sidebar.markdown('## 🪐 AstroMarket')
page = st.sidebar.radio('Go to', ['Today', 'Month view', '12-month outlook', 'Look ahead', 'Scorecard', 'About & settings'], label_visibility='collapsed')
st.sidebar.markdown('---')
st.sidebar.caption('**Colours everywhere:** ▲ green = Bullish · ◆ amber = Neutral · ▼ red = Bearish.')
st.sidebar.caption('**Edge** tells you whether that kind of call has beaten a simple benchmark in 14 years of history. '
                   'Only "Tradeable" or "Strong edge" calls are worth acting on; the rest is context.')
st.sidebar.caption('New calls are logged automatically every trading morning (08:00 IST) and scored every evening (20:00 IST).')

# ================================================================= TODAY
if page == 'Today':
    c0, c1 = st.columns([3, 1])
    d = c1.date_input('Date', next_session(date.today()), label_visibility='collapsed')
    c0.title(f"{d:%A, %d %B %Y}")
    v = eng.view(d)
    F = frame(d - timedelta(days=270), d + timedelta(days=270), FKEY)

    st.markdown('#### Market (Nifty 50)')
    cols = st.columns(3)
    for col, hz in zip(cols, E.HORIZONS):
        s = v.scores['NIFTY'][hz]; cf = C.confidence('NIFTY', hz, s)
        extra = ''
        if hz != 'intraday':
            since, nxt = run_info(F, 'NIFTY', d, hz)
            if since: extra = f"<br><span style='font-size:12px;color:#4a5568'>holding since {since:%d %b} · next change {nxt:%d %b %Y}</span>" if nxt else \
                              f"<br><span style='font-size:12px;color:#4a5568'>holding since {since:%d %b} · no change in the next 9 months</span>"
        col.markdown(f"**{HZ[hz]}**<br>{pill(s)}<br>{edge_txt(cf)}{extra}", unsafe_allow_html=True, help=HZ_HELP[hz])
    rg = v.regime
    st.info(f"**Business-cycle backdrop:** {rg['phase']} ({rg['state'].split(' ')[0].lower()}). {rg['desc']}", icon='🧭')
    for f in v.flags: st.caption('⚠️ ' + f)

    st.markdown('#### Actionable calls')
    st.caption('Only calls whose type has historically beaten the simple benchmark. Most days there are few or none — that is by design.')
    rows = []
    for hz in E.HORIZONS:
        for t in TR.TRACKABLE:
            if t == 'NIFTY': continue
            s = v.scores[t][hz]; cf = C.confidence(t, hz, s)
            if C.actionable(cf):
                em = C.expected_move(t, hz, s)
                rows.append((hz, t, s, cf, em))
    if not rows:
        st.success('No sector or commodity call has a proven edge today. Use the board below as context only.', icon='🧘')
    for hz, t, s, cf, em in sorted(rows, key=lambda x: -x[3]['p']):
        mv = f"Typical move after such calls: {em['mean'] * 100:+.2f}% (up {em['up']:.0%} of the time)" if em else ''
        st.markdown(f"**{NAME[t]}** · {HZ[hz]} &nbsp; {pill(s)} &nbsp; {edge_txt(cf)}<br><span style='font-size:12px;color:#4a5568'>{mv}</span>", unsafe_allow_html=True)

    st.markdown('#### Best timing in the session')
    st.caption('Planetary hours (horā). A buying hour favours entries in the listed groups; a selling hour favours exits / shorts. Timing only — it does not set direction.')
    for h in v.hora:
        if h['signal'] == 'neutral': continue
        bias = 'Buying hour' if 'BUY' in h['signal'] else 'Selling hour'
        names = [NAME[x] for x in h['targets'] if x in NAME][:5]
        colr = GREEN if bias == 'Buying hour' else RED
        st.markdown(f"<span style='font-family:monospace'>{h['start']:%H:%M}–{h['end']:%H:%M}</span> &nbsp; <b style='color:{colr}'>{bias}</b> "
                    f"({ac.EN[h['lord']]} hour) — {', '.join(names)}", unsafe_allow_html=True)

    st.markdown('#### All sectors & commodities')
    show_scores = st.toggle('Show numeric scores (−1 … +1)', False)
    tab = []
    for t in TARGETS:
        r = dict(Name=NAME[t])
        for hz in E.HORIZONS:
            s = v.scores[t][hz]; r[HZ[hz]] = f"{cell_text(s)}" + (f"  {s:+.2f}" if show_scores else '')
        since, nxt = run_info(F, t, d, 'long')
        r['2-month view since'] = f'{since:%d %b %Y}' if since else ''
        r['Next change'] = f'{nxt:%d %b %Y}' if nxt else '> 9 months'
        cf = C.confidence(t, 'long', v.scores[t]['long'])
        r['Edge (2-month)'] = EDGE[cf['tier'] if cf else None][0]
        tab.append(r)
    st.dataframe(pd.DataFrame(tab).style.map(board_style, subset=list(HZ.values())), width='stretch', height=760, hide_index=True)

    with st.expander('Why? — see the drivers behind any call'):
        t = st.selectbox('Pick a sector or commodity', TARGETS, format_func=lambda x: NAME[x])
        for hz in E.HORIZONS:
            cs = sorted((c for c in v.raw_contrib(t) if c.horizon == hz) if hasattr(v, 'raw_contrib') else (c for c in v.contrib.get(t, []) if c.horizon == hz), key=lambda c: -abs(c.value))[:5]
            st.markdown(f"**{HZ[hz]}** — {cell_text(v.scores[t][hz])}")
            for c in cs:
                st.markdown(f"- {'🟢' if c.value > 0 else '🔴'} {c.text}")
            if hz != 'intraday': st.caption('Shown for this day; the displayed view averages these readings over the coming sessions.')
    with st.expander('Sky today'):
        cm = v.chart_mid
        st.caption(f"Moon in {ac.NAK[cm.moon_nak]} nakshatra · tithi {cm.tithi} ({'waxing' if cm.waxing else 'waning'}) · market-open ascendant {ac.fmt_deg(v.chart_open.asc)}")
        st.dataframe(pd.DataFrame([dict(Planet=f"{ac.EN[g]} ({ac.NAMES[g]})", Sign=ac.fmt_deg(cm[g].lon), Nakshatra=ac.NAK[cm[g].nak],
                                         Motion='retrograde' if cm[g].retro else '', Strength=ac.dignity(g, cm[g].sign)[0]) for g in ac.GRAHAS]),
                     hide_index=True, width='stretch')

# ================================================================= MONTH VIEW
elif page == 'Month view':
    st.title('Month view')
    st.caption('One box per day for every sector and commodity. Green = Bullish, amber = Neutral, red = Bearish; faded = weekend. Hover a box for details.')
    c1, c2 = st.columns([1, 2])
    m0 = c1.date_input('Month', date.today().replace(day=1)).replace(day=1)
    hz = c2.radio('Which view', ['intraday', 'short', 'long'], format_func=lambda x: {'intraday': "That day's trading bias", 'short': 'Next-week view', 'long': 'Next-2-month view'}[x], horizontal=True)
    end = (m0 + timedelta(days=32)).replace(day=1) - timedelta(days=1)
    days = [m0 + timedelta(days=i) for i in range((end - m0).days + 1)]
    F = frame(m0, end, FKEY)
    def grid(targets):
        head = ''.join(f"<th style='font-size:10px;padding:1px;color:{'#bbb' if d.weekday() >= 5 else '#333'}'>{d.day}<br>{'MTWTFSS'[d.weekday()]}</th>" for d in days)
        body = []
        for t in targets:
            cells = []
            for d in days:
                if d.weekday() >= 5:
                    cells.append("<td style='background:#f1f1f1;width:20px;height:18px'></td>"); continue
                s = F.loc[pd.Timestamp(d), (t, hz)]; w = view(s)
                cells.append(f"<td title='{NAME[t]} · {d:%a %d %b}: {w} ({s:+.2f})' style='background:{DARK[w]};width:20px;height:18px'></td>")
            body.append(f"<tr><td style='font-size:12px;white-space:nowrap;padding-right:8px'>{NAME[t]}</td>{''.join(cells)}</tr>")
        return f"<div style='overflow-x:auto'><table style='border-collapse:separate;border-spacing:2px'><tr><th></th>{head}</tr>{''.join(body)}</table></div>"
    st.markdown('**Market & sectors**'); st.markdown(grid(['NIFTY'] + E.SECTORS), unsafe_allow_html=True)
    st.markdown('**Commodities**'); st.markdown(grid(E.COMMODITIES), unsafe_allow_html=True)
    st.markdown('#### Key planetary dates this month')
    ev = []
    for g in ['Su', 'Ma', 'Me', 'Ju', 'Ve', 'Sa', 'Ra']:
        for tt, a, b in ac.find_ingresses(g, m0 - timedelta(days=1), end):
            if m0 <= tt.date() <= end: ev.append((tt.date(), f'{ac.EN[g]} moves into {ac.RASI_EN[b]} ({ac.RASI[b]})'))
    prev = None
    for d in days:
        c = ac.chart(datetime(d.year, d.month, d.day, 6, tzinfo=ac.timezone.utc)); rs = {g: c[g].retro for g in ['Me', 'Ve', 'Ma', 'Ju', 'Sa']}
        if prev:
            for g in rs:
                if rs[g] != prev[g]: ev.append((d, f"{ac.EN[g]} turns {'retrograde' if rs[g] else 'direct'}"))
        prev = rs
    for k, tjd in ac.eclipses_in_year(m0.year):
        dd = ac.from_jd(tjd).date()
        if m0 <= dd <= end: ev.append((dd, f'{k.title()} eclipse'))
    for dd, e in sorted(ev): st.markdown(f"- **{dd:%a %d %b}** — {e}")
    if not ev: st.caption('No major sign changes or stations this month.')

# ================================================================= 12-MONTH OUTLOOK
elif page == '12-month outlook':
    st.title('12-month outlook')
    s0 = st.date_input('Start', date.today().replace(day=1)).replace(day=1)
    e0 = (s0 + timedelta(days=366)).replace(day=1) - timedelta(days=1)
    with st.spinner('Working through 12 months of planetary positions…'):
        F = frame(s0, e0, FKEY)
    st.markdown('#### How long each 2-month view lasts')
    st.caption('Each bar is a stretch of time with the same next-2-month view. Long views change only on slow-planet events, so bars usually run for weeks or months.')
    pick = st.multiselect('Show', TARGETS, default=['NIFTY', 'BANK', 'IT', 'OILGAS', 'PHARMA', 'METAL', 'FMCG', 'AUTO', 'REALTY', 'GOLD', 'SILVER', 'CRUDE'], format_func=lambda x: NAME[x])
    segs = []
    for t in pick:
        calls = F[(t, 'long')].map(view); start = calls.index[0]; cur = calls.iloc[0]
        for ts, w in calls.items():
            if w != cur:
                segs.append(dict(Target=NAME[t], Start=start, End=ts, View=cur)); start, cur = ts, w
        segs.append(dict(Target=NAME[t], Start=start, End=calls.index[-1] + pd.Timedelta(days=1), View=cur))
    if segs:
        G = pd.DataFrame(segs)
        fig = px.timeline(G, x_start='Start', x_end='End', y='Target', color='View', color_discrete_map=DARK,
                          category_orders={'Target': [NAME[t] for t in pick], 'View': ['Bullish', 'Neutral', 'Bearish']})
        fig.update_layout(height=60 + 28 * len(pick), margin=dict(l=0, r=0, t=10, b=0), legend_title_text='')
        st.plotly_chart(fig, width='stretch')
    st.markdown('#### Month-by-month heat-map')
    hz = st.radio('View', ['long', 'short', 'intraday'], format_func=lambda x: {'long': 'Next-2-month view', 'short': 'Next-week view', 'intraday': 'Daily trading bias'}[x], horizontal=True)
    M = F.xs(hz, axis=1, level=1).copy(); M.index = pd.to_datetime(M.index)
    avg = M.resample('MS').mean().T.reindex(TARGETS); avg.index = [NAME[t] for t in avg.index]; avg.columns = [c.strftime('%b %y') for c in avg.columns]
    lab = avg.map(lambda s: f"{ARROW[view(s)]}")
    fig = go.Figure(go.Heatmap(z=avg.values, x=avg.columns, y=avg.index, zmin=-0.7, zmax=0.7, text=lab.values, texttemplate='%{text}',
                               colorscale=[[0, RED], [0.39, '#f6ad55'], [0.5, '#fefcbf'], [0.61, '#9ae6b4'], [1, GREEN]],
                               colorbar=dict(title='Bearish ⟵ ⟶ Bullish', tickvals=[-0.6, 0, 0.6], ticktext=['Bearish', 'Neutral', 'Bullish']),
                               hovertemplate='%{y} · %{x}: %{z:+.2f}<extra></extra>'))
    fig.update_layout(height=1050, margin=dict(l=0, r=0, t=10, b=0), yaxis_autorange='reversed')
    st.plotly_chart(fig, width='stretch')
    st.markdown('#### Business-cycle backdrop by month')
    rows = []
    for m in pd.date_range(s0, e0, freq='MS'):
        r = eng.raw(m.date() + timedelta(days=14)); rows.append(dict(Month=m.strftime('%b %Y'), Phase=r.regime['phase'], Status=r.regime['state'].split(' ')[0].title()))
    st.dataframe(pd.DataFrame(rows), hide_index=True, width='stretch')

# ================================================================= LOOK AHEAD
elif page == 'Look ahead':
    st.title('Look ahead')
    st.caption('Pick a future date or month to see the call, how often that kind of call has been right, and the typical move that followed it in the past.')
    c1, c2 = st.columns(2)
    mode = c1.radio('Look at', ['A date', 'A month'], horizontal=True)
    t = c2.selectbox('Sector or commodity', TARGETS, format_func=lambda x: NAME[x])
    if mode == 'A date':
        d = st.date_input('Date', next_session(date.today() + timedelta(days=30)))
        v = eng.view(d)
        cols = st.columns(3)
        for col, hz in zip(cols, E.HORIZONS):
            s = v.scores[t][hz]; cf = C.confidence(t, hz, s); em = C.expected_move(t, hz, s)
            mv = (f"<br><span style='font-size:13px'>Typical move afterwards: <b>{em['mean'] * 100:+.2f}%</b> "
                  f"(middle half of outcomes {em['p25'] * 100:+.1f}% to {em['p75'] * 100:+.1f}%; normal average {em['all_mean'] * 100:+.2f}%)</span>") if em else ''
            col.markdown(f"**{HZ[hz]}**<br>{pill(s)}<br>{edge_txt(cf)}{mv}", unsafe_allow_html=True, help=HZ_HELP[hz])
        st.caption('If the typical move after a call is close to the normal average, the call has added little in the past.')
    else:
        m = st.date_input('Month', (date.today().replace(day=1) + timedelta(days=32)).replace(day=1)).replace(day=1)
        e = (m + timedelta(days=32)).replace(day=1) - timedelta(days=1)
        F = frame(m, e, FKEY)
        df = pd.DataFrame({HZ[hz]: F[(t, hz)] for hz in E.HORIZONS})
        fig = go.Figure()
        for col, c in zip(df.columns, ['#805ad5', '#3182ce', '#1a202c']):
            fig.add_trace(go.Scatter(x=df.index, y=df[col], name=col, line=dict(color=c, width=3 if col == 'Next 2 months' else 1.6)))
        fig.add_hrect(y0=-E.THRESH, y1=E.THRESH, fillcolor=AMBER, opacity=0.12, line_width=0, annotation_text='Neutral zone', annotation_position='top left')
        fig.update_layout(height=360, yaxis=dict(range=[-1, 1], tickvals=[-0.8, 0, 0.8], ticktext=['Bearish', 'Neutral', 'Bullish']), margin=dict(l=0, r=0, t=10, b=0))
        st.plotly_chart(fig, width='stretch')
        c = st.columns(3)
        for col, hz in zip(c, E.HORIZONS):
            w = F[(t, hz)].map(view).value_counts(normalize=True)
            col.markdown(f"**{HZ[hz]}** — ▲ {w.get('Bullish', 0):.0%} of days · ◆ {w.get('Neutral', 0):.0%} · ▼ {w.get('Bearish', 0):.0%}")

# ================================================================= SCORECARD
elif page == 'Scorecard':
    st.title('Scorecard — were the calls right?')
    st.info('This runs by itself. Every trading morning at 08:00 IST the Nifty view and any actionable calls are logged before the market opens; '
            'every evening at 20:00 IST they are checked against actual prices. Nothing to press. Logged calls are never edited afterwards.', icon='⚙️')
    df = TR.load()
    incl = st.toggle('Include reconstructed history (paper record Apr–Oct 2026) for context', value=not (df['mode'] == 'live').any())
    modes = ('live', 'paper') if incl else ('live',)
    S = TR.stats(df, modes)
    pending = int(((df.status == 'pending') & df['mode'].isin(modes)).sum())
    k = st.columns(4)
    k[0].metric('Calls checked', f"{S.get('n', 0):,}", help='Calls whose outcome is known (neutral views are not counted).')
    k[1].metric('Right', f"{S['hit']:.0%}" if S.get('n') else '—', help='Coin-flip = 50%.')
    if S.get('n'):
        nv = sum(b['naive'] * b['n'] for b in S['by_horizon'].values()) / sum(b['n'] for b in S['by_horizon'].values())
        k[2].metric('Simple benchmark', f'{nv:.0%}', help='How often you would be right by always predicting whichever direction actually happened more often in those same windows.')
    k[3].metric('Awaiting outcome', f'{pending}')
    if S.get('n'):
        verdict = S['hit'] - nv
        if incl: st.caption('Figures include the reconstructed paper record; switch the toggle off to see live calls only.')
        if S['n'] < 60: st.caption('Fewer than 60 calls checked — too early to judge.')
        elif verdict > 0.03: st.success(f"Calls are beating the benchmark by {verdict:.0%} so far.")
        elif verdict < -0.03: st.error(f"Calls are trailing the benchmark by {-verdict:.0%} so far.")
        else: st.warning('Calls are performing roughly in line with the benchmark — no edge yet.')
        g = TR.running(df, modes)
        fig = go.Figure(go.Scatter(x=g.date, y=g.cumulative, line=dict(color='#1a365d', width=3), name='Cumulative % right'))
        fig.add_hline(y=0.5, line_dash='dot', annotation_text='coin-flip'); fig.add_hline(y=nv, line_dash='dash', line_color=AMBER, annotation_text='benchmark')
        fig.update_layout(height=300, yaxis_tickformat='.0%', yaxis_range=[0.2, 0.8], margin=dict(l=0, r=0, t=10, b=0))
        st.plotly_chart(fig, width='stretch')
        bh = pd.DataFrame([dict(Horizon=HZ[h], Checked=b['n'], Right=f"{b['hit']:.0%}", Benchmark=f"{b['naive']:.0%}") for h, b in S['by_horizon'].items()])
        st.dataframe(bh, hide_index=True, width='stretch')
    st.markdown('#### Recent calls')
    sub = df[df['mode'].isin(modes + ('late',))].sort_values(['date', 'horizon'], ascending=[False, True]).head(300).copy()
    if sub.empty:
        st.caption('The first live calls appear after the next 08:00 IST run.')
    else:
        def res(r):
            if r['mode'] == 'late': return '⚪ logged late — not counted'
            if r['status'] == 'pending': return f"⏳ result on {(r['date'] + pd.tseries.offsets.BDay(TR.HZ_SESSIONS[r['horizon']] - 1)):%d %b}"
            if r['status'] != 'scored': return '— market closed'
            return ('✅ right' if r['correct'] == 1 else '❌ wrong') + f" (actual {r['actual_ret'] * 100:+.2f}%)"
        sub['Result'] = sub.apply(res, axis=1)
        sub['Call'] = sub.apply(lambda r: f"{ARROW.get(r['view'], '')} {r['view']}", axis=1)
        out = sub[['date', 'name', 'horizon', 'Call', 'tier', 'Result']].rename(columns={'date': 'Date', 'name': 'Sector / commodity', 'horizon': 'Horizon', 'tier': 'Edge'})
        out['Horizon'] = out['Horizon'].map(HZ); out['Edge'] = out['Edge'].map(lambda x: EDGE.get(x, (x,))[0] if isinstance(x, str) else '—')
        out['Date'] = out['Date'].dt.strftime('%d %b %Y')
        st.dataframe(out.style.map(board_style, subset=['Call']), hide_index=True, width='stretch', height=520)
        st.download_button('Download full log (CSV)', TR.LOG.read_bytes(), 'astro_predictions.csv')
    with st.expander('Manual controls — only needed if you run the app on your own computer'):
        c1, c2 = st.columns(2)
        dd = c1.date_input('Log calls for', next_session(date.today()))
        if c1.button('Log calls now'):
            st.success(f'{TR.log_predictions(eng, dd, mode="live")} calls logged.')
        if c2.button('Check outcomes now'):
            with st.spinner('Fetching prices…'): st.success(f'{TR.settle()} calls checked.')

# ================================================================= ABOUT & SETTINGS
else:
    st.title('About & settings')
    st.markdown('''
**What this does, in five steps**
1. Works out where every planet is (sign, nakshatra, retrograde, aspects) for each trading day and for the market's opening moment.
2. Applies the rule set: each rule says which sectors or commodities are helped or hurt by a given planetary condition.
3. Adds the rules up into a score for each sector / commodity on three horizons — *Today*, *Next week*, *Next 2 months* — and labels it **Bullish**, **Neutral** or **Bearish**.
4. Checks every kind of call against 14 years of real prices and tells you whether it has a proven **edge**.
5. Logs the worthwhile calls each morning and checks them each evening, so you build an honest track record.

**Reading the labels**
- ▲ **Bullish** / ◆ **Neutral** / ▼ **Bearish** — direction. *Mild / Moderate / Strong* — how many rules agree.
- **Edge** — *Strong edge* or *Tradeable* = that kind of call beat both a coin-flip and the simple benchmark on enough independent past occurrences. *No proven edge* = it hasn't. *Too little history* = not enough data to say.
- **Next 2 months** views are averaged over the coming 40 sessions, so they change only on slow-planet events (Jupiter/Saturn/Rahu sign changes, stations, major aspects). The *Today* board shows when each one started and when it is next expected to change.
''')
    cal = C.cal()
    if cal:
        st.markdown('**What 14 years of history say (Feb 2012 – Oct 2026, NSE indices)**')
        rows = []
        for hz in E.HORIZONS:
            o = cal['overall'][f'{hz}|direct']
            rows.append(dict(Horizon=HZ[hz], Calls=f"{o['n']:,}", Right=f"{o['hit']:.1%}", Benchmark=f"{max(o['base_up'], 1 - o['base_up']):.1%}"))
        st.dataframe(pd.DataFrame(rows), hide_index=True, width='stretch')
        st.caption('Overall the calls are close to a coin-flip, which is why only the handful of call types with a historical edge are flagged as actionable. '
                   'Treat everything here as one input alongside your own analysis, never as a stand-alone signal.')
    with st.expander('Advanced settings'):
        ex = st.selectbox('Market location (for the opening-bell chart and planetary hours)', list(ac.EXCHANGES), index=list(ac.EXCHANGES).index(ss['exch']))
        thr = st.slider('Neutral zone width (scores between −x and +x are Neutral)', 0.05, 0.40, float(ss['thr']), 0.01)
        mu = st.text_area('Diwali Muhurat-session results (date, points) — sets the annual bias', '\n'.join(f'{a}, {b:g}' for a, b in ss['mu']))
        if st.button('Apply'):
            parsed = []
            for ln in mu.strip().splitlines():
                try: a, b = ln.split(','); parsed.append([date.fromisoformat(a.strip()).isoformat(), float(b)])
                except Exception: pass
            ss['exch'], ss['thr'], ss['mu'] = ex, thr, parsed; st.cache_data.clear(); st.rerun()
        st.caption('To make a Muhurat entry permanent for the automatic daily runs, add it to data/muhurat.json in the GitHub repo.')
    with st.expander('Downloads'):
        wb = HERE / 'AstroMarket_Workbook.xlsx'
        if wb.exists(): st.download_button('12-month Excel workbook', wb.read_bytes(), 'AstroMarket_Workbook.xlsx')
        p = HERE / 'data' / 'rule_level_hitrates.csv'
        if p.exists(): st.download_button('Every rule with its historical hit-rate (CSV)', p.read_bytes(), 'rule_hitrates.csv')
    with st.expander('Technical detail: data checks'):
        vr = HERE / 'data' / 'validation_report.json'
        if vr.exists():
            v = json.loads(vr.read_text()); m = v['chosen']
            st.write(f"Planetary positions verified against {m['hard_total']} dated facts; all {m['hard_pass']} reproduced.")
            st.dataframe(pd.DataFrame(v['tests'])[['test', 'book', 'engine', 'pass_']].rename(columns={'test': 'Check', 'book': 'Expected', 'engine': 'Computed', 'pass_': 'OK'}), hide_index=True, width='stretch')
        st.caption('Prices: NSE index end-of-day data (daily), EIA crude oil and natural gas.')
