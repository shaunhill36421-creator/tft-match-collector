"""
analyzer.py
===========
Phân tích SÂU một trận TFT để đưa ra nhận xét và gợi ý cải thiện.

QUAN TRỌNG — giới hạn dữ liệu:
  Riot Match API chỉ cho "ảnh chụp CUỐI trận" (không có timeline từng round,
  không có shop, không có vị trí xếp bài, không có hành vi scout). Vì vậy module
  này CHỈ phân tích được những gì suy ra được từ trạng thái cuối trận của cả 8
  người chơi:
    - Contest: đội hình của bạn bị bao nhiêu nhà khác tranh chấp.
    - Lõi/carry: quân nào đang gánh đồ.
    - Trần sức mạnh: heuristic dựa trên số sao, đồ hoàn chỉnh, mốc tộc-hệ, level.
    - Econ cuối trận & gợi ý cải thiện.

  Những thứ CẦN dữ liệu live trong game (composition/econ/shop theo từng round,
  xếp bài, scout, đánh giá quyết định theo thời điểm) KHÔNG nằm trong Match API
  — xem docs/GIOI_HAN_DU_LIEU.md để biết hướng lấy.

Module này KHÔNG gọi mạng, có thể test ngoại tuyến qua --test.
"""

# Quân được coi là "đã hoàn chỉnh đồ" khi giữ đủ 3 món.
FULL_ITEM_COUNT = 3


def _active_traits(p: dict) -> list:
    """Trait đang kích hoạt (style > 0)."""
    return [t for t in p.get("traits", []) if t.get("style", 0) > 0]


def _item_count(unit: dict) -> int:
    """Số trang bị của một quân (hỗ trợ cả itemNames mới lẫn items cũ)."""
    if unit.get("itemNames"):
        return len(unit["itemNames"])
    if unit.get("items"):
        return len(unit["items"])
    return 0


def _find_player(info: dict, puuid: str):
    for p in info.get("participants", []):
        if p.get("puuid") == puuid:
            return p
    return None


def _analyze_contest(info: dict, me: dict) -> list:
    """Đội hình của 'me' bị bao nhiêu nhà KHÁC tranh chấp.

    So sánh trait và từng quân của me với 7 người còn lại (dựa trên đội hình
    CUỐI — đây là xấp xỉ contest, không phải contest theo thời gian thực).
    """
    lines = []
    others = [p for p in info.get("participants", []) if p.get("puuid") != me.get("puuid")]
    total_others = len(others)

    # --- Contest theo TỘC-HỆ chính ---
    my_traits = sorted(_active_traits(me),
                       key=lambda t: (t.get("style", 0), t.get("num_units", 0)),
                       reverse=True)
    if my_traits:
        lines.append("  Mức tranh chấp theo tộc-hệ (so với 7 nhà còn lại):")
        for t in my_traits[:4]:  # 4 trait mạnh nhất là đủ để đánh giá
            name = t.get("name", "?")
            cnt = sum(1 for o in others
                      if any(ot.get("name") == name and ot.get("style", 0) > 0
                             for ot in o.get("traits", [])))
            muc = "❗nặng" if cnt >= 3 else ("vừa" if cnt in (1, 2) else "✔ độc tôn")
            lines.append(f"    - {name}: {cnt}/{total_others} nhà khác cùng chơi  [{muc}]")

    # --- Contest theo QUÂN ---
    my_units = me.get("units", [])
    if my_units:
        lines.append("  Mức tranh chấp theo quân chủ lực (giữ đồ):")
        # Ưu tiên xét quân đang gánh đồ (carry) vì đó là quân tranh giành thật sự.
        carries = sorted(my_units, key=lambda u: (_item_count(u), u.get("tier", 0)), reverse=True)
        for u in carries[:3]:
            cid = u.get("character_id", "?")
            cnt = sum(1 for o in others
                      if any(ou.get("character_id") == cid for ou in o.get("units", [])))
            muc = "❗nặng" if cnt >= 3 else ("vừa" if cnt in (1, 2) else "✔ ít tranh")
            lines.append(f"    - {cid} (giữ {_item_count(u)} đồ): {cnt}/{total_others} nhà khác cũng dùng  [{muc}]")

    if not lines:
        lines.append("  (Không có dữ liệu trait/quân để xét contest.)")
    return lines


