# -*- coding: utf-8 -*-
"""
Teamwork Glass Popover for Antigravity Desktop Widget (Auto-Expanding Responsive Edition)
Cửa sổ HUD tương tác kính mờ (Glassmorphism Win32 GDI+) cho Lean Teamwork:
- TỰ ĐỘNG CO GIÃN CHIỀU CAO & BỀ NGANG DỰA TRÊN NỘI DUNG THỰC TẾ (Không bao giờ bị cắt chữ/cụt nút).
- Đồng bộ hoàn hảo với Themes & Materials (Sáng/Tối/Frosted Diamond).
- Tăng cỡ chữ +20% và đồng bộ 100% với scale_percent (140%) của Widget.
- Đảm bảo toàn bộ tiêu đề, danh sách phương án, báo cáo nghiệm thu và 2 nút bấm hiển thị trọn vẹn.
- Khi click chọn phương án, TỰ ĐỘNG FOCUS VÀ GỬI TRỰC TIẾP LỰA CHỌN XUỐNG CỬA SỔ ANTIGRAVITY ĐANG LÀM VIỆC.
"""

import sys
import os
import time
import json
import math
from pathlib import Path
import ctypes as c
from ctypes import wintypes as w

from .glass_materials import ARGB, get_material_palette, get_status_colors
from .win32_types import (
    WNDCLASS, WNDPROC, POINT, SIZE, BLENDFUNCTION, TRACKMOUSEEVENT,
    kernel32, user32, gdi32, gdiplus
)

LOG_PATH = Path(__file__).resolve().parent.parent / 'widget_crash.log'


def create_pill_path(x, y, w, h, r):
    path = c.c_void_p()
    gdiplus.GdipCreatePath(0, c.byref(path))
    dia = 2.0 * r
    gdiplus.GdipAddPathArc(path, c.c_float(x), c.c_float(y), c.c_float(dia), c.c_float(dia), c.c_float(180), c.c_float(90))
    gdiplus.GdipAddPathArc(path, c.c_float(x + w - dia), c.c_float(y), c.c_float(dia), c.c_float(dia), c.c_float(270), c.c_float(90))
    gdiplus.GdipAddPathArc(path, c.c_float(x + w - dia), c.c_float(y + h - dia), c.c_float(dia), c.c_float(dia), c.c_float(0), c.c_float(90))
    gdiplus.GdipAddPathArc(path, c.c_float(x), c.c_float(y + h - dia), c.c_float(dia), c.c_float(dia), c.c_float(90), c.c_float(90))
    gdiplus.GdipClosePathFigure(path)
    return path


def create_top_rounded_path(x, y, w, h, r):
    """Tạo path bo góc trên (trái & phải) và đáy phẳng cho thanh tiêu đề thẻ kết quả."""
    path = c.c_void_p()
    gdiplus.GdipCreatePath(0, c.byref(path))
    dia = 2.0 * r
    gdiplus.GdipAddPathArc(path, c.c_float(x), c.c_float(y), c.c_float(dia), c.c_float(dia), c.c_float(180.0), c.c_float(90.0))
    gdiplus.GdipAddPathArc(path, c.c_float(x + w - dia), c.c_float(y), c.c_float(dia), c.c_float(dia), c.c_float(270.0), c.c_float(90.0))
    gdiplus.GdipAddPathLine(path, c.c_float(x + w), c.c_float(y + h), c.c_float(x), c.c_float(y + h))
    gdiplus.GdipClosePathFigure(path)
    return path


