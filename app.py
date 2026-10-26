"""
AstroMarket Terminal — live platform implementing Banerjee, 'Stock Market Astrology' (2009).
Run:  streamlit run app.py
"""
from __future__ import annotations
import json, math
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
import data_sources as DS

HERE = Path(__file__).parent
st.set_page_config(page_title='AstroMarket Terminal', page_icon='🪐', layout='wide')
RB = E.RB
COLORS = {'G': '#1f9d55', 'A': '#d69e2e', 'R': '#c53030'}
BG = {'G': '#c6f6d5', 'A': '#fefcbf', 'R': '#fed7d7'}

# ------------------------------------------------------------------ sidebar / settings
st.sidebar.title('🪐 AstroMarket Terminal')
st.sidebar.caption('Rule engine: Banerjee, *Stock Market Astrology* (2009) · Sidereal Lahiri · Swiss Ephemeris')
page = st.sidebar.radio('View', ['Daily plan', 'Month grid', '12-month outlook', 'Future date / month projection',
                                 'Prediction tracker', 'Backtest & confidence', 'Rulebook', 'Source validation', 'Settings & help'])
with st.sidebar.expander('Engine settings', expanded=False):
    exch = st.selectbox('Market location (opening-bell chart & horā)', list(ac.EXCHANGES), index=0)
    ex = ac.EXCHANGES[exch]
    ot = st.time_input('Opening bell', ex['open']); ctm = st.time_input('Close', ex['close'])
    th = st.slider('Green/Red threshold', 0.05, 0.5, E.THRESH, 0.01)
    E.THRESH = th
    mix_i = st.slider('Daily composite: intraday weight', 0.0, 1.0, 0.5, 0.05)
    mix_s = st.slider('short-term weight', 0.0, 1.0, 0.3, 0.05)
    mix_l = round(max(0.0, 1 - mix_i - mix_s), 2); st.caption(f'long-term weight = {mix_l}')
    st.markdown('**Rule-family weights** (book default = equal)')
    W = {}
    for k, v in E.DEFAULT_W.items():
        W[k] = st.slider(k.upper(), 0.0, 2.0, float(v), 0.1, key='w_' + k)
    mu_txt = st.text_area('Dīpāvali Muhurat results (YYYY-MM-DD, points) one per line',
                          '2023-11-12, 354\n2024-11-01, 335\n2025-10-21, 63', help='Enter Sensex/Nifty Muhurat-session change; Ch.19 uses the sign for the next Samvat year. Edit / extend each Diwali.')
MIX = (mix_i, mix_s, mix_l)
def parse_mu(t):
    out = []
    for ln in t.strip().splitlines():
        try:
            a, b = ln.split(','); out.append((date.fromisoformat(a.strip()), float(b)))
        except Exception: pass
    return out

@st.cache_resource(show_spinner=False)
def get_engine(exch, ot, ctm, wkey, mukey):
    return E.Engine(exch, ot, ctm, weights=dict(wkey), muhurat=list(mukey))
eng = get_engine(exch, ot, ctm, tuple(sorted(W.items())), tuple(parse_mu(mu_txt)))

@st.cache_data(show_spinner=False, max_entries=4000)
def day_cached(d: date, _k):
    return eng.day(d)
KEY = (exch, ot, ctm, tuple(sorted(W.items())), tuple(parse_mu(mu_txt)))
def day(d): return day_cached(d, KEY)

def next_trading(d):
    while d.weekday() >= 5: d += timedelta(days=1)
    return d

def chip(score, conf=None):
    c = E.rag(score)
    lab = {'G': '▲ UP', 'R': '▼ DOWN', 'A': '◆ NEUTRAL'}[c]
    cf = f" · conf {conf['p']:.0%}" if conf else ''
    return f"<span style='background:{BG[c]};color:{COLORS[c]};padding:2px 8px;border-radius:10px;font-weight:600'>{lab} {score:+.2f}{cf}</span>"

def conf_txt(cf):
    if not cf: return '—'
    nv = f", naive {cf['naive']:.0%}" if cf.get('naive') else ''
    return f"{cf['p']:.0%} (hist {cf['raw']:.0%}, n={cf['n']:,}{nv})"

