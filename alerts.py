"""
alerts.py — Telegram messages: the morning call and the evening check.

Needs one GitHub secret: TELEGRAM_BOT_TOKEN. The chat is found automatically the first time: send any message
(e.g. /start) to your bot once, and the next run stores your chat id in data/telegram_chat.txt.
TELEGRAM_CHAT_ID (secret or variable) overrides it. Without a token, alerts are skipped silently.
"""
from __future__ import annotations
import json, os, urllib.parse, urllib.request
from datetime import datetime
from zoneinfo import ZoneInfo
from pathlib import Path

HERE = Path(__file__).parent
CHAT_FILE = HERE / 'data' / 'telegram_chat.txt'
SENT = HERE / 'data' / 'tracker' / 'alerts_sent.json'


def _token():
    tok = os.environ.get('TELEGRAM_BOT_TOKEN', '').strip()
    if not tok:
        try:
            import streamlit as st                     # the app's own secret (Streamlit Cloud → Settings → Secrets)
            tok = str(st.secrets.get('TELEGRAM_BOT_TOKEN', '')).strip()
        except Exception:
            tok = ''
    return tok


def _api(method, **params):
    tok = _token()
    if not tok: return None
    data = urllib.parse.urlencode(params).encode()
    req = urllib.request.Request(f'https://api.telegram.org/bot{tok}/{method}', data=data)
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())


def chat_id():
    cid = os.environ.get('TELEGRAM_CHAT_ID', '').strip()
    if cid: return cid
    if CHAT_FILE.exists() and CHAT_FILE.read_text().strip(): return CHAT_FILE.read_text().strip()
    try:
        res = _api('getUpdates') or {}
    except Exception as e:
        print('telegram getUpdates failed:', e); return None
    if not res.get('ok', True): print('telegram getUpdates error:', res.get('description'))
    print(f"telegram: {len(res.get('result', []))} recent update(s) seen by the bot")
    for u in reversed(res.get('result', [])):
        m = u.get('message') or u.get('channel_post') or u.get('edited_message') or u.get('my_chat_member') or {}
        if m.get('chat', {}).get('id'):
            cid = str(m['chat']['id']); CHAT_FILE.write_text(cid); print('telegram chat id stored'); return cid
    print('telegram: no chat yet — send any message to your bot once'); return None


def send(text: str) -> bool:
    if not _token():
        print('telegram: no TELEGRAM_BOT_TOKEN secret — alert skipped'); return False
    cid = chat_id()
    if not cid: return False
    ok = True
    for i in range(0, len(text), 3900):
        try:
            res = _api('sendMessage', chat_id=cid, text=text[i:i + 3900], parse_mode='HTML', disable_web_page_preview='true',
                 disable_notification='true' if datetime.now(ZoneInfo('Asia/Kolkata')).hour < 6 else 'false')
            if not (res or {}).get('ok'): ok = False
        except Exception as e:
            print('telegram send failed:', e); ok = False
    return ok


def once(key: str) -> bool:
    """True the first time a key is seen (so a re-run never sends the same alert twice)."""
    s = json.loads(SENT.read_text()) if SENT.exists() else {}
    if key in s: return False
    s[key] = True; SENT.write_text(json.dumps(s, indent=0)); return True


def unmark(key: str):
    s = json.loads(SENT.read_text()) if SENT.exists() else {}
    s.pop(key, None); SENT.write_text(json.dumps(s, indent=0))
