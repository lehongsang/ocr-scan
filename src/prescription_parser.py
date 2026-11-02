import os
import sys
import json
import re
import io
import time
from typing import List, Dict, Any, Optional, Tuple
from PIL import Image
import fitz  # PyMuPDF
import requests

from src.utils import logger
from src.config import GEMINI_API_KEY, GEMINI_TEMPERATURE, GEMINI_VISION_MODEL
from src.gemini_vision import _get_image_mime_type

PRESCRIPTION_SYSTEM_PROMPT = """Bạn là một chuyên gia y tế và dược sĩ có kinh nghiệm phân tích đơn thuốc, toa thuốc, phiếu khám bệnh (bao gồm cả bản in máy tính và chữ viết tay của bác sĩ).
Nhiệm vụ của bạn là đọc toàn bộ hình ảnh đơn thuốc này và phân tích trực tiếp thuần túy từ thị giác (Vision OCR) để bóc tách cấu trúc dữ liệu chính xác thành định dạng JSON chuẩn theo các trường DTO (camelCase).

Yêu cầu nghiêm ngặt cho từng loại thuốc kê trong đơn:
Trích xuất đúng và đầy đủ các trường dữ liệu sau cho mỗi thuốc (nếu có thông tin thì điền, nếu không có thì để chuỗi rỗng "" hoặc null):
1. "order": Số thứ tự của thuốc trong đơn (số nguyên 1, 2, 3...).
2. "drugName": Tên thuốc / biệt dược ghi trên đơn (VD: Efferalgan, Augmentin, Nexium, Panadol Extra...).
3. "activeIngredient": Tên hoạt chất chính của thuốc. Nếu trên đơn có ghi rõ hoạt chất thì trích xuất; nếu đơn chỉ ghi tên biệt dược thì dựa vào kiến thức dược lý chuyên môn để xác định chính xác tên hoạt chất (VD: Efferalgan -> Paracetamol, Augmentin -> Amoxicillin + Acid clavulanic, Nexium -> Esomeprazole; nếu không xác định được thì để "").
4. "strength": Hàm lượng hoặc nồng độ của thuốc ghi trên đơn (VD: 500mg, 1g, 40mg, 250mg/5ml, 0.5%...).
5. "unit": Đơn vị tính của thuốc (VD: viên, gói, chai, lọ, ống, tuýp, vỉ, hộp, tép...).
6. "quantity": Số lượng thuốc được kê dạng số (VD: 10, 14, 1, 20...). Nếu không có thì để null.
7. "route": Đường dùng thuốc (VD: Uống, Tiêm bắp, Tiêm tĩnh mạch, Bôi ngoài da, Nhỏ mắt, Nhỏ tai, Đặt hậu môn, Đặt dưới lưỡi, Hít/Khí dung...). Mặc định là "Uống" nếu là dạng viên uống.
8. "instructions": Hướng dẫn chi tiết về cách dùng, cách pha, thời điểm dùng so với bữa ăn hoặc cách thao tác (VD: uống sau ăn no, uống trước ăn 30 phút, hòa tan trong 100ml nước, thoa một lớp mỏng...).
9. "timing": Thời điểm hoặc lịch trình dùng thuốc trong ngày, khoảng cách giữa các lần, hoặc điều kiện triệu chứng khi dùng (VD: ngày 2 lần sáng 1 viên - tối 1 viên, uống khi sốt hơn 38.5*C, dùng trong 5 ngày...).

Ngoài ra, trích xuất:
- "prescription_info": Thông tin hành chính của đơn thuốc:
  + "patient_name": Tên bệnh nhân
  + "age": Tuổi hoặc năm sinh
  + "gender": Giới tính
  + "diagnosis": Chẩn đoán bệnh
  + "doctor_name": Tên bác sĩ kê đơn
  + "facility_name": Tên cơ sở khám chữa bệnh / bệnh viện / phòng khám
  + "date": Ngày kê đơn
- "raw_text": Toàn bộ văn bản đọc được từ ảnh đơn thuốc.

CHỈ TRẢ VỀ DUY NHẤT ĐỊNH DẠNG JSON hợp lệ theo cấu trúc sau, không kèm bất kỳ giải thích hay markdown codeblock thừa:
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
      "order": 1,
      "drugName": "Efferalgan",
      "activeIngredient": "Paracetamol",
      "strength": "500mg",
      "unit": "viên",
      "quantity": 10,
      "route": "Uống",
      "instructions": "uống sau ăn no",
      "timing": "uống khi sốt hơn 38*C"
    }
  ],
  "raw_text": ""
}
"""

def _get_document_mime_type(file_bytes: bytes, filename: str = "") -> str:
    """Xác định MIME type cho tệp tin (ảnh hoặc PDF)"""
    fn_lower = filename.lower()
    if fn_lower.endswith(".pdf") or file_bytes.startswith(b"%PDF"):
        return "application/pdf"
    return _get_image_mime_type(file_bytes, filename)