def grid_html(days, targets, hz='composite', show_vals=False):
    head = ''.join(f"<th style='font-size:10px;padding:1px 2px;{'color:#999' if d.weekday() >= 5 else ''}'>{d.day}<br>{'MTWTFSS'[d.weekday()]}</th>" for d in days)
    rows = []
    res = {d: day(d) for d in days}
    for t in targets:
        cells = []
        for d in days:
            r = res[d]
            v = r.composite(t, MIX) if hz == 'composite' else r.scores[t][hz]
            c = E.rag(v)
            op = '0.45' if d.weekday() >= 5 else '1'
            txt = f'{v:+.1f}' if show_vals else ''
            cells.append(f"<td title='{E.TARGET_NAME[t]} {d:%d-%b}: {v:+.2f}' style='background:{COLORS[c]};opacity:{op};width:18px;height:16px;font-size:9px;color:white;text-align:center'>{txt}</td>")
        rows.append(f"<tr><td style='font-size:11px;white-space:nowrap;padding-right:6px'>{E.TARGET_NAME[t]}</td>{''.join(cells)}</tr>")
    return f"<div style='overflow-x:auto'><table style='border-collapse:separate;border-spacing:1px'><tr><th></th>{head}</tr>{''.join(rows)}</table></div>"

TGT_ALL = ['NIFTY'] + E.SECTORS + E.COMMODITIES

st.sidebar.warning('Research tool. Backtest 2012–2026: intraday hit-rate ≈ 50.5 %, short ≈ 50 %, long-term below naive buy-and-hold. '
                   'Confidence % shown is the empirical hit-rate of comparable past calls.', icon='⚠️')

