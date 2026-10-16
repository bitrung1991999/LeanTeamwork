import os
import sys
import json
from pathlib import Path

GLOBAL_CONFIG_DIR = Path(os.path.expanduser('~')) / '.gemini' / 'config'
GLOBAL_SCRIPTS_DIR = GLOBAL_CONFIG_DIR / 'scripts'
GLOBAL_SCRIPTS_DIR.mkdir(parents=True, exist_ok=True)

hook_py = GLOBAL_SCRIPTS_DIR / 'auto_reanchor_hook.py'
hook_content = '''#!/usr/bin/env python3
"""
Antigravity Global PreInvocation Lifecycle Hook
Tự động tiêm thông điệp Re-Anchor tàng hình trước MỖI lượt gọi model ở mọi dự án.
Chống trôi ngữ cảnh (Anti-Context Drift) 100%, không bao giờ để AI quên hỏi và quên popup!
"""

import os
import sys
import json
from pathlib import Path

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

CONFIG_DIR = Path(__file__).resolve().parent.parent
SKILL_VER_FILE = CONFIG_DIR / 'skills' / 'lean-teamwork' / 'VERSION'

def get_active_version():
    try:
        if SKILL_VER_FILE.exists():
            return SKILL_VER_FILE.read_text(encoding='utf-8').strip()
    except Exception:
        pass
    return '1.3.1'

def main():
    ver = get_active_version()

    # Tự động cấp sẵn đồng hồ macOS Spectrum 480x84 trong suốt vào thư mục brain của session
    cid = os.environ.get('ANTIGRAVITY_CONVERSATION_ID')
    svg_img_tag = '![🧭 ĐỀ XUẤT KỸ THUẬT 💡](technical_proposal_timer.svg)'
    if cid:
        try:
            brain_dir = Path.home() / '.gemini' / 'antigravity' / 'brain' / cid
            brain_dir.mkdir(parents=True, exist_ok=True)
            dst_svg = brain_dir / 'technical_proposal_timer.svg'
            src_svg = CONFIG_DIR / 'skills' / 'lean-teamwork' / 'resources' / 'technical_proposal_timer.svg'
            if src_svg.exists():
                if not dst_svg.exists() or dst_svg.stat().st_size != src_svg.stat().st_size or 'fill="#0D1117"' in dst_svg.read_text(encoding='utf-8', errors='ignore'):
                    import shutil
                    shutil.copyfile(src_svg, dst_svg)
            svg_abs = dst_svg.as_posix()
            svg_img_tag = f'![🧭 ĐỀ XUẤT KỸ THUẬT 💡]({svg_abs})'
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
                bridge_file.write_text(json.dumps(b_data, ensure_ascii=False, indent=2), encoding='utf-8')
                act = resp.get('action')
                if act == 'SELECT_OPTION':
                    opt_id = resp.get('selected_option_id')
                    widget_event_msg = f"\\n\\n🖱️ [SỰ KIỆN TỪ WIDGET DESKTOP]: Người dùng vừa bấm CHỌN PHƯƠNG ÁN [{opt_id}] trực tiếp từ Antigravity Desktop Widget! Hãy thi hành ngay theo phương án này!"
                elif act == 'ACCEPT':
                    widget_event_msg = f"\\n\\n💎 [SỰ KIỆN TỪ WIDGET DESKTOP]: Người dùng vừa bấm [100% HOÀN TẤT - CHẤP THUẬN NGHIỆM THU] trên Desktop Widget! Hãy tổng kết và hoàn thành!"
                elif act == 'DEBUG':
                    widget_event_msg = f"\\n\\n⚡ [SỰ KIỆN TỪ WIDGET DESKTOP]: Người dùng vừa bấm [SUPERPOWERS DEBUG] trên Desktop Widget! Hãy rà soát sâu!"
    except Exception:
        pass

    anchor_msg = (
        f'⚡ [MANDATORY RE-ANCHOR — Lean Teamwork v{ver} (Widget HUD Decoupled & Zero-Block Chat)]:\\n'
        '1. 🧭 [CHẾ ĐỘ ĐỀ XUẤT KỸ THUẬT] 💡 (Hiển Thị Chat Lịch Sử + Chọn Trên Widget HUD + Hết Giờ Tự Động Tiếp Tục): Khi mở đầu hoặc chọn giải pháp kỹ thuật: (a) Khung Chat: BỎ HOÀN TOÀN modal popup ask_question trên chat Antigravity (giải phóng khung chat 100%, TUYỆT ĐỐI KHÔNG gọi modal ask_question). Chỉ hiển thị đề xuất ra lịch sử chat thông thường dạng markdown để nhìn thấy kèm đánh số "[1] (Recommended) ⭐", "[2]"...; (b) Widget HUD: Phát đề xuất lên Desktop Widget HUD Popover (teamwork_bridge.publish_proposal), người dùng chọn trực tiếp trên Widget; (c) Hết Giờ Tự Động Tiếp Tục: Khởi chạy "py scripts/wait_for_proposal_choice.py --timeout 150" ngầm (hoặc schedule(DurationSeconds=150, TimerCondition="any")), khi hết hạn 150s tự động kích hoạt [1] (Khuyên dùng) và tiếp tục thực thi ngay lập tức, không bao giờ bị treo phiên.\\n'
        '2. 💎 [CHẾ ĐỘ NGHIỆM THU HOÀN THIỆN] ✨ (Widget HUD): Khi code xong và test pass (exit 0): BƯỚC 1 in toàn văn Báo cáo & Hướng dẫn đối chứng ra màn hình chat (TUYỆT ĐỐI KHÔNG gọi modal popup ask_question che chữ); BƯỚC 2 gọi teamwork_bridge.publish_acceptance(...) để treo bảng nghiệm thu cố định trên Desktop Widget Popover. Khung chat rảnh rang 100%, user có thể bấm trực tiếp từ Desktop Widget (điều phối an toàn qua IPC bridge) hoặc xác nhận trực tiếp trong chat ("ok" / "OK 💎").\\n'
        '3. 🔑 [MẬT MÃ NGHIỆM THU "OK 💎" / "ok::" & CHỐNG NHẦM LẪN]: Tín hiệu nghiệm thu chuẩn hóa là "OK 💎" (hoặc "ok::" / "hoàn tất"). CẤM nhầm lẫn các từ "ok" trao đổi thông thường (như "ok làm tiếp", "ok nhé"...) là lệnh nghiệm thu. AI chỉ kích hoạt Self-Evolution khi bắt được mật mã nghiệm thu hoặc sự kiện từ widget, và BẮT BUỘC rà soát TOÀN BỘ chuỗi lỗi từ lần bấm Hoàn tất gần nhất đến nay.\\n'
        '4. FIRST-TIME RIGHT: Inspect First kỹ lưỡng trước khi sửa, cấm đoán mò vì sợ đọc tài liệu.'
    )
    if widget_event_msg:
        anchor_msg += widget_event_msg

    response = {
        'injectSteps': [
            {
                'ephemeralMessage': anchor_msg
            }
        ]
    }

    sys.stdout.write(json.dumps(response, ensure_ascii=False) + '\\n')
    sys.stdout.flush()
    sys.exit(0)

if __name__ == '__main__':
    main()
'''
hook_py.write_text(hook_content, encoding='utf-8')