def extract_prescription_gemini(
    image_items: List[Tuple[str, bytes]],
    api_key: Optional[str] = None
) -> Dict[str, Any]:
    """
    Sử dụng Gemini Vision để phân tích và bóc tách đơn thuốc thuần Vision từ 1 hoặc nhiều ảnh / tệp PDF gốc.
    """
    key = api_key or GEMINI_API_KEY
    if not key or key == "YOUR_API_KEY":
        raise ValueError("Chưa cấu hình GEMINI_API_KEY hợp lệ trong file .env")

    parts = []
    for fname, bts in image_items:
        mime_type = _get_document_mime_type(bts, fname)
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

    candidate_models = [GEMINI_VISION_MODEL, "gemini-3.5-flash", "gemini-3.5-flash-lite"]
    seen = set()
    unique_models = []
    for m in candidate_models:
        if m and m not in seen:
            seen.add(m)
            unique_models.append(m)

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
    for model_name in unique_models:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={key}"
        for attempt in range(2):
            try:
                resp = requests.post(url, headers=headers, json=payload, timeout=30)
                if resp.status_code == 200:
                    data = resp.json()
                    candidates = data.get("candidates", [])
                    if candidates:
                        text_resp = candidates[0].get("content", {}).get("parts", [{}])[0].get("text", "")
                        text_clean = text_resp.strip()
                        if text_clean.startswith("```json"):
                            text_clean = text_clean[7:]
                        if text_clean.startswith("```"):
                            text_clean = text_clean[3:]
                        if text_clean.endswith("```"):
                            text_clean = text_clean[:-3]
                        return json.loads(text_clean.strip())
                elif resp.status_code in (429, 503):
                    last_error = f"Model {model_name} HTTP {resp.status_code} (quá tải)"
                    logger.warning(f"Gemini API {model_name} (lần thử {attempt + 1}/2) trả về HTTP {resp.status_code}. Thử lại...")
                    time.sleep(1.5)
                    continue
                else:
                    last_error = f"Model {model_name} HTTP {resp.status_code}: {resp.text}"
                    logger.warning(f"Gemini API {model_name} gặp lỗi: {last_error}")
                    break
            except Exception as e:
                last_error = f"Model {model_name} error: {str(e)}"
                logger.warning(f"Gemini API {model_name} ngoại lệ: {last_error}")
                time.sleep(1.0)

    raise RuntimeError(f"Không thể phân tích đơn thuốc qua Gemini Vision: {last_error}")

def normalize_medication_item(item: Dict[str, Any], idx: int = 1) -> Dict[str, Any]:
    """
    Chuẩn hóa dữ liệu từng dòng thuốc theo đúng chuẩn DTO Backend (camelCase) và tương thích ngược alias tiếng Việt:
    drugName | activeIngredient | strength | unit | quantity | route | instructions | timing | order
    """
    raw_order = item.get("order") if item.get("order") is not None else (item.get("stt") or item.get("index") or idx)
    try:
        order_val = int(raw_order)
    except (ValueError, TypeError):
        order_val = idx

    drug_name = str(item.get("drugName") or item.get("drug_name") or item.get("ten_thuoc") or item.get("Tên thuốc") or item.get("raw_name") or item.get("name") or "").strip()
    active_ingredient = str(item.get("activeIngredient") or item.get("active_ingredient") or item.get("ten_hoat_chat") or item.get("Tên hoạt chất") or item.get("hoat_chat") or "").strip()
    strength = str(item.get("strength") or item.get("ham_luong") or item.get("hàm lượng") or item.get("dosage") or "").strip()
    unit = str(item.get("unit") or item.get("don_vi_tinh") or item.get("đơn vị tính") or item.get("dvt") or "").strip()

    raw_qty = item.get("quantity") if item.get("quantity") is not None else (item.get("so_luong") or item.get("số lượng") or item.get("sl"))
    qty_num: Optional[float] = None
    if raw_qty is not None:
        if isinstance(raw_qty, (int, float)):
            qty_num = raw_qty
        else:
            clean_q = re.sub(r'[^\d\.]', '', str(raw_qty).replace(',', '.'))
            if clean_q:
                try:
                    qty_num = int(clean_q) if '.' not in clean_q else float(clean_q)
                except ValueError:
                    qty_num = None

    route = str(item.get("route") or item.get("duong_dung") or item.get("đường dùng") or "").strip()
    if not route:
        route = "Uống"

    instructions = str(item.get("instructions") or item.get("cach_dung") or item.get("cách dùng") or item.get("usage") or item.get("instruction") or "").strip()
    timing = str(item.get("timing") or item.get("thoi_gian_dung") or item.get("thời gian dùng") or item.get("schedule") or "").strip()

    return {
        "order": order_val,
        "drugName": drug_name,
        "activeIngredient": active_ingredient,
        "strength": strength,
        "unit": unit,
        "quantity": qty_num,
        "route": route,
        "instructions": instructions,
        "timing": timing
    }

