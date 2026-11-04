"""AstroMarket — Book 1 (Stock Market Astrology) + Book 2 (Investment Muhurtas). Phone-first, plain-language.
Two screens: Today, and the 12-month outlook. The 12-month outlook is pre-computed each evening (data/outlook.csv)."""
from __future__ import annotations
import json
from datetime import date, datetime, timedelta
from pathlib import Path
import pandas as pd
import streamlit as st

import astro_core as ac
import engine as E
import tracker as TR
import insights as I

HERE = Path(__file__).parent
st.set_page_config(page_title='AstroMarket', page_icon='🪐', layout='centered', initial_sidebar_state='collapsed')
st.markdown("""<style>
.block-container{padding:3.2rem 0.8rem 3rem 0.8rem;max-width:760px}
h1{font-size:1.5rem!important} h3{font-size:1.1rem!important}
.card{border-radius:12px;padding:10px 12px;margin:8px 0;background:#f7fafc;border-left:5px solid #a0aec0}
.card.up{border-color:#1f9d55;background:#f0fff4}.card.down{border-color:#c53030;background:#fff5f5}
.card.neutral{border-color:#d69e2e;background:#fffff0}.card.warn{border-color:#dd6b20;background:#fffaf0}.card.info{border-color:#3182ce;background:#ebf8ff}
.card b{font-size:15px}.card div{font-size:14px;color:#2d3748;margin-top:2px;line-height:1.35}
.row{display:flex;align-items:center;justify-content:space-between;padding:7px 4px;border-bottom:1px solid #edf2f7;font-size:14px}
.row .n{flex:1;min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;padding-right:6px}
.chip{display:inline-block;min-width:22px;text-align:center;border-radius:6px;padding:1px 5px;font-size:12px;font-weight:700;margin-left:3px;color:#fff}
.lg{font-size:11px;color:#718096}
.m{display:inline-block;width:20px;height:20px;border-radius:4px;margin:1px;font-size:9px;line-height:20px;text-align:center;color:#fff}
@media (prefers-color-scheme: dark){.card{background:#1a202c}.card div{color:#e2e8f0}.card.up{background:#1c2b22}.card.down{background:#2d1c1c}
 .card.neutral{background:#2b2a1c}.card.warn{background:#2d241c}.card.info{background:#1c2533}.row{border-color:#2d3748}}
</style>""", unsafe_allow_html=True)

COL = {1: '#1f9d55', -1: '#c53030', 0: '#d69e2e', None: '#a0aec0'}
SYM = {1: '▲', -1: '▼', 0: '◆', None: '·'}
WORD = {1: 'Up', -1: 'Down', 0: 'Neutral', None: 'No rule'}


def chip(d, label=None): return f"<span class='chip' style='background:{COL[d]}'>{label or SYM[d]}</span>"
def card(x): return f"<div class='card {x['tone']}'><b>{x['icon']} {x['title']}</b><div>{x['text']}</div></div>"


@st.cache_resource(show_spinner=False)
def get_engine():
    mu = json.loads((HERE / 'data' / 'muhurat.json').read_text()) if (HERE / 'data' / 'muhurat.json').exists() else []
    return E.Engine(muhurat=[(date.fromisoformat(a), float(b)) for a, b in mu])


@st.cache_data(show_spinner=False, max_entries=3, ttl=6 * 3600)
def day(d: date):
    r = get_engine().day(d); get_engine()._cache.clear(); return r


@st.cache_data(show_spinner=False, ttl=3600)
def outlook():
    p = HERE / 'data' / 'outlook.csv'
    return pd.read_csv(p, parse_dates=['date']) if p.exists() else None


def next_session(d):
    while d.weekday() >= 5: d += timedelta(days=1)
    return d


page = st.segmented_control('Screen', ['📅 Today', '🗓️ 12 months'], default='📅 Today', label_visibility='collapsed') or '📅 Today'

