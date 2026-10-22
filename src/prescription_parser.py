import os
import sys
import json
import re
import io
from typing import List, Dict, Any, Optional, Tuple
from PIL import Image
import fitz  # PyMuPDF
import requests

from src.utils import logger
from src.config import GEMINI_API_KEY, GEMINI_TEMPERATURE
from src.gemini_vision import VISION_MODEL, _get_image_mime_type
from src.drug_matcher import DrugCatalogMatcher, parse_drug_line_details

PRESCRIPTION_SYSTEM_PROMPT = """Bạn là một chuyên gia y tế và dược sĩ có kinh nghiệm phân tích đơn thuốc, phiếu khám, toa thuốc (cả bản in vi tính và chữ viết tay của bác sĩ).
Nhiệm vụ của bạn là đọc toàn bộ hình ảnh đơn thuốc này và bóc tách cấu trúc dữ liệu chính xác thành định dạng JSON chuẩn.

Yêu cầu nghiêm ngặt:
1. Đọc kỹ tất cả các loại thuốc được kê trong đơn thuốc. Cố gắng luận giải chính xác tên thuốc viết tay hoặc viết tắt.
2. Với mỗi thuốc, tách riêng:
   - "stt": Số thứ tự của thuốc trong đơn (ví dụ: "1", "2"...)
   - "raw_name": Tên thuốc (biệt dược hoặc hoạt chất) cùng hàm lượng nếu có (ví dụ: "Augmentin 1g", "Panadol Extra 500mg", "Klamentin 1g", "Nexium 40mg")
   - "strength": Hàm lượng ghi trên đơn (ví dụ: "1g", "500mg", "40mg", "100ml"...)
   - "quantity": Số lượng & đơn vị tính (ví dụ: "14 viên", "1 hộp", "20 gói", "1 chai"...)
   - "usage": Hướng dẫn liều dùng và cách dùng (ví dụ: "Uống 1 viên x 2 lần/ngày sau khi ăn", "Sáng 1 viên, tối 1 viên"...)
3. Bóc tách thông tin chung của đơn thuốc trong "prescription_info":
   - "patient_name": Tên bệnh nhân
   - "age": Tuổi
   - "gender": Giới tính
   - "diagnosis": Chẩn đoán bệnh
   - "doctor_name": Tên bác sĩ kê đơn
   - "facility_name": Tên bệnh viện hoặc phòng khám
   - "date": Ngày kê đơn
4. Trả về toàn bộ nội dung chữ đọc được trong đơn thuốc vào trường "raw_text".
5. CHỈ TRẢ VỀ DUY NHẤT ĐỊNH DẠNG JSON hợp lệ theo cấu trúc sau, không kèm lời giải thích, không markdown codeblock thừa:
{
  "prescription_info": {
    "patient_name": "",
    "age": "",
    "gender": "",
    "diagnosis": "",
    "doctor_name": "",
    "facility_name": "",
    "date": ""
  },
  "medications": [
    {
      "stt": "1",
      "raw_name": "",
      "strength": "",
      "quantity": "",
      "usage": ""
    }
  ],
  "raw_text": ""
}
"""

