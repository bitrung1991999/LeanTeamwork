# -*- coding: utf-8 -*-
"""Read-only view of Native Antigravity IDE account.

Re-written to strictly support Native IDE without Cockpit dependencies.
"""

import os
import time
from datetime import datetime, timezone
from pathlib import Path
import sqlite3
import base64
import re

_native_acc_cache = None
_native_acc_time = 0.0

def mask_email(value):
    """Strip domain for clean account display without ellipsis masking."""
    value = str(value or '').strip()
    if '@' not in value:
        return value if value else 'Chưa rõ'
    local, _ = value.split('@', 1)
    return local if local else 'Chưa rõ'

def get_native_antigravity_account():
    """Discover native logged-in Antigravity / Antigravity IDE account.
    Reads directly from Antigravity IDE state database (state.vscdb).
    Cached for 10 seconds.
    """
    global _native_acc_cache, _native_acc_time
    now = time.monotonic()
    if _native_acc_cache is not None and (now - _native_acc_time) < 10.0:
        return _native_acc_cache

    candidates = []
    # Windows paths
    appdata = os.environ.get('APPDATA')
    if appdata:
        p_appdata = Path(appdata)
        candidates.extend([
            p_appdata / 'Antigravity IDE' / 'User' / 'globalStorage' / 'state.vscdb',
            p_appdata / 'Antigravity' / 'User' / 'globalStorage' / 'state.vscdb',
            p_appdata / 'Code' / 'User' / 'globalStorage' / 'state.vscdb',
        ])
    # macOS paths
    home = Path.home()
    mac_appsupport = home / 'Library' / 'Application Support'
    if mac_appsupport.exists():
        candidates.extend([
            mac_appsupport / 'Antigravity IDE' / 'User' / 'globalStorage' / 'state.vscdb',
            mac_appsupport / 'Antigravity' / 'User' / 'globalStorage' / 'state.vscdb',
        ])
    # Linux paths
    linux_config = home / '.config'
    if linux_config.exists():
        candidates.extend([
            linux_config / 'Antigravity IDE' / 'User' / 'globalStorage' / 'state.vscdb',
            linux_config / 'Antigravity' / 'User' / 'globalStorage' / 'state.vscdb',
        ])

    for db_path in candidates:
        if not db_path.exists():
            continue
        try:
            conn = sqlite3.connect(f'file:{db_path}?mode=ro', uri=True)
            c = conn.cursor()
            c.execute('SELECT value FROM ItemTable WHERE key = ?', ('antigravityUnifiedStateSync.userStatus',))
            row = c.fetchone()
            conn.close()
            if not row or not row[0]:
                continue
            val = row[0]
            email = None
            name = None
            plan = None
            try:
                dec = base64.b64decode(val)
                for sub in re.findall(rb'[A-Za-z0-9+/=]{16,}', dec):
                    try:
                        sdec = base64.b64decode(sub)
                        m = re.findall(rb'[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+', sdec)
                        if m and not email:
                            email = m[0].decode('latin1')
                        sdec_text = sdec.decode('utf-8', errors='ignore')
                        if 'Google AI Pro' in sdec_text:
                            plan = 'Google AI Pro'
                        elif 'Google AI Ultra' in sdec_text:
                            plan = 'Google AI Ultra'
                    except Exception:
                        pass
                if not email:
                    m = re.findall(rb'[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+', dec)
                    if m:
                        email = m[0].decode('latin1')
            except Exception:
                pass
            if not email:
                m = re.findall(r'[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+', str(val))
                if m:
                    email = m[0]
            if email:
                result = {
                    'email': email,
                    'name': name or mask_email(email),
                    'plan': plan or 'Antigravity IDE',
                    'source': str(db_path.parent.parent.parent.name),
                }
                _native_acc_cache = result
                _native_acc_time = now
                return result
        except Exception:
            continue

    _native_acc_cache = None
    _native_acc_time = now
    return None

def get_cockpit_accounts_with_quota():
    """Dummy to keep UI compatible, returns only native account."""
    native = get_native_antigravity_account()
    if native and native.get('email'):
        native_res = {
            'id': 'native_ide',
            'email': native['email'],
            'clean_name': mask_email(native['email']),
            'is_active': True,
            'has_cache': True,
            'g_5h': 100,
            'c_5h': 100,
            'g_w': 100,
            'c_w': 100,
            'status_text': f"[{native.get('plan') or 'Native IDE'}]",
            'score': 100,
        }
        return {
            'active': [native_res],
            'ready': [],
            'empty': [],
            'all': [native_res],
        }
    return {'active': [], 'ready': [], 'empty': [], 'all': []}

def get_cockpit_account_groups():
    """Returns only native account as IDE."""
    native = get_native_antigravity_account()
    res = {'antigravity': [], 'ide': []}
    if native and native.get('email'):
        res['ide'] = [{
            'id': 'native_ide',
            'label': mask_email(native['email']),
            'active': True,
        }]
    return res

def query_antigravity_data():
    """Return Native IDE data."""
    native = get_native_antigravity_account()
    if native and native.get('email'):
        return {
            'accounts': 1,
            'available_count': 1,
            'cooldown_count': 0,
            'missing_count': 0,
            'five_hour_pct': 100,
            'weekly_pct': 100,
            'claude_five_hour_pct': 100,
            'claude_weekly_pct': 100,
            'five_hour_reset': 'Native IDE',
            'weekly_reset': 'Active',
            'active_email': mask_email(native['email']),
            'active_account_id': 'native_ide',
            'active_account_name': native.get('name') or mask_email(native['email']),
            'healthy': True,
            'error': '',
            'timestamp': time.time(),
            'cache_updated_at': datetime.now(timezone.utc).isoformat(),
            'source': 'native-antigravity-ide',
            'plan': native.get('plan') or 'Antigravity IDE',
        }
    return {'healthy': False, 'accounts': 0, 'error': 'Chưa đăng nhập Antigravity IDE'}

def switch_active_account(account_id, email=None):
    return False


def get_antigravity_detail_rows():
    native = get_native_antigravity_account()
    if native and native.get("email"):
        return [{"id": "native_ide", "email": native["email"], "clean_name": mask_email(native["email"]), "is_active": True, "g_5h": 100, "c_5h": 100, "g_w": 100, "c_w": 100, "status_text": native.get("plan") or "Antigravity IDE"}]
    return []

def get_recent_antigravity_rows():
    return get_antigravity_detail_rows()

def get_top_quota_accounts(limit=4):
    return get_antigravity_detail_rows()[:limit]