# ================================================================== DAILY PLAN
if page == 'Daily plan':
    d = st.date_input('Trading date', next_trading(date.today()))
    r = day(d)
    cm = r.chart_mid
    st.title(f'Daily plan — {d:%A, %d %b %Y}')
    c1, c2, c3, c4 = st.columns(4)
    for col, hz in zip((c1, c2, c3), E.HORIZONS):
        s = r.scores['NIFTY'][hz]; cf = C.confidence('NIFTY', hz, s)
        col.markdown(f"**Nifty 50 · {E.HZ_LABEL[hz]}**<br>{chip(s, cf)}", unsafe_allow_html=True)
    reg = r.regime
    c4.markdown(f"**Business cycle (Ch.16)**<br><b>{reg['phase']}</b> · {reg['state']}", unsafe_allow_html=True)
    st.caption(f"Candra {ac.fmt_deg(cm['Mo'].lon)} · {ac.NAK[cm.moon_nak]} (lord {ac.NAMES[ac.DASHA_ORDER[cm.moon_nak % 9]]}) · tithi {cm.tithi} "
               f"({'waxing' if cm.waxing else 'waning'}) · Opening lagna {ac.fmt_deg(r.chart_open.asc)} at {r.open_dt:%H:%M} {exch}")
    for f in r.flags: st.info(f)

    plan = E.action_plan(r, C.confidence)
    st.subheader('Suggested actions (per book rules)')
    a1, a2, a3 = st.columns(3)
    def show(col, title, xs, hz):
        col.markdown(f'**{title}**')
        if not xs: col.caption('No signal beyond threshold.')
        for x in xs:
            em = C.expected_move(x['target'], hz, x['score'])
            mv = f" · hist. avg {em['mean']*100:+.2f}% ({em['up']:.0%} up, n={em['n']})" if em else ''
            col.markdown(f"- {x['name']} {chip(x['score'], x['conf'])}<span style='font-size:11px;color:#666'>{mv}</span>", unsafe_allow_html=True)
    show(a1, '📈 Intraday long', plan['intraday_long'], 'intraday'); show(a1, '📉 Intraday short / avoid', plan['intraday_short'], 'intraday')
    show(a2, '📈 Swing long (days–weeks)', plan['swing_long'], 'short'); show(a2, '📉 Swing short / reduce', plan['swing_short'], 'short')
    show(a3, '🏦 Positional overweight (months)', plan['position_long'], 'long'); show(a3, '⚠️ Positional underweight', plan['position_avoid'], 'long')
    with st.expander('Book guidance & regime notes', expanded=True):
        for n in plan['notes']: st.markdown('- ' + n)

    st.subheader('Intraday timing — horā (Ch.10) and micro-daśā (Ch.12)')
    tl = [dict(Task='Horā', Start=h['start'], Finish=h['end'], Lord=ac.NAMES[h['lord']], Signal=h['signal'], Detail=h['text'][:90]) for h in r.hora]
    tl += [dict(Task='Daśā', Start=x['start'], Finish=x['end'], Lord=ac.NAMES[x['lord']], Signal=x['signal'], Detail=', '.join(E.TARGET_NAME.get(t, t) for t in x['targets'][:6])) for x in r.dasha]
    if tl:
        df = pd.DataFrame(tl)
        df['Signal2'] = df.Signal.map(lambda s: 'positive' if ('BUY' in s or 'positive' in s) else 'negative' if ('SELL' in s or 'negative' in s) else 'neutral')
        fig = px.timeline(df, x_start='Start', x_end='Finish', y='Task', color='Signal2', text='Lord', hover_data=['Detail'],
                          color_discrete_map={'positive': COLORS['G'], 'negative': COLORS['R'], 'neutral': COLORS['A']})
        fig.update_layout(height=220, margin=dict(l=0, r=0, t=10, b=0), legend_title_text='')
        st.plotly_chart(fig, width='stretch')
    for w in plan['hora_windows']: st.markdown('- ' + w)

    st.subheader('All sectors & commodities')
    rows = []
    for t in TGT_ALL:
        row = dict(Target=E.TARGET_NAME[t])
        for hz in E.HORIZONS:
            s = r.scores[t][hz]; row[hz] = round(s, 2); cf = C.confidence(t, hz, s)
            row[f'{hz} conf'] = f"{cf['p']:.0%}" if cf else ''
        row['Composite'] = round(r.composite(t, MIX), 2); row['Call'] = E.rag(row['Composite'])
        rows.append(row)
    tab = pd.DataFrame(rows)
    def colr(v):
        if isinstance(v, (int, float)): return f'background-color:{BG[E.rag(v)]}'
        return ''
    st.dataframe(tab.style.map(colr, subset=['intraday', 'short', 'long', 'Composite']).format({c: '{:+.2f}' for c in ['intraday', 'short', 'long', 'Composite']}), width='stretch', height=560)
    with st.expander('🔎 Why? — rule-by-rule drivers'):
        t = st.selectbox('Target', TGT_ALL[1:], format_func=lambda x: E.TARGET_NAME[x])
        cs = r.contrib.get(t, [])
        st.dataframe(pd.DataFrame([dict(Chapter=c.family, Horizon=c.horizon, Contribution=round(c.value, 3), Reason=c.text) for c in cs]),
                     width='stretch')
    with st.expander('Planetary positions & aspects received'):
        A = ac.aspect_matrix(cm)
        pos = []
        for g in ac.GRAHAS:
            b = cm[g]; dn, _ = ac.dignity(g, b.sign)
            pos.append(dict(Graha=ac.NAMES[g], Position=ac.fmt_deg(b.lon), Nakshatra=f'{ac.NAK[b.nak]} p{b.pada}', Retro='R' if b.retro else '',
                            Dignity=dn, Combust='asta' if ac.combust(cm, g) else '',
                            Aspected_by=', '.join(f"{ac.NAMES[a]}({h})" for a, (h, s) in A[g].items())))
        st.dataframe(pd.DataFrame(pos), width='stretch')
    if st.button('📝 Log these predictions to the tracker (immutable)'):
        n = TR.log_predictions(eng, d, C.conf_fn); st.success(f'Logged {n} new prediction rows for {d}.')

