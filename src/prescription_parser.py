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
from src.config import GEMINI_API_KEY, GEMINI_TEMPERATURE, GEMINI_MODEL, GEMINI_VISION_MODEL
from src.gemini_vision import _get_image_mime_type
from src.ocr_engine import get_rapid_ocr_engine
import numpy as np

PRESCRIPTION_SYSTEM_PROMPT = """Bạn là một chuyên gia y tế và dược sĩ có kinh nghiệm phân tích đơn thuốc, toa thuốc, phiếu khám bệnh (bao gồm cả bản in máy tính và chữ viết tay của bác sĩ).
Nhiệm vụ của bạn là đọc toàn bộ hình ảnh đơn thuốc này và phân tích trực tiếp thuần túy từ thị giác (Vision OCR) để bóc tách cấu trúc dữ liệu chính xác thành định dạng JSON chuẩn theo các trường DTO (camelCase).

CÁC NGUYÊN TẮC BẮT BUỘC (NGHIÊM NGẶT - TUÂN THỦ 100%):
1. NGUYÊN TẮC BẢO TOÀN DỮ LIỆU - TUYỆT ĐỐI KHÔNG BỊA (ZERO HALLUCINATION):
   - CHỈ trích xuất đúng những thuốc THỰC TẾ XUẤT HIỆN trong văn bản đơn thuốc. Tuyệt đối KHÔNG tự sáng tác, suy đoán hoặc thêm thuốc ngoài đơn.
   - Nếu đơn chỉ ghi tên hoạt chất (ví dụ đơn BHYT ghi: "Paracetamol 500mg" hoặc "Amoxicillin 500mg"), TUYỆT ĐỐI KHÔNG tự gán tên biệt dược thương mại (như Panadol, Hapacol). Trong trường hợp này: drugName = "Paracetamol", activeIngredient = "Paracetamol".

2. TRÍCH XUẤT HOẠT CHẤT ĐẦY ĐỦ VÀ CHÍNH XÁC THEO ĐƠN:
   - Nếu đơn thuốc có ghi hoạt chất: Phải lấy ĐỦ toàn bộ hoạt chất có trên đơn.
   - Thuốc phối hợp nhiều hoạt chất: Liệt kê đầy đủ tất cả hoạt chất và nối bằng dấu "+" (VD: "Amoxicillin + Acid clavulanic", "Paracetamol + Ibuprofen"). Không được bỏ sót hoạt chất nào.
   - Thuốc thảo dược / Đông y / Thực phẩm chức năng / Men vi sinh: Ghi tên dược liệu chính (VD: "Cao khô lá Thường xuân") hoặc để chuỗi rỗng "", tuyệt đối không tự bịa công thức hóa học lạ.

3. QUY TẮC PHÂN TÁCH drugName VÀ activeIngredient:
   - TUYỆT ĐỐI KHÔNG để cả cụm đóng mở ngoặc chứa 2 tên vào drugName (ví dụ: KHÔNG ĐƯỢC để "Sulpiride (Sulpiride stella)" hay "Colecalciferol (Brivita D3)").
   - Dạng "Hoạt chất (Tên biệt dược/thương mại)": drugName là tên biệt dược/thương phẩm của nhà sản xuất (VD: "Sulpiride stella", "Brivita D3"), activeIngredient là tên hoạt chất gốc (VD: "Sulpiride", "Colecalciferol").
   - Dạng "Tên biệt dược (Hoạt chất)": drugName là tên biệt dược (VD: "Augmentin"), activeIngredient là hoạt chất (VD: "Amoxicillin + Acid clavulanic").
   - Dạng chỉ có tên biệt dược: drugName là tên biệt dược (VD: "Efferalgan", "Nexium"), activeIngredient là hoạt chất theo dược thư (VD: "Paracetamol", "Esomeprazole").
   - TUYỆT ĐỐI KHÔNG để hàm lượng (500mg, 50mg, 1g, 25mcg...) bên trong drugName, hàm lượng bắt buộc phải đưa vào trường "strength".

4. GIẢI MÃ TỪ VIẾT TẮT Y TẾ VÀ LỊCH DÙNG:
   - "S: 1, Tr: 1, C: 1, T: 1" hoặc "Sang 1, Toi 1" -> "Sáng 1 viên, Tối 1 viên".
   - "U. tr. ăn" / "Trước ăn" -> "Uống trước ăn".
   - "U. s. ăn" / "Sau ăn" -> "Uống sau ăn".
   - "K. sốt" -> "Uống khi sốt".
   - "Songay 30" / "x 30 ngày" -> Bổ sung vào timing (VD: "dùng trong 30 ngày").

Yêu cầu các trường cho từng loại thuốc:
- "order": Số thứ tự nguyên 1, 2, 3...
- "drugName": Tên biệt dược / tên thương phẩm thuốc.
- "activeIngredient": Tên hoạt chất chính / tên gốc hóa học.
- "strength": Hàm lượng (VD: 500mg, 1g, 40mg, 25mcg...).
- "unit": Đơn vị tính (VD: viên, gói, chai, lọ, ống, tuýp, vỉ, hộp...).
- "quantity": Số lượng thuốc kê dạng số nguyên (VD: 10, 14, 60...). Nếu không có thì để null.
- "route": Đường dùng (VD: Uống, Tiêm bắp, Tiêm tĩnh mạch, Bôi ngoài da, Nhỏ mắt, Nhỏ tai...). Mặc định là "Uống" nếu là dạng viên.
- "instructions": Hướng dẫn chi tiết cách dùng (VD: Uống sau ăn no, uống trước ăn 30 phút, hòa tan trong nước...).
- "timing": Thời điểm, liều lượng dùng trong ngày (VD: Sáng 1 viên, Tối 1 viên, dùng trong 30 ngày...).

Ngoài ra, trích xuất:
- "prescription_info":
  + "patient_name": Tên bệnh nhân
  + "age": Tuổi
  + "gender": Giới tính
  + "diagnosis": Chẩn đoán bệnh
  + "doctor_name": Tên bác sĩ
  + "facility_name": Tên cơ sở y tế / bệnh viện
  + "date": Ngày kê đơn
- "raw_text": Toàn bộ văn bản đọc được từ ảnh đơn thuốc.

CHỈ TRẢ VỀ DUY NHẤT ĐỊNH DẠNG JSON HỢP LỆ THEO CẤU TRÚC:
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

PRESCRIPTION_TEXT_PROMPT = """Bạn là một chuyên gia y tế và dược sĩ có kinh nghiệm phân tích đơn thuốc, toa thuốc, phiếu khám bệnh.
Dưới đây là TOÀN BỘ VĂN BẢN THÔ thu được từ hệ thống quét OCR RapidOCR trên đơn thuốc (văn bản có thể chứa một số lỗi ký tự/chính tả do quá trình nhận dạng hình ảnh).
Nhiệm vụ của bạn là đọc và phân tích ngữ nghĩa y khoa, tự động hiệu đính lỗi ký tự/chính tả do quá trình OCR và trích xuất cấu trúc dữ liệu thành JSON chuẩn theo đúng định dạng DTO (camelCase).