def _identify_core(me: dict) -> list:
    """Xác định lõi/carry: quân nào đang gánh đồ, quân nào 3 sao."""
    lines = []
    units = me.get("units", [])
    if not units:
        return ["  (Không có quân để xác định lõi.)"]

    carries = sorted(units, key=lambda u: (_item_count(u), u.get("tier", 0)), reverse=True)
    lines.append("  Lõi / quân gánh (theo số đồ và số sao):")
    for u in carries:
        ic = _item_count(u)
        if ic == 0 and u.get("tier", 0) < 3:
            continue  # bỏ qua quân phụ không đồ, không 3 sao
        stars = "★" * int(u.get("tier", 0) or 0)
        note = "đồ hoàn chỉnh" if ic >= FULL_ITEM_COUNT else (f"{ic} đồ" if ic else "không đồ")
        lines.append(f"    - {u.get('character_id', '?')} {stars} ({note})")
    if len(lines) == 1:
        lines.append("    (Không quân nào nổi bật về đồ/sao — đội hình có thể chưa định hình lõi rõ.)")
    return lines


def _analyze_power_ceiling(me: dict) -> list:
    """Heuristic: đội hình cuối có 'đạt trần sức mạnh' không.

    Dựa trên: số quân 3-sao, số quân đủ 3 đồ, số mốc tộc-hệ vàng/lăng kính,
    và lấp đủ sân chưa (số quân == level).
    """
    lines = []
    units = me.get("units", [])
    level = me.get("level", 0) or 0

    three_star = sum(1 for u in units if u.get("tier", 0) >= 3)
    two_star = sum(1 for u in units if u.get("tier", 0) == 2)
    full_item_units = sum(1 for u in units if _item_count(u) >= FULL_ITEM_COUNT)
    strong_traits = sum(1 for t in _active_traits(me) if t.get("style", 0) >= 3)  # vàng/lăng kính
    board = len(units)

    lines.append(f"  • Lấp sân       : {board}/{level} (số quân / level — bằng nhau là đã đầy)")
    lines.append(f"  • Quân 3-sao    : {three_star}    | quân 2-sao: {two_star}")
    lines.append(f"  • Quân đủ 3 đồ  : {full_item_units}")
    lines.append(f"  • Mốc tộc mạnh  : {strong_traits} (vàng/lăng kính)")

    # Cho điểm thô để ra nhận định (chỉ mang tính tham khảo).
    score = 0
    if board >= level and level > 0:
        score += 1
    if three_star >= 1:
        score += 1
    if full_item_units >= 2:
        score += 1
    if strong_traits >= 2:
        score += 1

    if score >= 3:
        verdict = "GẦN/ĐÃ đạt trần sức mạnh — đội hình cuối khá hoàn chỉnh."
    elif score == 2:
        verdict = "Ở mức TRUNG BÌNH — còn dư địa nâng cấp (3-sao / hoàn thiện đồ / mốc tộc)."
    else:
        verdict = "CHƯA đạt trần — đội hình cuối còn yếu so với chuẩn cuối trận."
    lines.append(f"  → Nhận định    : {verdict}")
    return lines


def _analyze_econ(me: dict) -> list:
    """Nhận xét econ cuối trận: vàng dư, level so với giai đoạn."""
    lines = []
    gold = me.get("gold_left", 0) or 0
    level = me.get("level", 0) or 0
    last_round = me.get("last_round", 0) or 0
    placement = me.get("placement", 0) or 0

    lines.append(f"  • Vàng còn lại lúc kết thúc: {gold}")
    lines.append(f"  • Level cuối / vòng kết thúc: {level} / {last_round}")

    # Heuristic: chết (hạng >4) mà còn nhiều vàng = tiếc nuối (đáng lẽ roll/level cứu).
    if placement > 4 and gold >= 50:
        lines.append("  ⚠️ Chết với khá nhiều vàng dư — đáng lẽ nên roll/level sớm để cứu máu.")
    elif placement > 4 and gold <= 5:
        lines.append("  • Đã tiêu gần hết vàng (all-in) nhưng vẫn xếp dưới — vấn đề có thể ở đội hình/đồ, không phải econ.")
    elif placement <= 4 and gold >= 30:
        lines.append("  • Top đầu mà vẫn dư vàng — econ tốt, có thể cân nhắc dùng vàng dư để cap mạnh hơn.")
    return lines