# ================================================================== MONTH GRID
elif page == 'Month grid':
    st.title('Month grid — day-by-day calls')
    c1, c2, c3 = st.columns(3)
    m0 = c1.date_input('Month', date.today().replace(day=1))
    hz = c2.selectbox('Horizon', ['composite'] + E.HORIZONS, format_func=lambda x: 'Daily composite' if x == 'composite' else E.HZ_LABEL[x])
    vals = c3.checkbox('Show scores in boxes', False)
    start = m0.replace(day=1); end = (start + timedelta(days=32)).replace(day=1) - timedelta(days=1)
    days = [start + timedelta(days=i) for i in range((end - start).days + 1)]
    st.markdown("<span style='color:#1f9d55'>■</span> Up &nbsp; <span style='color:#d69e2e'>■</span> Neutral &nbsp; <span style='color:#c53030'>■</span> Down &nbsp; (faded = weekend; hover for score)", unsafe_allow_html=True)
    st.markdown('**Market & sectors**'); st.markdown(grid_html(days, ['NIFTY'] + E.SECTORS, hz, vals), unsafe_allow_html=True)
    st.markdown('**Commodities**'); st.markdown(grid_html(days, E.COMMODITIES, hz, vals), unsafe_allow_html=True)
    st.subheader('Key transits this month')
    ev = []
    for g in ['Su', 'Ma', 'Me', 'Ju', 'Ve', 'Sa', 'Ra']:
        for t, a, b in ac.find_ingresses(g, start - timedelta(days=1), end):
            if start <= t.date() <= end: ev.append(dict(Date=t.date(), Event=f'{ac.NAMES[g]} enters {ac.RASI[b]}'))
    for k, t in ac.eclipses_in_year(start.year):
        dd = ac.from_jd(t).date()
        if start <= dd <= end: ev.append(dict(Date=dd, Event=f'{k.title()} eclipse'))
    prev = None
    for dd in days:
        c = ac.chart(datetime(dd.year, dd.month, dd.day, 6, tzinfo=ac.timezone.utc))
        rs = {g: c[g].retro for g in ['Me', 'Ve', 'Ma', 'Ju', 'Sa']}
        if prev:
            for g in rs:
                if rs[g] != prev[g]: ev.append(dict(Date=dd, Event=f"{ac.NAMES[g]} turns {'retrograde' if rs[g] else 'direct'}"))
        prev = rs
    st.dataframe(pd.DataFrame(sorted(ev, key=lambda x: x['Date'])), width='stretch')

# ================================================================== 12-MONTH OUTLOOK
elif page == '12-month outlook':
    st.title('12-month outlook — sectors & commodities')
    s0 = st.date_input('Start month', date.today().replace(day=1)).replace(day=1)
    hz = st.selectbox('Horizon for monthly heat-map', ['long', 'short', 'composite'], format_func=lambda x: 'Daily composite' if x == 'composite' else E.HZ_LABEL[x])
    months = [(s0.replace(day=1) + timedelta(days=32 * i)).replace(day=1) for i in range(12)]
    with st.spinner('Computing 365 days …'):
        data = []
        for m in months:
            e = (m + timedelta(days=32)).replace(day=1) - timedelta(days=1)
            ds_ = [m + timedelta(days=i) for i in range((e - m).days + 1) if (m + timedelta(days=i)).weekday() < 5]
            for t in TGT_ALL:
                vs = [day(x).composite(t, MIX) if hz == 'composite' else day(x).scores[t][hz] for x in ds_]
                data.append(dict(target=E.TARGET_NAME[t], month=m.strftime('%b-%y'), avg=sum(vs) / len(vs),
                                 green=sum(v > E.THRESH for v in vs) / len(vs), red=sum(v < -E.THRESH for v in vs) / len(vs)))
    D = pd.DataFrame(data)
    P = D.pivot(index='target', columns='month', values='avg')[[m.strftime('%b-%y') for m in months]].reindex([E.TARGET_NAME[t] for t in TGT_ALL])
    fig = px.imshow(P, color_continuous_scale=[[0, COLORS['R']], [0.42, COLORS['A']], [0.58, COLORS['A']], [1, COLORS['G']]],
                    zmin=-0.8, zmax=0.8, aspect='auto', text_auto='.2f')
    fig.update_layout(height=1100, margin=dict(l=0, r=0, t=20, b=0))
    st.plotly_chart(fig, width='stretch')
    st.caption('Cell = average score of trading days in the month. Long-term horizon is driven by Guru/Śani/Rāhu/Ketu/outer transits, the business-cycle regime, gold and crude cycles.')
    st.subheader('Day-by-day boxes per month (granular view where transits change mid-month)')
    for m in months:
        with st.expander(m.strftime('%B %Y')):
            e = (m + timedelta(days=32)).replace(day=1) - timedelta(days=1)
            st.markdown(grid_html([m + timedelta(days=i) for i in range((e - m).days + 1)], TGT_ALL, 'composite' if hz == 'composite' else hz), unsafe_allow_html=True)
    st.subheader('Regime path (Ch.16) and cycle signals')
    rp = []
    for m in months:
        r = day(m + timedelta(days=14)); rg = r.regime
        rp.append(dict(Month=m.strftime('%b-%y'), Phase=rg['phase'], State=rg['state'], Detail=rg['detail'],
                       Gold=round(r.scores['GOLD']['long'], 2), Crude=round(r.scores['CRUDE']['long'], 2)))
    st.dataframe(pd.DataFrame(rp), width='stretch')

