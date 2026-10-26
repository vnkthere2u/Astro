"""
data_sources.py — market data for backtesting and live tracking.

Primary (verified reachable, daily-updated, no API key):
  • NSE index EOD (OHLC):  github.com/BennyThadikaran/eod2_data  (daily/<index>.csv) — compiled from NSE bhavcopies
  • Gold (INR) / Silver (INR): NSE ETFs GOLDBEES / SILVERBEES from the same repository
  • WTI & Brent crude, Henry Hub gas (daily) : github.com/datasets/oil-prices, datasets/natural-gas (EIA source)
  • Gold USD monthly since 1833: github.com/datasets/gold-prices
Optional (used automatically when reachable from the user's machine): Yahoo Finance via yfinance for
commodities with no free GitHub feed (copper, aluminium, wheat, cotton, sugar) and as a cross-check.
"""
from __future__ import annotations
import io, json, time, urllib.parse, urllib.request
from datetime import date, datetime, timedelta
from pathlib import Path
import pandas as pd

HERE = Path(__file__).parent
CACHE = HERE / 'data' / 'prices'
CACHE.mkdir(parents=True, exist_ok=True)
EOD2 = 'https://raw.githubusercontent.com/BennyThadikaran/eod2_data/main/daily/{}.csv'
DATASETS = {'WTI': 'https://raw.githubusercontent.com/datasets/oil-prices/main/data/wti-daily.csv',
            'BRENT': 'https://raw.githubusercontent.com/datasets/oil-prices/main/data/brent-daily.csv',
            'HENRYHUB': 'https://raw.githubusercontent.com/datasets/natural-gas/main/data/daily.csv',
            'GOLD_USD_M': 'https://raw.githubusercontent.com/datasets/gold-prices/main/data/monthly.csv'}

# target -> list of (source, key, quality) in order of preference; quality: direct | proxy | weak
PROXY = {
 'NIFTY': [('eod2', 'nifty 50', 'direct')],
 'BANK': [('eod2', 'nifty bank', 'direct')], 'IT': [('eod2', 'nifty it', 'direct')], 'AUTO': [('eod2', 'nifty auto', 'direct')],
 'PHARMA': [('eod2', 'nifty pharma', 'direct')], 'FMCG': [('eod2', 'nifty fmcg', 'direct')], 'METAL': [('eod2', 'nifty metal', 'direct')],
 'REALTY': [('eod2', 'nifty realty', 'direct')], 'MEDIA': [('eod2', 'nifty media', 'direct')], 'INFRA': [('eod2', 'nifty infrastructure', 'direct')],
 'PSU': [('eod2', 'nifty pse', 'direct')], 'OILGAS': [('eod2', 'nifty energy', 'proxy')], 'POWER': [('eod2', 'nifty energy', 'proxy')],
 'CAPGOODS': [('eod2', 'nifty infrastructure', 'proxy')], 'CEMENT': [('eod2', 'nifty infrastructure', 'weak')],
 'HEALTH': [('eod2', 'nifty pharma', 'proxy')], 'GEMS': [('eod2', 'nifty consumer durables', 'proxy')],
 'PAINTS': [('eod2', 'nifty consumer durables', 'weak')], 'TELECOM': [('eod2', 'nifty services sector', 'weak')],
 'EXPORTS': [('eod2', 'nifty it', 'weak')], 'SHIPPING': [('eod2', 'nifty transportation & logistics', 'weak')],
 'AVIATION': [('eod2', 'nifty transportation & logistics', 'weak')], 'HOSPITALITY': [('eod2', 'nifty india tourism', 'proxy')],
 'TRAVEL': [('eod2', 'nifty india tourism', 'proxy')], 'AGRI': [('eod2', 'nifty india consumption', 'weak')],
 'EDIBLEOIL': [('eod2', 'nifty fmcg', 'weak')], 'ESSOIL': [('eod2', 'nifty fmcg', 'weak')], 'EDU': [('eod2', 'nifty services sector', 'weak')],
 'LEATHER': [('eod2', 'nifty india consumption', 'weak')], 'TEXTILE': [('eod2', 'nifty india consumption', 'weak')],
 'PUBLICATION': [('eod2', 'nifty media', 'proxy')], 'SUGAR': [('eod2', 'nifty fmcg', 'weak')],
 'GOLD': [('eod2', 'goldbees', 'direct'), ('yf', 'GC=F', 'direct')], 'SILVER': [('eod2', 'silverbees', 'direct'), ('yf', 'SI=F', 'direct')],
 'CRUDE': [('ds', 'WTI', 'direct'), ('yf', 'CL=F', 'direct')], 'NATGAS': [('ds', 'HENRYHUB', 'direct'), ('yf', 'NG=F', 'direct')],
 'COPPER': [('yf', 'HG=F', 'direct'), ('eod2', 'nifty metal', 'weak')], 'ALUMINIUM': [('yf', 'ALI=F', 'direct'), ('eod2', 'nifty metal', 'weak')],
 'STEEL': [('eod2', 'nifty metal', 'proxy')], 'WHEAT': [('yf', 'ZW=F', 'direct')], 'COTTON': [('yf', 'CT=F', 'direct')],
 'SUGARC': [('yf', 'SB=F', 'direct')],
}

_YF_DEAD = False

def _get(url, timeout=30):
    req = urllib.request.Request(url, headers={'User-Agent': 'astro-market-engine/1.0'})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()

def _cache_path(src, key):
    return CACHE / f"{src}__{key.replace(' ', '_').replace('&', 'and').replace('=', '').replace('^', '')}.csv"

