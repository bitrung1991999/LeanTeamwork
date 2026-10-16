#!/usr/bin/env python3
"""
Antigravity PreInvocation Lifecycle Hook
Tự động kiểm tra và cân bằng phiên bản 2 chiều giữa folder gốc và máy tính ngầm.
Hoàn toàn tự động, người dùng không cần gõ bất kỳ câu lệnh nào!
"""

import sys
import json
import os
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

def main():
    sync_occurred = False
    active_version = "1.0.0"

    try:
        import sync_skill
        src_v = sync_skill.get_source_version()
        inst_v = sync_skill.get_installed_version()
        active_version = src_v

        src_tuple = sync_skill.parse_semver(src_v)
        inst_tuple = sync_skill.parse_semver(inst_v)

        # Kiểm tra xem có lệch version không
        if src_tuple != inst_tuple:
            sync_skill.auto_smart_sync()
            sync_occurred = True
        else:
            # Kiểm tra nhanh xem patterns có lệch nhau không
            src_p = REPO_ROOT / "docs" / "learned_patterns.md"
            dst_p = sync_skill.GLOBAL_CONFIG_DIR / "learned_patterns.md"
            if src_p.exists() and dst_p.exists():
                if src_p.stat().st_size != dst_p.stat().st_size:
                    sync_skill.bidirectional_merge_patterns()
                    sync_occurred = True
    except Exception as e:
        pass

    # Tự động cấp sẵn đồng hồ macOS Spectrum 480x84 trong suốt vào thư mục brain của session
    cid = os.environ.get("ANTIGRAVITY_CONVERSATION_ID")
    svg_img_tag = "![🧭 ĐỀ XUẤT KỸ THUẬT 💡](technical_proposal_timer.svg)"
    if cid:
        try:
            brain_dir = Path.home() / ".gemini" / "antigravity" / "brain" / cid
            brain_dir.mkdir(parents=True, exist_ok=True)
            dst_svg = brain_dir / "technical_proposal_timer.svg"
            src_svg = REPO_ROOT / ".agents" / "skills" / "lean-teamwork" / "resources" / "technical_proposal_timer.svg"
            if src_svg.exists():
                if not dst_svg.exists() or dst_svg.stat().st_size != src_svg.stat().st_size or 'fill="#0D1117"' in dst_svg.read_text(encoding="utf-8", errors="ignore"):
                    import shutil
                    shutil.copyfile(src_svg, dst_svg)
            svg_abs = dst_svg.as_posix()
            svg_img_tag = f"![🧭 ĐỀ XUẤT KỸ THUẬT 💡]({svg_abs})"
        except Exception:
            pass

    # Kiểm tra phản hồi từ Antigravity Desktop Widget
    widget_event_msg = ""
    try:
        bridge_file = Path.home() / '.antigravity_cockpit' / 'teamwork_bridge.json'
        if bridge_file.exists():
            b_data = json.loads(bridge_file.read_text(encoding='utf-8'))
            resp = b_data.get('response')
            if resp and not resp.get('handled'):
                resp['handled'] = True
                b_data['response'] = resp
                act = resp.get('action')
                if act == 'SELECT_OPTION':
                    opt_id = resp.get('selected_option_id')
                    b_data['status'] = 'EXECUTING'
                    b_data['proposal'] = None
                    widget_event_msg = f"\n\n🖱️ [SỰ KIỆN TỪ WIDGET DESKTOP]: Người dùng vừa bấm CHỌN PHƯƠNG ÁN [{opt_id}] trực tiếp từ Antigravity Desktop Widget! Hãy thi hành ngay theo phương án này!"
                elif act == 'ACCEPT':
                    b_data['status'] = 'IDLE'
                    b_data['acceptance'] = None
                    widget_event_msg = f"\n\n💎 [SỰ KIỆN TỪ WIDGET DESKTOP]: Người dùng vừa bấm [100% HOÀN TẤT - CHẤP THUẬN NGHIỆM THU] trên Desktop Widget! Hãy tổng kết và hoàn thành!"
                elif act == 'DEBUG':
                    b_data['status'] = 'EXECUTING'
                    b_data['acceptance'] = None
                    widget_event_msg = f"\n\n⚡ [SỰ KIỆN TỪ WIDGET DESKTOP]: Người dùng vừa bấm [SUPERPOWERS DEBUG] trên Desktop Widget! Hãy rà soát sâu!"

            # Tự động đóng bảng đề xuất khi người dùng gửi tin nhắn vào chat
            if b_data.get('status') == 'PROPOSAL':
                b_data['status'] = 'EXECUTING'
                b_data['proposal'] = None
                b_data['updated_at'] = time.time()
                if not b_data.get('response'):
                    b_data['response'] = {
                        'action': 'SELECT_OPTION',
                        'selected_option_id': 1,
                        'note': 'Auto-closed proposal on chat input',
                        'timestamp': time.time(),
                        'handled': True
                    }

            bridge_file.write_text(json.dumps(b_data, ensure_ascii=False, indent=2), encoding='utf-8')
    except Exception:
        pass

    anchor_msg = (
        f"⚡ [MANDATORY RE-ANCHOR — Lean Teamwork v{active_version} (Widget HUD Decoupled & Zero-Block Chat)]:\n"
        "1. 🧭 [CHẾ ĐỘ ĐỀ XUẤT KỸ THUẬT] 💡 (Hiển Thị Chat Lịch Sử + Chọn Trên Widget HUD + Hết Giờ Tự Động Tiếp Tục): Khi mở đầu hoặc chọn giải pháp kỹ thuật: (a) Khung Chat: BỎ HOÀN TOÀN modal popup ask_question trên chat Antigravity (giải phóng khung chat 100%, TUYỆT ĐỐI KHÔNG gọi modal ask_question). Chỉ hiển thị đề xuất ra lịch sử chat thông thường dạng markdown để nhìn thấy kèm đánh số '[1] (Recommended) ⭐', '[2]'...; (b) Widget HUD: Phát đề xuất lên Desktop Widget HUD Popover (teamwork_bridge.publish_proposal), người dùng chọn trực tiếp trên Widget; (c) Hết Giờ Tự Động Tiếp Tục: Khởi chạy 'py scripts/wait_for_proposal_choice.py --timeout 150' ngầm (hoặc schedule(DurationSeconds=150, TimerCondition='any')), khi hết hạn 150s tự động kích hoạt [1] (Khuyên dùng) và tiếp tục thực thi ngay lập tức, không bao giờ bị treo phiên.\n"
        "2. 💎 [CHẾ ĐỘ NGHIỆM THU HOÀN THIỆN] ✨ (Widget HUD): Khi code xong và test pass (exit 0): BƯỚC 1 in toàn văn Báo cáo & Hướng dẫn đối chứng ra màn hình chat (TUYỆT ĐỐI KHÔNG gọi modal popup ask_question che chữ); BƯỚC 2 gọi teamwork_bridge.publish_acceptance(...) để treo bảng nghiệm thu cố định trên Desktop Widget Popover. Khung chat rảnh rang 100%, user có thể bấm trực tiếp từ Desktop Widget (điều phối an toàn qua IPC bridge) hoặc xác nhận trực tiếp trong chat ('ok' / 'OK 💎').\n"
        "3. 🔑 [MẬT MÃ NGHIỆM THU 'OK 💎' / 'ok::' & CHỐNG NHẦM LẪN]: Tín hiệu nghiệm thu chuẩn hóa là 'OK 💎' (hoặc 'ok::' / 'hoàn tất'). CẤM nhầm lẫn các từ 'ok' trao đổi thông thường (như 'ok làm tiếp', 'ok nhé'...) là lệnh nghiệm thu. AI chỉ kích hoạt Self-Evolution khi bắt được mật mã nghiệm thu hoặc sự kiện từ widget, và BẮT BUỘC rà soát TOÀN BỘ chuỗi lỗi từ lần bấm Hoàn tất gần nhất đến nay.\n"
        "4. FIRST-TIME RIGHT: Inspect First kỹ lưỡng trước khi sửa, cấm đoán mò vì sợ đọc tài liệu."
    )
    if widget_event_msg:
        anchor_msg += widget_event_msg
    if sync_occurred:
        anchor_msg = f"🔄 [AUTO-SYNC]: Đã đồng bộ 2 chiều ngầm v{active_version}.\n" + anchor_msg

    response = {
        "injectSteps": [
            {
                "ephemeralMessage": anchor_msg
            }
        ]
    }

    sys.stdout.write(json.dumps(response, ensure_ascii=False) + "\n")
    sys.stdout.flush()
    sys.exit(0)

if __name__ == "__main__":
    main()
