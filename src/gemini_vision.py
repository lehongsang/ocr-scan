import os
import base64
import io
import time
from typing import List, Dict, Any, Optional
from PIL import Image
import requests
from src.utils import logger
from src.config import GEMINI_API_KEY, GEMINI_MODEL, GEMINI_TEMPERATURE

# Mặc định sử dụng model gemini-3.5-flash-lite hoặc gemini-3.8-flash
VISION_MODEL = os.environ.get("GEMINI_VISION_MODEL", "gemini-3.5-flash-lite")

DEFAULT_OCR_PROMPT = (
    "Bạn là một chuyên gia OCR tài liệu có độ chính xác cao. "
    "Nhiệm vụ của bạn là đọc và trích xuất TOÀN BỘ văn bản xuất hiện trong hình ảnh này. "
    "Yêu cầu:\n"
    "1. Giữ nguyên toàn bộ nội dung tiếng Việt có dấu, chữ số, ký hiệu đặc biệt.\n"
    "2. Giữ nguyên cấu trúc dòng, đoạn, danh sách hoặc dạng bảng nếu có.\n"
    "3. Nếu là chữ viết tay (ví dụ trong đơn thuốc, bệnh án), hãy đọc cẩn thận và dịch sát nhất có thể.\n"
    "4. Tuyệt đối KHÔNG tự ý thêm lời giải thích, mở đầu hay kết luận. Chỉ xuất ra nội dung văn bản đọc được."
)

def _get_image_mime_type(image_bytes: bytes, filename: str = "") -> str:
    """Xác định MIME type từ phần mở rộng hoặc magic bytes"""
    fn_lower = filename.lower()
    if fn_lower.endswith(".png"):
        return "image/png"
    if fn_lower.endswith(".webp"):
        return "image/webp"
    if fn_lower.endswith(".bmp"):
        return "image/bmp"
    if fn_lower.endswith(".tiff") or fn_lower.endswith(".tif"):
        return "image/tiff"
    
    # Kiểm tra magic bytes
    if image_bytes.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if image_bytes.startswith(b"RIFF") and b"WEBP" in image_bytes[:16]:
        return "image/webp"
    if image_bytes.startswith(b"BM"):
        return "image/bmp"
    return "image/jpeg"

def ocr_image_gemini(
    image_bytes: bytes,
    filename: str = "",
    prompt: Optional[str] = None,
    api_key: Optional[str] = None,
    model: Optional[str] = None
) -> str:
    """
    Thực hiện OCR một ảnh bằng Gemini Vision API.
    Tự động thử lại và chuyển đổi model dự phòng (fallback) nếu gặp lỗi 503/429 (quá tải).
    """
    key = api_key or GEMINI_API_KEY
    if not key or key == "YOUR_API_KEY":
        raise ValueError("Chưa cấu hình GEMINI_API_KEY hợp lệ trong file .env")

    # Danh sách các model thử nghiệm theo thứ tự ưu tiên
    primary_model = model or VISION_MODEL
    candidate_models = [primary_model]
    for fallback in ["gemini-3.5-flash-lite", "gemini-3.8-flash", "gemini-3.5-flash"]:
        if fallback not in candidate_models:
            candidate_models.append(fallback)

    mime_type = _get_image_mime_type(image_bytes, filename)
    image_b64 = base64.b64encode(image_bytes).decode("utf-8")
    instruction = prompt.strip() if (prompt and prompt.strip()) else DEFAULT_OCR_PROMPT

    payload = {
        "contents": [
            {
                "parts": [
                    {
                        "inline_data": {
                            "mime_type": mime_type,
                            "data": image_b64
                        }
                    },
                    {
                        "text": instruction
                    }
                ]
            }
        ],
        "generationConfig": {
            "temperature": GEMINI_TEMPERATURE,
            "maxOutputTokens": 4096
        }
    }
    headers = {"Content-Type": "application/json"}

    last_error = ""
    for current_model in candidate_models:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{current_model}:generateContent?key={key}"
        
        # Thử gọi API (tối đa 2 lần cho mỗi model nếu gặp 503)
        for attempt in range(2):
            try:
                response = requests.post(url, json=payload, headers=headers, timeout=35)
                if response.status_code == 200:
                    resp_json = response.json()
                    candidates = resp_json.get("candidates", [])
                    if not candidates:
                        return ""
                    parts = candidates[0].get("content", {}).get("parts", [])
                    return "".join([p.get("text", "") for p in parts]).strip()

                # Nếu bị 503 (High Demand) hoặc 429 (Rate Limit)
                if response.status_code in (503, 429):
                    last_error = f"Model {current_model} trả về {response.status_code} (quá tải)"
                    time.sleep(1.0)
                    continue

                # Lỗi khác (400, 404, etc.)
                err_text = response.text
                try:
                    err_json = response.json()
                    if "error" in err_json and "message" in err_json["error"]:
                        err_text = err_json["error"]["message"]
                except Exception:
                    pass
                last_error = f"Lỗi Gemini Vision ({response.status_code}): {err_text}"
                break

            except requests.RequestException as e:
                last_error = f"Lỗi kết nối tới {current_model}: {str(e)}"
                time.sleep(0.5)

    raise RuntimeError(f"Không thể OCR ảnh qua Gemini Vision sau khi thử các model: {last_error}")
