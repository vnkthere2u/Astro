"""
backtest.py — historical scoring of every rule against realised prices, and the
calibration table that supplies the 'confidence %' shown next to every prediction.

Astrological inputs are deterministic functions of the calendar, so there is no look-ahead
bias: the score for day t uses only the sky on day t.  Returns are measured from the open of
day t (or prior close where no open exists): intraday = open→close, short = 5 sessions, long = 40 sessions.

Outputs (data/):
  score_history.parquet  — date × target × horizon composite scores
  family_history.parquet — date × target × horizon × rule-family contribution
  calibration.json       — hit-rates with Wilson 95% CIs by target/horizon/strength bucket, by rule family,
                           in-sample (2012-2019) vs out-of-sample (2020-), and long-run cycle tests
"""
from __future__ import annotations
import json, math, sys, time as _t
from datetime import date, datetime, timedelta
from pathlib import Path
import numpy as np, pandas as pd
sys.path.insert(0, str(Path(__file__).parent))
import astro_core as ac, engine as E, data_sources as ds

HERE = Path(__file__).parent
DATA = HERE / 'data'
BUCKETS = [(0.15, 0.30, 'weak'), (0.30, 0.50, 'moderate'), (0.50, 1.01, 'strong')]
SPLIT = pd.Timestamp('2020-01-01')

def wilson(k, n, z=1.96):
    if n == 0: return (float('nan'),) * 3
    p = k / n; d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d; h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return p, c - h, c + h

def binom_p(k, n):
    """two-sided normal-approx p-value vs 50%"""
    if n == 0: return float('nan')
    z = (k - n / 2) / math.sqrt(n / 4)
    return math.erfc(abs(z) / math.sqrt(2))

def compute_history(start: date, end: date, local_dir=None, progress=True):
    eng = E.Engine()
    rows, frows = [], []
    d = start; n = 0; t0 = _t.time()
    while d <= end:
        if d.weekday() < 5:
            r = eng.day(d)
            for tgt, hz in r.scores.items():
                rows.append((d, tgt, hz['intraday'], hz['short'], hz['long']))
            for tgt, cs in r.contrib.items():
                agg = {}
                for c in cs:
                    agg[(c.horizon, c.family)] = agg.get((c.horizon, c.family), 0) + c.value
                for (hz, fam), v in agg.items():
                    frows.append((d, tgt, hz, fam, v))
            n += 1
            if progress and n % 500 == 0: print(f'  {n} days … {d}  ({_t.time() - t0:.0f}s)', flush=True)
        d += timedelta(days=1)
    S = pd.DataFrame(rows, columns=['date', 'target', 'intraday', 'short', 'long'])
    F = pd.DataFrame(frows, columns=['date', 'target', 'horizon', 'family', 'value'])
    S['date'] = pd.to_datetime(S['date']); F['date'] = pd.to_datetime(F['date'])
    return S, F

def smooth(S: pd.DataFrame) -> pd.DataFrame:
    """Apply the same forward averaging the app shows (E.SMOOTH sessions) to raw daily scores."""
    S = S.sort_values(['target', 'date']).copy()
    for hz, n in E.SMOOTH.items():
        S[hz] = S.groupby('target')[hz].transform(lambda x: x[::-1].rolling(n, min_periods=1).mean()[::-1])
    return S

