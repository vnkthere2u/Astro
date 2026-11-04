"""AstroMarket — Book 1 (Stock Market Astrology) and Book 2 (Investment Muhurtas), applied as written.
Two screens: the daily view, and the 12-month short / long-term outlook. Kept light so Streamlit Cloud stays up:
no charting library, the 12-month outlook is pre-computed every evening by the GitHub job (data/outlook.csv)."""
from __future__ import annotations
import json
from datetime import date, datetime, timedelta
from pathlib import Path
import pandas as pd
import streamlit as st

import astro_core as ac
import engine as E
import tracker as TR

HERE = Path(__file__).parent
st.set_page_config(page_title='AstroMarket', page_icon='🪐', layout='wide')

GREEN, AMBER, RED, GREY = '#1f9d55', '#d69e2e', '#c53030', '#cbd5e0'
WORD = {1: 'Up', -1: 'Down', 0: 'Neutral', None: 'No rule'}
LIGHT = {'Up': '#c6f6d5', 'Neutral': '#fefcbf', 'Down': '#fed7d7', 'No rule': '#edf2f7'}
DARK = {'Up': GREEN, 'Neutral': AMBER, 'Down': RED, 'No rule': GREY}
ARROW = {'Up': '▲', 'Neutral': '◆', 'Down': '▼', 'No rule': '·'}
HZ = {'intraday': 'Today', 'short': 'Short-term', 'long': 'Long-term'}
TARGETS = E.TARGETS; NAME = E.TARGET_NAME


def pill(d, small=False, suffix=''):
    w = WORD[d]
    return (f"<span style='background:{LIGHT[w]};color:{DARK[w]};padding:2px 10px;border-radius:12px;font-weight:600;"
            f"font-size:{'12px' if small else '15px'};white-space:nowrap'>{ARROW[w]} {w}{suffix}</span>")


def board_style(val):
    for k in ('No rule', 'Up', 'Down', 'Neutral'):
        if isinstance(val, str) and val.endswith(k): return f'background-color:{LIGHT[k]};color:{DARK[k]};font-weight:600'
    return ''


@st.cache_resource(show_spinner=False)
def get_engine():
    mu = json.loads((HERE / 'data' / 'muhurat.json').read_text()) if (HERE / 'data' / 'muhurat.json').exists() else []
    return E.Engine(muhurat=[(date.fromisoformat(a), float(b)) for a, b in mu])


@st.cache_data(show_spinner=False, max_entries=3, ttl=6 * 3600)
def day(d: date):
    r = get_engine().day(d); get_engine()._cache.clear()
    return r


@st.cache_data(show_spinner=False, ttl=3600)
def outlook():
    p = HERE / 'data' / 'outlook.csv'
    if not p.exists(): return None
    df = pd.read_csv(p, parse_dates=['date'])
    return df


def next_session(d):
    while d.weekday() >= 5: d += timedelta(days=1)
    return d


st.sidebar.markdown('## 🪐 AstroMarket')
page = st.sidebar.radio('Go to', ['Daily view', '12-month outlook'], label_visibility='collapsed')
st.sidebar.markdown('---')
st.sidebar.caption('▲ green = **Up** · ◆ amber = **Neutral** · ▼ red = **Down** · grey = no rule in the books.')
st.sidebar.caption('**B1** = Stock Market Astrology · **B2** = Investment Muhurtas. If one says Up and the other Down, the combined call is Neutral ⚖️.')
st.sidebar.caption('Calls are logged automatically the evening before; a Telegram alert goes out each morning and a right/wrong check after the close.')