# ================================================================= TODAY
if page == '📅 Today':
    d = st.date_input('Date', next_session(date.today()), format='DD/MM/YYYY', label_visibility='collapsed')
    st.markdown(f"# {d:%A, %d %b %Y}")
    r = day(d)
    for x in I.daily(r, TR.TRACKABLE):
        st.markdown(card(x), unsafe_allow_html=True)
    for x in I.ahead(outlook(), d, 30)[:1]:
        st.markdown(card(x), unsafe_allow_html=True)

    st.markdown('### All markets')
    st.markdown(f"<div class='lg'>Today · then short-term (S) and long-term (L). {chip(1)} up {chip(-1)} down {chip(0)} neutral/books split</div>", unsafe_allow_html=True)
    order = sorted(E.TARGETS, key=lambda t: (t != 'NIFTY', -(r.final[(t, 'intraday')] or 0), I.nm(t)))
    rows = ''.join(f"<div class='row'><span class='n'>{'⚖️ ' if r.disagree[(t, 'intraday')] else ''}{I.nm(t)}</span>"
                   f"{chip(r.final[(t, 'intraday')])}{chip(r.final[(t, 'short')], 'S')}{chip(r.final[(t, 'long')], 'L')}</div>" for t in order)
    st.markdown(rows, unsafe_allow_html=True)

    with st.expander('Details — book by book'):
        st.caption('B1 = Stock Market Astrology · B2 = Investment Muhurtas')
        rows = ''.join(f"<div class='row'><span class='n'>{I.nm(t)}</span>{chip(r.book[(t, 'intraday')][1], 'B1')}{chip(r.book[(t, 'intraday')][2], 'B2')}</div>"
                       for t in order)
        st.markdown(rows, unsafe_allow_html=True)
    with st.expander('Why? — the rules behind a call'):
        t = st.selectbox('Market', E.TARGETS, format_func=I.nm)
        for hz, lab in (('intraday', 'Today'), ('short', 'Short term'), ('long', 'Long term')):
            st.markdown(f"**{lab}: {WORD[r.final[(t, hz)]]}**")
            for v in r.votes(t, hz):
                st.markdown(f"- {SYM[v['dir']]} B{v['book']} · {v['text']}")
    with st.expander('Track record'):
        df = TR.load(); s = df[(df.status == 'scored') & (df.horizon == 'intraday')]
        if s.empty: st.caption('No scored calls yet.')
        else:
            out = []
            for dd, g in s.groupby('date'):
                rec = {'Date': dd.strftime('%d %b')}
                for col, n in (('book1', 'B1'), ('book2', 'B2')):
                    y = g[g[col].isin(['Up', 'Down'])]
                    rec[n] = f"{((y[col] == 'Up') == (y.actual_ret > 0)).sum()}/{len(y)}" if len(y) else '—'
                rec['On time'] = '✓' if (g['mode'] == 'live').all() else 'late'
                out.append(rec)
            st.dataframe(pd.DataFrame(out[::-1][:30]), hide_index=True, width='stretch')
    with st.expander('⚙️ Alerts'):
        if st.button('📨 Send Telegram test ping', width='stretch'):
            import alerts as A
            if not A._token(): st.error('Add TELEGRAM_BOT_TOKEN in Streamlit → app → Settings → Secrets, as:  TELEGRAM_BOT_TOKEN = "…"')
            elif not A.chat_id(): st.error('Send /start to your bot in Telegram, then press again.')
            elif A.send(f"✅ <b>AstroMarket test ping</b>\nSent from the app at {datetime.now(ac.IST):%d %b %Y %H:%M} IST."): st.success('Sent — check Telegram.')
            else: st.error('Telegram refused it — is the token current?')

# ================================================================= 12 MONTHS
else:
    st.markdown('# Next 12 months')
    F = outlook()
    if F is None:
        st.info('The outlook is prepared each evening; it will appear after the next run.'); st.stop()
    for x in I.ahead(F, date.today(), 60):
        st.markdown(card(x), unsafe_allow_html=True)

    t = st.selectbox('Market', E.TARGETS, index=E.TARGETS.index('GOLD'), format_func=I.nm)
    st.markdown(f"<div class='card info'><b>{I.nm(t)}</b><div>{I.outlook_summary(F, t)}</div></div>", unsafe_allow_html=True)
    g = F[F.target == t].copy(); g['m'] = g.date.dt.to_period('M')
    months = list(g.m.unique())
    net = lambda s: 1 if (s == 1).mean() - (s == -1).mean() > 0.2 else -1 if (s == -1).mean() - (s == 1).mean() > 0.2 else (0 if s.notna().any() else None)
    for hz, lab in (('short', 'Short term'), ('long', 'Long term')):
        cells = ''.join(f"<span class='m' title='{m.strftime('%b %Y')}' style='background:{COL[net(g[g.m == m][hz])]}'>{m.strftime('%b')[:1]}</span>" for m in months)
        st.markdown(f"<div style='margin:4px 0'><span class='lg'>{lab}</span><br>{cells}</div>", unsafe_allow_html=True)
    st.markdown(f"<div class='lg'>{' '.join(m.strftime('%b') for m in months[:1])} → {months[-1].strftime('%b %Y')} · one box per month</div>", unsafe_allow_html=True)
    with st.expander('Day by day'):
        hz = st.radio('Horizon', ['short', 'long'], format_func=lambda x: 'Short term' if x == 'short' else 'Long term', horizontal=True)
        s = g.set_index('date')[hz]
        html = ''
        for m, gg in s.groupby(s.index.to_period('M')):
            html += f"<div><span class='lg' style='display:inline-block;width:46px'>{m.strftime('%b %y')}</span>" + ''.join(
                f"<span class='m' style='width:16px;height:16px;line-height:16px;font-size:8px;background:{COL[None if pd.isna(v) else int(v)]}'>{ix.day}</span>" for ix, v in gg.items()) + '</div>'
        st.markdown(html, unsafe_allow_html=True)

    st.markdown('### All markets at a glance')
    hz2 = st.radio('View', ['long', 'short'], format_func=lambda x: 'Long term' if x == 'long' else 'Short term', horizontal=True, key='hz2')
    F['m'] = F.date.dt.to_period('M'); months = sorted(F.m.unique())
    P = F.groupby(['target', 'm'])[hz2].apply(net).unstack()
    head = ''.join(f"<span class='m' style='background:none;color:#718096'>{m.strftime('%b')[:1]}</span>" for m in months)
    rows = f"<div class='row'><span class='n'></span><span>{head}</span></div>"
    for t in E.TARGETS:
        if t not in P.index: continue
        rows += f"<div class='row'><span class='n'>{I.nm(t)}</span><span>" + ''.join(f"<span class='m' style='background:{COL[None if pd.isna(v) else int(v)]}'></span>" for v in P.loc[t]) + '</span></div>'
    st.markdown(f"<div style='overflow-x:auto'>{rows}</div>", unsafe_allow_html=True)
    st.caption(f"Months {months[0].strftime('%b %Y')} – {months[-1].strftime('%b %Y')}. Green = mostly up, red = mostly down, amber = mixed.")
