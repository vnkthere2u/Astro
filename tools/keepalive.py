"""Open the Streamlit app like a visitor; if it is asleep, press the wake-up button and wait until it is running."""
import sys, time
from playwright.sync_api import sync_playwright

URL = sys.argv[1]
WAKE = ['Yes, get this app back up', 'get this app back up', 'Wake up', 'wake app']

with sync_playwright() as p:
    b = p.chromium.launch()
    pg = b.new_page()
    pg.goto(URL, wait_until='domcontentloaded', timeout=120_000)
    time.sleep(8)
    woke = False
    for frame in [pg] + pg.frames:
        for label in WAKE:
            btn = frame.get_by_role('button', name=label)
            try:
                if btn.count():
                    btn.first.click(); woke = True; print('app was asleep — wake-up pressed'); break
            except Exception:
                pass
        if woke: break
    # wait for the Streamlit app itself (its root container) to render, up to 5 minutes
    ok = False
    for _ in range(60):
        for frame in [pg] + pg.frames:
            try:
                if frame.locator('[data-testid="stApp"], .stApp').count():
                    ok = True; break
            except Exception:
                pass
        if ok: break
        time.sleep(5)
    print('app is up' if ok else 'app did not finish loading within 5 minutes (it will be retried on the next run)')
    time.sleep(10)
    b.close()