def calibrate(S: pd.DataFrame, F: pd.DataFrame, local_dir=None):
    out = dict(targets={}, family={}, overall={}, meta=dict(threshold=E.THRESH, buckets=BUCKETS, split=str(SPLIT.date())))
    R = {}
    for tgt in list(ds.PROXY):
        rf, meta = ds.returns_frame(tgt, local_dir=local_dir)
        if rf is None: continue
        R[tgt] = (rf, meta)
    allrows = []
    for tgt, (rf, meta) in R.items():
        s = S[S.target == tgt].set_index('date')
        j = s.join(rf, how='inner', lsuffix='_s')
        info = dict(meta=meta, horizons={})
        for hz in E.HORIZONS:
            sc = j[f'{hz}_s'] if f'{hz}_s' in j else j[hz]
            rt = j[hz] if f'{hz}_s' in j else None
            if rt is None: continue
            m = sc.notna() & rt.notna() & (rt != 0)
            sc, rt = sc[m], rt[m]
            base_up = float((rt > 0).mean()) if len(rt) else float('nan')
            H = dict(base_up=base_up, n_days=int(len(rt)), buckets={})
            call = sc.abs() > E.THRESH
            hit = (np.sign(sc) == np.sign(rt))
            k, n = int(hit[call].sum()), int(call.sum())
            p, lo, hi = wilson(k, n)
            H['all'] = dict(n=n, hits=k, hit=p, lo=lo, hi=hi, p_value=binom_p(k, n),
                            green_mean=float(rt[sc > E.THRESH].mean()) if (sc > E.THRESH).any() else None,
                            red_mean=float(rt[sc < -E.THRESH].mean()) if (sc < -E.THRESH).any() else None,
                            amber_mean=float(rt[~call].mean()) if (~call).any() else None)
            # naive benchmark: always predict the majority direction on the same days
            H['all']['naive_hit'] = max(base_up, 1 - base_up)
            for lo_, hi_, name in BUCKETS:
                mm = (sc.abs() >= lo_) & (sc.abs() < hi_)
                k2, n2 = int(hit[mm].sum()), int(mm.sum())
                p2, l2, h2 = wilson(k2, n2)
                H['buckets'][name] = dict(n=n2, hits=k2, hit=p2, lo=l2, hi=h2)
            for nm, msk in (('in_sample', sc.index < SPLIT), ('out_of_sample', sc.index >= SPLIT)):
                c2 = call & msk; k3, n3 = int(hit[c2].sum()), int(c2.sum()); p3, l3, h3 = wilson(k3, n3)
                H[nm] = dict(n=n3, hits=k3, hit=p3, lo=l3, hi=h3)
            if hz == 'long': H['effective_n_note'] = 'overlapping 40-session windows: effective independent n ≈ n/40'
            if hz == 'short': H['effective_n_note'] = 'overlapping 5-session windows: effective independent n ≈ n/5'
            info['horizons'][hz] = H
            tmp = pd.DataFrame({'date': sc.index, 'target': tgt, 'hz': hz, 'score': sc.values, 'ret': rt.values, 'quality': meta['quality']})
            allrows.append(tmp)
        out['targets'][tgt] = info
    A = pd.concat(allrows, ignore_index=True)
    for hz in E.HORIZONS:
        for q in ('direct', 'all'):
            a = A[(A.hz == hz) & ((A.quality == 'direct') if q == 'direct' else True)]
            call = a.score.abs() > E.THRESH
            hit = np.sign(a.score) == np.sign(a.ret)
            k, n = int(hit[call].sum()), int(call.sum()); p, lo, hi = wilson(k, n)
            out['overall'][f'{hz}|{q}'] = dict(n=n, hits=k, hit=p, lo=lo, hi=hi, p_value=binom_p(k, n),
                                                base_up=float((a.ret > 0).mean()))
            for lo_, hi_, name in BUCKETS:
                mm = (a.score.abs() >= lo_) & (a.score.abs() < hi_)
                k2, n2 = int(hit[mm].sum()), int(mm.sum()); p2, l2, h2 = wilson(k2, n2)
                out['overall'][f'{hz}|{q}|{name}'] = dict(n=n2, hits=k2, hit=p2, lo=l2, hi=h2)
    # rule-family level (direct-quality proxies only, to avoid proxy noise)
    direct = [t for t, (rf, m) in R.items() if m['quality'] == 'direct']
    for tgt in direct:
        rf, meta = R[tgt]
        f = F[F.target == tgt]
        for (hz, fam), g in f.groupby(['horizon', 'family']):
            j = g.set_index('date')[['value']].join(rf[[hz]], how='inner').dropna()
            j = j[(j[hz] != 0) & (j.value.abs() > 0.05)]
            key = f'{fam}|{hz}'
            d = out['family'].setdefault(key, dict(n=0, hits=0))
            d['n'] += int(len(j)); d['hits'] += int((np.sign(j.value) == np.sign(j[hz])).sum())
    for key, d in out['family'].items():
        p, lo, hi = wilson(d['hits'], d['n']); d.update(hit=p, lo=lo, hi=hi, p_value=binom_p(d['hits'], d['n']))
    return out, A

