"""
main.py
=======
Điểm khởi chạy của TFT Match Collector.

Việc của file này:
  1) Đọc cấu hình (config/settings.json) và API key (config/api_key.txt).
  2) Nếu thiếu key -> in hướng dẫn rõ ràng và thoát LỊCH SỰ (không crash).
  3) Hỏi/lấy Riot ID rồi gọi collector để tải trận gần nhất.
  4) Lưu {matchId}_raw.json và {matchId}_summary.txt vào thư mục output/.

Chế độ test ngoại tuyến (không cần key):
      python src/main.py --test
  -> đọc samples/sample_match.json và chỉ chạy summarizer để kiểm tra đầu ra.
"""

import json
import sys
from pathlib import Path

# riot_api.py, collector.py, summarizer.py nằm cùng thư mục với file này,
# nên import thẳng được (Python tự thêm thư mục của script vào đường dẫn tìm kiếm).
import collector
import summarizer
import analyzer
from riot_api import RiotApiError


# Các thư mục/file quan trọng, tính tương đối so với gốc dự án (cha của src/).
BASE_DIR = Path(__file__).resolve().parent.parent
CONFIG_DIR = BASE_DIR / "config"
OUTPUT_DIR = BASE_DIR / "output"
SAMPLES_DIR = BASE_DIR / "samples"

API_KEY_FILE = CONFIG_DIR / "api_key.txt"
SETTINGS_FILE = CONFIG_DIR / "settings.json"
SAMPLE_MATCH_FILE = SAMPLES_DIR / "sample_match.json"


def print_key_instructions():
    """In hướng dẫn lấy & đặt API key (dùng khi key thiếu/rỗng/còn mẫu)."""
    print()
    print("=" * 68)
    print("  ⚠️  CHƯA CÓ API KEY HỢP LỆ")
    print("=" * 68)
    print("  Để chạy được, bạn cần một API key của Riot:")
    print()
    print("  1) Mở trình duyệt vào: https://developer.riotgames.com")
    print("  2) Đăng nhập bằng tài khoản Riot của bạn.")
    print("  3) Tìm mục 'Development API Key', bấm copy.")
    print("     (Lưu ý: key dạng này HẾT HẠN sau 24 giờ — hôm sau phải lấy lại.)")
    print(f"  4) Mở file sau bằng Notepad và DÁN key vào (đúng 1 dòng):")
    print(f"        {API_KEY_FILE}")
    print("  5) Lưu file lại rồi chạy lại chương trình.")
    print()
    print("  (Mẹo: có thể test phần tóm tắt mà KHÔNG cần key bằng lệnh:")
    print("        python src/main.py --test )")
    print("=" * 68)
    print()


def load_settings() -> dict:
    """Đọc settings.json; nếu thiếu/hỏng thì dùng giá trị mặc định an toàn."""
    defaults = {
        "account_region": "asia",
        "match_region": "sea",
        "default_riot_id": "",
        "request_timeout_seconds": 15,
    }
    if not SETTINGS_FILE.exists():
        print(f"⚠️  Không thấy {SETTINGS_FILE}, tạm dùng cấu hình mặc định.")
        return defaults
    try:
        with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        # Gộp với mặc định để không bị thiếu trường nào.
        defaults.update({k: v for k, v in data.items() if v is not None or k == "default_riot_id"})
        # Đảm bảo timeout là số nguyên hợp lệ.
        defaults["request_timeout_seconds"] = int(defaults.get("request_timeout_seconds", 15))
        return defaults
    except (json.JSONDecodeError, ValueError) as exc:
        print(f"⚠️  File settings.json bị lỗi định dạng ({exc}). Dùng cấu hình mặc định.")
        return defaults


def load_api_key() -> str:
    """Đọc API key từ config/api_key.txt và kiểm tra tính hợp lệ cơ bản.

    Trả về key (str) nếu hợp lệ; trả về None nếu thiếu/rỗng/còn nội dung mẫu
    (kèm việc đã in hướng dẫn cho người dùng).
    """
    if not API_KEY_FILE.exists():
        print_key_instructions()
        return None

    try:
        content = API_KEY_FILE.read_text(encoding="utf-8").strip()
    except OSError as exc:
        print(f"⚠️  Không đọc được file API key: {exc}")
        print_key_instructions()
        return None

    # Rỗng?
    if not content:
        print_key_instructions()
        return None

    # Còn là nội dung mẫu (chứa chuỗi 'xxxx' của placeholder)?
    if "xxxx" in content.lower():
        print("⚠️  File api_key.txt vẫn đang chứa key MẪU (placeholder).")
        print_key_instructions()
        return None

    # Cảnh báo nhẹ nếu định dạng trông lạ, nhưng vẫn cho chạy thử.
    if not content.startswith("RGAPI-"):
        print("ℹ️  Lưu ý: API key thường bắt đầu bằng 'RGAPI-'. Vẫn thử chạy tiếp...")

    return content


