# -*- coding: utf-8 -*-
"""
Lean Teamwork Desktop Bridge SDK
Điều phối dữ liệu 2 chiều thời gian thực giữa Antigravity IDE và Antigravity Desktop Widget.
Vị trí lưu trữ chia sẻ: ~/.antigravity_cockpit/teamwork_bridge.json
"""

import os
import sys
import time
import json
from pathlib import Path
from typing import Optional, List, Dict, Any

if sys.platform == "win32":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")

BRIDGE_DIR = Path.home() / '.antigravity_cockpit'
BRIDGE_FILE = BRIDGE_DIR / 'teamwork_bridge.json'

# Mật mã chuẩn hóa để nghiệm thu hoàn tất, phân biệt tuyệt đối với trao đổi "ok" thông thường
ACCEPTANCE_PASSCODE = "OK 💎"


def is_acceptance_signal(text: str) -> bool:
    """
    Kiểm tra xem chuỗi đầu vào có phải là tín hiệu nghiệm thu hoàn tất chính thức hay không.
    Mật mã chuẩn hóa: 'OK 💎' (hoặc '💎 OK', '[ACCEPT] 💎', '[100% HOÀN TẤT]').
    Loại trừ tuyệt đối các từ 'ok' trao đổi thông thường (ví dụ: 'ok', 'ok bạn', 'ok làm tiếp'...)
    nếu không có mật mã hoặc emoji kim cương 💎 đi kèm, tránh nhầm lẫn ngắt quãng công việc.
    """
    if not text or not isinstance(text, str):
        return False
    t = text.strip()
    if not t:
        return False

    # Khớp chính xác mật mã chuẩn hóa
    if t == ACCEPTANCE_PASSCODE or t == "💎 OK" or t == "OK💎":
        return True

    # Mật mã tắt siêu tốc thuần bàn phím (không cần mở bảng emoji Windows)
    if t.lower() == "ok::" or t.lower().startswith("ok::") or t.lower() == "ok:gem:":
        return True

    # Có emoji kim cương đi kèm chữ ok / accept / hoàn tất
    if "💎" in t:
        lower = t.lower()
        if "ok" in lower or "accept" in lower or "hoàn tất" in lower or "hoan tat" in lower:
            return True
        if t == "💎":
            return True

    # Tag nghiệm thu đặc biệt
    if "[100% HOÀN TẤT]" in t or "[ACCEPT]" in t:
        return True

    return False


def _ensure_dir():
    try:
        BRIDGE_DIR.mkdir(parents=True, exist_ok=True)
    except Exception:
        pass


def get_bridge_state() -> Dict[str, Any]:
    """Đọc trạng thái hiện tại từ file bridge."""
    if not BRIDGE_FILE.exists():
        return {
            "version": "1.0",
            "updated_at": 0.0,
            "status": "IDLE",
            "session_id": "",
            "proposal": None,
            "acceptance": None,
            "response": None
        }
    try:
        data = json.loads(BRIDGE_FILE.read_text(encoding='utf-8'))
        return data
    except Exception:
        return {
            "version": "1.0",
            "updated_at": 0.0,
            "status": "IDLE",
            "session_id": "",
            "proposal": None,
            "acceptance": None,
            "response": None
        }


def write_bridge_state(state: Dict[str, Any]) -> bool:
    """Ghi trạng thái an toàn nguyên tử (atomic write) vào file bridge."""
    _ensure_dir()
    state["updated_at"] = time.time()
    temp_file = BRIDGE_DIR / f'teamwork_bridge.tmp.{os.getpid()}'
    try:
        content = json.dumps(state, ensure_ascii=False, indent=2)
        temp_file.write_text(content, encoding='utf-8')
        temp_file.replace(BRIDGE_FILE)
        return True
    except Exception:
        try:
            BRIDGE_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding='utf-8')
            return True
        except Exception:
            return False
    finally:
        if temp_file.exists():
            try:
                temp_file.unlink()
            except Exception:
                pass


def detect_antigravity_surface() -> str:
    """
    Tự động nhận diện môi trường đang chạy Antigravity:
    - 'Antigravity 2.0': App desktop độc lập (Parallel Desktop App)
    - 'Antigravity IDE': AI-first IDE (Standalone VS Code based)
    """
    agent_api = os.environ.get("ANTIGRAVITY_AGENTAPI_EXE", "").lower()
    if "antigravity ide" in agent_api:
        return "Antigravity IDE"
    elif "antigravity" in agent_api:
        return "Antigravity 2.0"

    if os.environ.get("VSCODE_PID") or os.environ.get("VSCODE_INJECTION"):
        return "Antigravity IDE"

    return "Antigravity 2.0"