def extract_prescription_gemini(
    image_items: List[Tuple[str, bytes]],
    api_key: Optional[str] = None
) -> Dict[str, Any]:
    """
    Sử dụng Gemini Vision để phân tích và bóc tách đơn thuốc từ 1 hoặc nhiều ảnh.
    """
    key = api_key or GEMINI_API_KEY
    if not key or key == "YOUR_API_KEY":
        raise ValueError("Chưa cấu hình GEMINI_API_KEY hợp lệ trong file .env")

    parts = []
    for fname, bts in image_items:
        mime_type = _get_image_mime_type(bts, fname)
        import base64
        b64 = base64.b64encode(bts).decode("utf-8")
        parts.append({
            "inline_data": {
                "mime_type": mime_type,
                "data": b64
            }
        })

    parts.append({
        "text": PRESCRIPTION_SYSTEM_PROMPT
    })

    candidate_models = [VISION_MODEL, "gemini-3.5-flash-lite", "gemini-3.8-flash", "gemini-3.5-flash"]
    payload = {
        "contents": [{"parts": parts}],
        "generationConfig": {
            "temperature": 0.1,
            "maxOutputTokens": 4096,
            "responseMimeType": "application/json"
        }
    }
    headers = {"Content-Type": "application/json"}

    last_error = ""
    for model_name in candidate_models:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={key}"
        for attempt in range(2):
            try:
                resp = requests.post(url, headers=headers, json=payload, timeout=90)
                if resp.status_code == 200:
                    data = resp.json()
                    candidates = data.get("candidates", [])
                    if candidates:
                        text_resp = candidates[0].get("content", {}).get("parts", [{}])[0].get("text", "")
                        # Parse JSON an toàn
                        text_clean = text_resp.strip()
                        if text_clean.startswith("```json"):
                            text_clean = text_clean[7:]
                        if text_clean.startswith("```"):
                            text_clean = text_clean[3:]
                        if text_clean.endswith("```"):
                            text_clean = text_clean[:-3]
                        return json.loads(text_clean.strip())
                elif resp.status_code in (429, 503):
                    import time
                    time.sleep(2)
                    continue
                else:
                    last_error = f"Model {model_name} HTTP {resp.status_code}: {resp.text}"
                    break
            except Exception as e:
                last_error = f"Model {model_name} error: {str(e)}"
                import time
                time.sleep(1)

    raise RuntimeError(f"Không thể phân tích đơn thuốc qua Gemini Vision: {last_error}")

def parse_prescription_text_rule_based(raw_text: str) -> Dict[str, Any]:
    """
    Bóc tách danh sách thuốc từ text thô bằng Rule-based & Regex (cho OCR offline / Tesseract / RapidOCR)
    """
    lines = [line.strip() for line in raw_text.split("\n") if line.strip()]
    medications = []
    
    # Tìm vùng chứa thuốc (thường sau 'Thuốc điều trị', 'Đơn thuốc', 'Toa thuốc', 'Chỉ định')
    is_in_med_section = False
    idx = 1

    for line in lines:
        lower = line.lower()
        if any(keyword in lower for keyword in ["đơn thuốc", "toa thuốc", "thuốc điều trị", "danh mục thuốc", "chỉ định dùng thuốc"]):
            is_in_med_section = True
            continue

        # Kiểm tra nếu là dòng kê thuốc (bắt đầu bằng STT hoặc có số lượng / cách dùng)
        stt_match = re.match(r'^([\d]{1,2})[\.\)\/\-\s]+([a-zA-ZÀ-ỹ].*)$', line)
        if stt_match:
            parsed = parse_drug_line_details(line)
            medications.append({
                "stt": parsed["stt"] or str(idx),
                "raw_name": parsed["clean_name"],
                "strength": parsed["strength"],
                "quantity": parsed["quantity"],
                "usage": parsed["usage"]
            })
            idx += 1
        elif is_in_med_section and re.search(r'(?i)\b(viên|gói|ống|chai|lọ|hộp|tuýp|vỉ)\b', line):
            parsed = parse_drug_line_details(line)
            medications.append({
                "stt": str(idx),
                "raw_name": parsed["clean_name"],
                "strength": parsed["strength"],
                "quantity": parsed["quantity"],
                "usage": parsed["usage"]
            })
            idx += 1

    return {
        "prescription_info": {},
        "medications": medications,
        "raw_text": raw_text
    }