def get_riot_id(settings: dict) -> str:
    """Lấy Riot ID: ưu tiên default_riot_id trong settings, nếu trống thì hỏi."""
    default_id = (settings.get("default_riot_id") or "").strip()
    if default_id:
        print(f"ℹ️  Dùng Riot ID mặc định từ settings.json: {default_id}")
        return default_id

    print()
    print("Nhập Riot ID của người chơi cần tra (dạng Tên#Tag, ví dụ Faker#VN2):")
    try:
        return input("  > ").strip()
    except (EOFError, KeyboardInterrupt):
        print("\nĐã hủy.")
        return ""


def save_outputs(match_id: str, match_data: dict, summary_text: str, analysis_text: str):
    """Lưu 3 file vào output/. Trả về (đường dẫn raw, summary, analysis)."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    raw_path = OUTPUT_DIR / f"{match_id}_raw.json"
    summary_path = OUTPUT_DIR / f"{match_id}_summary.txt"
    analysis_path = OUTPUT_DIR / f"{match_id}_analysis.txt"

    with open(raw_path, "w", encoding="utf-8") as f:
        json.dump(match_data, f, ensure_ascii=False, indent=2)

    with open(summary_path, "w", encoding="utf-8") as f:
        f.write(summary_text)

    with open(analysis_path, "w", encoding="utf-8") as f:
        f.write(analysis_text)

    return raw_path, summary_path, analysis_path


def run_test_mode() -> int:
    """Chế độ ngoại tuyến: đọc samples/sample_match.json, chạy summarizer."""
    print("🧪 CHẾ ĐỘ TEST NGOẠI TUYẾN — không gọi Riot API, không cần key.")
    if not SAMPLE_MATCH_FILE.exists():
        print(f"❌ Không tìm thấy file mẫu: {SAMPLE_MATCH_FILE}")
        return 1

    try:
        with open(SAMPLE_MATCH_FILE, "r", encoding="utf-8") as f:
            match_data = json.load(f)
    except (json.JSONDecodeError, OSError) as exc:
        print(f"❌ Lỗi đọc file mẫu: {exc}")
        return 1

    match_id = match_data.get("metadata", {}).get("match_id", "SAMPLE")
    # Lấy PUUID người đầu tiên để minh họa phần "người chơi được tra cứu".
    participants = match_data.get("metadata", {}).get("participants", [])
    sample_puuid = participants[0] if participants else None

    summary_text = summarizer.build_summary(
        match_data,
        looked_up_puuid=sample_puuid,
        looked_up_riot_id="(người chơi mẫu)",
    )
    analysis_text = analyzer.build_analysis(match_data, sample_puuid)

    raw_path, summary_path, analysis_path = save_outputs(
        match_id, match_data, summary_text, analysis_text
    )

    print()
    print("✅ Đã tạo file kết quả từ dữ liệu mẫu:")
    print(f"   • {raw_path}")
    print(f"   • {summary_path}")
    print(f"   • {analysis_path}")
    print()
    print("----- XEM TRƯỚC BẢN TÓM TẮT -----")
    print(summary_text)
    print()
    print("----- XEM TRƯỚC BẢN PHÂN TÍCH -----")
    print(analysis_text)
    return 0


def run_live_mode() -> int:
    """Chế độ thật: đọc key, lấy Riot ID, gọi Riot API, lưu kết quả."""
    settings = load_settings()

    api_key = load_api_key()
    if api_key is None:
        # Đã in hướng dẫn bên trong load_api_key -> thoát lịch sự.
        return 0

    riot_id = get_riot_id(settings)
    if not riot_id:
        print("❌ Chưa nhập Riot ID. Dừng lại.")
        return 1

    try:
        match_id, match_data, puuid = collector.collect_latest_match(settings, riot_id, api_key)
    except RiotApiError as exc:
        # Lỗi đã được "dịch" sang tiếng Việt -> chỉ việc in ra.
        print()
        print("❌ " + exc.message)
        return 1

    # Sinh tóm tắt + phân tích rồi lưu file.
    summary_text = summarizer.build_summary(
        match_data, looked_up_puuid=puuid, looked_up_riot_id=riot_id
    )
    analysis_text = analyzer.build_analysis(match_data, puuid)
    raw_path, summary_path, analysis_path = save_outputs(
        match_id, match_data, summary_text, analysis_text
    )

    print()
    print("✅ HOÀN TẤT! Đã lưu 3 file vào thư mục output/:")
    print(f"   • {raw_path.name}      (dữ liệu thô)")
    print(f"   • {summary_path.name}  (bản tóm tắt dễ đọc)")
    print(f"   • {analysis_path.name} (phân tích & gợi ý cải thiện)")
    print(f"   Thư mục: {OUTPUT_DIR}")
    return 0


def main() -> int:
    print()
    print("============================================")
    print("   TFT MATCH COLLECTOR — prototype nội bộ")
    print("============================================")

    # Cờ dòng lệnh: --test / --offline -> chạy chế độ ngoại tuyến.
    args = sys.argv[1:]
    if any(a in ("--test", "--offline") for a in args):
        return run_test_mode()

    return run_live_mode()


if __name__ == "__main__":
    sys.exit(main())
