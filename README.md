# TFT Match Collector

Phần mềm dòng lệnh nhỏ, chạy trên Windows, dùng để **thu thập dữ liệu trận đấu
Đấu Trường Chân Lý (Teamfight Tactics — TFT) gần nhất** của một người chơi thông
qua **API chính thức của Riot Games**, rồi lưu lại để phân tích sau.

> Đây là prototype nội bộ. Phần mềm **chỉ gọi API chính thức của Riot** — không
> overlay, không giao diện đồ họa, không can thiệp vào game. Đây là cách hợp lệ
> và an toàn duy nhất cho tài khoản người chơi.

---

## 1. Yêu cầu

- **Python 3.10 trở lên**. Tải tại: https://www.python.org/downloads/
  - ⚠️ Khi cài, **nhớ tích vào ô "Add Python to PATH"** ở màn hình đầu tiên.
- Kết nối Internet.
- Một **API key của Riot** (xem bước 2).

---

## 2. Lấy API key của Riot

1. Mở trình duyệt vào: https://developer.riotgames.com
2. **Đăng nhập** bằng tài khoản Riot của bạn.
3. Tìm mục **"Development API Key"**, bấm **Copy**.
   > ⏰ Key dạng Development **hết hạn sau 24 giờ**. Hôm sau dùng lại thì phải
   > vào lấy key mới và dán lại.

---

## 3. Bỏ API key vào phần mềm

1. Mở thư mục `config/`.
2. Mở file **`config/api_key.txt`** bằng **Notepad**.
   - Nếu chưa có file này, hãy tạo mới một file tên đúng là `api_key.txt`
     trong thư mục `config/` (có thể copy từ `api_key.example.txt` rồi đổi tên).
3. **Dán API key vào (đúng 1 dòng)**, xóa hết nội dung mẫu.
4. **Lưu lại** (Ctrl + S).

> 🔒 File `config/api_key.txt` đã được `.gitignore` loại trừ nên **không bao giờ
> bị commit/chia sẻ nhầm**. Tuyệt đối không dán key vào trong code.

---

## 4. Cách chạy

**Cách dễ nhất:** bấm đúp vào file **`run.bat`**.

Phần mềm sẽ:
1. Kiểm tra Python, tự cài thư viện `requests` nếu thiếu.
2. Hỏi bạn **Riot ID** của người chơi cần tra (dạng `Tên#Tag`, ví dụ `Faker#VN2`).
   - Nếu bạn đã đặt sẵn `default_riot_id` trong `config/settings.json` thì nó
     dùng luôn, không hỏi nữa.
3. Gọi Riot API theo 3 bước: **Riot ID → PUUID → trận gần nhất → chi tiết trận**.
4. Lưu kết quả vào thư mục `output/`.

> 💡 **Test trước khi có key:** muốn xem thử bản tóm tắt mà chưa cần API key,
> mở Command Prompt trong thư mục dự án và gõ:
> ```
> python src\main.py --test
> ```
> Lệnh này đọc file mẫu `samples/sample_match.json` và sinh bản tóm tắt mẫu.

---

## 5. Nơi xem kết quả

Mỗi lần chạy tạo **2 file** trong thư mục `output/`, đặt tên theo mã trận:

| File | Nội dung |
|------|----------|
| `{matchId}_raw.json` | Toàn bộ dữ liệu **thô** từ Riot (giữ nguyên, có thụt dòng cho dễ đọc). |
| `{matchId}_summary.txt` | **Bản tóm tắt tiếng Việt**: thông tin chung, người chơi được tra cứu (hạng, level, vàng, trait, đội hình tướng, augment), và bảng xếp hạng cả 8 người. |

> Dữ liệu thật trong `output/` đã được `.gitignore` loại trừ.

---

## 6. Cấu hình — `config/settings.json`

```json
{
  "account_region": "asia",
  "match_region": "sea",
  "default_riot_id": "",
  "request_timeout_seconds": 15
}
```

| Trường | Ý nghĩa |
|--------|---------|
| `account_region` | Cluster cho **Account API** (đổi Riot ID → PUUID). Máy chủ Việt Nam dùng **`asia`**. |
| `match_region` | Region cho **TFT Match API**. Máy chủ Việt Nam (VN2) dùng **`sea`**. |
| `default_riot_id` | Riot ID mặc định (dạng `Tên#Tag`). Để **trống** thì phần mềm sẽ hỏi mỗi lần chạy. |
| `request_timeout_seconds` | Số giây tối đa chờ Riot phản hồi mỗi request. |

> ✅ Theo tài liệu chính thức của Riot: Vietnam có **platform routing `VN2`** và
> **regional routing `SEA`** (cho match-v1); Account API dùng cluster **`asia`**.
> Vì vậy mặc định ở trên là đúng cho người chơi Việt Nam.

---

## 7. Xử lý sự cố thường gặp

| Hiện tượng | Nguyên nhân & cách xử lý |
|-----------|--------------------------|
| Báo **"API key bị từ chối / hết hạn"** (401/403) | Key Development chỉ sống 24 giờ. Lấy key mới ở https://developer.riotgames.com rồi dán lại vào `config/api_key.txt`. |
| Báo **"Không tìm thấy" (404)** | (a) Riot ID gõ sai — đúng dạng `Tên#Tag` (ví dụ `Faker#VN2`); (b) người chơi chưa có trận TFT nào; (c) **sai routing khu vực**. |
| Nghi sai **routing khu vực** | Mặc định VN dùng `account_region=asia`, `match_region=sea`. Nếu vẫn 404 bất thường, thử đổi `match_region` thành `asia` trong `config/settings.json`. |
| Báo **"giới hạn tần suất" (429)** | Bạn gọi quá nhanh. Phần mềm tự chờ và thử lại; nếu vẫn lỗi, đợi 1–2 phút rồi chạy lại. |
| Báo **lỗi mạng / hết thời gian chờ** | Kiểm tra Internet, tường lửa/VPN; tăng `request_timeout_seconds` nếu mạng chậm. |
| Cửa sổ chạy xong **tự tắt** | Hãy chạy qua `run.bat` (có lệnh `pause` giữ cửa sổ), đừng bấm đúp thẳng vào `main.py`. |

---

## 8. Cấu trúc dự án

```
tft-match-collector/
├── config/
│   ├── api_key.txt          # (Bạn tự tạo) dán API key vào đây — KHÔNG commit.
│   ├── api_key.example.txt   # File mẫu để tham khảo định dạng key.
│   └── settings.json         # Cấu hình khu vực, Riot ID mặc định, timeout.
├── src/
│   ├── main.py               # Điểm khởi chạy, điều phối toàn bộ.
│   ├── riot_api.py           # Mọi lời gọi HTTP tới Riot API + xử lý lỗi.
│   ├── collector.py          # Logic: Riot ID → PUUID → match ID → chi tiết trận.
│   └── summarizer.py         # Sinh bản tóm tắt tiếng Việt từ dữ liệu trận.
├── output/                   # Nơi lưu kết quả (tự tạo nếu chưa có).
├── samples/
│   └── sample_match.json     # Dữ liệu trận giả để test ngoại tuyến (--test).
├── run.bat                   # Bấm đúp để chạy trên Windows.
├── requirements.txt          # Thư viện cần cài (chỉ có requests).
├── .gitignore
└── README.md
```