def process_prescription_document(
    file_bytes: bytes,
    filename: str,
    engine_type: str = "gemini",
    threshold: float = 75.0
) -> Dict[str, Any]:
    """
    Hàm tổng xử lý đơn thuốc từ dữ liệu byte của tệp (Ảnh hoặc PDF).
    1. Kiểm tra định dạng (PDF hoặc Ảnh).
    2. Nếu PDF, trích xuất text trực tiếp hoặc render trang thành ảnh.
    3. Chạy phân tích qua Gemini Vision hoặc Local OCR + Rule-based.
    4. Đối chiếu toàn bộ danh sách thuốc với từ điển 44.000+ thuốc chuẩn (DrugCatalogMatcher).
    5. Trả về cấu trúc JSON hoàn chỉnh, bao gồm mảng tên các thuốc (drug_names) và thông tin chi tiết.
    """
    matcher = DrugCatalogMatcher.get_instance()
    fn_lower = filename.lower()
    is_pdf = fn_lower.endswith(".pdf") or file_bytes.startswith(b"%PDF")

    image_items: List[Tuple[str, bytes]] = []
    raw_ocr_text = ""

    if is_pdf:
        # Xử lý PDF
        doc = fitz.open(stream=file_bytes, filetype="pdf")
        total_pages = len(doc)
        logger.info(f"Đang xử lý đơn thuốc PDF gồm {total_pages} trang: {filename}")

        for page_idx in range(total_pages):
            page = doc[page_idx]
            # Render trang sang ảnh để xử lý OCR chất lượng cao
            zoom = 2.0  # 144 DPI
            mat = fitz.Matrix(zoom, zoom)
            pix = page.get_pixmap(matrix=mat, alpha=False)
            img_bytes = pix.tobytes("jpeg")
            image_items.append((f"{filename}_page_{page_idx+1}.jpg", img_bytes))
        doc.close()
    else:
        # Xử lý ảnh trực tiếp
        image_items.append((filename, file_bytes))

    # Thực hiện bóc tách
    extracted_data = None
    engine_used = engine_type.lower()

    if engine_used == "gemini":
        try:
            extracted_data = extract_prescription_gemini(image_items)
            raw_ocr_text = extracted_data.get("raw_text", "")
        except Exception as e:
            logger.warning(f"Gemini Vision lỗi hoặc không khả dụng ({e}), chuyển sang RapidOCR/Tesseract fallback.")
            engine_used = "fallback_local"

    if extracted_data is None:
        # Fallback sang OCR cục bộ
        from src.ocr_engine import ocr_multiple_images
        ocr_res = ocr_multiple_images(image_items, engine_type="rapidocr")
        raw_ocr_text = ocr_res.get("combined_text", "")
        extracted_data = parse_prescription_text_rule_based(raw_ocr_text)

    # Đối chiếu toàn bộ danh sách thuốc với từ điển chuẩn
    raw_meds = extracted_data.get("medications", [])
    matched_medications = []
    drug_names_list = []

    for item in raw_meds:
        raw_name = item.get("raw_name") or ""
        # Kết hợp raw_name và strength nếu có để tăng độ chính xác matching
        full_query = raw_name
        if item.get("strength") and item.get("strength") not in raw_name:
            full_query = f"{raw_name} {item.get('strength')}"

        match_res = matcher.match_drug_name(full_query, threshold=threshold)
        
        # Nếu match_res không tìm thấy với full_query, thử chỉ với raw_name
        if not match_res.get("matched") and raw_name != full_query:
            match_res = matcher.match_drug_name(raw_name, threshold=threshold)

        final_drug_name = match_res.get("drug_name") if match_res.get("matched") else raw_name
        
        matched_item = {
            "stt": item.get("stt", ""),
            "raw_name": raw_name,
            "matched_name": final_drug_name,
            "base_name": match_res.get("base_name", ""),
            "active_ingredient": match_res.get("active_ingredient", ""),
            "strength": item.get("strength") or match_res.get("strength", ""),
            "dosage_form": match_res.get("dosage_form", ""),
            "quantity": item.get("quantity") or match_res.get("quantity", ""),
            "usage": item.get("usage") or match_res.get("usage", ""),
            "confidence": match_res.get("confidence", 0.0),
            "match_type": match_res.get("match_type", "none"),
            "is_verified": match_res.get("matched", False)
        }

        matched_medications.append(matched_item)
        if final_drug_name and final_drug_name not in drug_names_list:
            drug_names_list.append(final_drug_name)

    return {
        "status": "success",
        "total_medications": len(matched_medications),
        "drug_names": drug_names_list,
        "prescription_info": extracted_data.get("prescription_info", {}),
        "medications": matched_medications,
        "raw_ocr_text": raw_ocr_text,
        "engine_used": engine_used
    }
