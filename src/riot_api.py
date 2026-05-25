"""
riot_api.py
===========
Gói gọn TẤT CẢ lời gọi HTTP tới Riot Games API.

Mỗi hàm chỉ làm đúng một việc: gọi một endpoint và trả về dữ liệu đã giải mã.
Mọi lỗi (key sai, không tìm thấy, quá tần suất, mạng hỏng...) đều được chuyển
thành ngoại lệ ``RiotApiError`` kèm thông báo tiếng Việt dễ hiểu, để tầng trên
chỉ việc in ra cho người dùng mà không phải lo về chi tiết kỹ thuật.
"""

import time
from urllib.parse import quote

import requests


# Số lần thử lại tối đa khi bị giới hạn tần suất (HTTP 429).
MAX_RETRIES_429 = 3
# Nếu Riot không gửi header Retry-After thì chờ tạm số giây này rồi thử lại.
DEFAULT_RETRY_WAIT_SECONDS = 5


class RiotApiError(Exception):
    """Lỗi đã được "dịch" sang thông báo thân thiện để in cho người dùng.

    Thuộc tính ``message`` luôn là một câu tiếng Việt rõ ràng.
    """

    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


def _xu(value: str) -> str:
    """URL-encode một đoạn đường dẫn (gameName / tagLine có thể có dấu cách).

    Dùng ``quote`` với ``safe=""`` để mã hóa cả dấu "/" phòng trường hợp tên
    người chơi chứa ký tự đặc biệt.
    """
    return quote(value, safe="")


def _request(url: str, api_key: str, timeout: int) -> requests.Response:
    """Gửi một GET request tới Riot API và xử lý mọi mã trạng thái HTTP.

    Trả về đối tượng Response nếu thành công (200). Mọi trường hợp khác đều
    ném ``RiotApiError`` với thông báo tiếng Việt. Riêng lỗi 429 sẽ tự động
    chờ rồi thử lại tối đa ``MAX_RETRIES_429`` lần trước khi bỏ cuộc.
    """
    headers = {"X-Riot-Token": api_key}

    for attempt in range(MAX_RETRIES_429 + 1):
        try:
            response = requests.get(url, headers=headers, timeout=timeout)
        except requests.exceptions.Timeout:
            raise RiotApiError(
                "Hết thời gian chờ phản hồi từ Riot (mạng chậm hoặc Riot đang bận). "
                "Hãy kiểm tra kết nối Internet rồi thử lại."
            )
        except requests.exceptions.ConnectionError:
            raise RiotApiError(
                "Không kết nối được tới máy chủ Riot. Hãy kiểm tra Internet "
                "(hoặc tường lửa/VPN đang chặn) rồi thử lại."
            )
        except requests.exceptions.RequestException as exc:
            raise RiotApiError(f"Lỗi mạng không xác định khi gọi Riot API: {exc}")

        status = response.status_code

        # 200: thành công.
        if status == 200:
            return response

        # 401 / 403: API key sai, thiếu hoặc đã hết hạn.
        if status in (401, 403):
            raise RiotApiError(
                "API key bị từ chối (sai hoặc đã HẾT HẠN).\n"
                "  • Key dạng 'Development' của Riot chỉ sống 24 giờ.\n"
                "  • Hãy vào https://developer.riotgames.com đăng nhập, copy "
                "'Development API Key' mới,\n"
                "    rồi dán đè vào file config/api_key.txt và chạy lại."
            )

        # 404: không tìm thấy (Riot ID gõ sai, hoặc người chơi chưa có trận nào).
        if status == 404:
            raise RiotApiError(
                "Không tìm thấy dữ liệu (HTTP 404).\n"
                "  • Có thể Riot ID gõ sai (đúng dạng Tên#Tag, ví dụ Faker#VN2),\n"
                "  • hoặc người chơi này chưa có trận TFT nào,\n"
                "  • hoặc cấu hình khu vực (routing) chưa khớp — xem mục xử lý sự cố trong README."
            )

        # 429: vượt giới hạn tần suất → đọc Retry-After, chờ rồi thử lại.
        if status == 429:
            if attempt < MAX_RETRIES_429:
                retry_after = response.headers.get("Retry-After")
                try:
                    wait_seconds = int(retry_after)
                except (TypeError, ValueError):
                    wait_seconds = DEFAULT_RETRY_WAIT_SECONDS
                print(
                    f"  ⏳ Bị giới hạn tần suất (429). Chờ {wait_seconds} giây rồi "
                    f"thử lại (lần {attempt + 1}/{MAX_RETRIES_429})..."
                )
                time.sleep(wait_seconds)
                continue
            raise RiotApiError(
                "Bị Riot giới hạn tần suất (HTTP 429) quá nhiều lần. "
                "Hãy đợi khoảng 1–2 phút rồi chạy lại."
            )

        # 5xx: máy chủ Riot đang gặp sự cố.
        if 500 <= status < 600:
            raise RiotApiError(
                f"Máy chủ Riot đang gặp sự cố (HTTP {status}). "
                "Đây là lỗi từ phía Riot, hãy thử lại sau ít phút."
            )

        # Mọi mã trạng thái lạ khác.
        raise RiotApiError(
            f"Riot API trả về mã trạng thái không mong đợi: HTTP {status}."
        )

    # Về lý thuyết không bao giờ chạy tới đây.
    raise RiotApiError("Đã thử lại nhiều lần nhưng vẫn thất bại khi gọi Riot API.")


def get_puuid(account_region: str, game_name: str, tag_line: str,
              api_key: str, timeout: int) -> str:
    """Bước 1 — Account API: đổi Riot ID (Tên#Tag) thành PUUID.

    Endpoint:
        GET https://{account_region}.api.riotgames.com
            /riot/account/v1/accounts/by-riot-id/{gameName}/{tagLine}
    """
    url = (
        f"https://{account_region}.api.riotgames.com"
        f"/riot/account/v1/accounts/by-riot-id/{_xu(game_name)}/{_xu(tag_line)}"
    )
    data = _request(url, api_key, timeout).json()
    puuid = data.get("puuid")
    if not puuid:
        raise RiotApiError("Riot trả về dữ liệu tài khoản nhưng thiếu PUUID (bất thường).")
    return puuid


def get_latest_match_ids(match_region: str, puuid: str, count: int,
                         api_key: str, timeout: int) -> list:
    """Bước 2 — TFT Match API: lấy danh sách ID trận gần nhất theo PUUID.

    Endpoint:
        GET https://{match_region}.api.riotgames.com
            /tft/match/v1/matches/by-puuid/{puuid}/ids?start=0&count={count}
    Trả về một mảng các match ID (mới nhất đứng đầu).
    """
    url = (
        f"https://{match_region}.api.riotgames.com"
        f"/tft/match/v1/matches/by-puuid/{_xu(puuid)}/ids"
        f"?start=0&count={count}"
    )
    return _request(url, api_key, timeout).json()


def get_match_detail(match_region: str, match_id: str,
                     api_key: str, timeout: int) -> dict:
    """Bước 3 — TFT Match API: lấy toàn bộ chi tiết của một trận.

    Endpoint:
        GET https://{match_region}.api.riotgames.com
            /tft/match/v1/matches/{matchId}
    Trả về dữ liệu thô (dict) đúng như Riot gửi về.
    """
    url = (
        f"https://{match_region}.api.riotgames.com"
        f"/tft/match/v1/matches/{_xu(match_id)}"
    )
    return _request(url, api_key, timeout).json()
