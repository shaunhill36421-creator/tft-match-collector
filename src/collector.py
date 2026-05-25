"""
collector.py
============
Tầng "điều phối logic" giữa giao diện dòng lệnh (main.py) và lớp gọi mạng
(riot_api.py).

Nhiệm vụ chính: nhận một Riot ID dạng ``Tên#Tag`` rồi chạy đủ 3 bước để lấy
về trận đấu gần nhất:

    Riot ID  ->  PUUID  ->  match ID gần nhất  ->  chi tiết trận
"""

import riot_api
from riot_api import RiotApiError


def parse_riot_id(riot_id: str) -> tuple:
    """Tách chuỗi ``Tên#Tag`` thành (game_name, tag_line).

    Chấp nhận tên người chơi có dấu cách (vd: "Hide on bush#KR1").
    Ném ``RiotApiError`` nếu định dạng sai (thiếu dấu '#').
    """
    riot_id = (riot_id or "").strip()
    if "#" not in riot_id:
        raise RiotApiError(
            f"Riot ID '{riot_id}' không đúng định dạng.\n"
            "  Đúng phải có dấu '#', ví dụ: Faker#VN2"
        )

    # Tách ở dấu '#' CUỐI CÙNG, phòng khi tên có chứa '#' (hiếm nhưng an toàn).
    game_name, _, tag_line = riot_id.rpartition("#")
    game_name = game_name.strip()
    tag_line = tag_line.strip()

    if not game_name or not tag_line:
        raise RiotApiError(
            f"Riot ID '{riot_id}' thiếu phần tên hoặc phần tag.\n"
            "  Đúng dạng: Tên#Tag, ví dụ: Faker#VN2"
        )
    return game_name, tag_line


def collect_latest_match(settings: dict, riot_id: str, api_key: str) -> tuple:
    """Chạy trọn vẹn quy trình thu thập 1 trận gần nhất.

    Trả về bộ ba: (match_id, match_data, puuid)
      - match_id   : ID của trận gần nhất (str)
      - match_data : dữ liệu thô của trận (dict, đúng như Riot gửi)
      - puuid      : PUUID của người chơi được tra cứu (str)

    Ném ``RiotApiError`` ở bất kỳ bước nào nếu có sự cố.
    """
    account_region = settings["account_region"]
    match_region = settings["match_region"]
    timeout = settings["request_timeout_seconds"]

    game_name, tag_line = parse_riot_id(riot_id)

    # --- Bước 1: Riot ID -> PUUID ---
    print(f"➡️  Bước 1/3: Tra PUUID cho '{game_name}#{tag_line}' (cluster: {account_region})...")
    puuid = riot_api.get_puuid(account_region, game_name, tag_line, api_key, timeout)
    print(f"    ✔ Đã có PUUID: {puuid[:16]}...")

    # --- Bước 2: PUUID -> match ID gần nhất ---
    print(f"➡️  Bước 2/3: Lấy ID trận gần nhất (region: {match_region})...")
    match_ids = riot_api.get_latest_match_ids(match_region, puuid, 1, api_key, timeout)
    if not match_ids:
        raise RiotApiError(
            "Người chơi này chưa có trận TFT nào trong lịch sử (danh sách trận trống)."
        )
    match_id = match_ids[0]
    print(f"    ✔ Trận gần nhất: {match_id}")

    # --- Bước 3: match ID -> chi tiết trận ---
    print(f"➡️  Bước 3/3: Tải chi tiết trận {match_id}...")
    match_data = riot_api.get_match_detail(match_region, match_id, api_key, timeout)
    print("    ✔ Đã tải xong dữ liệu trận.")

    return match_id, match_data, puuid