# ================================================================= DAILY VIEW
if page == 'Daily view':
    c0, c1 = st.columns([3, 1])
    d = c1.date_input('Date', next_session(date.today()), label_visibility='collapsed')
    c0.title(f"{d:%A, %d %B %Y}")
    r = day(d)

    k = st.columns(3)
    for col, hz in zip(k, E.HORIZONS):
        bv = r.book[('NIFTY', hz)]
        col.markdown(f"**Nifty — {HZ[hz]}**<br>{pill(r.final[('NIFTY', hz)], suffix=' ⚖️' if r.disagree[('NIFTY', hz)] else '')}"
                     f"<br><span style='font-size:12px'>B1 {ARROW[WORD[bv[1]]]} {WORD[bv[1]]} · B2 {ARROW[WORD[bv[2]]]} {WORD[bv[2]]}</span>",
                     unsafe_allow_html=True)

    st.markdown('#### All sectors & commodities')
    rows = []
    for t in TARGETS:
        row = {'Market': NAME[t]}
        bv = r.book[(t, 'intraday')]
        row['Today'] = ('⚖️ ' if r.disagree[(t, 'intraday')] else '') + f"{ARROW[WORD[r.final[(t, 'intraday')]]]} {WORD[r.final[(t, 'intraday')]]}"
        row['Book 1 today'] = f"{ARROW[WORD[bv[1]]]} {WORD[bv[1]]}"
        row['Book 2 today'] = f"{ARROW[WORD[bv[2]]]} {WORD[bv[2]]}"
        for hz in ('short', 'long'):
            row[HZ[hz]] = f"{ARROW[WORD[r.final[(t, hz)]]]} {WORD[r.final[(t, hz)]]}"
        rows.append(row)
    T = pd.DataFrame(rows)
    st.dataframe(T.style.map(board_style, subset=[c for c in T.columns if c != 'Market']), hide_index=True, width='stretch', height=36 * len(T) + 40)
    st.caption('Short- and long-term calls come from Book 1 only (Book 2 is a day-by-day book).')

    b2 = r.b2
    with st.expander(f"Book 2 — today's muhurta: {b2['weekday']} · {b2['tithi']} · {b2['nakshatra']} · {b2['yoga']} yoga · {b2['karana']} karana", expanded=True):
        for v in b2['votes']:
            if v['targets'] == 'ALL':
                st.markdown(f"{'🟢' if v['dir'] > 0 else '🔴' if v['dir'] < 0 else '◆'} {v['text']} *({v['factor']})*")
            else:
                st.markdown(f"{'🟢' if v['dir'] > 0 else '🔴'} {v['text']} — {', '.join(NAME.get(x, x) for x in v['targets'])} *({v['factor']})*")
        for n in b2['notes']: st.caption('ℹ️ ' + n)
    with st.expander('Timing inside the session (Book 2, and Book 1 planetary hours)'):
        o, cl = r.open_dt, r.close_dt; rows = []
        for w in r.windows:
            if w['end'] <= o or w['start'] >= cl or (w['kind'].startswith(('Gouri', 'Chaughadia', 'Hora')) and w['dir'] == 0): continue
            rows.append(dict(From=max(w['start'], o).strftime('%H:%M'), To=min(w['end'], cl).strftime('%H:%M'), Window=w['kind'] + ' (B2)',
                             Meaning='Buy-side' if w['dir'] > 0 else 'Avoid buying / sell-side' if w['dir'] < 0 else 'Neutral'))
        for h in r.hora:
            if h['dir']: rows.append(dict(From=h['start'].strftime('%H:%M'), To=h['end'].strftime('%H:%M'), Window=f"Hora {ac.EN[h['lord']]} (B1)",
                                          Meaning=('Buy-side' if h['dir'] > 0 else 'Avoid buying / sell-side') + ' — ' + ', '.join(NAME.get(x, x) for x in h['targets'][:4])))
        if rows: st.dataframe(pd.DataFrame(rows).sort_values('From'), hide_index=True, width='stretch')
    if r.reversal:
        st.warning('**Trend-reversal window (Book 2 Ch.34):** ' + '; '.join(x['text'] for x in r.reversal), icon='🔄')
    rg = r.regime
    st.info(f"**Business cycle (Book 1 Ch.16):** {rg['phase']} — {'active' if rg['active'] else 'not active'}. {rg['detail']}", icon='🧭')
    for f in r.flags: st.caption('⚠️ ' + f)
    with st.expander('Why? — every rule behind a call'):
        t = st.selectbox('Market', TARGETS, format_func=lambda x: NAME[x])
        for hz in E.HORIZONS:
            st.markdown(f"**{HZ[hz]}** — {pill(r.final[(t, hz)], True)}", unsafe_allow_html=True)
            vs = r.votes(t, hz)
            if not vs: st.caption('No rule applies.')
            for v in vs: st.markdown(f"- {'🟢' if v['dir'] > 0 else '🔴' if v['dir'] < 0 else '◆'} **B{v['book']} {v['chapter']}** — {v['text']}")
    with st.expander('Track record (live calls, today horizon)'):
        df = TR.load()
        s = df[(df.status == 'scored') & (df.horizon == 'intraday')]
        if s.empty: st.caption('No scored calls yet.')
        else:
            out = []
            for dd, g in s.groupby('date'):
                rec = {'Date': dd.strftime('%d %b'), 'Logged': 'on time' if (g['mode'] == 'live').all() else 'late' if (g['mode'] == 'late').all() else 'mixed'}
                for col, nm in (('book1', 'Book 1'), ('book2', 'Book 2')):
                    y = g[g[col].isin(['Up', 'Down'])]
                    rec[nm] = f"{((y[col] == 'Up') == (y.actual_ret > 0)).sum()}/{len(y)}" if len(y) else '—'
                out.append(rec)
            st.dataframe(pd.DataFrame(out[::-1][:60]), hide_index=True, width='stretch')