def publish_proposal(
    title: str,
    options: List[Dict[str, Any]],
    duration_seconds: int = 150,
    session_id: Optional[str] = None,
    surface: Optional[str] = None
) -> bool:
    """
    Phát tín hiệu Đề Xuất Kế Hoạch lên Desktop Widget.
    """
    now = time.time()
    cid = session_id or os.environ.get('ANTIGRAVITY_CONVERSATION_ID', '')
    surf = surface or detect_antigravity_surface()
    norm_options = []
    for idx, opt in enumerate(options or [], 1):
        if isinstance(opt, str):
            norm_options.append({
                "id": idx,
                "text": opt,
                "recommended": "(Recommended)" in opt or "(Khuyên dùng)" in opt or idx == 1
            })
        elif isinstance(opt, dict):
            c_opt = dict(opt)
            if "id" not in c_opt:
                c_opt["id"] = idx
            norm_options.append(c_opt)
        else:
            norm_options.append({"id": idx, "text": str(opt), "recommended": idx == 1})

    state = {
        "version": "1.0",
        "updated_at": now,
        "status": "PROPOSAL",
        "session_id": cid,
        "proposal": {
            "title": title,
            "duration_seconds": duration_seconds,
            "start_time": now,
            "deadline_ts": now + duration_seconds,
            "options": norm_options,
            "surface": surf
        },
        "acceptance": None,
        "response": None
    }
    return write_bridge_state(state)


def publish_acceptance(
    title: str,
    summary: str,
    files_changed: List[str],
    exit_code: int = 0,
    session_id: Optional[str] = None,
    surface: Optional[str] = None
) -> bool:
    """
    Phát tín hiệu Báo Cáo Nghiệm Thu Hoàn Thiện lên Desktop Widget.
    """
    now = time.time()
    cid = session_id or os.environ.get('ANTIGRAVITY_CONVERSATION_ID', '')
    surf = surface or detect_antigravity_surface()
    state = {
        "version": "1.0",
        "updated_at": now,
        "status": "ACCEPTANCE",
        "session_id": cid,
        "proposal": None,
        "acceptance": {
            "title": title,
            "summary": summary,
            "status": "PASS" if exit_code == 0 else "FAIL",
            "exit_code": exit_code,
            "files_changed": files_changed,
            "completed_at": now,
            "surface": surf
        },
        "response": None
    }
    return write_bridge_state(state)


def submit_user_response(
    action: str,
    selected_option_id: Optional[int] = None,
    note: str = ""
) -> bool:
    """
    Ghi nhận phản hồi từ Widget về IDE.
    action: "SELECT_OPTION" | "ACCEPT" | "DEBUG" | "PAUSE"
    """
    state = get_bridge_state()
    now_ts = time.time()
    state["response"] = {
        "action": action,
        "selected_option_id": selected_option_id,
        "note": note,
        "timestamp": now_ts,
        "handled": False
    }
    if action == "SELECT_OPTION":
        state["status"] = "EXECUTING"
        state["proposal"] = None
    elif action == "ACCEPT":
        state["status"] = "IDLE"
        state["acceptance"] = None
        state["last_completed_at"] = now_ts
        hist = state.get("completion_history") or []
        hist.append({
            "completed_at": now_ts,
            "session_id": state.get("session_id", ""),
            "acceptance": state.get("acceptance", {})
        })
        state["completion_history"] = hist[-20:]
    elif action == "DEBUG":
        state["status"] = "EXECUTING"
        state["acceptance"] = None
    state["updated_at"] = now_ts
    return write_bridge_state(state)


def close_proposal(selected_option_id: Optional[int] = None, note: str = "") -> bool:
    """
    Đóng bảng đề xuất trên Desktop Widget và chuyển trạng thái sang EXECUTING.
    Được gọi ngay khi phương án được chọn (qua chat hoặc widget) để không che màn hình.
    """
    return submit_user_response(
        action="SELECT_OPTION",
        selected_option_id=selected_option_id or 1,
        note=note or "Proposal closed"
    )


def check_user_response(mark_handled: bool = True) -> Optional[Dict[str, Any]]:
    """
    Kiểm tra xem người dùng đã tương tác bấm nút trên Widget hay chưa.
    Tự động ghi nhận mốc thời gian hoàn tất (last_completed_at) khi người dùng bấm ACCEPT.
    """
    state = get_bridge_state()
    resp = state.get("response")
    if resp and not resp.get("handled", False):
        if mark_handled:
            resp["handled"] = True
            state["response"] = resp
            if resp.get("action") == "ACCEPT":
                now_ts = resp.get("timestamp") or time.time()
                state["last_completed_at"] = now_ts
                hist = state.get("completion_history") or []
                hist.append({
                    "completed_at": now_ts,
                    "session_id": state.get("session_id", ""),
                    "acceptance": state.get("acceptance", {})
                })
                state["completion_history"] = hist[-20:]
            write_bridge_state(state)
        return resp
    return None


def get_last_completed_timestamp() -> float:
    """Trả về timestamp của lần bấm hoàn tất gần nhất (nếu có), hoặc 0.0 nếu chưa có trong phiên."""
    state = get_bridge_state()
    return float(state.get("last_completed_at") or 0.0)