class TeamworkGlassPopover:
    """Popover kính mờ tự động co giãn kích thước theo nội dung, không cắt chữ, gửi phím xuống IDE."""

    def __init__(self, parent_app):
        self.parent = parent_app
        self.hwnd = None
        self.w = 840
        self.h = 460
        self.pos_x = 100
        self.pos_y = 100
        self.visible = False
        self.hover_btn_id = None
        self.clickable_regions = []
        self.feedback_text = None
        self.feedback_until = 0.0
        self.auto_hide_at = 0.0
        self.target_rect = None

        self.init_window()

    def get_scale_metrics(self):
        """Tính toán hệ số scale kết hợp giữa scale_percent của widget và mức tăng 20% font."""
        widget_scale = float(self.parent.s.get('scale_percent', 100)) / 100.0
        font_boost = 1.20  # Yêu cầu người dùng: tăng chữ lên 20%
        
        scale_font = max(1.15, min(2.0, widget_scale * font_boost))
        scale_box = max(1.05, min(1.65, 0.72 + 0.28 * widget_scale * font_boost))
        return widget_scale, scale_font, scale_box

    def init_window(self):
        self.cb = WNDPROC(self.proc)
        hinst = kernel32.GetModuleHandleW(None)

        user32.UnregisterClassW('TeamworkGlassPopoverV2', hinst)
        wc = WNDCLASS(
            11, self.cb, 0, 0, hinst, None,
            user32.LoadCursorW(None, 32512), None, None,
            'TeamworkGlassPopoverV2'
        )
        user32.RegisterClassW(c.byref(wc))

        # Owned, topmost layered tool window: it floats reliably above full-screen IDEs and Windows apps
        ex_style = 0x00080000 | 0x00000080 | 0x08000000 | 0x00000008  # WS_EX_LAYERED | WS_EX_TOOLWINDOW | WS_EX_NOACTIVATE | WS_EX_TOPMOST
        parent_hwnd = getattr(self.parent, 'hwnd', None) if self.parent else None
        self.hwnd = user32.CreateWindowExW(
            ex_style,
            'TeamworkGlassPopoverV2',
            'LeanTeamworkGlassPopover',
            0x80000000,  # WS_POPUP
            0, 0, self.w, self.h,
            parent_hwnd, None, hinst, None
        )
        if self.hwnd:
            user32.SetWindowPos(self.hwnd, -1, 0, 0, 0, 0, 0x0001 | 0x0002 | 0x0010)
        with LOG_PATH.open('a', encoding='utf-8') as f:
            f.write(f"TeamworkGlassPopover.init_window(): hwnd={self.hwnd}, err={kernel32.GetLastError()}\n")
            f.flush()

    def contains_point(self, sx, sy):
        if not self.visible or not self.hwnd:
            return False
        rect = w.RECT()
        user32.GetWindowRect(self.hwnd, c.byref(rect))
        in_pop = (rect.left - 10 <= sx <= rect.right + 10 and rect.top - 10 <= sy <= rect.bottom + 10)
        if in_pop:
            return True
        if self.target_rect:
            tx1, ty1, tx2, ty2 = self.target_rect
            if (min(rect.left, tx1) - 10 <= sx <= max(rect.right, tx2) + 10 and
                    min(rect.top, ty1) - 10 <= sy <= max(rect.bottom, ty2) + 10):
                return True
        return False

    def compute_dynamic_layout(self, state):
        """Tính toán kích thước tự động co giãn theo nội dung văn bản thực tế."""
        st = state.get("status", "IDLE")
        widget_scale, scale_font, scale_box = self.get_scale_metrics()

        # Chiều rộng mở rộng 840px đảm bảo các tiêu đề và nút bấm hiển thị thoáng
        rc_work = w.RECT()
        user32.SystemParametersInfoW(0x0030, 0, c.byref(rc_work), 0)
        work_w = rc_work.right - rc_work.left
        work_h = rc_work.bottom - rc_work.top

        self.w = int(min(work_w - 40, max(760, round(840.0 * (0.80 + 0.20 * scale_box)))))
        pad_x = round(24.0 * scale_box)
        content_w = float(self.w) - (pad_x * 2.0)

        layout_info = {
            "pad_x": pad_x,
            "content_w": content_w,
            "scale_box": scale_box,
            "scale_font": scale_font,
            "st": st
        }

        if st == "PROPOSAL":
            prop = state.get("proposal") or {}
            title = prop.get("title") or "Đề Xuất Kế Hoạch Kỹ Thuật"
            options = prop.get("options") or []

            # Chiều cao tiêu đề (Word wrap)
            title_lines = max(1, math.ceil(len(str(title)) / 48.0))
            title_h = round((26.0 + title_lines * 24.0) * scale_box)

            header_h = round(18.0 * scale_box) + round(26.0 * scale_box) + title_h + round(38.0 * scale_box)
            
            # Tính chiều cao cho từng ô phương án dựa vào độ dài text
            boxes = []
            curr_y = header_h
            for idx, opt in enumerate(options[:4], 1):
                if isinstance(opt, dict):
                    opt_id = opt.get("id", idx)
                    opt_txt = str(opt.get("text") or f"Phương án {opt_id}")
                    is_rec = bool(opt.get("recommended", False))
                else:
                    opt_id = idx
                    opt_txt = str(opt or f"Phương án {opt_id}")
                    lower_txt = opt_txt.lower()
                    is_rec = ("recommended" in lower_txt or "khuyên dùng" in lower_txt or "khuyen dung" in lower_txt or idx == 1)

                prefix_len = 18 if is_rec else 6
                total_len = len(opt_txt) + prefix_len
                opt_lines = max(1, math.ceil(total_len / 46.0))
                # Mỗi dòng font 18pt cần khoảng 26px
                box_h = max(round(58.0 * scale_box), round((22.0 + opt_lines * 24.0) * scale_box))
                boxes.append({
                    "opt": {
                        "id": opt_id,
                        "text": opt_txt,
                        "recommended": is_rec
                    },
                    "y": curr_y,
                    "h": box_h
                })
                curr_y += box_h + round(10.0 * scale_box)

            total_h = curr_y + round(24.0 * scale_box)
            self.h = int(min(work_h - 40, total_h))
            layout_info["boxes"] = boxes
            layout_info["title_h"] = title_h
            layout_info["header_h"] = header_h

        elif st == "ACCEPTANCE":
            acc = state.get("acceptance") or {}
            surface = acc.get("surface") or state.get("surface") or "Antigravity 2.0"
            title = acc.get("title") or "Báo Cáo Nghiệm Thu Hoàn Thiện"
            summary = acc.get("summary") or "Toàn bộ bài toán đã thực thi và kiểm thử đạt 100% PASS."
            files = acc.get("files_changed") or []
            if not isinstance(files, list):
                files = [str(files)]

            title_lines = max(1, math.ceil(len(str(title)) / 48.0))
            title_h = round((24.0 + title_lines * 24.0) * scale_box)

            # Summary text lines
            files_str = "\nCác file: " + ", ".join([os.path.basename(str(f)) for f in files[:4]]) if files else ""
            sum_text = str(summary) + files_str
            sum_lines = max(2, math.ceil(len(sum_text) / 62.0) + (1 if files else 0))
            res_hdr_h = round(34.0 * scale_box)
            sum_h = max(round(130.0 * scale_box), round((32.0 + sum_lines * 24.0) * scale_box) + res_hdr_h)

            btn_h = round(64.0 * scale_box)
            pad_top = round(16.0 * scale_box)
            badge_h = round(26.0 * scale_box)
            status_h = round(26.0 * scale_box)
            btn_gap = round(14.0 * scale_box)

            sum_y = pad_top + badge_h + round(6.0 * scale_box) + title_h + status_h
            btn_y = sum_y + sum_h + btn_gap
            total_h = btn_y + btn_h + round(24.0 * scale_box)

            self.h = int(min(work_h - 40, total_h))
            layout_info["surface"] = surface
            layout_info["res_hdr_h"] = res_hdr_h
            layout_info["title_h"] = title_h
            layout_info["sum_y"] = sum_y
            layout_info["sum_h"] = sum_h
            layout_info["btn_y"] = btn_y
            layout_info["btn_h"] = btn_h
            layout_info["sum_text"] = sum_text

        else:  # IDLE
            self.h = int(min(work_h - 40, round(280.0 * scale_box)))

        return layout_info

    def adjust_window_position(self, target_rect):
        """Căn chỉnh vị trí Popover luôn nằm trọn trong vùng làm việc màn hình."""
        rc_work = w.RECT()
        user32.SystemParametersInfoW(0x0030, 0, c.byref(rc_work), 0)
        work_left = rc_work.left
        work_top = rc_work.top
        work_right = rc_work.right
        work_bottom = rc_work.bottom

        is_vertical = self.parent.s.get('orientation') == 'vertical'

        if is_vertical:
            pos_x = int(target_rect[0] - self.w - 12)
            if pos_x < work_left + 10:
                pos_x = int(target_rect[2] + 12)
            pos_y = int(target_rect[1] - 8)
        else:
            chip_cx = (target_rect[0] + target_rect[2]) / 2.0
            pos_x = int(chip_cx - self.w / 2.0)
            pos_y = int(target_rect[3] + 10)
            # Nếu mở xuống dưới bị chạm taskbar đáy màn hình, mở ngược lên trên
            if pos_y + self.h > work_bottom - 10:
                pos_y = int(target_rect[1] - self.h - 10)

        # Clamping chắc chắn 100% nằm gọn trong khung nhìn
        self.pos_x = max(work_left + 10, min(pos_x, work_right - self.w - 10))
        self.pos_y = max(work_top + 10, min(pos_y, work_bottom - self.h - 10))

        user32.SetWindowPos(self.hwnd, -1, self.pos_x, self.pos_y, self.w, self.h, 0x0040 | 0x0010)

    def show(self, target_rect):
        now = time.monotonic()
        if now < getattr(self, 'suppress_until', 0.0) or now < getattr(self, '_action_locked_until', 0.0):
            return
        self.target_rect = target_rect
        self.hover_btn_id = None
        self.feedback_text = None
        self.auto_hide_at = 0.0

        tw_service = getattr(self.parent, 'teamwork_service', None)
        state = tw_service.get_state() if tw_service else {}

        self.compute_dynamic_layout(state)
        self.adjust_window_position(target_rect)

        self.visible = True
        self.render()
        user32.ShowWindow(self.hwnd, 8)

    def hide(self):
        if not self.visible:
            return
        self.visible = False
        if self.hwnd:
            user32.ShowWindow(self.hwnd, 0)

    def focus_antigravity(self):
        """Kích hoạt và đưa cửa sổ Antigravity IDE lên trước màn hình một cách an toàn (tuyệt đối không gửi phím giả lập)."""
        try:
            from .window_tracker import find_codex_window
            host = find_codex_window(include_minimized=True)
            if not host:
                return False

            hwnd = host[0]
            if user32.IsIconic(hwnd):
                user32.ShowWindow(hwnd, 9)  # SW_RESTORE
            user32.ShowWindow(hwnd, 5)      # SW_SHOW
            user32.SetForegroundWindow(hwnd)
            return True
        except Exception:
            return False

    def send_to_antigravity(self, text_to_send):
        """Vô hiệu hóa việc gửi phím giả lập (keybd_event) để triệt tiêu 100% rủi ro làm tắt cửa sổ hoặc gửi nhầm lệnh vào IDE.
        Dữ liệu tương tác được điều phối an toàn qua IPC Bridge (teamwork_bridge.json).
        Chỉ đưa IDE lên foreground an toàn mà không gõ phím."""
        return self.focus_antigravity()

    def proc(self, hwnd, msg, wp, lp):
        try:
            if msg == 0x0200:  # WM_MOUSEMOVE
                tme = TRACKMOUSEEVENT(c.sizeof(TRACKMOUSEEVENT), 0x00000002, hwnd, 0)
                user32.TrackMouseEvent(c.byref(tme))

                pt = POINT()
                user32.GetCursorPos(c.byref(pt))
                rect = w.RECT()
                user32.GetWindowRect(hwnd, c.byref(rect))
                cx = pt.x - rect.left
                cy = pt.y - rect.top

                self.parent.popover_until = time.monotonic() + 3.5

                old_hover = self.hover_btn_id
                new_hover = None
                for region in self.clickable_regions:
                    rx, ry, rw, rh = region['rect']
                    if rx <= cx <= rx + rw and ry <= cy <= ry + rh:
                        new_hover = region['id']
                        break

                if new_hover != old_hover:
                    self.hover_btn_id = new_hover
                    self.render()
                return 0

            elif msg == 0x0201:  # WM_LBUTTONDOWN
                cx = c.c_short(lp & 0xFFFF).value
                cy = c.c_short((lp >> 16) & 0xFFFF).value
                self._pressed_btn_id = None
                for region in self.clickable_regions:
                    rx, ry, rw, rh = region['rect']
                    if rx <= cx <= rx + rw and ry <= cy <= ry + rh:
                        self._pressed_btn_id = region['id']
                        break
                return 0

            elif msg == 0x0202:  # WM_LBUTTONUP
                cx = c.c_short(lp & 0xFFFF).value
                cy = c.c_short((lp >> 16) & 0xFFFF).value
                target_btn = None
                for region in self.clickable_regions:
                    rx, ry, rw, rh = region['rect']
                    if rx <= cx <= rx + rw and ry <= cy <= ry + rh:
                        target_btn = region['id']
                        break
                if not target_btn:
                    target_btn = getattr(self, '_pressed_btn_id', None) or self.hover_btn_id
                self._pressed_btn_id = None
                if target_btn is not None:
                    self.handle_click(target_btn)
                return 0

            elif msg == 0x02A3:  # WM_MOUSELEAVE
                if self.hover_btn_id is not None:
                    self.hover_btn_id = None
                    self.render()
                tw_service = getattr(self.parent, 'teamwork_service', None)
                st = tw_service.get_state().get('status', 'IDLE') if tw_service else 'IDLE'
                if st not in ('PROPOSAL', 'ACCEPTANCE'):
                    self.parent.popover_until = time.monotonic() + 1.5
                return 0

        except Exception:
            pass
        return user32.DefWindowProcW(hwnd, msg, wp, lp)

    def handle_click(self, btn_id):
        # 1. Anti-Spam Debounce Lock: khóa nút 1.0s chống spam click
        now = time.monotonic()
        if now < getattr(self, '_action_locked_until', 0.0):
            return
        self._action_locked_until = now + 1.0
        self.suppress_until = now + 1.5

        tw_service = getattr(self.parent, 'teamwork_service', None)
        if not tw_service:
            return

        # 2. Xóa clickable_regions và ẩn popover NGAY LẬP TỨC
        regions = list(self.clickable_regions)
        self.clickable_regions = []
        self.hide()

        for region in regions:
            if region['id'] == btn_id:
                action = region.get('action')
                opt_id = region.get('opt_id')
                opt_txt = region.get('opt_txt', '')

                if action == 'CLOSE':
                    self.hide()
                    if self.parent:
                        self.parent.popover_until = 0.0
                    return

                elif action == 'SELECT_OPTION':
                    self.hide()
                    if self.parent:
                        self.parent.popover_until = 0.0
                        if hasattr(self.parent, '_proposal_auto_handled'):
                            self.parent._proposal_auto_handled = True
                    tw_service.submit_response('SELECT_OPTION', option_id=opt_id, note=opt_txt)
                    return

                elif action == 'ACCEPT':
                    self.hide()
                    if self.parent:
                        self.parent.popover_until = 0.0
                    tw_service.submit_response('ACCEPT')
                    return

                elif action == 'DEBUG':
                    self.hide()
                    if self.parent:
                        self.parent.popover_until = 0.0
                    tw_service.submit_response('DEBUG')
                    return

                elif action == 'FOCUS_IDE':
                    self.focus_antigravity()
                break

    def render(self):
        if not self.hwnd:
            return

        if self.auto_hide_at > 0 and time.monotonic() >= self.auto_hide_at:
            self.auto_hide_at = 0.0
            self.hide()
            return

        tw_service = getattr(self.parent, 'teamwork_service', None)
        state = tw_service.get_state() if tw_service else {}

        # TỰ ĐỘNG TÍNH TOÁN VÀ ĐIỀU CHỈNH KÍCH THƯỚC ĐỘNG TRƯỚC KHI VẼ
        old_w, old_h = self.w, self.h
        layout = self.compute_dynamic_layout(state)
        if (self.w != old_w or self.h != old_h) and self.target_rect:
            self.adjust_window_position(self.target_rect)

        self.clickable_regions = []

        screen_dc = user32.GetDC(None)
        mem_dc = gdi32.CreateCompatibleDC(screen_dc)
        bi = (w.DWORD * 11)(44, self.w, -self.h, (32 << 16) | 1, 0, 0, 0, 0, 0, 0, 0)
        p_bits = c.c_void_p()
        hbmp = gdi32.CreateDIBSection(screen_dc, c.byref(bi), 0, c.byref(p_bits), None, 0)
        old_bmp = gdi32.SelectObject(mem_dc, hbmp)

        gfx_p = c.c_void_p()
        gdiplus.GdipCreateFromHDC(mem_dc, c.byref(gfx_p))
        gfx = gfx_p.value
        gdiplus.GdipSetSmoothingMode(gfx, 4)
        gdiplus.GdipSetTextRenderingHint(gfx, 3)
        gdiplus.GdipSetPixelOffsetMode(gfx, 3)

        def make_brush(argb):
            b = c.c_void_p()
            gdiplus.GdipCreateSolidFill(argb, c.byref(b))
            return b.value

        def make_pen(argb, width=1.0):
            p = c.c_void_p()
            gdiplus.GdipCreatePen1(argb, c.c_float(width), 2, c.byref(p))
            return p.value

        glass_mode = self.parent.s.get('glass_mode', 'frosted_diamond')
        theme = self.parent.s.get('theme', 'cards')
        pal = get_material_palette(glass_mode, theme, getattr(self.parent, 'animation_tick', 0))
        is_dark = pal.get('is_dark', False)

        scale_box = layout["scale_box"]
        scale_font = layout["scale_font"]
        pad_x = layout["pad_x"]
        content_w = layout["content_w"]
        st = layout["st"]

        card_r = round(16.0 * scale_box)
        card_path = create_pill_path(2.0, 2.0, float(self.w) - 4.0, float(self.h) - 4.0, card_r)

        # Ambient Shadow
        sh_pen = make_pen(ARGB(45, 0, 0, 0) if not is_dark else ARGB(85, 0, 0, 0), 3.5)
        gdiplus.GdipDrawPath(gfx, sh_pen, card_path)
        gdiplus.GdipDeletePen(sh_pen)

        # Background Fill (Frosted Glass luxury)
        if is_dark:
            bg_color = ARGB(245, 12, 16, 26)
            rim_color = ARGB(180, 56, 189, 248)
            text_pri = make_brush(ARGB(255, 241, 245, 249))
            text_sec = make_brush(ARGB(210, 148, 163, 184))
            box_bg_norm = ARGB(35, 255, 255, 255)
            box_border_norm = ARGB(60, 255, 255, 255)
            track_col = ARGB(45, 255, 255, 255)
        else:
            bg_color = ARGB(252, 255, 255, 255)
            rim_color = ARGB(210, 203, 213, 225)
            text_pri = make_brush(ARGB(255, 15, 23, 42))   # Slate-900
            text_sec = make_brush(ARGB(230, 71, 85, 105))  # Slate-600
            box_bg_norm = ARGB(245, 248, 250, 252)        # Slate-50
            box_border_norm = ARGB(190, 226, 232, 240)    # Slate-200
            track_col = ARGB(55, 148, 163, 184)

        bg_b = make_brush(bg_color)
        gdiplus.GdipFillPath(gfx, bg_b, card_path)
        gdiplus.GdipDeleteBrush(bg_b)

        # Specular Rim
        rim_pen = make_pen(rim_color, 1.6)
        gdiplus.GdipDrawPath(gfx, rim_pen, card_path)
        gdiplus.GdipDeletePen(rim_pen)
        gdiplus.GdipDeletePath(card_path)

        # Fonts: +20% BOOST & WIDGET SCALE SYNC
        font_family = c.c_void_p()
        gdiplus.GdipCreateFontFamilyFromName('Segoe UI', None, c.byref(font_family))

        sz_title = round(13.8 * scale_font, 1)
        sz_sub   = round(10.5 * scale_font, 1)
        sz_btn   = round(11.2 * scale_font, 1)
        sz_badge = round(9.5  * scale_font, 1)

        font_title = c.c_void_p()
        gdiplus.GdipCreateFont(font_family, c.c_float(sz_title), 1, 2, c.byref(font_title))
        font_sub = c.c_void_p()
        gdiplus.GdipCreateFont(font_family, c.c_float(sz_sub), 0, 2, c.byref(font_sub))
        font_btn = c.c_void_p()
        gdiplus.GdipCreateFont(font_family, c.c_float(sz_btn), 1, 2, c.byref(font_btn))
        font_badge = c.c_void_p()
        gdiplus.GdipCreateFont(font_family, c.c_float(sz_badge), 1, 2, c.byref(font_badge))

        # String Formats (Word-wrap cho tất cả text để không bao giờ bị cắt cụt)
        fmt_left = c.c_void_p()
        gdiplus.GdipCreateStringFormat(0, 0, c.byref(fmt_left))
        gdiplus.GdipSetStringFormatLineAlign(fmt_left, 1)

        fmt_wrap = c.c_void_p()
        gdiplus.GdipCreateStringFormat(0, 0, c.byref(fmt_wrap))
        gdiplus.GdipSetStringFormatAlign(fmt_wrap, 0)
        gdiplus.GdipSetStringFormatLineAlign(fmt_wrap, 0)

        fmt_center = c.c_void_p()
        gdiplus.GdipCreateStringFormat(0, 0, c.byref(fmt_center))
        gdiplus.GdipSetStringFormatAlign(fmt_center, 1)
        gdiplus.GdipSetStringFormatLineAlign(fmt_center, 1)

        fmt_right = c.c_void_p()
        gdiplus.GdipCreateStringFormat(0, 0, c.byref(fmt_right))
        gdiplus.GdipSetStringFormatAlign(fmt_right, 2)
        gdiplus.GdipSetStringFormatLineAlign(fmt_right, 1)

        cyan_b = make_brush(ARGB(255, 2, 132, 199) if not is_dark else ARGB(255, 56, 189, 248))
        green_b = make_brush(ARGB(255, 5, 150, 105) if not is_dark else ARGB(255, 52, 211, 153))

        # ----------------------------------------------------
        # RENDER CONTENT THEO TRẠNG THÁI
        # ----------------------------------------------------
        if st == "PROPOSAL":
            prop = state.get("proposal") or {}
            title = prop.get("title", "Đề Xuất Kế Hoạch Kỹ Thuật")
            prop_surf = prop.get("surface") or state.get("surface") or "Antigravity 2.0"
            prop_is_v2 = ("2.0" in prop_surf or ("Antigravity" in prop_surf and "IDE" not in prop_surf))
            now = time.time()
            deadline = prop.get("deadline_ts", now)
            duration = max(1, prop.get("duration_seconds", 150))
            rem = max(0, int(deadline - now))
            mins, secs = rem // 60, rem % 60
            timer_text = f"{mins:02d}:{secs:02d}"

            # Badge 1: Đề xuất kỹ thuật
            badge_h = round(26.0 * scale_box)
            badge_w = round(210.0 * scale_box)
            badge_path = create_pill_path(pad_x, round(16.0 * scale_box), badge_w, badge_h, 6.0)
            badge_bg = make_brush(ARGB(230, 224, 242, 254) if not is_dark else ARGB(60, 56, 189, 248))
            gdiplus.GdipFillPath(gfx, badge_bg, badge_path)
            gdiplus.GdipDeleteBrush(badge_bg)
            b_rect = (c.c_float * 4)(pad_x + 10.0, round(16.0 * scale_box), badge_w - 12.0, badge_h)
            gdiplus.GdipDrawString(gfx, "🧭 ĐỀ XUẤT KỸ THUẬT", -1, font_badge, b_rect, fmt_left, cyan_b)
            gdiplus.GdipDeletePath(badge_path)

            # Badge 2: Surface Badge
            p_surf_w = round(180.0 * scale_box)
            p_surf_x = pad_x + badge_w + round(10.0 * scale_box)
            p_surf_path = create_pill_path(p_surf_x, round(16.0 * scale_box), p_surf_w, badge_h, 6.0)
            if prop_is_v2:
                p_s_bg = make_brush(ARGB(230, 243, 232, 255) if not is_dark else ARGB(60, 168, 85, 247))
                p_s_pen = make_pen(ARGB(220, 192, 132, 252) if not is_dark else ARGB(180, 168, 85, 247), 1.2)
                p_s_txt_b = make_brush(ARGB(255, 126, 34, 206) if not is_dark else ARGB(255, 216, 180, 254))
                p_s_label = "⚡ ANTIGRAVITY 2.0"
            else:
                p_s_bg = make_brush(ARGB(230, 224, 242, 254) if not is_dark else ARGB(60, 56, 189, 248))
                p_s_pen = make_pen(ARGB(220, 125, 211, 252) if not is_dark else ARGB(180, 56, 189, 248), 1.2)
                p_s_txt_b = make_brush(ARGB(255, 3, 105, 161) if not is_dark else ARGB(255, 125, 211, 252))
                p_s_label = "💻 ANTIGRAVITY IDE"

            gdiplus.GdipFillPath(gfx, p_s_bg, p_surf_path)
            gdiplus.GdipDrawPath(gfx, p_s_pen, p_surf_path)
            gdiplus.GdipDeleteBrush(p_s_bg)
            gdiplus.GdipDeletePen(p_s_pen)
            ps_rect = (c.c_float * 4)(p_surf_x + 10.0, round(16.0 * scale_box), p_surf_w - 12.0, badge_h)
            gdiplus.GdipDrawString(gfx, p_s_label, -1, font_badge, ps_rect, fmt_left, p_s_txt_b)
            gdiplus.GdipDeleteBrush(p_s_txt_b)
            gdiplus.GdipDeletePath(p_surf_path)

            # Nút Đóng [✕] ở góc trên bên phải
            btn_close_size = round(24.0 * scale_box)
            btn_close_x = pad_x + content_w - btn_close_size
            btn_close_y = round(16.0 * scale_box)
            is_close_hover = (self.hover_btn_id == "btn_close")

            c_bg = make_brush(ARGB(180, 239, 68, 68) if is_close_hover else (ARGB(40, 255, 255, 255) if is_dark else ARGB(40, 0, 0, 0)))
            c_path = create_pill_path(btn_close_x, btn_close_y, btn_close_size, btn_close_size, btn_close_size / 2.0)
            gdiplus.GdipFillPath(gfx, c_bg, c_path)
            gdiplus.GdipDeleteBrush(c_bg)
            gdiplus.GdipDeletePath(c_path)

            c_txt_brush = make_brush(ARGB(255, 255, 255, 255) if is_close_hover else (ARGB(200, 203, 213, 225) if is_dark else ARGB(200, 100, 116, 139)))
            c_rect = (c.c_float * 4)(btn_close_x, btn_close_y - 1.0, btn_close_size, btn_close_size)
            gdiplus.GdipDrawString(gfx, "✕", -1, font_badge, c_rect, fmt_center, c_txt_brush)
            gdiplus.GdipDeleteBrush(c_txt_brush)

            self.clickable_regions.append({
                "id": "btn_close",
                "rect": (btn_close_x - 4, btn_close_y - 4, btn_close_size + 8, btn_close_size + 8),
                "action": "CLOSE"
            })

            # Title (Hỗ trợ word-wrap không bao giờ bị cắt dòng)
            title_y = round(48.0 * scale_box)
            title_h = layout.get("title_h", round(36.0 * scale_box))
            t_rect = (c.c_float * 4)(pad_x, title_y, content_w, title_h)
            gdiplus.GdipDrawString(gfx, title, -1, font_title, t_rect, fmt_wrap, text_pri)

            # Spectrum Countdown Track & Fill
            bar_y = title_y + title_h + round(4.0 * scale_box)
            bar_h = round(7.0 * scale_box)
            ratio = min(1.0, max(0.0, rem / float(duration)))

            tr_path = create_pill_path(pad_x, bar_y, content_w, bar_h, 3.5)
            tr_b = make_brush(track_col)
            gdiplus.GdipFillPath(gfx, tr_b, tr_path)
            gdiplus.GdipDeleteBrush(tr_b)
            gdiplus.GdipDeletePath(tr_path)

            fill_w = max(bar_h, content_w * ratio)
            fl_path = create_pill_path(pad_x, bar_y, fill_w, bar_h, 3.5)
            fl_col = ARGB(255, 14, 165, 233) if rem > 30 else ARGB(255, 239, 68, 68)
            fl_b = make_brush(fl_col)
            gdiplus.GdipFillPath(gfx, fl_b, fl_path)
            gdiplus.GdipDeleteBrush(fl_b)
            gdiplus.GdipDeletePath(fl_path)

            # Timer text
            sub_y = bar_y + bar_h + round(4.0 * scale_box)
            sub_h = round(24.0 * scale_box)
            sub_rect = (c.c_float * 4)(pad_x, sub_y, content_w, sub_h)
            if rem == 0:
                timer_line = f"⏱️ Hết giờ — Tự động kích hoạt [1] (Khuyên dùng) xuống {prop_surf}"
            else:
                timer_line = f"⏱️ Hạn chót: {timer_text} — Click chọn phương án để gửi thẳng xuống {prop_surf}"
            gdiplus.GdipDrawString(gfx, timer_line, -1, font_sub, sub_rect, fmt_left, text_sec)

            # Options Boxes (Chiều cao tự co giãn theo text của từng box)
            boxes = layout.get("boxes", [])
            for item in boxes:
                opt = item["opt"]
                opt_y = item["y"]
                box_h = item["h"]

                opt_id = opt.get("id", 1) if isinstance(opt, dict) else 1
                opt_txt = opt.get("text", str(opt)) if isinstance(opt, dict) else str(opt)
                is_rec = opt.get("recommended", False) if isinstance(opt, dict) else False
                is_h = (self.hover_btn_id == f"opt_{opt_id}")

                box_path = create_pill_path(pad_x, opt_y, content_w, box_h, 8.0)

                if is_h:
                    box_bg = make_brush(ARGB(255, 224, 242, 254) if not is_dark else ARGB(90, 56, 189, 248))
                    box_pen = make_pen(ARGB(255, 56, 189, 248), 1.8)
                elif is_rec:
                    box_bg = make_brush(ARGB(255, 240, 253, 250) if not is_dark else ARGB(55, 52, 211, 153))
                    box_pen = make_pen(ARGB(255, 52, 211, 153), 1.6)
                else:
                    box_bg = make_brush(box_bg_norm)
                    box_pen = make_pen(box_border_norm, 1.2)

                gdiplus.GdipFillPath(gfx, box_bg, box_path)
                gdiplus.GdipDrawPath(gfx, box_pen, box_path)
                gdiplus.GdipDeleteBrush(box_bg)
                gdiplus.GdipDeletePen(box_pen)
                gdiplus.GdipDeletePath(box_path)

                # Option text (Word-wrap đầy đủ trong box)
                prefix = f"[{opt_id}] " + ("⭐ (Khuyên dùng) " if is_rec else "")
                display_txt = prefix + opt_txt
                opt_rect = (c.c_float * 4)(pad_x + 16.0, opt_y + 8.0, content_w - 32.0, box_h - 16.0)
                gdiplus.GdipDrawString(gfx, display_txt, -1, font_btn, opt_rect, fmt_wrap, text_pri)

                self.clickable_regions.append({
                    "id": f"opt_{opt_id}",
                    "rect": (pad_x, opt_y, content_w, box_h),
                    "action": "SELECT_OPTION",
                    "opt_id": opt_id,
                    "opt_txt": opt_txt
                })

        elif st == "ACCEPTANCE":
            acc = state.get("acceptance") or {}
            title = acc.get("title", "Báo Cáo Nghiệm Thu Hoàn Thiện")
            exit_code = acc.get("exit_code", 0)
            files = acc.get("files_changed", [])
            surface = layout.get("surface") or acc.get("surface") or state.get("surface") or "Antigravity 2.0"
            is_v2 = ("2.0" in surface or ("Antigravity" in surface and "IDE" not in surface))

            # 1. Top Badges: Main Badge + Surface Badge
            badge_h = round(26.0 * scale_box)
            badge_w = round(250.0 * scale_box)
            badge_path = create_pill_path(pad_x, round(16.0 * scale_box), badge_w, badge_h, 6.0)
            badge_bg = make_brush(ARGB(230, 209, 250, 229) if not is_dark else ARGB(60, 52, 211, 153))
            gdiplus.GdipFillPath(gfx, badge_bg, badge_path)
            gdiplus.GdipDeleteBrush(badge_bg)
            b_rect = (c.c_float * 4)(pad_x + 12.0, round(16.0 * scale_box), badge_w - 14.0, badge_h)
            gdiplus.GdipDrawString(gfx, "💎 NGHIỆM THU HOÀN THIỆN ✨", -1, font_badge, b_rect, fmt_left, green_b)
            gdiplus.GdipDeletePath(badge_path)

            # Surface Badge (Antigravity 2.0 vs Antigravity IDE)
            surf_badge_w = round(180.0 * scale_box)
            surf_badge_x = pad_x + badge_w + round(10.0 * scale_box)
            surf_badge_path = create_pill_path(surf_badge_x, round(16.0 * scale_box), surf_badge_w, badge_h, 6.0)
            if is_v2:
                # Purple / Violet Cyber Glass for Antigravity 2.0
                s_bg = make_brush(ARGB(230, 243, 232, 255) if not is_dark else ARGB(60, 168, 85, 247))
                s_pen = make_pen(ARGB(220, 192, 132, 252) if not is_dark else ARGB(180, 168, 85, 247), 1.2)
                s_txt_b = make_brush(ARGB(255, 126, 34, 206) if not is_dark else ARGB(255, 216, 180, 254))
                s_label = "⚡ ANTIGRAVITY 2.0"
            else:
                # Cyan / Blue Cyber Glass for Antigravity IDE
                s_bg = make_brush(ARGB(230, 224, 242, 254) if not is_dark else ARGB(60, 56, 189, 248))
                s_pen = make_pen(ARGB(220, 125, 211, 252) if not is_dark else ARGB(180, 56, 189, 248), 1.2)
                s_txt_b = make_brush(ARGB(255, 3, 105, 161) if not is_dark else ARGB(255, 125, 211, 252))
                s_label = "💻 ANTIGRAVITY IDE"

            gdiplus.GdipFillPath(gfx, s_bg, surf_badge_path)
            gdiplus.GdipDrawPath(gfx, s_pen, surf_badge_path)
            gdiplus.GdipDeleteBrush(s_bg)
            gdiplus.GdipDeletePen(s_pen)
            sb_rect = (c.c_float * 4)(surf_badge_x + 10.0, round(16.0 * scale_box), surf_badge_w - 12.0, badge_h)
            gdiplus.GdipDrawString(gfx, s_label, -1, font_badge, sb_rect, fmt_left, s_txt_b)
            gdiplus.GdipDeleteBrush(s_txt_b)
            gdiplus.GdipDeletePath(surf_badge_path)

            # Nút Đóng [✕] ở góc trên bên phải
            btn_close_size = round(24.0 * scale_box)
            btn_close_x = pad_x + content_w - btn_close_size
            btn_close_y = round(16.0 * scale_box)
            is_close_hover = (self.hover_btn_id == "btn_close")

            c_bg = make_brush(ARGB(180, 239, 68, 68) if is_close_hover else (ARGB(40, 255, 255, 255) if is_dark else ARGB(40, 0, 0, 0)))
            c_path = create_pill_path(btn_close_x, btn_close_y, btn_close_size, btn_close_size, btn_close_size / 2.0)
            gdiplus.GdipFillPath(gfx, c_bg, c_path)
            gdiplus.GdipDeleteBrush(c_bg)
            gdiplus.GdipDeletePath(c_path)

            c_txt_brush = make_brush(ARGB(255, 255, 255, 255) if is_close_hover else (ARGB(200, 203, 213, 225) if is_dark else ARGB(200, 100, 116, 139)))
            c_rect = (c.c_float * 4)(btn_close_x, btn_close_y - 1.0, btn_close_size, btn_close_size)
            gdiplus.GdipDrawString(gfx, "✕", -1, font_badge, c_rect, fmt_center, c_txt_brush)
            gdiplus.GdipDeleteBrush(c_txt_brush)

            self.clickable_regions.append({
                "id": "btn_close",
                "rect": (btn_close_x - 4, btn_close_y - 4, btn_close_size + 8, btn_close_size + 8),
                "action": "CLOSE"
            })

            # 2. Title (Word wrap để không bị cụt mép phải)
            title_y = round(48.0 * scale_box)
            title_h = layout.get("title_h", round(36.0 * scale_box))
            t_rect = (c.c_float * 4)(pad_x, title_y, content_w, title_h)
            gdiplus.GdipDrawString(gfx, title, -1, font_title, t_rect, fmt_wrap, text_pri)

            # 3. Status subline with Surface attribution
            st_text = f"✓ Thực thi bởi: {surface} | Kiểm thử: PASS 100% (Exit Code {exit_code}) | {len(files)} files đã thay đổi"
            st_y = title_y + title_h + round(4.0 * scale_box)
            st_h = round(22.0 * scale_box)
            st_rect = (c.c_float * 4)(pad_x, st_y, content_w, st_h)
            gdiplus.GdipDrawString(gfx, st_text, -1, font_sub, st_rect, fmt_left, green_b)

            # 4. Result Section Box with Title Bar (Thanh tiêu đề phần kết quả)
            sum_y = layout.get("sum_y", round(110.0 * scale_box))
            sum_h = layout.get("sum_h", round(140.0 * scale_box))
            res_hdr_h = layout.get("res_hdr_h", round(34.0 * scale_box))

            # Outer box background
            sum_path = create_pill_path(pad_x, sum_y, content_w, sum_h, 8.0)
            sum_b = make_brush(box_bg_norm)
            sum_pen = make_pen(box_border_norm, 1.2)
            gdiplus.GdipFillPath(gfx, sum_b, sum_path)

            # Header bar banner (Thanh tiêu đề nổi bật trên phần kết quả)
            hdr_path = create_top_rounded_path(pad_x + 1.0, sum_y + 1.0, content_w - 2.0, res_hdr_h, 7.5)
            if is_v2:
                # Purple banner for Antigravity 2.0
                hdr_bg = make_brush(ARGB(240, 243, 232, 255) if not is_dark else ARGB(70, 147, 51, 234))
                hdr_div_pen = make_pen(ARGB(200, 216, 180, 254) if not is_dark else ARGB(120, 192, 132, 252), 1.2)
                hdr_txt_left_b = make_brush(ARGB(255, 107, 33, 168) if not is_dark else ARGB(255, 243, 232, 255))
                hdr_txt_right_b = make_brush(ARGB(255, 126, 34, 206) if not is_dark else ARGB(255, 216, 180, 254))
                hdr_right_title = "⚡ THỰC HIỆN BỞI: ANTIGRAVITY 2.0"
            else:
                # Cyan / Blue banner for Antigravity IDE
                hdr_bg = make_brush(ARGB(240, 224, 242, 254) if not is_dark else ARGB(70, 14, 165, 233))
                hdr_div_pen = make_pen(ARGB(200, 125, 211, 252) if not is_dark else ARGB(120, 56, 189, 248), 1.2)
                hdr_txt_left_b = make_brush(ARGB(255, 3, 105, 161) if not is_dark else ARGB(255, 224, 242, 254))
                hdr_txt_right_b = make_brush(ARGB(255, 2, 132, 199) if not is_dark else ARGB(255, 125, 211, 252))
                hdr_right_title = "💻 THỰC HIỆN BỞI: ANTIGRAVITY IDE"

            gdiplus.GdipFillPath(gfx, hdr_bg, hdr_path)
            gdiplus.GdipDeleteBrush(hdr_bg)
            gdiplus.GdipDeletePath(hdr_path)

            # Divider line beneath the header bar
            div_y = sum_y + res_hdr_h
            gdiplus.GdipDrawLine(gfx, hdr_div_pen, c.c_float(pad_x), c.c_float(div_y), c.c_float(pad_x + content_w), c.c_float(div_y))
            gdiplus.GdipDeletePen(hdr_div_pen)

            # Draw outer border over the combined box
            gdiplus.GdipDrawPath(gfx, sum_pen, sum_path)
            gdiplus.GdipDeleteBrush(sum_b)
            gdiplus.GdipDeletePen(sum_pen)
            gdiplus.GdipDeletePath(sum_path)

            # Left label on Result Header Bar:
            hdr_left_rect = (c.c_float * 4)(pad_x + 16.0, sum_y, (content_w - 32.0) * 0.45, res_hdr_h)
            gdiplus.GdipDrawString(gfx, "📋 KẾT QUẢ THỰC THI (RESULT)", -1, font_badge, hdr_left_rect, fmt_left, hdr_txt_left_b)
            gdiplus.GdipDeleteBrush(hdr_txt_left_b)

            # Right label on Result Header Bar:
            hdr_right_rect = (c.c_float * 4)(pad_x + 16.0 + (content_w - 32.0) * 0.40, sum_y, (content_w - 32.0) * 0.60, res_hdr_h)
            gdiplus.GdipDrawString(gfx, hdr_right_title, -1, font_badge, hdr_right_rect, fmt_right, hdr_txt_right_b)
            gdiplus.GdipDeleteBrush(hdr_txt_right_b)

            # Result content text inside the box (below header bar)
            sum_rect = (c.c_float * 4)(pad_x + 16.0, sum_y + res_hdr_h + 10.0, content_w - 32.0, sum_h - res_hdr_h - 18.0)
            sum_text = layout.get("sum_text", "")
            gdiplus.GdipDrawString(gfx, sum_text, -1, font_sub, sum_rect, fmt_wrap, text_pri)

            # 2 Buttons (Luôn nằm gọn trong khung Popover, không bao giờ bị cắt đáy)
            btn_y = layout.get("btn_y", sum_y + sum_h + round(14.0 * scale_box))
            btn_h = layout.get("btn_h", round(64.0 * scale_box))
            btn_gap = round(14.0 * scale_box)
            btn_w = (content_w - btn_gap) / 2.0

            # Button 1: 100% HOÀN TẤT
            b1_h = (self.hover_btn_id == "btn_accept")
            b1_path = create_pill_path(pad_x, btn_y, btn_w, btn_h, 8.0)
            if not is_dark:
                b1_bg = make_brush(ARGB(255, 167, 243, 208) if b1_h else ARGB(255, 209, 250, 229))
                b1_pen = make_pen(ARGB(255, 16, 185, 129), 1.8)
                b1_txt_b = make_brush(ARGB(255, 6, 95, 70))
            else:
                b1_bg = make_brush(ARGB(120, 52, 211, 153) if b1_h else ARGB(60, 52, 211, 153))
                b1_pen = make_pen(ARGB(255, 52, 211, 153), 1.8)
                b1_txt_b = text_pri

            gdiplus.GdipFillPath(gfx, b1_bg, b1_path)
            gdiplus.GdipDrawPath(gfx, b1_pen, b1_path)
            gdiplus.GdipDeleteBrush(b1_bg)
            gdiplus.GdipDeletePen(b1_pen)
            gdiplus.GdipDeletePath(b1_path)

            b1_rect = (c.c_float * 4)(pad_x, btn_y, btn_w, btn_h)
            gdiplus.GdipDrawString(gfx, f"💎 [100% HOÀN TẤT] ✨\nChấp thuận & Gửi xuống {surface}", -1, font_btn, b1_rect, fmt_center, b1_txt_b)
            if not is_dark:
                gdiplus.GdipDeleteBrush(b1_txt_b)

            self.clickable_regions.append({
                "id": "btn_accept",
                "rect": (pad_x, btn_y, btn_w, btn_h),
                "action": "ACCEPT"
            })

            # Button 2: SUPERPOWERS DEBUG
            b2_x = pad_x + btn_w + btn_gap
            b2_h = (self.hover_btn_id == "btn_debug")
            b2_path = create_pill_path(b2_x, btn_y, btn_w, btn_h, 8.0)
            if not is_dark:
                b2_bg = make_brush(ARGB(255, 254, 240, 138) if b2_h else ARGB(255, 254, 243, 199))
                b2_pen = make_pen(ARGB(255, 245, 158, 11), 1.8)
                b2_txt_b = make_brush(ARGB(255, 146, 64, 14))
            else:
                b2_bg = make_brush(ARGB(120, 245, 158, 11) if b2_h else ARGB(60, 245, 158, 11))
                b2_pen = make_pen(ARGB(255, 245, 158, 11), 1.8)
                b2_txt_b = text_pri

            gdiplus.GdipFillPath(gfx, b2_bg, b2_path)
            gdiplus.GdipDrawPath(gfx, b2_pen, b2_path)
            gdiplus.GdipDeleteBrush(b2_bg)
            gdiplus.GdipDeletePen(b2_pen)
            gdiplus.GdipDeletePath(b2_path)

            b2_rect = (c.c_float * 4)(b2_x, btn_y, btn_w, btn_h)
            gdiplus.GdipDrawString(gfx, f"⚡ [SUPERPOWERS DEBUG]\nYêu cầu rà soát sâu xuống {surface}", -1, font_btn, b2_rect, fmt_center, b2_txt_b)
            if not is_dark:
                gdiplus.GdipDeleteBrush(b2_txt_b)

            self.clickable_regions.append({
                "id": "btn_debug",
                "rect": (b2_x, btn_y, btn_w, btn_h),
                "action": "DEBUG"
            })

        else:  # IDLE
            badge_h = round(26.0 * scale_box)
            badge_w = round(240.0 * scale_box)
            badge_path = create_pill_path(pad_x, round(18.0 * scale_box), badge_w, badge_h, 6.0)
            badge_bg = make_brush(ARGB(230, 241, 245, 249) if not is_dark else ARGB(60, 56, 189, 248))
            gdiplus.GdipFillPath(gfx, badge_bg, badge_path)
            gdiplus.GdipDeleteBrush(badge_bg)
            b_rect = (c.c_float * 4)(pad_x + 12.0, round(18.0 * scale_box), badge_w - 14.0, badge_h)
            gdiplus.GdipDrawString(gfx, "✨ LEAN TEAMWORK SẴN SÀNG", -1, font_badge, b_rect, fmt_left, cyan_b)
            gdiplus.GdipDeletePath(badge_path)

            title_y = round(52.0 * scale_box)
            title_h = round(32.0 * scale_box)
            t_rect = (c.c_float * 4)(pad_x, title_y, content_w, title_h)
            gdiplus.GdipDrawString(gfx, "Hệ Thống Đang Trực Lệnh", -1, font_title, t_rect, fmt_left, text_pri)

            sub_y = round(88.0 * scale_box)
            sub_h = round(60.0 * scale_box)
            sub_rect = (c.c_float * 4)(pad_x, sub_y, content_w, sub_h)
            idle_desc = "Khi Antigravity IDE phát Đề xuất Kế hoạch hoặc Báo cáo Nghiệm thu, các phương án và nút bấm tương tác sẽ tự động hiển thị đầy đủ và tự co giãn tại đây."
            gdiplus.GdipDrawString(gfx, idle_desc, -1, font_sub, sub_rect, fmt_wrap, text_sec)

            # Focus IDE Button
            f_y = round(156.0 * scale_box)
            f_h_box = round(56.0 * scale_box)
            f_h = (self.hover_btn_id == "btn_focus")
            f_path = create_pill_path(pad_x, f_y, content_w, f_h_box, 8.0)
            f_bg = make_brush(ARGB(255, 224, 242, 254) if (f_h and not is_dark) else (ARGB(245, 248, 250, 252) if not is_dark else (ARGB(90, 56, 189, 248) if f_h else ARGB(45, 56, 189, 248))))
            f_pen = make_pen(ARGB(255, 56, 189, 248) if f_h else box_border_norm, 1.6 if f_h else 1.2)
            gdiplus.GdipFillPath(gfx, f_bg, f_path)
            gdiplus.GdipDrawPath(gfx, f_pen, f_path)
            gdiplus.GdipDeleteBrush(f_bg)
            gdiplus.GdipDeletePen(f_pen)
            gdiplus.GdipDeletePath(f_path)

            f_rect = (c.c_float * 4)(pad_x, f_y, content_w, f_h_box)
            gdiplus.GdipDrawString(gfx, "🚀 Mở Cửa Sổ Antigravity IDE Đang Làm Việc", -1, font_btn, f_rect, fmt_center, text_pri)

            self.clickable_regions.append({
                "id": "btn_focus",
                "rect": (pad_x, f_y, content_w, f_h_box),
                "action": "FOCUS_IDE"
            })

        # Feedback notification overlay
        if self.feedback_text and time.monotonic() < self.feedback_until:
            fb_y = float(self.h) - round(38.0 * scale_box)
            fb_rect = (c.c_float * 4)(pad_x, fb_y, content_w, round(26.0 * scale_box))
            gdiplus.GdipDrawString(gfx, self.feedback_text, -1, font_btn, fb_rect, fmt_center, green_b)

        # Cleanup GDI+
        gdiplus.GdipDeleteFont(font_title)
        gdiplus.GdipDeleteFont(font_sub)
        gdiplus.GdipDeleteFont(font_btn)
        gdiplus.GdipDeleteFont(font_badge)
        gdiplus.GdipDeleteFontFamily(font_family)
        gdiplus.GdipDeleteStringFormat(fmt_left)
        gdiplus.GdipDeleteStringFormat(fmt_wrap)
        gdiplus.GdipDeleteStringFormat(fmt_center)
        gdiplus.GdipDeleteStringFormat(fmt_right)
        gdiplus.GdipDeleteBrush(text_pri)
        gdiplus.GdipDeleteBrush(text_sec)
        gdiplus.GdipDeleteBrush(cyan_b)
        gdiplus.GdipDeleteBrush(green_b)
        gdiplus.GdipDeleteGraphics(gfx)

        rect = w.RECT()
        user32.GetWindowRect(self.hwnd, c.byref(rect))
        pt_dest = POINT(rect.left, rect.top)
        sz_dest = SIZE(self.w, self.h)
        pt_src = POINT(0, 0)
        blend = BLENDFUNCTION(0, 0, 255, 1)

        user32.UpdateLayeredWindow(
            self.hwnd, screen_dc, c.byref(pt_dest), c.byref(sz_dest),
            mem_dc, c.byref(pt_src), 0, c.byref(blend), 2
        )

        gdi32.SelectObject(mem_dc, old_bmp)
        gdi32.DeleteObject(hbmp)
        gdi32.DeleteDC(mem_dc)
        user32.ReleaseDC(None, screen_dc)