CÁC NGUYÊN TẮC BẮT BUỘC (NGHIÊM NGẶT - TUÂN THỦ 100%):
1. NGUYÊN TẮC BẢO TOÀN DỮ LIỆU - TUYỆT ĐỐI KHÔNG BỊA (ZERO HALLUCINATION):
   - CHỈ trích xuất đúng những thuốc THỰC TẾ XUẤT HIỆN trong văn bản OCR. Tuyệt đối KHÔNG tự sáng tác, suy đoán hoặc thêm thuốc ngoài đơn.
   - Nếu đơn chỉ ghi tên hoạt chất (ví dụ đơn BHYT ghi: "Paracetamol 500mg" hoặc "Amoxicillin 500mg"), TUYỆT ĐỐI KHÔNG tự gán tên biệt dược thương mại (như Panadol, Hapacol). Trong trường hợp này: drugName = "Paracetamol", activeIngredient = "Paracetamol".

2. TRÍCH XUẤT HOẠT CHẤT ĐẦY ĐỦ VÀ CHÍNH XÁC THEO PHIẾU OCR:
   - Nếu phiếu OCR có ghi hoạt chất: Phải lấy ĐỦ toàn bộ hoạt chất có trên phiếu.
   - Thuốc phối hợp nhiều hoạt chất: Liệt kê đầy đủ tất cả hoạt chất và nối bằng dấu "+" (VD: "Amoxicillin + Acid clavulanic", "Paracetamol + Ibuprofen"). Không được bỏ sót hoạt chất nào.
   - Thuốc thảo dược / Đông y / Thực phẩm chức năng / Men vi sinh: Ghi tên dược liệu chính (VD: "Cao khô lá Thường xuân") hoặc để chuỗi rỗng "", tuyệt đối không tự bịa công thức hóa học lạ.