# ================================================================== PROJECTION
elif page == 'Future date / month projection':
    st.title('Projection for a future date or month')
    mode = st.radio('Select', ['Date', 'Month'], horizontal=True)
    tgt = st.selectbox('Target', TGT_ALL, format_func=lambda x: E.TARGET_NAME[x])
    if mode == 'Date':
        d = st.date_input('Date', next_trading(date.today() + timedelta(days=30)))
        r = day(d)
        rows = []
        for hz in E.HORIZONS:
            s = r.scores[tgt][hz]; cf = C.confidence(tgt, hz, s); em = C.expected_move(tgt, hz, s)
            rows.append(dict(Horizon=E.HZ_LABEL[hz], Score=round(s, 2), Call=E.rag(s), Confidence=conf_txt(cf),
                             **({'Hist. mean move': f"{em['mean']*100:+.2f}%", 'IQR': f"{em['p25']*100:+.2f}% … {em['p75']*100:+.2f}%",
                                 '% up': f"{em['up']:.0%}", 'Unconditional mean': f"{em['all_mean']*100:+.2f}%", 'n': em['n']} if em else {})))
        st.dataframe(pd.DataFrame(rows), width='stretch')
        st.caption('"Hist. mean move" = average realised return on past days that had a call of the same direction and strength bucket — compare with the unconditional mean to judge whether the signal adds anything.')
        st.dataframe(pd.DataFrame([dict(Chapter=c.family, Horizon=c.horizon, Contribution=round(c.value, 3), Reason=c.text) for c in r.contrib.get(tgt, [])]), width='stretch')
    else:
        m = st.date_input('Month', (date.today().replace(day=1) + timedelta(days=32)).replace(day=1)).replace(day=1)
        e = (m + timedelta(days=32)).replace(day=1) - timedelta(days=1)
        ds_ = [m + timedelta(days=i) for i in range((e - m).days + 1) if (m + timedelta(days=i)).weekday() < 5]
        df = pd.DataFrame([dict(date=x, **{hz: day(x).scores[tgt][hz] for hz in E.HORIZONS}, composite=day(x).composite(tgt, MIX)) for x in ds_])
        fig = go.Figure()
        for hz, col in zip(E.HORIZONS + ['composite'], ['#805ad5', '#3182ce', '#2c7a7b', '#1a202c']):
            fig.add_trace(go.Scatter(x=df.date, y=df[hz], name=hz, line=dict(color=col, width=3 if hz == 'composite' else 1.5)))
        fig.add_hrect(y0=-E.THRESH, y1=E.THRESH, fillcolor=COLORS['A'], opacity=0.15, line_width=0)
        fig.update_layout(height=380, margin=dict(l=0, r=0, t=10, b=0), yaxis_range=[-1, 1])
        st.plotly_chart(fig, width='stretch')
        # projected path: cumulative sum of bucket-conditional mean intraday moves
        path, lvl = [], 100.0
        for _, rw in df.iterrows():
            em = C.expected_move(tgt, 'intraday', rw['intraday']); lvl *= (1 + (em['mean'] if em else 0)); path.append(lvl)
        df['projected index (base 100)'] = path
        st.line_chart(df.set_index('date')['projected index (base 100)'])
        st.caption('Projected path compounds the historical average intraday move for each day\'s call bucket — an illustration of what the rules imply, not a forecast with demonstrated skill.')
        st.markdown(f"Green days: **{(df.composite > E.THRESH).mean():.0%}** · Red days: **{(df.composite < -E.THRESH).mean():.0%}** · Mean composite **{df.composite.mean():+.2f}**")