hooks_json = GLOBAL_CONFIG_DIR / 'hooks.json'
py_exe_path = Path(sys.executable)
if sys.platform == 'win32':
    pyw_path = py_exe_path.with_name('pythonw.exe')
    if pyw_path.exists():
        py_exe_path = pyw_path
py_exe = py_exe_path.as_posix()
hook_py_str = hook_py.as_posix()
hooks_json_data = {
    "lean-teamwork-global-reanchor": {
        "PreInvocation": [
            {
                "type": "command",
                "command": f'"{py_exe}" "{hook_py_str}"',
                "timeout": 10
            }
        ]
    }
}
hooks_json.write_text(json.dumps(hooks_json_data, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
print(f'SUCCESS: Created universal global hook pointing to {py_exe} at {GLOBAL_CONFIG_DIR}')

# Đóng gói thành Antigravity Global Plugin để tự động nạp trên mọi workspace
plugin_dir = GLOBAL_CONFIG_DIR / 'plugins' / 'lean-teamwork-plugin'
plugin_dir.mkdir(parents=True, exist_ok=True)
plugin_json = plugin_dir / 'plugin.json'
plugin_json.write_text(json.dumps({
    "name": "lean-teamwork-plugin",
    "version": "1.5.14",
    "description": "Lean Multi-Agent Protocol & Desktop Widget HUD Integration"
}, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')

plugin_hooks_json = plugin_dir / 'hooks.json'
plugin_hooks_json.write_text(json.dumps(hooks_json_data, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')

plugin_rules_dir = plugin_dir / 'rules'
plugin_rules_dir.mkdir(parents=True, exist_ok=True)
plugin_agents_md = plugin_rules_dir / 'AGENTS.md'
plugin_agents_md.write_text("""# 🧭 Lean Teamwork Global Operating Rules

Quy chuẩn nạp bắt buộc cho Antigravity trên toàn bộ các dự án.

## 1. Điều Phối Kỹ Thuật (Decoupled Desktop Widget HUD)
- Khi bắt đầu lập trình hoặc chọn giải pháp kỹ thuật: BẮT BUỘC kích hoạt `🧭 [ĐỀ XUẤT KỸ THUẬT]` qua lệnh:
  `py -c "import teamwork_bridge; teamwork_bridge.publish_proposal('<Tiêu đề>', ['Phương án 1 (Recommended)', 'Phương án 2'], 150)"`
  để mở thẻ tương tác trực tiếp lên Desktop Widget HUD ngoài màn hình.
- Khi hoàn thành code và test pass: BẮT BUỘC kích hoạt `💎 [NGHIỆM THU HOÀN THIỆN]` qua lệnh:
  `py -c "import teamwork_bridge; teamwork_bridge.publish_acceptance('<Tiêu đề>', '<Tóm tắt>', ['file1', 'file2'])"`
- Tuyệt đối không dùng modal `ask_question` làm che khuất khung chat.
""", encoding='utf-8')
print(f'SUCCESS: Created global plugin at {plugin_dir}')