def _improvement_suggestions(info: dict, me: dict) -> list:
    """Tổng hợp gợi ý cải thiện từ các phân tích trên (heuristic)."""
    tips = []
    units = me.get("units", [])
    level = me.get("level", 0) or 0
    gold = me.get("gold_left", 0) or 0
    placement = me.get("placement", 0) or 0
    others = [p for p in info.get("participants", []) if p.get("puuid") != me.get("puuid")]

    three_star = sum(1 for u in units if u.get("tier", 0) >= 3)
    full_item_units = sum(1 for u in units if _item_count(u) >= FULL_ITEM_COUNT)

    # 1) Contest nặng?
    my_main = sorted(_active_traits(me),
                     key=lambda t: (t.get("style", 0), t.get("num_units", 0)),
                     reverse=True)
    if my_main:
        main_name = my_main[0].get("name", "")
        contest_cnt = sum(1 for o in others
                          if any(ot.get("name") == main_name and ot.get("style", 0) > 0
                                 for ot in o.get("traits", [])))
        if contest_cnt >= 3:
            tips.append(f"Đội hình chủ lực ({main_name}) bị {contest_cnt} nhà khác tranh — "
                        "lần sau nên đọc bàn sớm và pivot khi thấy tranh chấp nặng (quân sẽ khó lên sao).")

    # 2) Không có 3-sao và xếp dưới?
    if three_star == 0 and placement > 4:
        tips.append("Cuối trận không có quân 3-sao chủ lực — xem lại tiến trình econ/roll để 3-sao đúng nhịp.")

    # 3) Đồ chưa hoàn chỉnh?
    if full_item_units < 2:
        tips.append("Ít quân đủ 3 đồ — ưu tiên ghép đồ về quân gánh chính thay vì rải đều.")

    # 4) Vàng dư khi chết?
    if placement > 4 and gold >= 50:
        tips.append(f"Chết còn {gold} vàng — khi sắp mất máu, hãy roll/level để tăng sức mạnh tức thì thay vì giữ vàng.")

    # 5) Lấp sân chưa đầy?
    if level > 0 and len(units) < level:
        tips.append(f"Mới có {len(units)}/{level} quân trên sân — thiếu quân/level so với khả năng, dễ thua combat.")

    if not tips:
        tips.append("Không phát hiện vấn đề rõ ràng từ dữ liệu cuối trận — kết quả khá hợp lý.")
    return tips


def _board_strength_score(p: dict) -> float:
    """Điểm 'độ mạnh đội hình' thô (chỉ để so sánh tương đối giữa các nhà).

    Không phải chỉ số chính thức của Riot — chỉ là heuristic gộp số 3-sao,
    quân đủ đồ, mốc tộc mạnh và độ lấp sân.
    """
    units = p.get("units", [])
    three_star = sum(1 for u in units if u.get("tier", 0) >= 3)
    full_item = sum(1 for u in units if _item_count(u) >= FULL_ITEM_COUNT)
    strong_traits = sum(1 for t in _active_traits(p) if t.get("style", 0) >= 3)
    return three_star * 3 + full_item * 2 + strong_traits * 1 + len(units) * 0.5


def _top_trait_name(p: dict) -> str:
    traits = sorted(_active_traits(p),
                    key=lambda t: (t.get("style", 0), t.get("num_units", 0)),
                    reverse=True)
    return traits[0].get("name", "-") if traits else "-"


def _compare_houses(info: dict, me: dict) -> list:
    """So sánh CẢ 8 NHÀ sau trận (phiên bản 'check từng nhà' khả thi từ dữ liệu cuối).

    Đánh dấu nhà nào tranh đội hình trực tiếp với bạn (trùng tộc chính hoặc trùng
    quân gánh), và nhà nào có đội hình mạnh hơn bạn theo điểm heuristic.
    """
    lines = []
    participants = sorted(info.get("participants", []),
                          key=lambda p: p.get("placement", 99))

    # Đội hình "của bạn" để đối chiếu trùng lặp.
    my_main_trait = _top_trait_name(me)
    my_carry_ids = {u.get("character_id") for u in sorted(
        me.get("units", []), key=lambda u: (_item_count(u), u.get("tier", 0)),
        reverse=True)[:3]}
    my_score = _board_strength_score(me)

    lines.append(f"  {'Hạng':<5}{'Lv':<4}{'Sân':<5}{'3sao':<6}{'Điểm':<7}{'Tên / ghi chú'}")
    lines.append(f"  {'-' * 68}")
    for p in participants:
        place = str(p.get("placement", "?"))
        level = str(p.get("level", "?"))
        board = str(len(p.get("units", [])))
        three_star = str(sum(1 for u in p.get("units", []) if u.get("tier", 0) >= 3))
        score = _board_strength_score(p)

        is_me = p.get("puuid") == me.get("puuid")
        name = "BẠN" if is_me else _player_short_name(p)

        flags = []
        if not is_me:
            # Tranh đội hình? (trùng tộc chính hoặc trùng quân gánh)
            shares_trait = any(t.get("name") == my_main_trait and t.get("style", 0) > 0
                               for t in p.get("traits", [])) and my_main_trait != "-"
            shares_carry = any(u.get("character_id") in my_carry_ids
                               for u in p.get("units", [])) and bool(my_carry_ids)
            if shares_trait or shares_carry:
                flags.append("⚔️ tranh đội hình với bạn")
            if score > my_score:
                flags.append("mạnh hơn bạn")
        note = f"  ({', '.join(flags)})" if flags else ""
        lines.append(f"  {place:<5}{level:<4}{board:<5}{three_star:<6}{score:<7.1f}{name}{note}")

    lines.append("")
    lines.append("  Ghi chú: 'Điểm' là chỉ số ĐỘ MẠNH ĐỘI HÌNH thô (heuristic, không")
    lines.append("  phải số liệu chính thức), chỉ dùng để so tương đối giữa các nhà.")
    return lines


