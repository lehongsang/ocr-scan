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
Nhiệm vụ của bạn là đọc toàn bộ hình ảnh đơn thuốc này và phân tích trực tiếp thuần túy từ thị giác (Vision OCR) để bóc tách cấu trúc dữ liệu chính xác thành định dạng JSON chuẩn.

Yêu cầu nghiêm ngặt cho từng loại thuốc kê trong đơn:
Trích xuất đúng và đầy đủ 8 trường dữ liệu sau cho mỗi thuốc (nếu có thông tin thì điền, nếu không có thì để chuỗi rỗng ""):
1. "ten_thuoc": Tên thuốc / biệt dược ghi trên đơn (VD: efferalgan, Augmentin, Nexium, Panadol Extra...).
2. "ten_hoat_chat": Tên hoạt chất chính của thuốc. Nếu trên đơn có ghi rõ hoạt chất thì trích xuất; nếu đơn chỉ ghi tên biệt dược thì dựa vào kiến thức dược lý chuyên môn để xác định chính xác tên hoạt chất (VD: efferalgan -> paracetamol, Augmentin -> amoxicillin + acid clavulanic, Nexium -> esomeprazole; nếu không xác định được thì để "").
3. "ham_luong": Hàm lượng hoặc nồng độ của thuốc ghi trên đơn (VD: 500mg, 1g, 40mg, 250mg/5ml, 0.5%...).
4. "don_vi_tinh": Đơn vị tính của thuốc (VD: viên, gói, chai, lọ, ống, tuýp, vỉ, hộp, tép...).
5. "so_luong": Số lượng thuốc được kê, chỉ ghi số hoặc định lượng (VD: 10, 14, 1, 20...).
6. "duong_dung": Đường dùng thuốc (VD: Uống, Tiêm bắp, Tiêm tĩnh mạch, Bôi ngoài da, Nhỏ mắt, Nhỏ tai, Đặt hậu môn, Đặt dưới lưỡi, Hít/Khí dung...).
7. "cach_dung": Hướng dẫn chi tiết về cách dùng, thời điểm dùng so với bữa ăn hoặc cách thao tác (VD: uống sau ăn no, uống trước ăn 30 phút, hòa tan trong 100ml nước, thoa một lớp mỏng...).
8. "thoi_gian_dung": Thời điểm hoặc lịch trình dùng thuốc trong ngày, khoảng cách giữa các lần, hoặc điều kiện triệu chứng khi dùng (VD: uống khi sốt hơn 38*C, sáng 1 viên - tối 1 viên, ngày 2 lần mỗi lần cách 4-6 tiếng, dùng trong 5 ngày...).

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
      "stt": 1,
      "ten_thuoc": "efferalgan",
      "ten_hoat_chat": "paracetamon",
      "ham_luong": "500mg",
      "don_vi_tinh": "viên",
      "so_luong": "10",
      "duong_dung": "Uống",
      "cach_dung": "uống sau ăn no",
      "thoi_gian_dung": "uống khi sốt hơn 38*C"
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

    candidate_models = [GEMINI_VISION_MODEL, "gemini-3.8-flash", "gemini-3.5-flash", "gemini-3.5-flash-lite"]
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
                resp = requests.post(url, headers=headers, json=payload, timeout=40)
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
                    time.sleep(1.5)
                    continue
                else:
                    last_error = f"Model {model_name} HTTP {resp.status_code}: {resp.text}"
                    break
            except Exception as e:
                last_error = f"Model {model_name} error: {str(e)}"
                time.sleep(1)

    raise RuntimeError(f"Không thể phân tích đơn thuốc qua Gemini Vision: {last_error}")

def normalize_medication_item(item: Dict[str, Any], idx: int = 1) -> Dict[str, Any]:
    """
    Chuẩn hóa dữ liệu từng dòng thuốc theo đúng 8 trường chuẩn:
    Tên thuốc | Tên hoạt chất | hàm lượng | đơn vị tính | số lượng | đường dùng | cách dùng | thời gian dùng
    """
    stt = str(item.get("stt") or idx).strip()
    ten_thuoc = str(item.get("ten_thuoc") or item.get("Tên thuốc") or item.get("raw_name") or item.get("name") or "").strip()
    ten_hoat_chat = str(item.get("ten_hoat_chat") or item.get("Tên hoạt chất") or item.get("active_ingredient") or item.get("hoat_chat") or "").strip()
    ham_luong = str(item.get("ham_luong") or item.get("hàm lượng") or item.get("strength") or "").strip()
    don_vi_tinh = str(item.get("don_vi_tinh") or item.get("đơn vị tính") or item.get("unit") or item.get("dvt") or "").strip()
    so_luong = str(item.get("so_luong") or item.get("số lượng") or item.get("quantity") or item.get("sl") or "").strip()
    duong_dung = str(item.get("duong_dung") or item.get("đường dùng") or item.get("route") or "").strip()
    cach_dung = str(item.get("cach_dung") or item.get("cách dùng") or item.get("usage") or item.get("instruction") or "").strip()
    thoi_gian_dung = str(item.get("thoi_gian_dung") or item.get("thời gian dùng") or item.get("timing") or item.get("schedule") or "").strip()

    return {
        "stt": stt,
        "ten_thuoc": ten_thuoc,
        "ten_hoat_chat": ten_hoat_chat,
        "ham_luong": ham_luong,
        "don_vi_tinh": don_vi_tinh,
        "so_luong": so_luong,
        "duong_dung": duong_dung,
        "cach_dung": cach_dung,
        "thoi_gian_dung": thoi_gian_dung
    }

def parse_prescription_text_rule_based(raw_text: str) -> Dict[str, Any]:
    """
    Bóc tách danh sách thuốc từ text thô bằng Rule-based & Regex (cho OCR offline / RapidOCR fallback).
    Không sử dụng database thuốc, bóc tách trực tiếp theo cấu trúc dòng thành 8 trường dữ liệu.
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

            medications.append({
                "stt": stt,
                "ten_thuoc": clean_name.strip(" -:,"),
                "ten_hoat_chat": "",
                "ham_luong": strength,
                "don_vi_tinh": unit,
                "so_luong": quantity,
                "duong_dung": route,
                "cach_dung": "Theo chỉ dẫn bác sĩ",
                "thoi_gian_dung": ""
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
    Tự động đọc và bóc tách trực tiếp 8 trường dữ liệu:
    Tên thuốc | Tên hoạt chất | hàm lượng | đơn vị tính | số lượng | đường dùng | cách dùng | thời gian dùng
    """
    extracted_data = extract_prescription_gemini(image_items)
    raw_ocr_text = extracted_data.get("raw_text", "")

    raw_meds = extracted_data.get("medications", [])
    normalized_meds = []
    drug_names = []

    for i, item in enumerate(raw_meds, 1):
        norm_item = normalize_medication_item(item, idx=i)
        normalized_meds.append(norm_item)
        if norm_item["ten_thuoc"] and norm_item["ten_thuoc"] not in drug_names:
            drug_names.append(norm_item["ten_thuoc"])

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
