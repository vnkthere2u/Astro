"""walkforward.py — does re-weighting rule families on 2012-2019 improve 2020+ out-of-sample accuracy?"""
import pandas as pd, numpy as np, json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
import data_sources as ds, engine as E

def run(local_dir=None):
    F = pd.read_parquet(Path(__file__).parent / 'data' / 'family_history.parquet')
    direct = [t for t, v in ds.PROXY.items() if v[0][2] == 'direct' and v[0][0] != 'yf' and t != 'NIFTY']
    F = F[F.target.isin(direct)]
    P = F.groupby(['target', 'date', 'horizon', 'family'])['value'].sum().unstack('family').fillna(0)
    split = pd.Timestamp('2020-01-01'); rows = []
    for t in direct:
        if t not in P.index.get_level_values(0): continue
        rf, m = ds.returns_frame(t, local_dir=local_dir)
        if rf is None: continue
        f = P.xs(t, level='target')
        for hz in E.HORIZONS:
            if hz not in f.index.get_level_values('horizon'): continue
            x = f.xs(hz, level='horizon'); j = x.join(rf[[hz]], how='inner').dropna(); j = j[j[hz] != 0]
            j = j.rename(columns={hz: 'ret'}); j['target'] = t; j['hz'] = hz; rows.append(j)
    A = pd.concat(rows).fillna(0); fams = sorted(c for c in A.columns if c.startswith('CH'))
    res = {}
    for hz in E.HORIZONS:
        a = A[A.hz == hz]; IS = a[a.index < split]; OOS = a[a.index >= split]; w = {}
        for f in fams:
            msk = IS[f].abs() > 0.05
            if msk.sum() < 200: w[f] = 1.0; continue
            hit = (np.sign(IS.loc[msk, f]) == np.sign(IS.loc[msk, 'ret'])).mean()
            w[f] = round(float(max(0.0, (hit - 0.5) / 0.02)), 2)
        def ev(df, W):
            s = np.tanh(sum(df[f] * W.get(f, 1) for f in fams) / 1.6); call = s.abs() > 0.15
            hit = (np.sign(s) == np.sign(df['ret']))[call]
            return dict(hit=round(float(hit.mean()), 4), n=int(call.sum()),
                        spread_bps=round(1e4 * float(df.loc[s > 0.15, 'ret'].mean() - df.loc[s < -0.15, 'ret'].mean()), 1))
        book = {f: 1.0 for f in fams}
        res[hz] = dict(in_sample_family_weights=w, book_IS=ev(IS, book), book_OOS=ev(OOS, book),
                       evidence_IS=ev(IS, w), evidence_OOS=ev(OOS, w),
                       naive_OOS=round(float(max((OOS.ret > 0).mean(), 1 - (OOS.ret > 0).mean())), 4))
    return res

if __name__ == '__main__':
    r = run(Path(sys.argv[1]) if len(sys.argv) > 1 else None)
    (Path(__file__).parent / 'data' / 'walkforward.json').write_text(json.dumps(r, indent=1)); print(json.dumps(r, indent=1))