# ================================================================= 12-MONTH OUTLOOK
else:
    st.title('12-month outlook — short & long term')
    F = outlook()
    if F is None:
        st.warning('The outlook file is built by the evening job; it will appear after the next run.')
        st.stop()
    st.caption(f"Pre-computed {F.date.min():%d %b %Y} → {F.date.max():%d %b %Y} from Book 1 transits (Book 2 has no multi-day rules). "
               'Each box is one trading day; hover for the date.')
    hz = st.radio('Horizon', ['short', 'long'], format_func=lambda x: HZ[x], horizontal=True)

    # weekly grid for every market
    F['week'] = F.date.dt.to_period('W-FRI').dt.start_time
    W = F.pivot_table(index='target', columns='week', values=hz, aggfunc=lambda s: (s == 1).sum() - (s == -1).sum())
    weeks = list(W.columns)
    months = ''.join(f"<th style='font-size:10px;font-weight:400;color:#555'>{w:%b}</th>" if (i == 0 or w.month != weeks[i - 1].month) else '<th></th>'
                     for i, w in enumerate(weeks))
    body = []
    for t in TARGETS:
        if t not in W.index: continue
        cells = ''.join(f"<td title='{NAME[t]} · week of {w:%d %b %Y}' style='background:{GREEN if v > 0 else RED if v < 0 else AMBER};width:13px;height:16px'></td>"
                        for w, v in W.loc[t].items())
        body.append(f"<tr><td style='font-size:12px;white-space:nowrap;padding-right:8px'>{NAME[t]}</td>{cells}</tr>")
    st.markdown('**Week by week** — colour = whether Up or Down days dominated that week')
    st.markdown(f"<div style='overflow-x:auto'><table style='border-collapse:separate;border-spacing:1px'><tr><th></th>{months}</tr>{''.join(body)}</table></div>",
                unsafe_allow_html=True)

    st.markdown('#### One market, day by day')
    t = st.selectbox('Market', TARGETS, format_func=lambda x: NAME[x])
    x = F[F.target == t].set_index('date')
    for h in ('short', 'long'):
        s = x[h]
        n = max(1, s.notna().sum())
        st.markdown(f"**{HZ[h]}** — ▲ Up {(s == 1).sum() / n:.0%} of days · ◆ Neutral {(s == 0).sum() / n:.0%} · ▼ Down {(s == -1).sum() / n:.0%}")
        html = []
        for m, g in s.groupby(s.index.to_period('M')):
            boxes = ''.join(f"<span title='{ix:%a %d %b %Y}: {WORD[None if pd.isna(v) else int(v)]}' style='display:inline-block;width:15px;height:15px;margin:1px;"
                            f"background:{DARK[WORD[None if pd.isna(v) else int(v)]]};font-size:8px;color:white;text-align:center;line-height:15px'>{ix.day}</span>"
                            for ix, v in g.items())
            html.append(f"<div style='margin:2px 0'><span style='display:inline-block;width:60px;font-size:12px'>{m.strftime('%b %y')}</span>{boxes}</div>")
        st.markdown(''.join(html), unsafe_allow_html=True)
    # when do the calls change?
    ch = []
    for h in ('short', 'long'):
        s = x[h].fillna(99)
        for ix in s.index[1:][(s.values[1:] != s.values[:-1])]:
            ch.append((ix, HZ[h], WORD[None if s.loc[ix] == 99 else int(s.loc[ix])]))
    if ch:
        with st.expander(f'Dates the call changes ({len(ch)})'):
            st.dataframe(pd.DataFrame([dict(Date=a.strftime('%a %d %b %Y'), Horizon=b, **{'New call': c}) for a, b, c in sorted(ch)]), hide_index=True, width='stretch')
