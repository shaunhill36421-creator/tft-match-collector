"""
summarizer.py
=============
Biến dữ liệu trận TFT thô (JSON từ Riot) thành một bản tóm tắt tiếng Việt
dễ đọc (chuỗi nhiều dòng) để lưu ra file ``{matchId}_summary.txt``.

Module này KHÔNG gọi mạng — chỉ xử lý dữ liệu — nên có thể test ngoại tuyến
bằng file samples/sample_match.json (xem chế độ --test trong main.py).

Lưu ý: ở prototype này, các mã định danh của Riot (TFT_Item_..., TFT9_Garen,
tên trait...) được GIỮ NGUYÊN, chưa dịch sang tên tiếng Việt.
"""

from datetime import datetime


# Một vài mã queue phổ biến -> tên dễ hiểu. Không có trong bảng thì in mã gốc.
QUEUE_NAMES = {
    1090: "Thường (Normal)",
    1100: "Xếp hạng (Ranked)",
    1130: "Hyper Roll",
    1150: "Double Up (thử nghiệm)",
    1160: "Double Up",
    1170: "Chế độ Fortune's Favor",
    1180: "Soul Brawl",
}

# style của trait: 0 = chưa kích hoạt, 1 = Đồng, 2 = Bạc, 3 = Vàng, 4 = Lăng kính.
TRAIT_STYLE_NAMES = {
    0: "Tắt",
    1: "Đồng",
    2: "Bạc",
    3: "Vàng",
    4: "Lăng kính",
}


def _format_datetime(epoch_ms) -> str:
    """Đổi mốc thời gian epoch (mili-giây) sang chuỗi ngày giờ địa phương."""
    if not epoch_ms:
        return "Không rõ"
    try:
        dt = datetime.fromtimestamp(epoch_ms / 1000)
        return dt.strftime("%d/%m/%Y %H:%M:%S")
    except (TypeError, ValueError, OSError):
        return "Không rõ"


def _format_duration(seconds) -> str:
    """Đổi số giây (có thể là số thực) sang dạng 'mm phút ss giây'."""
    if not seconds:
        return "Không rõ"
    try:
        total = int(round(float(seconds)))
        return f"{total // 60} phút {total % 60:02d} giây"
    except (TypeError, ValueError):
        return "Không rõ"


def _queue_name(queue_id, game_type) -> str:
    """Tên loại trận: ưu tiên bảng tra, kèm theo tft_game_type nếu có."""
    name = QUEUE_NAMES.get(queue_id, f"Mã queue {queue_id}")
    if game_type:
        return f"{name} (type: {game_type})"
    return name


def _player_name(participant: dict) -> str:
    """Lấy tên hiển thị của một người chơi từ dữ liệu participant.

    Dữ liệu TFT mới có riotIdGameName/riotIdTagline; nếu thiếu thì dùng tạm
    8 ký tự đầu của PUUID để vẫn phân biệt được người chơi.
    """
    name = participant.get("riotIdGameName") or participant.get("riotIdName")
    tag = participant.get("riotIdTagline")
    if name and tag:
        return f"{name}#{tag}"
    if name:
        return name
    puuid = participant.get("puuid", "")
    return f"(PUUID {puuid[:8]}...)" if puuid else "(không rõ tên)"


def _item_list(unit: dict) -> list:
    """Trả về danh sách trang bị của một tướng.

    Dữ liệu mới dùng 'itemNames' (mảng chuỗi mã), dữ liệu cũ dùng 'items'
    (mảng số). Hàm này hỗ trợ cả hai để chắc ăn.
    """
    if unit.get("itemNames"):
        return list(unit["itemNames"])
    if unit.get("items"):
        return [str(i) for i in unit["items"]]
    return []


def _active_traits(participant: dict) -> list:
    """Danh sách trait ĐANG kích hoạt (style > 0), sắp theo độ mạnh giảm dần."""
    traits = [t for t in participant.get("traits", []) if t.get("style", 0) > 0]
    # Sắp xếp: style cao trước, rồi tới số quân nhiều trước.
    traits.sort(key=lambda t: (t.get("style", 0), t.get("num_units", 0)), reverse=True)
    return traits


def _format_trait(trait: dict) -> str:
    """Một trait -> chuỗi kiểu 'Set9_Trait (4) [Vàng]'."""
    name = trait.get("name", "?")
    num = trait.get("num_units", 0)
    style = TRAIT_STYLE_NAMES.get(trait.get("style", 0), "?")
    return f"{name} ({num}) [{style}]"


def _find_participant(info: dict, puuid: str):
    """Tìm participant trùng PUUID người được tra cứu (có thể trả None)."""
    if not puuid:
        return None
    for p in info.get("participants", []):
        if p.get("puuid") == puuid:
            return p
    return None