3. QUY TẮC PHÂN TÁCH drugName VÀ activeIngredient:
   - TUYỆT ĐỐI KHÔNG để cả cụm đóng mở ngoặc chứa 2 tên vào drugName (ví dụ: KHÔNG ĐƯỢC để "Sulpiride (Sulpiride stella)" hay "Colecalciferol (Brivita D3)").
   - Dạng "Hoạt chất (Tên biệt dược/thương mại)": drugName là tên biệt dược/thương phẩm của nhà sản xuất (VD: "Sulpiride stella", "Brivita D3"), activeIngredient là tên hoạt chất gốc (VD: "Sulpiride", "Colecalciferol").
   - Dạng "Tên biệt dược (Hoạt chất)": drugName là tên biệt dược (VD: "Augmentin"), activeIngredient là hoạt chất (VD: "Amoxicillin + Acid clavulanic").
   - Dạng chỉ có tên biệt dược: drugName là tên biệt dược (VD: "Efferalgan", "Nexium"), activeIngredient là hoạt chất theo dược thư (VD: "Paracetamol", "Esomeprazole").
   - TUYỆT ĐỐI KHÔNG để hàm lượng (500mg, 50mg, 1g, 25mcg...) bên trong drugName, hàm lượng bắt buộc phải đưa vào trường "strength".

4. GIẢI MÃ TỪ VIẾT TẮT Y TẾ VÀ LỊCH DÙNG:
   - "S: 1, Tr: 1, C: 1, T: 1" hoặc "Sang 1, Toi 1" -> "Sáng 1 viên, Tối 1 viên".
   - "U. tr. ăn" / "Trước ăn" -> "Uống trước ăn".
   - "U. s. ăn" / "Sau ăn" -> "Uống sau ăn".
   - "K. sốt" -> "Uống khi sốt".
   - "Songay 30" / "x 30 ngày" -> Bổ sung vào timing (VD: "dùng trong 30 ngày").

Yêu cầu các trường cho từng loại thuốc:
- "order": Số thứ tự nguyên 1, 2, 3...
- "drugName": Tên biệt dược / tên thương phẩm thuốc.
- "activeIngredient": Tên hoạt chất chính / tên gốc hóa học.
- "strength": Hàm lượng (VD: 500mg, 1g, 40mg, 25mcg...).
- "unit": Đơn vị tính (VD: viên, gói, chai, lọ, ống, tuýp, vỉ, hộp...).
- "quantity": Số lượng thuốc kê dạng số nguyên (VD: 10, 14, 60...). Nếu không có thì để null.
- "route": Đường dùng (VD: Uống, Tiêm bắp, Tiêm tĩnh mạch, Bôi ngoài da, Nhỏ mắt, Nhỏ tai...). Mặc định là "Uống" nếu là dạng viên.
- "instructions": Hướng dẫn chi tiết cách dùng (VD: Uống sau ăn no, uống trước ăn 30 phút, hòa tan trong nước...).
- "timing": Thời điểm, liều lượng dùng trong ngày (VD: Sáng 1 viên, Tối 1 viên, dùng trong 30 ngày...).

Ngoài ra, trích xuất:
- "prescription_info":
  + "patient_name": Tên bệnh nhân
  + "age": Tuổi
  + "gender": Giới tính
  + "diagnosis": Chẩn đoán bệnh
  + "doctor_name": Tên bác sĩ
  + "facility_name": Tên cơ sở y tế / bệnh viện
  + "date": Ngày kê đơn

CHỈ TRẢ VỀ DUY NHẤT ĐỊNH DẠNG JSON HỢP LỆ THEO CẤU TRÚC:
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
  ]
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

    # Tự động chuẩn hóa nếu drug_name bị dính dạng "Tên (Ngoặc)"
    m_paren = re.match(r'^([^\(\)]+)\s*\(([^\(\)]+)\)$', drug_name)
    if m_paren:
        p1 = m_paren.group(1).strip()
        p2 = m_paren.group(2).strip()
        if active_ingredient:
            # Nếu active_ingredient trùng p1 -> p2 là tên thuốc thương mại / biệt dược
            if active_ingredient.lower() == p1.lower() or p1.lower() in active_ingredient.lower():
                drug_name = p2
                active_ingredient = p1
            # Nếu active_ingredient trùng p2 -> p1 là tên thuốc
            elif active_ingredient.lower() == p2.lower() or p2.lower() in active_ingredient.lower():
                drug_name = p1
                active_ingredient = p2
            else:
                # Mặc định theo quy chuẩn BYT: Hoạt chất (Biệt dược)
                drug_name = p2
        else:
            drug_name = p2
            active_ingredient = p1

    # Tương tự nếu active_ingredient bị dính dạng "Hoạt chất (Ghi chú)"
    m_act_paren = re.match(r'^([^\(\)]+)\s*\(([^\(\)]+)\)$', active_ingredient)
    if m_act_paren:
        act1 = m_act_paren.group(1).strip()
        act2 = m_act_paren.group(2).strip()
        if drug_name and drug_name.lower() == act2.lower():
            active_ingredient = act1
        elif drug_name and drug_name.lower() == act1.lower():
            active_ingredient = act2

    # Làm sạch hàm lượng nếu còn dính trong drugName
    if strength and strength.lower() in drug_name.lower():
        drug_name = re.sub(re.escape(strength), '', drug_name, flags=re.I).strip()
    drug_name = re.sub(r'[\s\-–]+\d+(?:[\.,]\d+)?\s*(?:mg|g|ml|mcg|µg|%|iu|ui)\b.*$', '', drug_name, flags=re.I).strip()
    drug_name = re.sub(r'^[\d\.\-\s]+', '', drug_name).strip(" -:,")

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