# ================================================================== TRACKER
elif page == 'Prediction tracker':
    st.title('Prediction tracker — predicted vs actual')
    c1, c2, c3, c4 = st.columns(4)
    d = c1.date_input('Log predictions for', next_trading(date.today()))
    if c2.button('📝 Log predictions'):
        st.success(f'{TR.log_predictions(eng, d, C.conf_fn)} rows logged.')
    if c3.button('🔄 Fetch prices & settle'):
        with st.spinner('Downloading latest prices …'):
            st.success(f'{TR.settle()} predictions settled.')
    bf = c4.number_input('Backfill trading days (paper history)', 0, 500, 0, 20)
    if c4.button('Backfill') and bf:
        with st.spinner('Backfilling …'):
            TR.backfill(eng, date.today() - timedelta(days=int(bf * 1.45)), date.today() - timedelta(days=1), C.conf_fn)
    df = TR.load()
    if df.empty:
        st.info('No predictions logged yet. Use "Log predictions" each morning, then "Fetch prices & settle" after the close.')
    else:
        md = st.radio('Mode', ['live', 'backfill', 'all'], horizontal=True)
        sub = df if md == 'all' else df[df['mode'] == md]
        S = TR.stats(sub)
        if S.get('n'):
            k = st.columns(4)
            k[0].metric('Settled directional calls', f"{S['n']:,}")
            k[1].metric('Overall hit-rate', f"{S['hit']:.1%}")
            for i, hz in enumerate(['intraday', 'short']):
                if hz in S['by_horizon']:
                    b = S['by_horizon'][hz]; k[2 + i].metric(f'{hz} hit (naive)', f"{b['hit']:.1%}", f"naive {b['naive']:.1%}", delta_color='off')
            g = TR.daily_accuracy(sub, 'intraday')
            if not g.empty:
                fig = go.Figure([go.Bar(x=g.date, y=g.hit, name='daily hit', marker_color='#a0aec0'),
                                 go.Scatter(x=g.date, y=g.roll20, name='20-day rolling', line=dict(color='#2b6cb0', width=2)),
                                 go.Scatter(x=g.date, y=g.cum_hit, name='cumulative', line=dict(color='#1a202c', width=2))])
                fig.add_hline(y=0.5, line_dash='dot'); fig.update_layout(height=320, yaxis_tickformat='.0%', margin=dict(l=0, r=0, t=10, b=0))
                st.plotly_chart(fig, width='stretch')
            bt = pd.DataFrame([dict(Target=E.TARGET_NAME.get(t, t), n=v['n'], hit=v['hit']) for t, v in S['by_target'].items()]).sort_values('hit')
            st.dataframe(bt.style.format({'hit': '{:.1%}'}), width='stretch')
        st.dataframe(sub.sort_values('date', ascending=False).head(2000), width='stretch')
        st.download_button('⬇️ Download tracker CSV', TR.LOG.read_bytes(), 'predictions.csv')

