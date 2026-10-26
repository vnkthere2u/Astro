"""
daily_job.py — unattended daily operation (run by GitHub Actions, or by hand).

  python daily_job.py morning   # log today's predictions (IST date) before the open — immutable
  python daily_job.py evening   # download latest prices, settle every pending prediction, refresh summary
  python daily_job.py weekly    # rebuild AstroMarket_Workbook.xlsx for the next 365 days
  python daily_job.py all       # morning + evening (catch-up)

Writes data/tracker/predictions.csv and data/tracker/summary.json; the workflow commits them,
so the git history is a timestamped, tamper-evident record of every call made before the outcome.
"""
from __future__ import annotations
import json, sys
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo
sys.path.insert(0, str(Path(__file__).parent))
import engine as E, tracker as TR, calib as C

HERE = Path(__file__).parent
IST = ZoneInfo('Asia/Kolkata')
MUHURAT_FILE = HERE / 'data' / 'muhurat.json'   # [["2025-10-21", 63], ...] — edit each Dīpāvali

def engine():
    mu = []
    if MUHURAT_FILE.exists():
        mu = [(date.fromisoformat(a), float(b)) for a, b in json.loads(MUHURAT_FILE.read_text())]
    return E.Engine(muhurat=mu)

def today_ist() -> date:
    return datetime.now(IST).date()

OPEN_IST = (9, 15)

def morning(d: date | None = None):
    """Log today's calls. If this runs after the 09:15 IST open (e.g. GitHub delayed the job), the rows are
    marked 'late' and excluded from the score, so a delayed run can never flatter the record."""
    now = datetime.now(IST); d = d or now.date()
    if d.weekday() >= 5:
        print(f'{d} is a weekend — nothing logged.'); return 0
    late = d < now.date() or (d == now.date() and (now.hour, now.minute) >= OPEN_IST)
    n = TR.log_predictions(engine(), d, mode='late' if late else 'live')
    print(f"logged {n} calls for {d}{' (LATE — excluded from score)' if late else ''}"); return n

def evening():
    """Score every pending call whose horizon has finished. Idempotent: a missed evening is caught up next time."""
    n = TR.settle(); s = TR.stats(modes=('live',)); p = TR.stats(modes=('paper',))
    summary = dict(updated=datetime.now(IST).isoformat(timespec='minutes'), scored_now=n, live=s, paper_baseline=p)
    (TR.TDIR / 'summary.json').write_text(json.dumps(summary, indent=1, default=float))
    print(f"scored {n}; live record: {s.get('n', 0)} calls" + (f", {s['hit']:.1%} correct" if s.get('n') else ''))
    return n

def weekly():
    import build_excel
    out = build_excel.build(today_ist() + timedelta(days=1), 365)
    print('workbook →', out)

if __name__ == '__main__':
    mode = sys.argv[1] if len(sys.argv) > 1 else 'all'
    if mode in ('morning', 'all'): morning(date.fromisoformat(sys.argv[2]) if len(sys.argv) > 2 else None)
    if mode in ('evening', 'all'): evening()
    if mode == 'weekly': weekly()