def extract_raw_text_rapidocr(image_items: List[Tuple[str, bytes]]) -> Tuple[str, List[Dict[str, Any]]]:
    """
    Sử dụng RapidOCR để khoanh vùng và đọc toàn bộ văn bản thô từ danh sách ảnh hoặc tệp PDF.
    Trả về (combined_text, page_details)
    """
    engine = get_rapid_ocr_engine()
    all_lines = []
    page_details = []
    page_idx = 1

    for fname, bts in image_items:
        fn_lower = fname.lower()
        if fn_lower.endswith(".pdf") or bts.startswith(b"%PDF"):
            # Xử lý PDF nhiều trang
            try:
                doc = fitz.open(stream=bts, filetype="pdf")
                for p_num in range(len(doc)):
                    page = doc[p_num]
                    pix = page.get_pixmap(dpi=150)
                    img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
                    img_np = np.array(img)
                    res, _ = engine(img_np)
                    page_text = "\n".join([line[1] for line in res]) if res else ""
                    all_lines.append(page_text)
                    page_details.append({
                        "page": page_idx,
                        "filename": fname,
                        "char_count": len(page_text),
                        "text": page_text
                    })
                    page_idx += 1
                doc.close()
            except Exception as e:
                logger.error(f"Lỗi khi đọc file PDF '{fname}' bằng RapidOCR: {e}")
        else:
            # Xử lý file ảnh thông thường
            try:
                img = Image.open(io.BytesIO(bts)).convert("RGB")
                img_np = np.array(img)
                res, _ = engine(img_np)
                img_text = "\n".join([line[1] for line in res]) if res else ""
                all_lines.append(img_text)
                page_details.append({
                    "page": page_idx,
                    "filename": fname,
                    "char_count": len(img_text),
                    "text": img_text
                })
                page_idx += 1
            except Exception as e:
                logger.error(f"Lỗi khi đọc file ảnh '{fname}' bằng RapidOCR: {e}")

    combined_text = "\n".join(all_lines).strip()
    return combined_text, page_details

def parse_prescription_text_gemini(
    raw_text: str,
    api_key: Optional[str] = None
) -> Dict[str, Any]:
    """
    Sử dụng Gemini Text API để phân tích ngữ nghĩa văn bản thô từ RapidOCR và trích xuất JSON.
    Tự động thử lại với gemini-3.5-flash và fallback sang gemini-3.5-flash-lite nếu gặp lỗi quá tải.
    """
    key = api_key or GEMINI_API_KEY
    if not key or key == "YOUR_API_KEY":
        raise ValueError("Chưa cấu hình GEMINI_API_KEY hợp lệ trong file .env")

    prompt = f"{PRESCRIPTION_TEXT_PROMPT}\n\nVĂN BẢN ĐƠN THUỐC OCR THÔ:\n\"\"\"\n{raw_text}\n\"\"\""

    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0.1,
            "maxOutputTokens": 4096,
            "responseMimeType": "application/json"
        }
    }
    headers = {"Content-Type": "application/json"}

    candidate_models = ["gemini-3.5-flash-lite", GEMINI_MODEL, "gemini-3.5-flash"]
    seen = set()
    unique_models = []
    for m in candidate_models:
        if m and m not in seen:
            seen.add(m)
            unique_models.append(m)

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
                    logger.warning(f"Gemini Text API {model_name} (lần {attempt + 1}/2) trả về HTTP {resp.status_code}. Đang thử lại...")
                    time.sleep(1.5)
                    continue
                else:
                    last_error = f"Model {model_name} HTTP {resp.status_code}: {resp.text}"
                    logger.warning(f"Gemini Text API {model_name} lỗi: {last_error}")
                    break
            except Exception as e:
                last_error = f"Model {model_name} error: {str(e)}"
                logger.warning(f"Gemini Text API {model_name} exception: {last_error}")
                time.sleep(1.0)

    raise RuntimeError(f"Không thể phân tích ngữ nghĩa đơn thuốc qua Gemini Text: {last_error}")

