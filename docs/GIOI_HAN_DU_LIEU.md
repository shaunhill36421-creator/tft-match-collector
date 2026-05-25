# Giới hạn dữ liệu & hướng lấy dữ liệu từng round

Tài liệu này giải thích **vì sao** một số phân tích chỉ làm được một phần, và
**cách nào** để lấy được phần còn lại.

---

## 1. Riot Match API cho gì?

`tft/match/v1/matches/{matchId}` trả về **một ảnh chụp DUY NHẤT ở cuối trận**
(thực chất là trạng thái lúc người chơi bị loại / trận kết thúc). Với mỗi người
trong 8 nhà, ta có:

- `placement`, `level`, `last_round`, `gold_left`, `players_eliminated`
- `traits` (tộc-hệ cuối, kèm mức style), `units` (quân cuối: id, số sao, đồ)
- `augments` (3 lõi đã chọn)

**KHÔNG có timeline.** Khác với LoL (có endpoint `/timeline` ghi sự kiện theo
phút), TFT Match API **không có** bản ghi theo từng round.

---

## 2. Cái gì LÀM ĐƯỢC từ dữ liệu cuối trận (đã làm trong `analyzer.py`)

| Mục | Cách làm |
|-----|----------|
| **Contest** (bị bao nhiêu nhà tranh) | So đội hình cuối của bạn với 7 nhà còn lại |
| **Lõi / carry** | Quân nào giữ nhiều đồ nhất / 3-sao |
| **Trần sức mạnh** | Heuristic: số 3-sao, số quân đủ 3 đồ, mốc tộc mạnh, lấp sân |
| **Econ cuối** | Vàng dư + level vs vòng kết thúc |
| **Điểm cải thiện** | Suy ra từ các chỉ số trên + thứ hạng |

> Lưu ý: "contest" tính từ đội hình **cuối** là *xấp xỉ*. Hai nhà có thể tranh
> nhau giữa trận rồi một bên pivot — dữ liệu cuối sẽ không thấy điều đó.

---

## 3. Cái gì KHÔNG làm được (cần dữ liệu LIVE trong game)

- Composition / econ / **shop** theo **từng round**
- **Xếp bài** (vị trí từng tướng trên sân)
- **Scout** (bạn có đi xem bàn nhà khác không)
- Đánh giá "quyết định có hợp thời điểm không" theo dòng thời gian

Những thứ này **không tồn tại** trong Match API. Muốn có, phải **đọc trạng thái
game lúc đang chơi**.

---

## 4. Hai hướng lấy dữ liệu live (cho bước sau, nếu anh muốn)

### Hướng A — Riot **Live Client Data API** (chính chủ Riot)
- Là API chạy nội bộ trên máy người chơi (`https://127.0.0.1:2999/...`) khi đang
  trong trận. Hợp lệ, Riot công khai cho LoL.
- Hạn chế với TFT: dữ liệu khá ít, chủ yếu cho LoL; phần TFT (shop, vàng, bàn cờ)
  hỗ trợ không đầy đủ → cần kiểm tra thực tế từng patch.

### Hướng B — **Overwolf Game Events Provider (GEP)** cho TFT
- Overwolf là đối tác được Riot phê duyệt; GEP cung cấp sự kiện live của TFT
  (vàng, level, round, đội hình, đôi khi cả shop) cho app companion.
- Đây là cách hầu hết app TFT (overlay) đang dùng. **Hợp lệ, an toàn tài khoản**
  vì chỉ ĐỌC, không can thiệp game.
- Đổi lại: phải viết app theo nền Overwolf (không còn là script Python thuần), và
  về bản chất nó **là một dạng companion/overlay** — khác với ràng buộc ban đầu
  của prototype ("không overlay").

### Hướng C — Giữ nguyên phạm vi hiện tại
- Chỉ phân tích sâu từ dữ liệu cuối trận (như `analyzer.py` đang làm), không đụng
  tới live. Đơn giản, an toàn, đúng tinh thần prototype ban đầu — nhưng không có
  dữ liệu từng round.

---

## 5. Khuyến nghị

- **Trước mắt:** dùng `analyzer.py` (Hướng C) để khai thác tối đa dữ liệu cuối
  trận — đã đủ cho contest, lõi, trần sức mạnh, gợi ý cải thiện.
- **Khi muốn phân tích theo từng round / xếp bài / scout:** chuyển sang **Hướng B
  (Overwolf GEP)** — đây là con đường thực tế và hợp lệ duy nhất để có dữ liệu
  live đầy đủ cho TFT. Cần chấp nhận rằng sản phẩm khi đó sẽ là một app companion.

Quyết định Hướng B/C là lựa chọn về **định hướng sản phẩm**, nên cần anh chốt
trước khi làm tiếp phần live.