# ---------------------------------------------------------------- long-run cycle tests (monthly)
def longrun_tests():
    res = {}
    eng = E.Engine()
    # Gold cycle (Ch.17) vs USD gold monthly, free-market era 1971+
    g = ds.load_series('ds', 'GOLD_USD_M')
    if g is not None:
        g = g['close']; rows = []
        for ts in g.index:
            if ts.year < 1971 or ts + pd.DateOffset(months=12) > g.index[-1]: continue
            d = date(ts.year, ts.month, 15)
            r = eng.day(d)
            s = sum(c.value for c in r.contrib.get('GOLD', []) if c.family == 'CH17' and c.horizon == 'long')
            f3 = g.asof(ts + pd.DateOffset(months=3)) / g.loc[ts] - 1
            f12 = g.asof(ts + pd.DateOffset(months=12)) / g.loc[ts] - 1
            rows.append((ts, s, f3, f12))
        G = pd.DataFrame(rows, columns=['date', 'score', 'f3', 'f12'])
        for h in ('f3', 'f12'):
            call = G.score.abs() > 0.2
            hit = np.sign(G.score) == np.sign(G[h])
            k, n = int(hit[call].sum()), int(call.sum()); p, lo, hi = wilson(k, n)
            res[f'gold_cycle_{h}'] = dict(test='Ch.17 gold-cycle score (mid-month) vs USD gold forward return', horizon=h,
                                          months=n, hits=k, hit=p, lo=lo, hi=hi, base_up=float((G[h] > 0).mean()),
                                          mean_ret_bull=float(G.loc[G.score > 0.2, h].mean()), mean_ret_bear=float(G.loc[G.score < -0.2, h].mean()),
                                          node_conj_months=int((G.score > 1.0).sum()),
                                          mean_ret_node_conj=float(G.loc[G.score > 1.0, h].mean()) if (G.score > 1.0).any() else None,
                                          note='monthly windows overlap for f12; effective n ≈ months/12')
    # Crude cycle (Ch.18) vs WTI daily 1986+ (sampled monthly)
    w = ds.load_series('ds', 'WTI')
    if w is not None:
        w = w['close']; rows = []
        months = pd.date_range(w.index[0], w.index[-1] - pd.DateOffset(months=3), freq='MS')
        for ts in months:
            d = date(ts.year, ts.month, 15)
            r = eng.day(d)
            s = sum(c.value for c in r.contrib.get('CRUDE', []) if c.family == 'CH18' and c.horizon == 'long')
            p0 = w.asof(pd.Timestamp(d)); f3 = w.asof(pd.Timestamp(d) + pd.DateOffset(months=3)) / p0 - 1
            rows.append((ts, s, f3))
        C = pd.DataFrame(rows, columns=['date', 'score', 'f3'])
        call = C.score.abs() > 0.2; hit = np.sign(C.score) == np.sign(C.f3)
        k, n = int(hit[call].sum()), int(call.sum()); p, lo, hi = wilson(k, n)
        res['crude_cycle_f3'] = dict(test='Ch.18 crude-cycle score vs WTI 3-month forward return', months=n, hits=k, hit=p, lo=lo, hi=hi,
                                     base_up=float((C.f3 > 0).mean()), mean_ret_bull=float(C.loc[C.score > 0.2, 'f3'].mean()),
                                     mean_ret_bear=float(C.loc[C.score < -0.2, 'f3'].mean()))
    # Business cycle (Ch.16) vs S&P 500 monthly since 1871
    try:
        raw = ds._get('https://raw.githubusercontent.com/datasets/s-and-p-500/main/data/data.csv')
        sp = pd.read_csv(__import__('io').BytesIO(raw), parse_dates=['Date']).set_index('Date')['SP500']
        rows = []
        for ts in sp.index:
            if ts + pd.DateOffset(months=12) > sp.index[-1]: continue
            c = ac.chart(datetime(ts.year, ts.month, 15, 6, tzinfo=ac.timezone.utc))
            rg = eng.regime_at(c)
            f12 = sp.asof(ts + pd.DateOffset(months=12)) / sp.loc[ts] - 1
            rows.append((ts, rg['phase'], rg['state'], rg['value'], f12))
        B = pd.DataFrame(rows, columns=['date', 'phase', 'state', 'value', 'f12'])
        tab = {}
        for (ph, st), g2 in B.groupby(['phase', B.state.str.split(' ').str[0]]):
            tab[f'{ph} | {st}'] = dict(months=int(len(g2)), mean_f12=float(g2.f12.mean()), pct_up=float((g2.f12 > 0).mean()))
        tab['ALL'] = dict(months=int(len(B)), mean_f12=float(B.f12.mean()), pct_up=float((B.f12 > 0).mean()))
        res['business_cycle_sp500'] = dict(test='Ch.16 regime (Śani rāśi element × Guru aspect) vs S&P 500 next-12-month return, 1871→',
                                           table=tab, note='12-month windows overlap; effective n ≈ months/12')
        rec = B[(B.phase == 'Recession') & (B.state.isin(['TRIGGERED', 'ACTIVE']))]
        res['business_cycle_sp500']['recession_active_vs_rest'] = dict(
            recession_mean=float(rec.f12.mean()) if len(rec) else None, rest_mean=float(B.drop(rec.index).f12.mean()),
            recession_pct_down=float((rec.f12 < 0).mean()) if len(rec) else None, rest_pct_down=float((B.drop(rec.index).f12 < 0).mean()))
    except Exception as e:
        res['business_cycle_sp500'] = dict(error=str(e))
    return res

def main(start=date(2012, 2, 21), end=None, local_dir=None):
    end = end or date.today()
    t0 = _t.time()
    print('scoring history …')
    S, F = compute_history(start, end + timedelta(days=90), local_dir)
    S = smooth(S); S = S[S.date <= pd.Timestamp(end)]; F = F[F.date <= pd.Timestamp(end)]
    S.to_parquet(DATA / 'score_history.parquet'); F.to_parquet(DATA / 'family_history.parquet')
    print(f'  done {len(S)} rows in {_t.time() - t0:.0f}s; calibrating …')
    cal, A = calibrate(S, F, local_dir)
    A.to_parquet(DATA / 'backtest_joined.parquet')
    print('long-run cycle tests …')
    cal['longrun'] = longrun_tests()
    cal['meta']['generated'] = datetime.now().isoformat(timespec='seconds')
    cal['meta']['period'] = f'{start} → {end}'
    (DATA / 'calibration.json').write_text(json.dumps(cal, indent=1, default=lambda x: None if (isinstance(x, float) and math.isnan(x)) else str(x)))
    print(f'finished in {_t.time() - t0:.0f}s')
    return cal

if __name__ == '__main__':
    ld = Path(sys.argv[1]) if len(sys.argv) > 1 else None
    main(local_dir=ld)