def process_prescription_images(
    image_items: List[Tuple[str, bytes]],
    **kwargs
) -> Dict[str, Any]:
    """
    Hàm phân tích đơn thuốc theo kiến trúc Pipeline 2 giai đoạn:
    Giai đoạn 1: RapidOCR khoanh vùng & đọc text thô cục bộ trên server.
    Giai đoạn 2: Gemini AI (Text LLM) phân tích ngữ nghĩa, sửa lỗi chính tả và trích xuất cấu trúc JSON DTO.
    (Tự động fallback sang Gemini Vision nếu text thô quá ngắn hoặc nghi là chữ viết tay khó).
    """
    t_total_start = time.perf_counter()

    # Giai đoạn 1: RapidOCR khoanh vùng và đọc text thô
    t_ocr_start = time.perf_counter()
    raw_ocr_text, page_details = extract_raw_text_rapidocr(image_items)
    ocr_time_ms = round((time.perf_counter() - t_ocr_start) * 1000, 2)
    logger.info(f"RapidOCR hoàn thành trong {ocr_time_ms} ms, đọc được {len(raw_ocr_text)} ký tự.")

    extracted_data = None
    engine_used = "rapidocr + gemini_text"
    gemini_time_ms = 0.0

    # Giai đoạn 2: Gemini AI xử lý ngữ nghĩa
    t_gemini_start = time.perf_counter()
    
    # Nếu RapidOCR đọc được đủ lượng text (>= 20 ký tự)
    if len(raw_ocr_text.strip()) >= 20:
        try:
            extracted_data = parse_prescription_text_gemini(raw_ocr_text)
            gemini_time_ms = round((time.perf_counter() - t_gemini_start) * 1000, 2)
        except Exception as e:
            logger.warning(f"Lỗi phân tích Gemini Text: {e}. Đang fallback sang Gemini Vision...")
            extracted_data = None

    # Fallback sang Gemini Vision nếu RapidOCR đọc quá ít ký tự hoặc Gemini Text thất bại
    if not extracted_data:
        try:
            logger.info("Chạy fallback sang Gemini Vision trực tiếp từ ảnh gốc...")
            t_fb_start = time.perf_counter()
            extracted_data = extract_prescription_gemini(image_items)
            gemini_time_ms = round((time.perf_counter() - t_fb_start) * 1000, 2)
            engine_used = "gemini_vision_fallback"
            if not raw_ocr_text:
                raw_ocr_text = extracted_data.get("raw_text", "")
        except Exception as e:
            logger.warning(f"Fallback Gemini Vision thất bại ({e}). Chuyển sang Rule-based Regex offline...")
            extracted_data = parse_prescription_text_rule_based(raw_ocr_text)
            engine_used = "rapidocr + regex_offline"
            gemini_time_ms = round((time.perf_counter() - t_gemini_start) * 1000, 2)

    raw_meds = extracted_data.get("medications", [])
    normalized_meds = []
    drug_names = []

    for i, item in enumerate(raw_meds, 1):
        norm_item = normalize_medication_item(item, idx=i)
        normalized_meds.append(norm_item)
        target_name = norm_item.get("drugName") or norm_item.get("ten_thuoc")
        if target_name and target_name not in drug_names:
            drug_names.append(target_name)

    total_time_ms = round((time.perf_counter() - t_total_start) * 1000, 2)

    return {
        "status": "success",
        "total_medications": len(normalized_meds),
        "drug_names": drug_names,
        "prescription_info": extracted_data.get("prescription_info", {}),
        "medications": normalized_meds,
        "raw_ocr_text": raw_ocr_text,
        "engine_used": engine_used,
        "timing": {
            "ocr_time_ms": ocr_time_ms,
            "gemini_time_ms": gemini_time_ms,
            "total_time_ms": total_time_ms
        }
    }

def process_prescription_document(
    file_bytes: bytes,
    filename: str,
    **kwargs
) -> Dict[str, Any]:
    """
    Hàm tổng xử lý đơn thuốc từ tệp (Ảnh hoặc PDF).
    Theo luồng: RapidOCR -> Raw text -> Gemini AI semantic processing -> JSON DTO.
    """
    return process_prescription_images([(filename, file_bytes)])