def record_intermediate_issue(issue_description: str, error_type: str = "BUG") -> bool:
    """Ghi nhận một lỗi trung gian phát sinh giữa 2 mốc hoàn tất."""
    state = get_bridge_state()
    issues = state.get("intermediate_issues") or []
    issues.append({
        "timestamp": time.time(),
        "error_type": error_type,
        "description": issue_description
    })
    state["intermediate_issues"] = issues
    return write_bridge_state(state)


def get_intermediate_issues(clear: bool = False) -> List[Dict[str, Any]]:
    """Lấy danh sách các lỗi trung gian phát sinh kể từ lần hoàn tất gần nhất."""
    state = get_bridge_state()
    issues = state.get("intermediate_issues") or []
    if clear:
        state["intermediate_issues"] = []
        write_bridge_state(state)
    return issues


def clear_bridge(status: str = "IDLE") -> bool:
    """Đưa trạng thái về IDLE khi hoàn thành toàn bộ công việc, bảo toàn mốc hoàn tất gần nhất."""
    old_state = get_bridge_state()
    state = {
        "version": "1.0",
        "updated_at": time.time(),
        "status": status,
        "session_id": os.environ.get('ANTIGRAVITY_CONVERSATION_ID', ''),
        "proposal": None,
        "acceptance": None,
        "response": None,
        "last_completed_at": old_state.get("last_completed_at", 0.0),
        "completion_history": old_state.get("completion_history", []),
        "intermediate_issues": []
    }
    return write_bridge_state(state)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Lean Teamwork Bridge CLI")
    sub = parser.add_subparsers(dest="command", help="Lệnh cần thực hiện")

    # proposal
    p_cmd = sub.add_parser("proposal", help="Phát đề xuất kỹ thuật lên Widget")
    p_cmd.add_argument("title", help="Tiêu đề đề xuất")
    p_cmd.add_argument("--options", required=True, help="JSON list các phương án hoặc chuỗi phân tách dấu phẩy")
    p_cmd.add_argument("--duration", type=int, default=150, help="Thời gian chờ tính bằng giây (mặc định 150)")

    # acceptance
    a_cmd = sub.add_parser("acceptance", help="Phát báo cáo nghiệm thu lên Widget")
    a_cmd.add_argument("title", help="Tiêu đề nghiệm thu")
    a_cmd.add_argument("--summary", default="", help="Nội dung tóm tắt nghiệm thu")
    a_cmd.add_argument("--files", default="", help="Danh sách files thay đổi (phân tách dấu phẩy)")
    a_cmd.add_argument("--exit-code", type=int, default=0, help="Exit code (mặc định 0)")

    # status
    s_cmd = sub.add_parser("status", help="Xem trạng thái bridge hiện tại")

    # clear
    c_cmd = sub.add_parser("clear", help="Xóa trạng thái bridge về IDLE")

    # close
    cl_cmd = sub.add_parser("close", help="Đóng bảng đề xuất kỹ thuật ngay khi chọn xong")
    cl_cmd.add_argument("--option", type=int, default=1, help="Phương án đã chọn (mặc định 1)")
    cl_cmd.add_argument("--note", default="Proposal closed", help="Ghi chú lựa chọn")

    args = parser.parse_args()

    if args.command == "proposal":
        opts = []
        try:
            opts = json.loads(args.options)
        except Exception:
            raw_items = [x.strip() for x in args.options.split(",") if x.strip()]
            for idx, text in enumerate(raw_items, 1):
                opts.append({
                    "id": idx,
                    "text": text,
                    "recommended": (idx == 1)
                })
        ok = publish_proposal(args.title, opts, duration_seconds=args.duration)
        if ok:
            print(f"✓ Đã phát đề xuất kỹ thuật [{args.title}] lên Desktop Widget HUD ({len(opts)} options, {args.duration}s)")
        else:
            print("❌ Lỗi khi phát đề xuất kỹ thuật lên Widget")
            sys.exit(1)

    elif args.command == "acceptance":
        f_list = [x.strip() for x in args.files.split(",") if x.strip()] if args.files else []
        ok = publish_acceptance(args.title, args.summary, files_changed=f_list, exit_code=args.exit_code)
        if ok:
            print(f"✓ Đã phát báo cáo nghiệm thu [{args.title}] lên Desktop Widget HUD")
        else:
            print("❌ Lỗi khi phát báo cáo nghiệm thu lên Widget")
            sys.exit(1)

    elif args.command == "status":
        print(json.dumps(get_bridge_state(), indent=2, ensure_ascii=False))

    elif args.command == "clear":
        clear_bridge()
        print("✓ Đã xóa trạng thái bridge về IDLE")

    elif args.command == "close":
        ok = close_proposal(selected_option_id=args.option, note=args.note)
        if ok:
            print(f"✓ Đã đóng bảng đề xuất Widget và chuyển sang EXECUTING (phương án [{args.option}])")
        else:
            print("❌ Lỗi khi đóng bảng đề xuất")
            sys.exit(1)

    else:
        parser.print_help()