def _summarize_player_block(p: dict) -> list:
    """Khối tóm tắt CHI TIẾT cho người chơi được tra cứu. Trả về list dòng."""
    lines = []
    lines.append(f"  • Thứ hạng cuối : {p.get('placement', '?')} / 8")
    lines.append(f"  • Level         : {p.get('level', '?')}")
    # Riot API hiện KHÔNG trả về máu còn lại trong dữ liệu trận đã kết thúc.
    lines.append("  • Máu còn lại   : (Riot API không cung cấp trong dữ liệu trận)")
    lines.append(f"  • Vàng còn lại  : {p.get('gold_left', '?')}")
    lines.append(f"  • Vòng bị loại  : {p.get('last_round', '?')}")
    lines.append(f"  • Hạ gục        : {p.get('players_eliminated', '?')} người")

    # Augment đã chọn.
    augments = p.get("augments", [])
    lines.append("")
    lines.append("  Augment đã chọn:")
    if augments:
        for a in augments:
            lines.append(f"    - {a}")
    else:
        lines.append("    (không có)")

    # Tộc - hệ (trait) đang kích hoạt.
    traits = _active_traits(p)
    lines.append("")
    lines.append("  Tộc - hệ (trait) đang kích hoạt:")
    if traits:
        for t in traits:
            lines.append(f"    - {_format_trait(t)}")
    else:
        lines.append("    (không có trait nào kích hoạt)")

    # Đội hình tướng.
    units = p.get("units", [])
    lines.append("")
    lines.append(f"  Đội hình tướng ({len(units)} tướng):")
    if units:
        # Sắp tướng: nhiều sao trước cho dễ nhìn.
        for u in sorted(units, key=lambda x: x.get("tier", 0), reverse=True):
            cid = u.get("character_id", "?")
            stars = "★" * int(u.get("tier", 0) or 0)
            items = _item_list(u)
            item_text = f" [{', '.join(items)}]" if items else ""
            lines.append(f"    - {cid} {stars}{item_text}")
    else:
        lines.append("    (không có tướng)")

    return lines


def _summarize_lobby_table(info: dict) -> list:
    """Bảng 8 người trong lobby, sắp theo thứ hạng. Trả về list dòng."""
    lines = []
    participants = sorted(
        info.get("participants", []),
        key=lambda p: p.get("placement", 99),
    )

    # Tiêu đề bảng (dùng khoảng trắng căn cột cho dễ đọc trong Notepad).
    lines.append(f"  {'Hạng':<5}{'Lv':<4}{'Tên người chơi':<28}{'Tộc-hệ chính'}")
    lines.append(f"  {'-' * 70}")

    for p in participants:
        place = str(p.get("placement", "?"))
        level = str(p.get("level", "?"))
        name = _player_name(p)
        # Lấy tối đa 3 trait mạnh nhất làm "tộc-hệ chính".
        top_traits = _active_traits(p)[:3]
        traits_text = ", ".join(
            f"{t.get('name', '?')}({t.get('num_units', 0)})" for t in top_traits
        ) or "(không)"
        # Cắt bớt tên quá dài để bảng không vỡ cột.
        name_short = name if len(name) <= 26 else name[:25] + "…"
        lines.append(f"  {place:<5}{level:<4}{name_short:<28}{traits_text}")

    return lines


def build_summary(match_data: dict, looked_up_puuid: str = None,
                  looked_up_riot_id: str = None) -> str:
    """Tạo toàn bộ bản tóm tắt (chuỗi nhiều dòng) từ dữ liệu trận.

    Tham số:
      - match_data       : dict dữ liệu thô từ Riot API.
      - looked_up_puuid  : PUUID người được tra cứu (để làm nổi bật). Có thể None.
      - looked_up_riot_id: Riot ID gốc người dùng nhập (chỉ để hiển thị). Có thể None.
    """
    metadata = match_data.get("metadata", {})
    info = match_data.get("info", {})

    match_id = metadata.get("match_id", "?")

    out = []
    out.append("=" * 72)
    out.append("           BẢN TÓM TẮT TRẬN ĐẤU TFT (Đấu Trường Chân Lý)")
    out.append("=" * 72)

    # ----- 1) Thông tin chung -----
    out.append("")
    out.append("[ THÔNG TIN CHUNG ]")
    out.append(f"  • Match ID      : {match_id}")
    out.append(f"  • Thời điểm     : {_format_datetime(info.get('game_datetime'))}")
    out.append(f"  • Phiên bản game: {info.get('game_version', 'Không rõ')}")
    out.append(f"  • Loại trận     : {_queue_name(info.get('queue_id'), info.get('tft_game_type'))}")
    out.append(f"  • Set / phiên bản set: {info.get('tft_set_number', '?')} ({info.get('tft_set_core_name', '?')})")
    # game_length thường tính bằng giây; một số bản trả mili-giây nên xử lý mềm.
    out.append(f"  • Độ dài trận   : {_format_duration(info.get('game_length'))}")
    out.append(f"  • Số người chơi : {len(info.get('participants', []))}")

    # ----- 2) Người chơi được tra cứu (nổi bật) -----
    out.append("")
    out.append("-" * 72)
    player = _find_participant(info, looked_up_puuid)
    label = looked_up_riot_id or (looked_up_puuid[:12] + "..." if looked_up_puuid else "?")
    out.append(f"[ NGƯỜI CHƠI ĐƯỢC TRA CỨU: {label} ]")
    out.append("")
    if player is not None:
        out.extend(_summarize_player_block(player))
    else:
        out.append("  (Không tìm thấy người chơi này trong dữ liệu trận —")
        out.append("   có thể PUUID không khớp. Bỏ qua phần chi tiết cá nhân.)")

    # ----- 3) Bảng 8 người trong lobby -----
    out.append("")
    out.append("-" * 72)
    out.append("[ BẢNG XẾP HẠNG CẢ LOBBY ]")
    out.append("  (Dữ liệu SAU trận — hợp lệ vì trận đã kết thúc)")
    out.append("")
    out.extend(_summarize_lobby_table(info))

    out.append("")
    out.append("=" * 72)
    out.append("Ghi chú: các mã như TFT_Item_..., TFT9_..., Set9_Trait... được giữ")
    out.append("nguyên ở bản prototype này (sẽ dịch sang tên tiếng Việt ở bước sau).")
    out.append("=" * 72)

    return "\n".join(out)
