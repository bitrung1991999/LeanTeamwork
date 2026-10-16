# -*- coding: utf-8 -*-
"""
Config Manager for Cockpit Quota Widget V10 Pro Ultimate
Manages configuration discovery, dynamic sidecar ports, API keys, and widget state.
"""

import os
import json
import base64
from pathlib import Path

from .glass_materials import GLASS_MODES, GLASS_NAMES

# Base Paths
USER_PROFILE = Path.home()
ROOT_DIR = USER_PROFILE / '.antigravity_widget'
STATE_FILE = ROOT_DIR / 'antigravity_widget_state.json'


# Exact Pixel-Perfect Dimensions
# Compact HUD: the former 680px default left a large amount of decorative
# whitespace once the content was reduced to the essential account/quota tools.
BASE_W = 700
BASE_H = 48
MAX_HORIZONTAL_W = 1600
# The normal horizontal bar may grow taller while unlocked. Keep a modest cap
# so the quota controls stay a compact overlay instead of becoming a panel.
MAX_HORIZONTAL_H = 180
NANO_BASE_W = 340
NANO_BASE_H = 32
VERTICAL_BASE_W = 48
VERTICAL_BASE_H = 320
PILL_H = 36.0
TOP_Y = 6.0


THEMES = ['battery', 'bar', 'ring', 'orbit', 'cards', 'nano']





def load_state():
    """Loads widget state with defaults and validates constraints."""
    default_state = {
        'theme': 'cards',
        'locked': True,
        'rel_x': None,
        'rel_y': None,
        'x': 500,
        'y': 400,
        'width': BASE_W,
        'horizontal_width': BASE_W,
        'height': round(BASE_H * 1.4),
        'scale_percent': 140,
        'glass_mode': 'deep_obsidian',
        'orbit_green': 'blue',
        'orbit_chip_bg': 'glass',
        'chip_text_rgb': None,
        'custom_colors': [],
        'orientation': 'horizontal',
        'anchor_codex_w': 0,
        'anchor_codex_h': 0,
        'anchor_widget_w': 0,
        'anchor_widget_h': 0,
        'anchor_preset': 'top_right',
    }

    try:
        if STATE_FILE.exists():
            data = json.loads(STATE_FILE.read_text(encoding='utf-8'))
            theme_val = data.get('theme')
            if theme_val in ['Pin', 'battery']:
                theme_val = 'battery'
            elif theme_val in ['Thanh', 'bar']:
                theme_val = 'bar'
            elif theme_val in ['Vòng', 'ring']:
                theme_val = 'ring'
            elif theme_val in ['Viền chạy', 'orbit']:
                theme_val = 'orbit'
            elif theme_val in ['Card sáng', 'cards']:
                theme_val = 'cards'
            elif theme_val in ['Nano', 'nano']:
                theme_val = 'nano'
            else:
                theme_val = 'cards'

            glass_val = data.get('glass_mode', 'deep_obsidian')
            if glass_val not in GLASS_MODES:
                glass_val = 'deep_obsidian'

            orientation = data.get('orientation', 'horizontal')
            if orientation not in ('horizontal', 'vertical'):
                orientation = 'horizontal'

            # Load scale_percent with fallback to 140% for prominent display
            try:
                scale_pct = int(data.get('scale_percent', 140))
                if not (70 <= scale_pct <= 250):
                    scale_pct = 140
            except Exception:
                scale_pct = 140

            user_scale = float(scale_pct) / 100.0

            horizontal_min_w = NANO_BASE_W if theme_val == 'nano' else round(BASE_W * user_scale)
            horizontal_h = NANO_BASE_H if theme_val == 'nano' else round(BASE_H * user_scale)
            saved_width_raw = int(data.get('horizontal_width', data.get('width', horizontal_min_w)) or horizontal_min_w)
            # Reset runaway width values from previous manual drag errors
            max_limit = round(1600 * user_scale)
            if saved_width_raw > max_limit or saved_width_raw in (680, 560):
                saved_width_raw = horizontal_min_w
            saved_horizontal_width = max(
                horizontal_min_w,
                min(saved_width_raw, max_limit)
            )

            # Vertical is a dedicated column. Horizontal HUD bar computes height with scale_percent
            if orientation == 'vertical':
                w_val, h_val = VERTICAL_BASE_W, VERTICAL_BASE_H
            else:
                w_val = saved_horizontal_width
                h_val = horizontal_h

            # Ensure coordinates are strictly within visible screen space
            cur_x = int(data.get('x', 500))
            cur_y = int(data.get('y', 400))
            try:
                import ctypes
                u32 = ctypes.windll.user32
                v_x = u32.GetSystemMetrics(76)  # SM_XVIRTUALSCREEN
                v_y = u32.GetSystemMetrics(77)  # SM_YVIRTUALSCREEN
                v_w = u32.GetSystemMetrics(78)  # SM_CXVIRTUALSCREEN
                v_h = u32.GetSystemMetrics(79)  # SM_CYVIRTUALSCREEN
                if v_w > 0 and v_h > 0:
                    if not (v_x <= cur_x <= v_x + v_w - 100) or not (v_y <= cur_y <= v_y + v_h - 40):
                        cur_x = max(v_x + 50, min(v_x + v_w - w_val - 50, 100))
                        cur_y = max(v_y + 40, min(v_y + v_h - h_val - 50, 40))
            except Exception:
                pass

            default_state.update({
                'theme': theme_val,
                'locked': bool(data.get('locked', True)),
                'rel_x': data.get('rel_x', None),
                'rel_y': data.get('rel_y', None),
                'x': cur_x,
                'y': cur_y,
                'width': w_val,
                'horizontal_width': saved_horizontal_width,
                'height': h_val,
                'scale_percent': scale_pct,
                'glass_mode': glass_val,
                'orbit_green': data.get('orbit_green', 'blue') if data.get('orbit_green') in ('blue', 'green') else 'blue',
                'orbit_chip_bg': data.get('orbit_chip_bg', 'glass') if data.get('orbit_chip_bg') in ('glass', 'transparent') else 'glass',
                'chip_text_rgb': int(data.get('chip_text_rgb')) if isinstance(data.get('chip_text_rgb'), int) and 0 <= data.get('chip_text_rgb') <= 0xFFFFFF else None,
                'custom_colors': [int(v) & 0xFFFFFF for v in data.get('custom_colors', [])[:16] if isinstance(v, int)],
                'orientation': orientation,
                'anchor_codex_w': int(data.get('anchor_codex_w', 0) or 0),
                'anchor_codex_h': int(data.get('anchor_codex_h', 0) or 0),
                'anchor_widget_w': w_val,
                'anchor_widget_h': h_val,
                'anchor_preset': data.get('anchor_preset', 'top_right') if data.get('anchor_preset') in (
                    'top_left', 'top_center', 'top_right',
                    'bottom_left', 'bottom_center', 'bottom_right', 'custom'
                ) else 'top_right',
            })
    except Exception:
        pass

    return default_state


def save_state(state_dict):
    """Safely writes widget state to disk."""
    try:
        STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
        STATE_FILE.write_text(json.dumps(state_dict, ensure_ascii=False, indent=2), encoding='utf-8')
    except OSError:
        pass