# ================================================================== BACKTEST
elif page == 'Backtest & confidence':
    st.title('Backtest & confidence calibration')
    cal = C.cal()
    if not cal: st.error('Run `python backtest.py` first.'); st.stop()
    st.caption(f"Period {cal['meta'].get('period')} · threshold ±{cal['meta']['threshold']} · split for in/out-of-sample {cal['meta']['split']}")
    ov = pd.DataFrame([dict(Key=k, **{x: v[x] for x in ('n', 'hit', 'lo', 'hi') if x in v}, base_up=v.get('base_up')) for k, v in cal['overall'].items()])
    st.subheader('Overall directional hit-rate'); st.dataframe(ov.style.format({'hit': '{:.1%}', 'lo': '{:.1%}', 'hi': '{:.1%}', 'base_up': '{:.1%}'}), width='stretch')
    st.subheader('By rule family (book chapter)')
    fm = pd.DataFrame([dict(Family=k, **{x: v[x] for x in ('n', 'hit', 'lo', 'hi', 'p_value')}) for k, v in sorted(cal['family'].items())])
    st.dataframe(fm.style.format({'hit': '{:.1%}', 'lo': '{:.1%}', 'hi': '{:.1%}', 'p_value': '{:.3g}'}), width='stretch')
    st.subheader('By target and horizon')
    rows = []
    for t, info in cal['targets'].items():
        for hz, H in info['horizons'].items():
            a = H['all']
            rows.append(dict(Target=E.TARGET_NAME.get(t, t), Proxy=f"{info['meta']['key']} ({info['meta']['quality']})", Horizon=hz, n=a['n'], Hit=a['hit'],
                             CI=f"{a['lo']:.1%}–{a['hi']:.1%}" if a['n'] else '', Naive=a['naive_hit'], InSample=H['in_sample']['hit'], OutSample=H['out_of_sample']['hit'],
                             GreenAvg=a['green_mean'], RedAvg=a['red_mean']))
    st.dataframe(pd.DataFrame(rows).style.format({'Hit': '{:.1%}', 'Naive': '{:.1%}', 'InSample': '{:.1%}', 'OutSample': '{:.1%}', 'GreenAvg': '{:+.3%}', 'RedAvg': '{:+.3%}'}, na_rep='—'),
                 width='stretch', height=600)
    st.subheader('Long-run cycle tests (Ch.16 / 17 / 18)'); st.json(cal.get('longrun', {}), expanded=False)
    wf = HERE / 'data' / 'walkforward.json'
    if wf.exists(): st.subheader('Walk-forward: evidence-weighted families (fit 2012-19, test 2020+)'); st.json(json.loads(wf.read_text()), expanded=False)

# ================================================================== RULEBOOK
elif page == 'Rulebook':
    st.title('Rulebook — every rule extracted from the book')
    tabs = st.tabs(['Ch.4 grahas', 'Ch.5 rāśis', 'Ch.6 sectors', 'Ch.7 transits', 'Ch.8 nakṣatras', 'Ch.10 horā', 'Ch.14 opening bell', 'Ch.16–20 cycles', 'Ch.7 general rules'])
    with tabs[0]:
        st.dataframe(pd.DataFrame([dict(Graha=ac.NAMES[g], Own=', '.join(ac.RASI[i] for i in d['own']), Exalted=ac.RASI[d['exalt']], Debilitated=ac.RASI[d['debil']],
                                        Friends=', '.join(ac.NAMES[x] for x in d['friends']), Enemies=', '.join(ac.NAMES[x] for x in d['enemies']),
                                        Sectors=d['sectors'], Commodities=d['commodities']) for g, d in RB['ch4'].items()]), width='stretch')
    with tabs[1]:
        st.dataframe(pd.DataFrame([dict(Rāśi=v['rasi'], Ruler=ac.NAMES[v['ruler']], Element=v['element'], Benefics=', '.join(ac.NAMES[x] for x in v['benefics']),
                                        Malefics=', '.join(ac.NAMES[x] for x in v['malefics']), Sectors=v['text']) for v in RB['ch5'].values()]), width='stretch')
    with tabs[2]:
        rows = []
        for r_ in RB['ch6']:
            for hz, sd in r_['horizons'].items():
                for side, x in sd.items():
                    rows.append(dict(Sector=r_['name'], Horizon=hz, Side=side, Kārakas=', '.join(ac.NAMES[k] for k in x['karakas']),
                                     Trigger=ac.NAMES[x['trigger_planet']], Rāśis=', '.join(ac.RASI[i] for i in x['trigger_rasis']),
                                     Nakṣatras=', '.join(ac.NAK[i] for i in x['trigger_naks']), Page=x['page'], Note=' '.join(x['editor_note'])))
        st.dataframe(pd.DataFrame(rows), width='stretch', height=600)
    with tabs[3]:
        rows = [dict(Graha=ac.NAMES[e['graha']], Rāśi=ac.RASI[e['rasi']], If_aspected_by=', '.join(ac.NAMES[a] for a in e['cond_aspectors']) or '(unconditional)',
                     Effect=e['effect'], Else_aspected_by=', '.join(ac.NAMES[a] for a in (e['whereas'] or {}).get('aspectors', [])),
                     Else_effect=(e['whereas'] or {}).get('effect'), Page=e['page'], Fix=e.get('editor_fix', ''), Text=e.get('text', '')) for e in RB['ch7']]
        st.dataframe(pd.DataFrame(rows), width='stretch', height=600)
    with tabs[4]:
        st.dataframe(pd.DataFrame([dict(Nakṣatra=n['nakshatra'], Lord=ac.NAMES[n['lord']], Positive_if=', '.join(ac.NAMES[x] for x in n['pos']['aspectors']),
                                        Candra_confirm=', '.join(ac.NAMES[x] for x in n['pos']['moon_confirm']), Negative_if=', '.join(ac.NAMES[x] for x in n['neg']['aspectors']),
                                        Candra_confirm_neg=', '.join(ac.NAMES[x] for x in n['neg']['moon_confirm']), Sectors=n['pos']['items']) for n in RB['ch8']]), width='stretch')
    with tabs[5]:
        st.dataframe(pd.DataFrame([dict(Horā=ac.NAMES[g], Buy_if=', '.join(ac.NAMES[x] for x in v['good']), Sell_if=', '.join(ac.NAMES[x] for x in v['bad']), Stocks=v['text'], Page=v['page'])
                                   for g, v in RB['ch10'].items()]), width='stretch')
    with tabs[6]:
        st.dataframe(pd.DataFrame([dict(Graha=ac.NAMES[e['graha']], Bhāva=e['house'], Benefic_aspects=', '.join(ac.NAMES[x] for x in e['good']), Effect=e['effect'],
                                        Malefic_aspects=', '.join(ac.NAMES[x] for x in e['bad']), Malefic_effect=e['bad_effect'], Unconditional=e['unconditional'],
                                        Sectors=', '.join(E.TARGET_NAME.get(x, x) for x in e['targets']), Weight=e['house_weight']) for e in RB['ch14']]), width='stretch', height=600)
    with tabs[7]:
        st.json({'Ch.16': RB['ch16'], 'Ch.17': RB['ch17'], 'Ch.18': RB['ch18'], 'Ch.19': RB['ch19'], 'Ch.20': RB['ch20'], 'Ch.15': RB['ch15']})
    with tabs[8]:
        for x in RB['ch7_general']: st.markdown('- ' + x)