def load_series(src: str, key: str, refresh=False, local_dir: Path | None = None) -> pd.DataFrame | None:
    """Return DataFrame indexed by date with columns open, high, low, close (open may be NaN)."""
    cp = _cache_path(src, key)
    if cp.exists() and not refresh and (time.time() - cp.stat().st_mtime) < 6 * 3600:
        df = pd.read_csv(cp, parse_dates=['date']).set_index('date')
        return df
    df = None
    try:
        if src == 'eod2':
            raw = None
            if local_dir and (local_dir / f'{key}.csv').exists():
                raw = (local_dir / f'{key}.csv').read_bytes()
            else:
                raw = _get(EOD2.format(urllib.parse.quote(key)))
            d = pd.read_csv(io.BytesIO(raw))
            d.columns = [c.strip().lower() for c in d.columns]
            d = d.rename(columns={'date': 'date'})
            d['date'] = pd.to_datetime(d['date'])
            df = d[['date', 'open', 'high', 'low', 'close']].set_index('date').sort_index()
        elif src == 'ds':
            d = pd.read_csv(io.BytesIO(_get(DATASETS[key])))
            d.columns = ['date', 'close']
            d['date'] = pd.to_datetime(d['date'], errors='coerce')
            d = d.dropna().set_index('date').sort_index()
            d['open'] = float('nan'); d['high'] = d['low'] = d['close']
            df = d[['open', 'high', 'low', 'close']]
        elif src == 'yf':
            global _YF_DEAD
            if _YF_DEAD: return None
            import yfinance as yf
            d = yf.download(key, period='max', interval='1d', progress=False, auto_adjust=False)
            if d is None or d.empty:
                _YF_DEAD = True; return None
            if isinstance(d.columns, pd.MultiIndex): d.columns = d.columns.get_level_values(0)
            d = d.rename(columns=str.lower)[['open', 'high', 'low', 'close']]
            d.index = pd.to_datetime(d.index).tz_localize(None); d.index.name = 'date'
            df = d
    except Exception as e:  # network or parsing failure → fall back to cache
        if cp.exists():
            return pd.read_csv(cp, parse_dates=['date']).set_index('date')
        return None
    if df is not None and not df.empty:
        df = df[~df.index.duplicated(keep='last')]
        df = df[df['close'] > 0]
        df.reset_index().to_csv(cp, index=False)
    return df

def series_for(target: str, refresh=False, local_dir=None):
    for src, key, q in PROXY.get(target, []):
        df = load_series(src, key, refresh, local_dir)
        if df is not None and len(df) > 50:
            return df, dict(source=src, key=key, quality=q)
    return None, None

def integrity_report(df: pd.DataFrame) -> dict:
    """Source-quality checks for a price series."""
    rep = dict(rows=len(df), start=str(df.index.min().date()), end=str(df.index.max().date()))
    c = df['close']
    rep['non_positive'] = int((c <= 0).sum())
    ohlc = df.dropna(subset=['open', 'high', 'low'])
    rep['ohlc_violations'] = int(((ohlc['high'] + 1e-6 < ohlc[['open', 'close']].max(axis=1)) | (ohlc['low'] - 1e-6 > ohlc[['open', 'close']].min(axis=1))).sum())
    gaps = df.index.to_series().diff().dt.days
    rep['max_gap_days'] = int(gaps.max()) if len(gaps) > 1 else 0
    r = c.pct_change().abs()
    rep['jumps_gt_15pct'] = int((r > 0.15).sum())
    rep['dup_dates'] = int(df.index.duplicated().sum())
    return rep

def cross_check(target: str, days=60) -> dict | None:
    """Compare primary feed with Yahoo Finance over the last `days` (only where both exist)."""
    yfmap = {'NIFTY': '^NSEI', 'BANK': '^NSEBANK', 'IT': '^CNXIT', 'PHARMA': '^CNXPHARMA', 'AUTO': '^CNXAUTO', 'FMCG': '^CNXFMCG',
             'METAL': '^CNXMETAL', 'REALTY': '^CNXREALTY', 'MEDIA': '^CNXMEDIA', 'CRUDE': 'CL=F', 'NATGAS': 'NG=F', 'GOLD': 'GOLDBEES.NS'}
    if target not in yfmap: return None
    a, meta = series_for(target)
    b = load_series('yf', yfmap[target])
    if a is None or b is None: return dict(target=target, status='cross-check source unreachable')
    j = a[['close']].join(b[['close']], rsuffix='_yf', how='inner').tail(days)
    if j.empty: return dict(target=target, status='no overlap')
    dev = (j['close'] / j['close_yf'] - 1).abs()
    return dict(target=target, status='ok' if dev.max() < 0.005 else 'DISCREPANCY', max_abs_dev_pct=round(100 * dev.max(), 3),
                mean_abs_dev_pct=round(100 * dev.mean(), 4), days=len(j))

def returns_frame(target: str, horizons=(('intraday', 0), ('short', 5), ('long', 63)), refresh=False, local_dir=None):
    df, meta = series_for(target, refresh, local_dir)
    if df is None: return None, None
    df = df.copy()
    c = df['close']; o = df['open']
    has_open = o.notna().mean() > 0.8
    prev = c.shift(1)
    entry = o.where(o.notna(), prev) if has_open else prev
    out = pd.DataFrame(index=df.index)
    out['intraday'] = (c / entry - 1) if has_open else (c / prev - 1)
    for name, n in horizons:
        if n == 0: continue
        out[name] = c.shift(-(n - 1)) / entry - 1
    meta['intraday_basis'] = 'open→close' if has_open else 'close→close'
    return out, meta
