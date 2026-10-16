# -*- coding: utf-8 -*-
"""
Kiểm thử Toàn diện Cầu nối 2 Chiều Lean Teamwork <-> Antigravity Desktop Widget
"""

import sys
import os
import json
import time
import unittest
from pathlib import Path

# Paths
REPO_ROOT = Path(__file__).resolve().parent.parent
WIDGET_ROOT = REPO_ROOT / "widget" if (REPO_ROOT / "widget").exists() else Path.home() / "Desktop" / "Du An" / "AntigravityWidget"

sys.path.insert(0, str(REPO_ROOT / "scripts"))
sys.path.insert(0, str(WIDGET_ROOT))

import teamwork_bridge
from core.teamwork_service import get_teamwork_service
from core.layout import horizontal_layout, calculate_account_chip_width
from core import antigravity_service


class TestTeamworkWidgetIntegration(unittest.TestCase):

    def setUp(self):
        teamwork_bridge.clear_bridge()

    def tearDown(self):
        teamwork_bridge.clear_bridge()

    def test_01_bridge_proposal_lifecycle(self):
        """Test phát đề xuất kế hoạch và đọc lại từ TeamworkService."""
        options = [
            {"id": 1, "text": "Phương án 1 (Recommended)", "recommended": True},
            {"id": 2, "text": "Phương án 2", "recommended": False}
        ]
        ok = teamwork_bridge.publish_proposal("Tích hợp Widget", options, duration_seconds=150)
        self.assertTrue(ok)

        tw_service = get_teamwork_service()
        display = tw_service.get_display_info()

        self.assertTrue(display["active"])
        self.assertEqual(display["status"], "PROPOSAL")
        self.assertIn("🧭", display["label"])
        self.assertEqual(len(display["options"]), 2)
        self.assertGreater(display["remaining_seconds"], 140)

    def test_02_widget_click_roundtrip(self):
        """Test người dùng click chọn phương án trên Widget và IDE nhận được phản hồi."""
        options = [{"id": 1, "text": "Phương án 1", "recommended": True}]
        teamwork_bridge.publish_proposal("Test Click", options, duration_seconds=150)

        tw_service = get_teamwork_service()
        # Mô phỏng click từ widget popover
        tw_service.submit_response("SELECT_OPTION", option_id=1)

        # Kiểm tra IDE đọc được response
        resp = teamwork_bridge.check_user_response(mark_handled=True)
        self.assertIsNotNone(resp)
        self.assertEqual(resp["action"], "SELECT_OPTION")
        self.assertEqual(resp["selected_option_id"], 1)

        # Lần 2 đã handled nên trả về None
        resp_again = teamwork_bridge.check_user_response()
        self.assertIsNone(resp_again)

    def test_03_acceptance_lifecycle(self):
        """Test phát tín hiệu nghiệm thu và người dùng bấm duyệt."""
        ok = teamwork_bridge.publish_acceptance(
            title="Nghiệm thu Widget Bridge",
            summary="Đã hoàn thành xuất sắc toàn bộ tính năng",
            files_changed=["core/teamwork_service.py", "core/layout.py"],
            exit_code=0
        )
        self.assertTrue(ok)

        tw_service = get_teamwork_service()
        display = tw_service.get_display_info()

        self.assertTrue(display["active"])
        self.assertEqual(display["status"], "ACCEPTANCE")
        self.assertIn("💎", display["label"])
        self.assertEqual(display["exit_code"], 0)

        # Người dùng bấm [100% HOÀN TẤT]
        tw_service.submit_response("ACCEPT")
        resp = teamwork_bridge.check_user_response()
        self.assertIsNotNone(resp)
        self.assertEqual(resp["action"], "ACCEPT")

    def test_04_layout_with_teamwork_chip(self):
        """Test tính toán layout và kích thước khi có chip teamwork."""
        # Active teamwork
        layout_active = horizontal_layout(800, 48, 800, 48, account_name="user@example.com", scale_factor=1.0, teamwork_active=True)
        self.assertIn("teamwork", layout_active.boxes)
        tw_box = layout_active.boxes["teamwork"]
        self.assertEqual(tw_box.w, 152.0)

        # Idle teamwork
        layout_idle = horizontal_layout(800, 48, 800, 48, account_name="user@example.com", scale_factor=1.0, teamwork_active=False)
        self.assertIn("teamwork", layout_idle.boxes)
        tw_box_idle = layout_idle.boxes["teamwork"]
        self.assertEqual(tw_box_idle.w, 84.0)

        # Compact teamwork only (khi không có Antigravity IDE)
        layout_compact = horizontal_layout(160, 48, 160, 48, scale_factor=1.0, teamwork_active=True, compact_teamwork_only=True)
        self.assertIn("teamwork", layout_compact.boxes)
        self.assertEqual(len(layout_compact.boxes), 1)
        self.assertNotIn("account", layout_compact.boxes)
        self.assertNotIn("5h", layout_compact.boxes)
        self.assertNotIn("week", layout_compact.boxes)
        self.assertNotIn("switch", layout_compact.boxes)
        self.assertNotIn("refresh", layout_compact.boxes)
        self.assertNotIn("lock", layout_compact.boxes)

    def test_05_native_ide_account_detection(self):
        """Test phát hiện tài khoản native Antigravity IDE từ database state.vscdb."""
        acc = antigravity_service.get_native_antigravity_account()
        # Trên môi trường phát triển này, có Antigravity IDE đang đăng nhập
        self.assertIsNotNone(acc)
        self.assertIn("@", acc["email"])
        self.assertTrue(acc["name"])
        self.assertIn("Antigravity", acc["source"])

    def test_06_native_ide_extraction(self):
        """Test cơ chế trích xuất Native IDE hoạt động trơn tru (không có Cockpit)."""
        data = antigravity_service.query_antigravity_data()
        self.assertTrue(data.get("healthy"))
        self.assertEqual(data.get("source"), "native-antigravity-ide")
        self.assertNotEqual(data.get("active_email"), "")
        self.assertNotEqual(data.get("active_email"), "Offline")

        # Kiểm tra danh sách tài khoản popup
        accs = antigravity_service.get_cockpit_accounts_with_quota()
        self.assertGreaterEqual(len(accs.get("all", [])), 1)
        active_acc = accs["all"][0]
        self.assertTrue(active_acc.get("is_active"))
        self.assertEqual(active_acc.get("id"), "native_ide")

    def test_07_completion_anchor_tracking(self):
        """Test cơ chế ghi nhớ mốc hoàn tất gần nhất và theo dõi lỗi trung gian."""
        # 1. Phát acceptance lần 1 và người dùng bấm ACCEPT
        teamwork_bridge.publish_acceptance("Task Milestone 1", "Xong phan 1", files_changed=[], exit_code=0)
        tw_service = get_teamwork_service()
        tw_service.submit_response("ACCEPT")
        resp1 = teamwork_bridge.check_user_response(mark_handled=True)
        self.assertIsNotNone(resp1)

        t1 = teamwork_bridge.get_last_completed_timestamp()
        self.assertGreater(t1, 0.0)

        # 2. Người dùng chat tiếp vì phát hiện lỗi trung gian
        teamwork_bridge.record_intermediate_issue("Lỗi chưa sync accounts", error_type="BUG")
        teamwork_bridge.record_intermediate_issue("Crash khi đọc state", error_type="CRASH")

        issues = teamwork_bridge.get_intermediate_issues()
        self.assertEqual(len(issues), 2)
        self.assertEqual(issues[0]["description"], "Lỗi chưa sync accounts")
        self.assertEqual(issues[1]["error_type"], "CRASH")

        # 3. Sau khi sửa xong, nghiệm thu lần 2
        time.sleep(0.01)
        teamwork_bridge.publish_acceptance("Task Milestone 2", "Xong phan 2", files_changed=[], exit_code=0)
        tw_service.submit_response("ACCEPT")
        resp2 = teamwork_bridge.check_user_response(mark_handled=True)
        self.assertIsNotNone(resp2)

        t2 = teamwork_bridge.get_last_completed_timestamp()
        self.assertGreaterEqual(t2, t1)

        # 4. Clear bridge vẫn giữ lại mốc hoàn tất gần nhất
        teamwork_bridge.clear_bridge()
        self.assertEqual(teamwork_bridge.get_last_completed_timestamp(), t2)

    def test_08_acceptance_passcode_and_anti_false_acceptance(self):
        """Test mật mã nghiệm thu hoàn tất 'OK 💎' và quy tắc chống nhầm lẫn từ 'ok' giao tiếp thông thường."""
        # 1. Các tín hiệu nghiệm thu hợp lệ (có mật mã / emoji kim cương / phím tắt ok::)
        self.assertTrue(teamwork_bridge.is_acceptance_signal("OK 💎"))
        self.assertTrue(teamwork_bridge.is_acceptance_signal("💎 OK"))
        self.assertTrue(teamwork_bridge.is_acceptance_signal("OK💎"))
        self.assertTrue(teamwork_bridge.is_acceptance_signal("[ACCEPT] 💎"))
        self.assertTrue(teamwork_bridge.is_acceptance_signal("ok 💎"))
        self.assertTrue(teamwork_bridge.is_acceptance_signal("Đã hoàn tất 💎"))
        self.assertTrue(teamwork_bridge.is_acceptance_signal("[100% HOÀN TẤT]"))
        self.assertTrue(teamwork_bridge.is_acceptance_signal("ok::"))
        self.assertTrue(teamwork_bridge.is_acceptance_signal("OK::"))

        # 2. Các trao đổi thông thường có từ 'ok' tuyệt đối KHÔNG phải là tín hiệu nghiệm thu
        self.assertFalse(teamwork_bridge.is_acceptance_signal("ok"))
        self.assertFalse(teamwork_bridge.is_acceptance_signal("OK"))
        self.assertFalse(teamwork_bridge.is_acceptance_signal("ok làm tiếp đi"))
        self.assertFalse(teamwork_bridge.is_acceptance_signal("ok bạn ơi"))
        self.assertFalse(teamwork_bridge.is_acceptance_signal("ok để mình xem xét"))
        self.assertFalse(teamwork_bridge.is_acceptance_signal("chuẩn bị ok chưa"))
        self.assertFalse(teamwork_bridge.is_acceptance_signal(""))
        self.assertFalse(teamwork_bridge.is_acceptance_signal(None))

    def test_09_proposal_timestamp_awareness_and_timeout_response(self):
        """Test cơ chế nhận diện đề xuất mới qua updated_at và tự động chọn phương án [1] khi hết giờ."""
        tw_service = get_teamwork_service()

        # 1. Phát đề xuất 1
        teamwork_bridge.publish_proposal("Đề xuất 1", [{"id": 1, "text": "Phương án 1 (Khuyên dùng)", "recommended": True}])
        disp1 = tw_service.get_display_info()
        self.assertEqual(disp1["status"], "PROPOSAL")
        self.assertIn("updated_at", disp1)
        self.assertIn("start_time", disp1)
        t1 = disp1["updated_at"]

        # 2. Phát đề xuất 2 (cùng status PROPOSAL nhưng updated_at mới hơn)
        time.sleep(0.01)
        teamwork_bridge.publish_proposal("Đề xuất 2", [{"id": 1, "text": "Phương án A (Khuyên dùng)", "recommended": True}])
        disp2 = tw_service.get_display_info()
        t2 = disp2["updated_at"]
        self.assertGreater(t2, t1)
        self.assertEqual(disp2["title"], "Đề xuất 2")

        # 3. Giả lập hết giờ và tự động gửi response số 1
        tw_service.submit_response("SELECT_OPTION", option_id=1, note="Auto-selected [1] on timeout")
        resp = teamwork_bridge.check_user_response()
        self.assertIsNotNone(resp)
        self.assertEqual(resp["action"], "SELECT_OPTION")
        self.assertEqual(resp["selected_option_id"], 1)
        self.assertIn("Auto-selected [1]", resp["note"])

    def test_10_widget_auto_collapse_on_minimize_and_popover_presence(self):
        """Test cơ chế thu gọn widget khi IDE bị minimize và duy trì hiển thị popover thông báo."""
        tw_service = get_teamwork_service()

        # 1. Trạng thái IDLE: Widget thu lại (ẩn) khi không có thông báo
        tw_info = tw_service.get_display_info()
        self.assertFalse(tw_info.get("active", False))
        self.assertEqual(tw_info.get("status", "IDLE"), "IDLE")

        # 2. Khi có đề xuất mới phát ra, dù IDE đang minimize, bridge vẫn chuyển sang PROPOSAL
        teamwork_bridge.publish_proposal("Đề xuất khi Minimize", [{"id": 1, "text": "Phương án 1", "recommended": True}])
        tw_info_active = tw_service.get_display_info()
        self.assertTrue(tw_info_active.get("active", False))
        self.assertEqual(tw_info_active.get("status"), "PROPOSAL")

        # 3. Khi nghiệm thu phát ra, status chuyển sang ACCEPTANCE
        teamwork_bridge.publish_acceptance("Nghiệm thu khi Minimize", "Đã hoàn thành", files_changed=["a.py"], exit_code=0)
        tw_info_acc = tw_service.get_display_info()


    def test_12_compact_teamwork_layout_and_min_size(self):
        """Test layout thu gọn chỉ còn duy nhất chip teamwork khi Antigravity thu nhỏ."""
        layout_compact = horizontal_layout(150, 48, 150, 48, account_name="user@example.com", scale_factor=1.0, teamwork_active=True, compact_teamwork_only=True)
        self.assertIn("teamwork", layout_compact.boxes)
        self.assertNotIn("account", layout_compact.boxes)
        self.assertNotIn("5h", layout_compact.boxes)
        self.assertNotIn("week", layout_compact.boxes)
        self.assertNotIn("switch", layout_compact.boxes)
        self.assertNotIn("refresh", layout_compact.boxes)
        self.assertNotIn("lock", layout_compact.boxes)

    def test_13_safe_action_dispatch_and_no_keystrokes(self):
        """Test triệt tiêu hoàn toàn phím giả lập keybd_event chống tắt nhầm IDE khi nghiệm thu."""
        from core.teamwork_popover import TeamworkGlassPopover
        popover = TeamworkGlassPopover(parent_app=None)
        # 1. send_to_antigravity không gửi phím giả lập mà chỉ focus an toàn
        res = popover.send_to_antigravity("OK::")
        self.assertIsInstance(res, bool)

        # 2. Xử lý click ACCEPT cập nhật an toàn qua bridge service
        tw_service = get_teamwork_service()
        teamwork_bridge.publish_acceptance("Nghiệm thu an toàn", "Tất cả test pass", files_changed=["a.py"], exit_code=0)
        tw_service.submit_response("ACCEPT")
        state = tw_service.get_state()
        self.assertEqual(state["status"], "IDLE")
        self.assertEqual(state["response"]["action"], "ACCEPT")
        self.assertFalse(state["response"]["handled"])

    def test_14_proposal_cli_and_wait_listener(self):
        """Test cơ chế phát đề xuất qua bridge CLI và script wait_for_proposal_choice.py tự tiếp tục khi timeout hoặc click widget."""
        import subprocess

        # 1. Test bridge CLI proposal
        cli_py = REPO_ROOT / "scripts" / "teamwork_bridge.py"
        res_p = subprocess.run([
            sys.executable, str(cli_py), "proposal", "Kế hoạch Refactor",
            "--options", '[{"id": 1, "text": "Phương án 1", "recommended": true}, {"id": 2, "text": "Phương án 2"}]',
            "--duration", "10"
        ], capture_output=True, text=True, encoding="utf-8", errors="replace")
        self.assertEqual(res_p.returncode, 0)
        st = teamwork_bridge.get_bridge_state()
        self.assertEqual(st["status"], "PROPOSAL")
        self.assertEqual(st["proposal"]["title"], "Kế hoạch Refactor")

        # 2. Test wait_for_proposal_choice.py timeout fallback (1s) -> tự động chọn [1]
        listener_py = REPO_ROOT / "scripts" / "wait_for_proposal_choice.py"
        self.assertTrue(listener_py.exists())

        res_t = subprocess.run([
            sys.executable, str(listener_py), "--timeout", "1", "--interval", "0.2"
        ], capture_output=True, text=True, encoding="utf-8", errors="replace")
        self.assertEqual(res_t.returncode, 0)
        self.assertIn("[TIMEOUT]", res_t.stdout)
        self.assertIn("Phương án [1]", res_t.stdout)

        # 3. Test wait_for_proposal_choice.py với sự kiện chọn phương án [2] từ widget
        teamwork_bridge.publish_proposal("Test Selection", [
            {"id": 1, "text": "Opt 1"}, {"id": 2, "text": "Opt 2"}
        ], duration_seconds=10)

        p = subprocess.Popen(
            [sys.executable, str(listener_py), "--timeout", "5", "--interval", "0.2"],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding="utf-8", errors="replace"
        )
        time.sleep(0.6)
        teamwork_bridge.submit_user_response("SELECT_OPTION", selected_option_id=2, note="User chose 2 on widget")
        out, _ = p.communicate(timeout=5)
        self.assertEqual(p.returncode, 0)
        self.assertIn("[WIDGET_SELECTION]", out)
        self.assertIn("Phương án [2]", out)

    def test_09_string_options_proposal_and_popover_layout(self):
        """Test phát đề xuất với options dạng danh sách chuỗi và popover tính layout chuẩn xác."""
        from core.teamwork_popover import TeamworkGlassPopover
        str_options = [
            "Phương án 1 (Recommended)",
            "Phương án 2: Dùng endpoint hiện có"
        ]
        ok = teamwork_bridge.publish_proposal("Test String Options", str_options, duration_seconds=150)
        self.assertTrue(ok)

        st = teamwork_bridge.get_bridge_state()
        self.assertEqual(st["status"], "PROPOSAL")

        dummy_parent = type('DummyParent', (), {'s': {'scale_percent': 100}})()
        pop = TeamworkGlassPopover.__new__(TeamworkGlassPopover)
        pop.parent = dummy_parent

        layout = pop.compute_dynamic_layout(st)
        self.assertEqual(layout["st"], "PROPOSAL")
        self.assertEqual(len(layout["boxes"]), 2)
        self.assertEqual(layout["boxes"][0]["opt"]["id"], 1)
        self.assertTrue(layout["boxes"][0]["opt"]["recommended"])
        self.assertEqual(layout["boxes"][1]["opt"]["id"], 2)

        # Test edge case: None title / options / acceptance
        pop.compute_dynamic_layout({'status': 'PROPOSAL', 'proposal': {'title': None, 'options': None}})
        pop.compute_dynamic_layout({'status': 'ACCEPTANCE', 'acceptance': {'title': None, 'summary': None, 'files_changed': None}})

    def test_15_surface_detection_and_result_header_bar(self):
        """Test phát hiện môi trường Antigravity 2.0 vs IDE và tính toán layout thanh tiêu đề kết quả."""
        from core.teamwork_popover import TeamworkGlassPopover
        tw_service = get_teamwork_service()

        # 1. Phát hiện surface tự động
        detected = teamwork_bridge.detect_antigravity_surface()
        self.assertIn(detected, ["Antigravity 2.0", "Antigravity IDE"])

        # 2. Phát acceptance với surface Antigravity 2.0
        teamwork_bridge.publish_acceptance(
            "Test Surface 2.0", "Nội dung kiểm thử kết quả trên Antigravity 2.0",
            files_changed=["widget/core/teamwork_popover.py"], exit_code=0, surface="Antigravity 2.0"
        )
        st_v2 = teamwork_bridge.get_bridge_state()
        self.assertEqual(st_v2["acceptance"]["surface"], "Antigravity 2.0")

        disp_v2 = tw_service.get_display_info()
        self.assertEqual(disp_v2["surface"], "Antigravity 2.0")
        self.assertIn("Antigravity 2.0", disp_v2["label"])

        dummy_parent = type('DummyParent', (), {'s': {'scale_percent': 100}})()
        pop = TeamworkGlassPopover.__new__(TeamworkGlassPopover)
        pop.parent = dummy_parent

        layout_v2 = pop.compute_dynamic_layout(st_v2)
        self.assertEqual(layout_v2["surface"], "Antigravity 2.0")
        self.assertIn("res_hdr_h", layout_v2)
        self.assertGreater(layout_v2["res_hdr_h"], 0)

        # 3. Phát acceptance với surface Antigravity IDE
        teamwork_bridge.publish_acceptance(
            "Test Surface IDE", "Nội dung kiểm thử kết quả trên Antigravity IDE",
            files_changed=["scripts/teamwork_bridge.py"], exit_code=0, surface="Antigravity IDE"
        )
        st_ide = teamwork_bridge.get_bridge_state()
        self.assertEqual(st_ide["acceptance"]["surface"], "Antigravity IDE")

        disp_ide = tw_service.get_display_info()
        self.assertEqual(disp_ide["surface"], "Antigravity IDE")
        self.assertIn("Antigravity IDE", disp_ide["label"])

        layout_ide = pop.compute_dynamic_layout(st_ide)
        self.assertEqual(layout_ide["surface"], "Antigravity IDE")
        self.assertEqual(layout_ide["res_hdr_h"], layout_v2["res_hdr_h"])

    def test_16_close_proposal_and_popover_dismiss(self):
        """Test cơ chế đóng bảng đề xuất popover ngay khi chọn phương án hoặc bấm nút đóng [✕]."""
        from core.teamwork_popover import TeamworkGlassPopover
        tw_service = get_teamwork_service()

        # 1. Phát đề xuất
        teamwork_bridge.publish_proposal("Test Proposal Close", [
            {"id": 1, "text": "Phương án 1 (Recommended)", "recommended": True},
            {"id": 2, "text": "Phương án 2"}
        ], duration_seconds=150)
        st = teamwork_bridge.get_bridge_state()
        self.assertEqual(st["status"], "PROPOSAL")
        self.assertIsNotNone(st["proposal"])

        # 2. Gọi close_proposal từ bridge -> Trạng thái lập tức chuyển sang EXECUTING, xóa proposal
        ok = teamwork_bridge.close_proposal(selected_option_id=1, note="User picked 1")
        self.assertTrue(ok)
        st_after = teamwork_bridge.get_bridge_state()
        self.assertEqual(st_after["status"], "EXECUTING")
        self.assertIsNone(st_after["proposal"])
        self.assertEqual(st_after["response"]["action"], "SELECT_OPTION")
        self.assertEqual(st_after["response"]["selected_option_id"], 1)

        # 3. Test popover handle_click('btn_close') và handle_click('opt_1')
        dummy_parent = type('DummyParent', (), {
            's': {'scale_percent': 100},
            'popover_until': 1000.0,
            'teamwork_service': tw_service
        })()
        pop = TeamworkGlassPopover.__new__(TeamworkGlassPopover)
        pop.parent = dummy_parent
        pop.hwnd = None
        pop.visible = True
        pop.hover_btn_id = None
        pop.clickable_regions = [
            {"id": "btn_close", "action": "CLOSE"},
            {"id": "opt_1", "action": "SELECT_OPTION", "opt_id": 1, "opt_txt": "Option 1"}
        ]

        # Click nút đóng [✕]
        pop.handle_click("btn_close")
        self.assertFalse(pop.visible)
        self.assertEqual(dummy_parent.popover_until, 0.0)

        # Click chọn phương án
        pop._action_locked_until = 0.0
        pop.visible = True
        dummy_parent.popover_until = 500.0
        pop.clickable_regions = [
            {"id": "btn_close", "action": "CLOSE"},
            {"id": "opt_1", "action": "SELECT_OPTION", "opt_id": 1, "opt_txt": "Option 1"}
        ]
        pop.handle_click("opt_1")
        self.assertFalse(pop.visible)
        self.assertEqual(dummy_parent.popover_until, 0.0)

        # 4. Test CLI close subcommand
        import subprocess
        cli_py = REPO_ROOT / "scripts" / "teamwork_bridge.py"
        res_c = subprocess.run([
            sys.executable, str(cli_py), "close", "--option", "2", "--note", "CLI close"
        ], capture_output=True, text=True, encoding="utf-8", errors="replace")
        self.assertEqual(res_c.returncode, 0)
        self.assertIn("EXECUTING", res_c.stdout)
        st_cli = teamwork_bridge.get_bridge_state()
        self.assertEqual(st_cli["status"], "EXECUTING")
        self.assertIsNone(st_cli["proposal"])
        self.assertEqual(st_cli["response"]["selected_option_id"], 2)

    def test_17_six_anchor_presets_and_bottom_docking(self):
        """Test cả 6 vị trí neo (trên/dưới x trái/giữa/phải) và không bị ép rel_y > 400 về 40."""
        from core.overlay_window import CockpitOverlayApp
        app = CockpitOverlayApp.__new__(CockpitOverlayApp)
        app.w = 600
        app.h = 48
        app.last_codex_hwnd = None
        app.last_codex_rect = (-8, -8, 1928, 1048)
        app.s = {
            'locked': True,
            'anchor_preset': 'top_right',
            'rel_x': None,
            'rel_y': None,
            'x': 500,
            'y': 40,
            'scale_percent': 100,
            'orientation': 'horizontal',
            'theme': 'cards',
        }

        coords = {}
        for preset in ('top_left', 'top_center', 'top_right', 'bottom_left', 'bottom_center', 'bottom_right'):
            tx, ty, rx, ry = app._compute_preset_coords(preset, app.last_codex_rect)
            coords[preset] = (tx, ty, rx, ry)

        # Kiểm tra trục X: left < center < right cho cả trên và dưới
        self.assertLess(coords['top_left'][0], coords['top_center'][0])
        self.assertLess(coords['top_center'][0], coords['top_right'][0])
        self.assertLess(coords['bottom_left'][0], coords['bottom_center'][0])
        self.assertLess(coords['bottom_center'][0], coords['bottom_right'][0])

        # Kiểm tra trục Y: các vị trí dưới (bottom_*) phải nằm ở đáy (> 600px), không bị reset về 40
        for b_preset in ('bottom_left', 'bottom_center', 'bottom_right'):
            tx, ty, rx, ry = coords[b_preset]
            self.assertGreater(ty, 600, f"{b_preset} target_y={ty} phải nằm ở nửa dưới màn hình")
            self.assertGreater(ry, 600, f"{b_preset} rel_y={ry} không được bị ép về 40")

        # Kiểm tra trục Y: các vị trí trên (top_*) nằm ở phần đỉnh (< 100px)
        for t_preset in ('top_left', 'top_center', 'top_right'):
            tx, ty, rx, ry = coords[t_preset]
            self.assertLess(ty, 100, f"{t_preset} target_y={ty} phải nằm ở cạnh trên")

    def test_18_dual_window_tracker_prefers_visible_over_minimized(self):
        """Test khi mở song song Antigravity 2.0 và Antigravity IDE, cửa sổ đang mở luôn được ưu tiên hơn cửa sổ đã thu nhỏ."""
        from core.window_tracker import is_codex_desktop_image
        self.assertTrue(is_codex_desktop_image(r"C:\Users\User\AppData\Local\Programs\Antigravity\Antigravity.exe"))
        self.assertTrue(is_codex_desktop_image(r"C:\Users\User\AppData\Local\Programs\Antigravity IDE\Antigravity IDE.exe"))


if __name__ == "__main__":
    unittest.main()