# ================================================================== VALIDATION
elif page == 'Source validation':
    st.title('Source validation — ephemeris & data feeds')
    p = HERE / 'data' / 'validation_report.json'
    if p.exists():
        v = json.loads(p.read_text())
        st.subheader('Ephemeris configurations tested against the book'); st.dataframe(pd.DataFrame(v['matrix']), width='stretch')
        st.success(f"Selected: {v['chosen']}  (Swiss Ephemeris {v['swisseph_version']})")
        st.dataframe(pd.DataFrame(v['tests'])[['id', 'group', 'test', 'book', 'engine', 'pass_', 'hard', 'page']], width='stretch', height=600)
        f = v['aspect_fit']
        st.subheader('Aspect rule vs the book\'s worked aspect lists')
        st.write(f"Recall {f['recall']:.0%}, precision {f['precision']:.0%} (TP {f['tp']}, FP {f['fp']}, FN {f['fn']}). Minimum achievable errors for any consistent rule = {f['minimum_possible_errors']} because:")
        for c in f['contradictions']: st.markdown('- ' + c)
        st.dataframe(pd.DataFrame(f['rows']), width='stretch')
    if st.button('Re-run validation now'):
        import validate; validate.main(HERE / 'data'); st.rerun()
    st.subheader('Price-feed integrity & cross-check')
    if st.button('Check feeds (downloads data)'):
        rows = []
        for t in ['NIFTY', 'BANK', 'IT', 'PHARMA', 'METAL', 'GOLD', 'SILVER', 'CRUDE', 'NATGAS']:
            df, meta = DS.series_for(t, refresh=True)
            if df is None: rows.append(dict(target=t, status='unavailable')); continue
            rep = DS.integrity_report(df); xc = DS.cross_check(t) or {}
            rows.append(dict(target=t, source=f"{meta['source']}:{meta['key']}", **rep, cross_check=xc.get('status'), max_dev_pct=xc.get('max_abs_dev_pct')))
        st.dataframe(pd.DataFrame(rows), width='stretch')

# ================================================================== SETTINGS & HELP
else:
    st.title('How this works')
    st.markdown((HERE / 'README.md').read_text() if (HERE / 'README.md').exists() else '')