def _player_short_name(p: dict) -> str:
    """Tên ngắn của người chơi (tái dùng logic giống summarizer)."""
    name = p.get("riotIdGameName") or p.get("riotIdName")
    tag = p.get("riotIdTagline")
    if name and tag:
        return f"{name}#{tag}"
    if name:
        return name
    puuid = p.get("puuid", "")
    return f"(PUUID {puuid[:8]}...)" if puuid else "(không rõ)"


def build_analysis(match_data: dict, puuid: str) -> str:
    """Tạo bản phân tích sâu (chuỗi nhiều dòng) cho người chơi có 'puuid'."""
    info = match_data.get("info", {})
    me = _find_player(info, puuid)

    out = []
    out.append("=" * 72)
    out.append("         PHÂN TÍCH & GỢI Ý CẢI THIỆN (dựa trên dữ liệu CUỐI trận)")
    out.append("=" * 72)

    if me is None:
        out.append("")
        out.append("Không tìm thấy người chơi (PUUID không khớp) — không thể phân tích.")
        return "\n".join(out)

    out.append("")
    out.append(f"[ KẾT QUẢ ] Hạng {me.get('placement', '?')}/8 · "
               f"Level {me.get('level', '?')} · Vòng kết thúc {me.get('last_round', '?')}")

    out.append("")
    out.append("[ 1. CONTEST — đội hình bị tranh chấp bao nhiêu ]")
    out.extend(_analyze_contest(info, me))

    out.append("")
    out.append("[ 2. LÕI / CARRY — quân gánh đồ & quân 3-sao ]")
    out.extend(_identify_core(me))

    out.append("")
    out.append("[ 3. TRẦN SỨC MẠNH — đội hình cuối đã 'cap' chưa ]")
    out.extend(_analyze_power_ceiling(me))

    out.append("")
    out.append("[ 4. ECON cuối trận ]")
    out.extend(_analyze_econ(me))

    out.append("")
    out.append("[ 5. AUGMENT đã chọn ] (liệt kê để bạn tự soi mức hợp đội hình)")
    augs = me.get("augments", [])
    if augs:
        for a in augs:
            out.append(f"    - {a}")
    else:
        out.append("    (không có)")

    out.append("")
    out.append("[ 6. ĐIỂM CẦN CẢI THIỆN ]")
    for i, tip in enumerate(_improvement_suggestions(info, me), 1):
        out.append(f"  {i}. {tip}")

    out.append("")
    out.append("[ 7. SO SÁNH CẢ 8 NHÀ — 'check từng nhà' (sau trận) ]")
    out.extend(_compare_houses(info, me))

    # Nói rõ phần KHÔNG phân tích được để không gây hiểu nhầm.
    out.append("")
    out.append("-" * 72)
    out.append("[ KHÔNG CÓ TRONG DỮ LIỆU API CHÍNH THỨC — cần dữ liệu live trong game ]")
    out.append("  • Composition / econ / shop theo TỪNG ROUND")
    out.append("  • Xếp bài (vị trí tướng), việc scout từng nhà")
    out.append("  • Đánh giá 'quyết định có hợp thời điểm không' theo dòng thời gian")
    out.append("  → Muốn có các mục này phải đọc game lúc đang chơi (Riot Live Client")
    out.append("    Data / Overwolf GEP). Xem docs/GIOI_HAN_DU_LIEU.md.")
    out.append("=" * 72)

    return "\n".join(out)