def parse_prescription_text_rule_based(raw_text: str) -> Dict[str, Any]:
    """
    Bóc tách danh sách thuốc từ text thô bằng Rule-based & Regex (cho OCR offline / RapidOCR fallback).
    Không sử dụng database thuốc, bóc tách trực tiếp theo cấu trúc dòng thành các trường DTO.
    """
    lines = [line.strip() for line in raw_text.split("\n") if line.strip()]
    medications = []
    
    unit_pattern = r'\b(viên|gói|ống|chai|lọ|hộp|tuýp|vỉ|tép|bình|liều)\b'
    strength_pattern = r'(\d+(?:[\.,]\d+)?\s*(?:mg|g|ml|mcg|µg|%|iu|ui))\b'
    route_pattern = r'\b(uống|tiêm bắp|tiêm tĩnh mạch|tiêm|bôi|nhỏ mắt|nhỏ tai|đặt|hít|ngậm)\b'
    
    idx = 1
    for line in lines:
        lower = line.lower()
        if any(keyword in lower for keyword in ["đơn thuốc", "toa thuốc", "thuốc điều trị", "danh mục thuốc", "chỉ định dùng thuốc"]):
            continue

        stt_match = re.match(r'^([\d]{1,2})[\.\)\/\-\s]+([a-zA-ZÀ-ỹ].*)$', line)
        if stt_match or re.search(unit_pattern, line, re.I):
            cur_line = stt_match.group(2) if stt_match else line
            stt = stt_match.group(1) if stt_match else str(idx)

            strength = ""
            s_match = re.search(strength_pattern, cur_line, re.I)
            if s_match:
                strength = s_match.group(1)

            unit = ""
            u_match = re.search(unit_pattern, cur_line, re.I)
            if u_match:
                unit = u_match.group(1)

            quantity = ""
            q_match = re.search(r'(?:sl|số lượng|x|\-)?\s*(\d+)\s*(?:' + unit_pattern + r')?', cur_line, re.I)
            if q_match:
                quantity = q_match.group(1)

            route = "Uống"
            r_match = re.search(route_pattern, cur_line, re.I)
            if r_match:
                route = r_match.group(1).capitalize()

            clean_name = cur_line
            clean_name = re.sub(r'[\-–xX]\s*\d+.*$', '', clean_name).strip()
            if strength and strength in clean_name:
                clean_name = clean_name.replace(strength, "").strip()

            order_int = int(stt) if stt.isdigit() else idx
            qty_int = int(quantity) if quantity and quantity.isdigit() else None

            medications.append({
                "order": order_int,
                "drugName": clean_name.strip(" -:,"),
                "activeIngredient": "",
                "strength": strength,
                "unit": unit,
                "quantity": qty_int,
                "route": route,
                "instructions": "Theo chỉ dẫn bác sĩ",
                "timing": ""
            })
            idx += 1

    return {
        "prescription_info": {},
        "medications": medications,
        "raw_text": raw_text
    }

def process_prescription_images(
    image_items: List[Tuple[str, bytes]],
    **kwargs
) -> Dict[str, Any]:
    """
    Hàm phân tích đơn thuốc thuần Vision bằng Gemini Vision.
    Tự động đọc và bóc tách trực tiếp các trường DTO:
    drugName | activeIngredient | strength | unit | quantity | route | instructions | timing | order
    """
    extracted_data = extract_prescription_gemini(image_items)
    raw_ocr_text = extracted_data.get("raw_text", "")

    raw_meds = extracted_data.get("medications", [])
    normalized_meds = []
    drug_names = []

    for i, item in enumerate(raw_meds, 1):
        norm_item = normalize_medication_item(item, idx=i)
        normalized_meds.append(norm_item)
        target_name = norm_item.get("drugName") or norm_item.get("ten_thuoc")
        if target_name and target_name not in drug_names:
            drug_names.append(target_name)

    return {
        "status": "success",
        "total_medications": len(normalized_meds),
        "drug_names": drug_names,
        "prescription_info": extracted_data.get("prescription_info", {}),
        "medications": normalized_meds,
        "raw_ocr_text": raw_ocr_text,
        "engine_used": "gemini"
    }

def process_prescription_document(
    file_bytes: bytes,
    filename: str,
    **kwargs
) -> Dict[str, Any]:
    """
    Hàm tổng xử lý đơn thuốc từ tệp (Ảnh hoặc PDF) thuần Vision qua Gemini.
    - Gửi trực tiếp tệp PDF gốc (application/pdf) hoặc file ảnh cho Gemini Vision.
    """
    return process_prescription_images([(filename, file_bytes)])
