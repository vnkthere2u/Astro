"""Rule-level hit rates: every individual rule (e.g. 'Śani in Mīna', 'Aśvinī day', 'Guru horā'), with in/out-of-sample persistence and a date-shuffle null."""
import sys, json, numpy as np, pandas as pd
from datetime import date, timedelta
from pathlib import Path
import engine as E, data_sources as ds
LD = Path('/root/data_src/eod2_data/daily')
eng = E.Engine(); rows = []
d = date(2012, 2, 21)
while d <= date(2026, 10, 23):
    if d.weekday() < 5:
        r = eng.day(d)
        for t, cs in r.contrib.items():
            agg = {}
            for c in cs:
                k = (c.horizon, c.rule if c.family not in ('CH16','CH17','CH18','CH19','CH20') else c.family + ':' + c.text.split('—')[0].split(':')[0])
                agg[k] = agg.get(k, 0) + c.value
            for (hz, rule), v in agg.items(): rows.append((d, t, hz, rule, v))
    d += timedelta(days=1)
F = pd.DataFrame(rows, columns=['date', 'target', 'hz', 'rule', 'v']); F['date'] = pd.to_datetime(F['date'])
direct = [t for t, v in ds.PROXY.items() if v[0][2] == 'direct' and v[0][0] != 'yf' and t != 'NIFTY']
R = []
for t in direct:
    rf, m = ds.returns_frame(t, local_dir=LD)
    x = F[F.target == t]
    for hz in E.HORIZONS:
        y = x[x.hz == hz].merge(rf[[hz]].rename(columns={hz: 'ret'}), left_on='date', right_index=True)
        R.append(y)
A = pd.concat(R); A = A[(A.v.abs() > 0.05) & A.ret.notna() & (A.ret != 0)]
A['hit'] = (np.sign(A.v) == np.sign(A.ret)).astype(int)
A['dir_up'] = (A.v > 0).astype(int); A['ret_up'] = (A.ret > 0).astype(int)
split = pd.Timestamp('2020-01-01')
def table(df):
    g = df.groupby(['hz', 'rule'])
    out = g.agg(n=('hit', 'size'), hit=('hit', 'mean'), base_up=('ret_up', 'mean'), pct_long=('dir_up', 'mean')).reset_index()
    out['naive'] = np.where(out.pct_long > 0.5, out.base_up, 1 - out.base_up)  # hit rate of always calling the rule's usual direction... 
    return out
ALL = table(A); IS = table(A[A.date < split]); OOS = table(A[A.date >= split])
M = IS.merge(OOS, on=['hz', 'rule'], suffixes=('_is', '_oos'))
res = {}
for hz in E.HORIZONS:
    al = ALL[(ALL.hz == hz) & (ALL.n >= 30)]
    m = M[(M.hz == hz) & (M.n_is >= 30) & (M.n_oos >= 30)]
    top = m[m.hit_is >= 0.60]
    res[hz] = dict(rules_tested=int(len(al)), rules_ge60=int((al.hit >= .60).sum()), rules_ge70=int((al.hit >= .70).sum()),
                   rules_le40=int((al.hit <= .40).sum()),
                   IS_ge60=int(len(top)), those_OOS_mean_hit=round(float(top.hit_oos.mean()), 3) if len(top) else None,
                   those_OOS_still_ge60=int((top.hit_oos >= .60).sum()),
                   corr_IS_OOS=round(float(m[['hit_is', 'hit_oos']].corr().iloc[0, 1]), 3) if len(m) > 3 else None)
# null: shuffle returns across dates within target/hz, recount rules >=60%
rng = np.random.default_rng(0); null = {hz: [] for hz in E.HORIZONS}
for k in range(20):
    B = A.copy()
    B['ret'] = B.groupby(['target', 'hz'])['ret'].transform(lambda s: s.sample(frac=1, random_state=int(rng.integers(1e9))).values)
    B['hit'] = (np.sign(B.v) == np.sign(B.ret)).astype(int)
    T = B.groupby(['hz', 'rule']).agg(n=('hit', 'size'), hit=('hit', 'mean')).reset_index()
    for hz in E.HORIZONS:
        t_ = T[(T.hz == hz) & (T.n >= 30)]; null[hz].append(int((t_.hit >= .60).sum()))
for hz in E.HORIZONS: res[hz]['null_shuffled_ge60_avg'] = round(float(np.mean(null[hz])), 1)
best = M[(M.n_is >= 30) & (M.n_oos >= 30)].sort_values('hit_is', ascending=False).head(25)
ALL.to_csv('data/rule_level_hitrates.csv', index=False); M.to_csv('data/rule_level_is_oos.csv', index=False)
print(json.dumps(res, indent=1)); print(best[['hz','rule','n_is','hit_is','n_oos','hit_oos','base_up_oos']].to_string())
