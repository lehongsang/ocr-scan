import re
import os
import json
import requests
from typing import Dict, Any, Optional, List, Tuple
from src.config import GEMINI_API_KEY, GEMINI_API_URL, GEMINI_TEMPERATURE, GEMINI_MAX_OUTPUT_TOKENS
from src.calculators import calculate_egfr, calculate_acr

def convert_to_gemini_schema(schema_dict: dict) -> dict:
    """
    Chuyển đổi file schema.json tùy chỉnh sang OpenAPI Schema chuẩn yêu cầu bởi Gemini API.
    """
    type_mapping = {
        "string": "STRING",
        "integer": "INTEGER",
        "boolean": "BOOLEAN",
        "float": "NUMBER",
        "number": "NUMBER"
    }
    
    gemini_properties = {}
    
    for section_name, section_fields in schema_dict.items():
        section_props = {}
        for field_name, field_meta in section_fields.items():
            field_type = field_meta.get("type", "string").lower()
            gemini_type = type_mapping.get(field_type, "STRING")
            
            field_schema = {
                "type": gemini_type,
            }
            
            if "description" in field_meta:
                field_schema["description"] = field_meta["description"]
                
            if "enum" in field_meta:
                field_schema["enum"] = field_meta["enum"]
                
            section_props[field_name] = field_schema
            
        gemini_properties[section_name] = {
            "type": "OBJECT",
            "properties": section_props
        }
        
    return {
        "type": "OBJECT",
        "properties": gemini_properties
    }

def get_disease_only_schema(schema_dict: dict) -> dict:
    """
    Tạo schema thu gọn chỉ bao gồm các trường cờ bệnh lý (boolean) để gửi cho Gemini.
    """
    disease_sections = ["PHAN_LOAI_BENH_LY_NEN", "TON_THUONG_CO_QUAN_DICH", "C_BENH_LY_MAN_TINH_KEM_THEO"]
    mini_schema = {}
    for section_name in disease_sections:
        if section_name in schema_dict:
            mini_fields = {}
            for field_name, field_meta in schema_dict[section_name].items():
                if field_meta.get("type") == "boolean":
                    mini_fields[field_name] = field_meta
            if mini_fields:
                mini_schema[section_name] = mini_fields
    return mini_schema

def filter_confirmed_diagnoses(diagnostic_text: str):
    """
    Tách các mục bệnh lý trong chẩn đoán, loại bỏ các mục có tiền tố 'TD' (Theo dõi / Nghi ngờ).
    Không đưa các bệnh theo dõi (TD) vào tiểu sử bệnh lý.
    Trả về:
    - filtered_text: chuỗi chẩn đoán đã lọc để gán vào tien_su_benh_ly
    - confirmed_items: danh sách các mục bệnh lý đã xác định (confirmed)
    """
    if not diagnostic_text:
        return "", []
    
    # Tách theo các dấu phân tách phổ biến: gạch ngang, chấm phẩy, phẩy, xuống dòng hoặc đánh số đầu mục
    # Ví dụ: "Stent động mạch vành - TD suy tim - tăng huyết áp - rối loạn chuyển hóa lipid - TD bướu giáp"
    raw_items = re.split(r'\s*(?:[-–—;,]|\b\d+[\.\)]\s*|\n)\s*', diagnostic_text)
    
    td_pattern = re.compile(
        r'^(?:T[DĐdđ][\s\.\:\/\-]|T[DĐdđ]$|T\/[DĐdđ]|T\.[DĐdđ]|theo\s*dõi|theo\s*doi|nghi\s*ngờ|nghi\s*ngo)',
        re.IGNORECASE
    )
    
    confirmed_items = []
    for item in raw_items:
        item_clean = item.strip().strip(".-:,")
        if not item_clean:
            continue
        if td_pattern.match(item_clean):
            # Bệnh có tiền tố TD (theo dõi / nghi ngờ) -> bỏ qua không cho vào tiểu sử/tiền sử bệnh lý
            continue
        confirmed_items.append(item_clean)
        
    filtered_text = " - ".join(confirmed_items)
    return filtered_text, confirmed_items

def extract_diagnostic_text(text: str) -> str:
    """
    Trích xuất đoạn văn bản Chẩn đoán / Tiền sử bệnh ngắn để gửi cho Gemini API.
    Đã lọc bỏ các mục chỉ là theo dõi (TD).
    """
    diag_match = re.search(
        r'(?:Chẩn đoán(?:\s*kèm\s*theo|\s*chính|\s*sơ\s*bộ|\s*phụ)?|Tiền sử(?:\s*bệnh(?:\s*lý)?)?|Bệnh lý):\s*\n?\s*([^\n]+(?:\n[^\n]+){0,5})',
        text,
        re.IGNORECASE
    )
    if diag_match:
        raw_diag = clean_value(diag_match.group(0))
        header_match = re.match(r'^([^:]+:)\s*(.*)$', raw_diag)
        if header_match:
            header = header_match.group(1)
            content = header_match.group(2)
            filtered_content, _ = filter_confirmed_diagnoses(content)
            return f"{header} {filtered_content}".strip()
        return raw_diag
    
    # Fallback: lấy các dòng chứa từ khóa y khoa
    lines = text.split('\n')
    diag_lines = [
        l.strip() for l in lines 
        if any(k in l.lower() for k in ["chẩn đoán", "tiền sử", "bệnh", "mạch", "tim", "xơ vữa", "tháo đường", "thận", "não", "vữa xơ", "huyết áp"])
    ]
    if diag_lines:
        return " ".join(diag_lines[:5])
    return text[:500].strip()

def fill_missing_fields(data: dict, schema_dict: dict) -> dict:
    """
    Điền các trường bị thiếu trong kết quả trả về bằng giá trị mặc định (null hoặc false)
    để đảm bảo file kết quả JSON luôn chứa đầy đủ 100% các trường định nghĩa trong schema.
    """
    if not isinstance(data, dict):
        data = {}
        
    filled_data = {}
    
    for section_name, section_fields in schema_dict.items():
        filled_data[section_name] = {}
        gemini_section = data.get(section_name, {})
        if not isinstance(gemini_section, dict):
            gemini_section = {}
            
        for field_name, field_meta in section_fields.items():
            field_type = field_meta.get("type", "string").lower()
            
            if field_name in gemini_section and gemini_section[field_name] is not None:
                val = gemini_section[field_name]
                filled_data[section_name][field_name] = val
            else:
                if field_type == "boolean":
                    filled_data[section_name][field_name] = False
                else:
                    filled_data[section_name][field_name] = None
                    
    return filled_data

def parse_medical_fields_gemini(text: str, schema_path: str = None) -> Dict[str, Any]:
    """
    Tối ưu tốc độ phản hồi toàn trình:
    1. Bóc tách dữ liệu hành chính & chỉ số số học bằng Regex offline.
    2. Chỉ trích xuất đoạn chẩn đoán y khoa ngắn và gửi kèm schema cờ bệnh lý thu gọn cho Gemini API.
    3. Kết hợp kết quả Regex + Gemini thành JSON hoàn chỉnh 100% cấu trúc schema.
    """
    # 1. Bóc tách bằng Regex offline trước
    regex_data = parse_medical_fields(text)
    
    if not schema_path:
        schema_path = os.path.join(os.path.dirname(__file__), "schema.json")
        
    schema_dict = {}
    if os.path.exists(schema_path):
        try:
            with open(schema_path, "r", encoding="utf-8") as f:
                schema_dict = json.load(f)
        except Exception:
            pass

    # Nếu không có API Key, trả về kết quả bóc tách Regex đã fill missing fields
    if not GEMINI_API_KEY or GEMINI_API_KEY == "YOUR_API_KEY":
        return fill_missing_fields(regex_data, schema_dict)

    try:
        # 2. Trích xuất đoạn chẩn đoán y khoa ngắn (đã lọc các mục TD)
        chandoan_text = extract_diagnostic_text(text)
        
        # 3. Tạo Schema thu gọn chỉ chứa các bệnh lý (boolean)
        disease_schema_dict = get_disease_only_schema(schema_dict)
        gemini_schema = convert_to_gemini_schema(disease_schema_dict)
        
        # 4. Gửi request Gemini API với prompt tối ưu & tham số sinh siêu tốc
        url = f"{GEMINI_API_URL}?key={GEMINI_API_KEY}"
        prompt = (
            "Bạn là chuyên gia y tế. Hãy phân tích đoạn chẩn đoán sau và xác định các bệnh lý có mặt "
            "(gán true cho các bệnh lý thực sự được chẩn đoán xác định).\n"
            "LƯU Ý QUAN TRỌNG: Tuyệt đối KHÔNG gán true cho các bệnh có tiền tố 'TD', 'T/D', 'Theo dõi', 'Nghi ngờ' "
            "(ví dụ: 'TD suy tim', 'TD bướu giáp' chỉ là theo dõi/nghi ngờ nên phải đặt false).\n\n"
            "Một số phiếu khám dùng chỉ số khác nhau nhưng cùng 1 ý nghĩa. Ví dụ: egfr và eGFR đều là 1 chỉ số giống nhau\n\n"
            f"VĂN BẢN CHẨN ĐOÁN:\n{chandoan_text}"
        )
        
        payload = {
            "contents": [{
                "parts": [{
                    "text": prompt
                }]
            }],
            "generationConfig": {
                "responseMimeType": "application/json",
                "responseSchema": gemini_schema,
                "temperature": GEMINI_TEMPERATURE,
                "maxOutputTokens": GEMINI_MAX_OUTPUT_TOKENS
            }
        }
        
        headers = {"Content-Type": "application/json"}
        
        response = requests.post(url, json=payload, headers=headers, timeout=15)
        
        if response.status_code == 200:
            resp_json = response.json()
            candidates = resp_json.get("candidates", [])
            if candidates:
                text_content = candidates[0].get("content", {}).get("parts", [{}])[0].get("text", "")
                gemini_data = json.loads(text_content)
                
                # Merge dữ liệu bệnh lý từ Gemini vào regex_data
                for sec_name, fields in gemini_data.items():
                    if sec_name in regex_data and isinstance(fields, dict):
                        for f_name, f_val in fields.items():
                            if f_val is True or regex_data[sec_name].get(f_name) is True:
                                regex_data[sec_name][f_name] = True
                            elif regex_data[sec_name].get(f_name) is None:
                                regex_data[sec_name][f_name] = f_val
                                
    except Exception as e:
        # Nếu có lỗi kết nối/API, giữ lại kết quả từ Regex
        pass

    return fill_missing_fields(regex_data, schema_dict)

def calculate_acr(alb_val: float, alb_unit: str = "mg/L", cre_val: float = 0.0, cre_unit: str = "mmol/L") -> Optional[float]:
    """
    Tính toán tỷ lệ Albumin/Creatinin niệu (ACR) theo công thức chuẩn:
    - Albumin (mg/L), Creatinin (g/L): ACR (mg/g) = Albumin ÷ Creatinin
    - Albumin (mg/L), Creatinin (mmol/L): ACR (mg/g) = Albumin × 8.84 ÷ Creatinin
    - Albumin (mg/L), Creatinin (mg/dL): ACR (mg/g) = Albumin × 100 ÷ Creatinin
    - Albumin (mg/dL), Creatinin (mg/dL): ACR (mg/g) = Albumin × 1000 ÷ Creatinin
    - Albumin (mg/L), Creatinin (µmol/L): ACR (mg/g) = Albumin × 8840 ÷ Creatinin
    """
    if not alb_val or not cre_val or cre_val <= 0:
        return None

    alb_u = (alb_unit or "mg/l").lower().strip()
    cre_u = (cre_unit or "mmol/l").lower().strip()

    if "mmol" in cre_u:
        acr = (alb_val * 8.84) / cre_val
    elif "µmol" in cre_u or "umol" in cre_u:
        cre_mmol = cre_val / 1000.0
        acr = (alb_val * 8.84) / cre_mmol if cre_mmol > 0 else 0
    elif "g/l" in cre_u:
        acr = alb_val / cre_val
    elif "mg/dl" in cre_u:
        if "mg/dl" in alb_u:
            acr = (alb_val * 1000.0) / cre_val
        else:
            acr = (alb_val * 100.0) / cre_val
    else:
        # Mặc định quy đổi theo mmol/L nếu không nhận dạng được
        acr = (alb_val * 8.84) / cre_val

    return round(acr, 2)


def calculate_egfr(scr_val: float, scr_unit: str = "µmol/L", age: int = None, gender: str = "Nam") -> Optional[float]:
    """
    Tính mức lọc cầu thận ước tính eGFR theo công thức CKD-EPI 2021:
    eGFR = 142 × min(SCr/κ, 1)^α × max(SCr/κ, 1)^−1.200 × 0.9938^Tuổi × Hệ số giới
    - SCr: Creatinin huyết thanh (mg/dL). Nếu µmol/L: SCr mg/dL = SCr µmol/L ÷ 88.4
    - Nam: κ = 0.9, α = -0.302, hệ số giới = 1.0
    - Nữ: κ = 0.7, α = -0.241, hệ số giới = 1.012
    """
    if not scr_val or scr_val <= 0 or not age or age < 18:
        return None

    scr_u = (scr_unit or "µmol/l").lower().strip()
    if "µmol" in scr_u or "umol" in scr_u:
        scr_mg_dl = scr_val / 88.4
    else:
        scr_mg_dl = scr_val

    is_female = "nữ" in (gender or "").lower() or "female" in (gender or "").lower()
    kappa = 0.7 if is_female else 0.9
    alpha = -0.241 if is_female else -0.302
    gender_factor = 1.012 if is_female else 1.0

    scr_k = scr_mg_dl / kappa
    egfr = 142 * (min(scr_k, 1.0) ** alpha) * (max(scr_k, 1.0) ** -1.200) * (0.9938 ** age) * gender_factor
    return round(egfr, 1)


def clean_value(val: str) -> str:
    """Dọn dẹp ký tự thừa."""
    if not val:
        return ""
    # Loại bỏ dấu xuống dòng và khoảng trắng thừa
    return re.sub(r'\s+', ' ', val).strip()

def normalize_medical_text(text: str) -> str:
    r"""
    Chuẩn hóa văn bản y tế từ OCR hình ảnh hoặc PDF:
    - Loại bỏ định dạng in đậm Markdown (**text** hoặc __text__)
    - Chuẩn hóa ký hiệu LaTeX hay gặp trong OCR y tế ($\mu$mol/L, $m^2$, v.v.)
    """
    if not text:
        return ""
    norm = re.sub(r'\*\*(.*?)\*\*', r'\1', text)
    norm = re.sub(r'__(.*?)__', r'\1', norm)
    norm = norm.replace(r'$\mu$', 'µ').replace(r'\mu', 'µ').replace('$', '')
    return norm

def extract_lab_measurement(text: str, test_pattern: str) -> tuple[Optional[float], Optional[str]]:
    """
    Trích xuất (giá trị_số, đơn_vị) của chỉ số xét nghiệm, hỗ trợ:
    1. Bảng Markdown có dấu '|' hoặc tab '\\t'
    2. Dòng ngang cùng hàng (Inline, ví dụ: 'eGFR = 41.2 ml/phút/1.73 m²', 'Albumin niệu 10 mg/L', 'Cholesterol toàn phần* H 5.59 mmol/L')
    3. Dòng dọc theo từng khối text (PDF/ảnh quét từng dòng)
    4. Tránh bắt nhầm phiên bản máy (novus_v2, AU5800), khoảng tham chiếu, hoặc mốc thời gian (08h54, ngày tháng).
    """
    lines = text.splitlines()
    units_pattern = r'(mmol/L|mg/dL|g/L|µmol/L|umol/L|mg/L|µg/mL|U/L|U/I|/µL|ml/phút/1\.73\s*m[²2]|ml/min)'

    for i, line in enumerate(lines):
        if not re.search(test_pattern, line, re.IGNORECASE):
            continue

        # 1. Hỗ trợ định dạng bảng phân cách bằng '|' hoặc '\\t'
        sep = '|' if '|' in line else ('\t' if '\t' in line else None)
        if sep:
            parts = [p.strip() for p in line.split(sep) if p.strip()]
            for idx, p in enumerate(parts):
                if re.search(test_pattern, p, re.IGNORECASE):
                    val = None
                    unit = None
                    for cell in parts[idx+1:]:
                        clean_cell = cell.strip()
                        if not clean_cell or clean_cell.upper() in ['H', 'L', 'NEGATIVE', 'NEG', 'POSITIVE', 'POS']:
                            continue
                        clean_cell_no_hl = re.sub(r'^[HL]\s+', '', clean_cell, flags=re.IGNORECASE)
                        num_match = re.search(r'^(\d+(?:\.\d+)?)', clean_cell_no_hl)
                        if num_match and val is None:
                            val = float(num_match.group(1))
                            continue
                        if val is not None:
                            unit_match = re.search(units_pattern, clean_cell, re.IGNORECASE)
                            if unit_match:
                                unit = unit_match.group(1)
                            break
                    if val is not None:
                        return val, unit

        # 2. Hỗ trợ trường hợp giá trị nằm ngay trên cùng dòng (Inline)
        # Ví dụ: 'Mức lọc cầu thận eGFR = 41.2 ml/phút/1.73 m²', 'Cholesterol toàn phần* H 5.59 mmol/L', 'Creatinin niệu L 4.4 mmol/L'
        m_pattern = re.search(test_pattern, line, re.IGNORECASE)
        after_text = line[m_pattern.end():].strip()
        if after_text:
            clean_after = re.sub(r'^[=\s:*]+', '', after_text)
            clean_after_no_hl = re.sub(r'^[HL]\s+', '', clean_after, flags=re.IGNORECASE)
            inline_match = re.search(r'^(\d+(?:\.\d+)?)', clean_after_no_hl)
            if inline_match:
                val = float(inline_match.group(1))
                unit_match = re.search(units_pattern, after_text, re.IGNORECASE)
                unit = unit_match.group(1) if unit_match else None
                return val, unit

        # 3. Hỗ trợ định dạng phân dòng dọc (Vertical layout)
        val = None
        unit = None
        for next_line in lines[i+1:i+6]:
            clean_cell = next_line.strip()
            if not clean_cell or clean_cell.upper() in ['H', 'L', 'NEGATIVE', 'NEG', 'POSITIVE', 'POS']:
                continue
            if re.search(r'^\d{1,2}h\d{2}|\d{1,2}/\d{1,2}/\d{4}|BÁC S|KHOA|NHẬN XÉT|KẾT LUẬN|PHIẾU', clean_cell, re.IGNORECASE):
                continue
            clean_cell_no_hl = re.sub(r'^[HL]\s+', '', clean_cell, flags=re.IGNORECASE)
            num_match = re.search(r'^(\d+(?:\.\d+)?)', clean_cell_no_hl)
            if num_match and val is None:
                val = float(num_match.group(1))
                continue
            if val is not None:
                unit_match = re.search(units_pattern, clean_cell, re.IGNORECASE)
                if unit_match:
                    unit = unit_match.group(1)
                break
        if val is not None:
            return val, unit

    return None, None

def parse_medical_fields(text: str) -> Dict[str, Any]:
    """
    Phân tích văn bản thô (OCR hoặc trích xuất số) để chuyển đổi thành cấu trúc
    trường thông tin chi tiết dựa trên schema đã định nghĩa.
    """
    text = normalize_medical_text(text)
    result = {
        "PHAN_LOAI_BENH_LY_NEN": {
            "has_underlying_disease": False
        },
        "A_CHI_SO_SINH_LY_CO_BAN": {
            "tuoi": None,
            "gioi_tinh": None,
            "hut_thuoc_la": False,
            "huyet_ap_tam_thu_sbp": None,
            "cholesterol_toan_phan": None,
            "hdl_cholesterol": None,
            "non_hdl_cholesterol": None
        },
        "TON_THUONG_CO_QUAN_DICH": {
            "phi_dai_that_trai": False,
            "ton_thuong_day_mat": False,
            "albumin_microalbumin_nieu": False,
            "ton_thuong_tham_lang_tren_nao": False
        },
        "C_BENH_LY_MAN_TINH_KEM_THEO": {
            "egfr": None,
            "acr": None,
            "suy_than": False,
            "dai_thao_duong": False,
            "roi_loan_chuyen_hoa_mo_mau": False,
            "nhoi_mau_co_tim": False,
            "benh_ly_mach_vanh": False,
            "phinh_dong_mach_chu": False,
            "vua_xo_mach_mau": False,
            "dot_quy_nao": False,
            "hoi_chung_vanh_cap": False,
            "thieu_mau_cuc_bo_nao_thoang_qua_tia": False,
            "benh_mach_mau_ngoai_vi": False,
            "tang_cholesterol_mau_gia_dinh": False,
            "tang_huyet_ap": False
        },
        "THONG_TIN_CA_NHAN": {
            "ho_va_ten": None,
            "ma_benh_nhan": None,
            "ngay_sinh": None,
            "gioi_tinh": None,
            "cccd_cmnd": None,
            "trang_thai_ho_so": "Hoạt động"
        },
        "THONG_TIN_LIEN_HE_AND_DIA_CHI": {
            "so_dien_thoai": None,
            "email": None,
            "tinh_thanh_pho": None,
            "quan_huyen": None,
            "so_nha_ten_duong": None,
            "dia_chi_day_du": None
        },
        "CHI_SO_AND_TIEN_SU_SUC_KHOE": {
            "chieu_cao": None,
            "can_nang": None,
            "nhom_mau": None,
            "tien_su_benh_ly": None
        },
        "D_THONG_TIN_NHOM_CHAM_SOC": {
            "ma_nhom_cham_soc": None
        }
    }

    # --- 1. Họ và tên & Mã bệnh nhân ---
    name_match = re.search(r'(?:Họ và tên|Họ tên|Tên bệnh nhân):\s*([^\n]+)', text, re.IGNORECASE)
    if name_match:
        result["THONG_TIN_CA_NHAN"]["ho_va_ten"] = clean_value(name_match.group(1))
    else:
        # Fallback tìm kiếm dòng đầu tiên dạng chữ IN HOA tên bệnh nhân (Ví dụ: NGUYỄN THỊ HỢP - BN000801164)
        first_lines = text.split('\n')[:5]
        for line in first_lines:
            match = re.match(r'^([A-ZÀÁÂÃÈÉÊÌÍÒÓÔÕÙÚÝĂĐĨŨƠƯ\s]+)(?:\s*-\s*(BN\d+))?$', line.strip())
            if match:
                result["THONG_TIN_CA_NHAN"]["ho_va_ten"] = clean_value(match.group(1))
                if match.group(2):
                    result["THONG_TIN_CA_NHAN"]["ma_benh_nhan"] = clean_value(match.group(2))
                break

    # Trích xuất Mã bệnh nhân nếu có trường riêng (ví dụ: "Mã BN: BN000802016", "Mã bệnh nhân: 123456")
    bn_match = re.search(r'(?:Mã\s*(?:số\s*)?(?:BN|bệnh\s*nhân|người\s*bệnh)|Mã\s*BN):\s*([A-Za-z0-9]+)', text, re.IGNORECASE)
    if bn_match:
        result["THONG_TIN_CA_NHAN"]["ma_benh_nhan"] = clean_value(bn_match.group(1))
    elif not result["THONG_TIN_CA_NHAN"]["ma_benh_nhan"]:
        # Fallback tìm mã dạng BN + số (ví dụ: BN000802016) trong toàn bộ văn bản
        bn_code_match = re.search(r'\b(BN\d{6,12})\b', text)
        if bn_code_match:
            result["THONG_TIN_CA_NHAN"]["ma_benh_nhan"] = bn_code_match.group(1)

    # --- 2. Giới tính ---
    gender_match = re.search(r'(?:GT|Giới tính):\s*(Nam|Nữ|N\u1eef|Khác)', text, re.IGNORECASE)
    if gender_match:
        gender = clean_value(gender_match.group(1))
        # Chuẩn hóa giới tính
        if gender.lower() == "nữ" or gender.lower() == "n\u1eef":
            gender = "Nữ"
        elif gender.lower() == "nam":
            gender = "Nam"
        else:
            gender = "Khác"
        result["THONG_TIN_CA_NHAN"]["gioi_tinh"] = gender
        result["A_CHI_SO_SINH_LY_CO_BAN"]["gioi_tinh"] = gender

    # --- 3. Năm sinh & Ngày sinh ---
    ns_match = re.search(r'(?:NS|Năm sinh):\s*(\d{4})', text, re.IGNORECASE)
    ngaysinh_match = re.search(r'Ngày sinh:\s*([^\n]+)', text, re.IGNORECASE)
    
    yob = None
    if ns_match:
        yob = int(ns_match.group(1))
        result["THONG_TIN_CA_NHAN"]["ngay_sinh"] = f"01/01/{yob}"
    elif ngaysinh_match:
        ngay_sinh_str = clean_value(ngaysinh_match.group(1))
        result["THONG_TIN_CA_NHAN"]["ngay_sinh"] = ngay_sinh_str
        year_match = re.search(r'(\d{4})$', ngay_sinh_str)
        if year_match:
            yob = int(year_match.group(1))

    # Tính tuổi dựa trên năm hiện tại (2026)
    if yob:
        result["A_CHI_SO_SINH_LY_CO_BAN"]["tuoi"] = 2026 - yob
    else:
        tuoi_match = re.search(r'Tuổi:\s*(\d+)', text, re.IGNORECASE)
        if tuoi_match:
            result["A_CHI_SO_SINH_LY_CO_BAN"]["tuoi"] = int(tuoi_match.group(1))

    # --- 4. Địa chỉ ---
    address_match = re.search(r'Địa chỉ:\s*\n?\s*([^\n]+)', text, re.IGNORECASE)
    if address_match:
        addr = clean_value(address_match.group(1))
        result["THONG_TIN_LIEN_HE_AND_DIA_CHI"]["dia_chi_day_du"] = addr
        # Cố gắng bóc tách Tỉnh/Thành phố
        tinh_match = re.search(r'(?:Tỉnh|TP)\s+([a-zA-ZÀ-ỹ\s]+)(?:-|$)', addr, re.IGNORECASE)
        if tinh_match:
            result["THONG_TIN_LIEN_HE_AND_DIA_CHI"]["tinh_thanh_pho"] = clean_value(tinh_match.group(1))

    # --- 5. Số điện thoại & Email ---
    sdt_match = re.search(r'(?:Số điện thoại|SĐT|Điện thoại):\s*([0-9\s]+)', text, re.IGNORECASE)
    if sdt_match:
        result["THONG_TIN_LIEN_HE_AND_DIA_CHI"]["so_dien_thoai"] = clean_value(sdt_match.group(1))
        
    email_match = re.search(r'([a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+)', text)
    if email_match:
        result["THONG_TIN_LIEN_HE_AND_DIA_CHI"]["email"] = email_match.group(1)

    # --- 6. Chiều cao & Cân nặng ---
    height_match = re.search(r'(?:Chiều cao|Cao)\s*(?:\(cm\))?:\s*(\d+)', text, re.IGNORECASE)
    if height_match:
        result["CHI_SO_AND_TIEN_SU_SUC_KHOE"]["chieu_cao"] = int(height_match.group(1))
        
    weight_match = re.search(r'(?:Cân nặng|Nặng)\s*(?:\(kg\))?:\s*(\d+)', text, re.IGNORECASE)
    if weight_match:
        result["CHI_SO_AND_TIEN_SU_SUC_KHOE"]["can_nang"] = int(weight_match.group(1))

    # --- 7. Chẩn đoán (Tiền sử bệnh lý) ---
    diag_match = re.search(
        r'(?:Chẩn đoán(?:\s*kèm\s*theo|\s*chính|\s*sơ\s*bộ|\s*phụ)?|Tiền sử(?:\s*bệnh(?:\s*lý)?)?|Bệnh lý):\s*\n?\s*([^\n]+(?:\n(?!(?:Thời gian|Người|Bác sĩ|KTV|Khoa|Khám|Mã|Ngày|Ket luan|Kết luận|\d+\.))[^\n]+){0,3})',
        text,
        re.IGNORECASE
    )
    diagnostics = ""
    confirmed_items = []
    if diag_match:
        raw_val = re.sub(r'\s*\n\s*', ' ', diag_match.group(1))
        diagnostics = clean_value(raw_val)
        # Lọc bỏ các bệnh lý có tiền tố TD (theo dõi / nghi ngờ) khỏi tiền sử bệnh lý
        filtered_diagnostics, confirmed_items = filter_confirmed_diagnoses(diagnostics)
        result["CHI_SO_AND_TIEN_SU_SUC_KHOE"]["tien_su_benh_ly"] = filtered_diagnostics if filtered_diagnostics else None

    # Phân tích từ các bệnh lý đã xác định (không chứa tiền tố TD) để xác định cờ bệnh mạn tính
    confirmed_str = " ; ".join(confirmed_items).lower()
    
    # Tăng huyết áp
    if any(k in confirmed_str for k in ["tăng huyết áp", "tang huyet ap", "cao huyết áp", "cao huyet ap", "huyết áp cao", "hypertension"]) or re.search(r'\btha\b', confirmed_str):
        result["C_BENH_LY_MAN_TINH_KEM_THEO"]["tang_huyet_ap"] = True
        result["PHAN_LOAI_BENH_LY_NEN"]["has_underlying_disease"] = True

    # Vữa xơ mạch máu
    if any(k in confirmed_str for k in ["xơ vữa", "xo vua", "vữa xơ", "vua xo", "vữa sơ", "vua so", "atherosclerosis"]):
        result["C_BENH_LY_MAN_TINH_KEM_THEO"]["vua_xo_mach_mau"] = True
        result["PHAN_LOAI_BENH_LY_NEN"]["has_underlying_disease"] = True

    # Rối loạn chuyển hoá mỡ máu (Rối loạn lipid máu)
    if any(k in confirmed_str for k in ["rối loạn chuyển hóa mỡ máu", "rối loạn chuyển hoá mỡ máu", "rối loạn mỡ máu", "roi loan mo mau", "rối loạn chuyển hóa lipid", "rối loạn chuyển hoá lipid", "rối loạn lipid", "roi loan lipid", "tăng lipid máu", "tang lipid mau", "dyslipidemia", "hyperlipidemia"]):
        result["C_BENH_LY_MAN_TINH_KEM_THEO"]["roi_loan_chuyen_hoa_mo_mau"] = True
        result["PHAN_LOAI_BENH_LY_NEN"]["has_underlying_disease"] = True
        
    # Đái tháo đường
    if any(k in confirmed_str for k in ["đái tháo đường", "dai thao duong", "đái đường", "dai duong", "tiểu đường", "tieu duong", "diabetes"]) or re.search(r'\b(?:đtđ|dtd)\b', confirmed_str):
        result["C_BENH_LY_MAN_TINH_KEM_THEO"]["dai_thao_duong"] = True
        result["PHAN_LOAI_BENH_LY_NEN"]["has_underlying_disease"] = True

    # Đột quỵ
    if any(k in confirmed_str for k in ["đột quỵ", "dot quy", "tai biến mạch máu não", "tai bien mach mau nao", "stroke", "nhồi máu não", "nhoi mau nao", "xuất huyết não", "xuat huyet nao"]):
        result["C_BENH_LY_MAN_TINH_KEM_THEO"]["dot_quy_nao"] = True
        result["PHAN_LOAI_BENH_LY_NEN"]["has_underlying_disease"] = True

    # Nhồi máu cơ tim
    if any(k in confirmed_str for k in ["nhồi máu cơ tim", "nhoi mau co tim"]) or re.search(r'\b(?:mi|stemi|nstemi)\b', confirmed_str):
        result["C_BENH_LY_MAN_TINH_KEM_THEO"]["nhoi_mau_co_tim"] = True
        result["PHAN_LOAI_BENH_LY_NEN"]["has_underlying_disease"] = True

    # Bệnh mạch vành / Stent động mạch vành
    if any(k in confirmed_str for k in ["mạch vành", "mach vanh", "cơn đau thắt ngực", "ngực crnn", "stent", "đặt stent", "can thiệp vành", "cad"]):
        result["C_BENH_LY_MAN_TINH_KEM_THEO"]["benh_ly_mach_vanh"] = True
        result["PHAN_LOAI_BENH_LY_NEN"]["has_underlying_disease"] = True

    # Hội chứng vành cấp
    if any(k in confirmed_str for k in ["hội chứng vành cấp", "hoi chung vanh cap"]) or re.search(r'\bacs\b', confirmed_str):
        result["C_BENH_LY_MAN_TINH_KEM_THEO"]["hoi_chung_vanh_cap"] = True
        result["PHAN_LOAI_BENH_LY_NEN"]["has_underlying_disease"] = True

    # Thiếu máu não thoáng qua (TIA)
    if any(k in confirmed_str for k in ["thiếu máu cục bộ não thoáng qua", "thieu mau cuc bo nao thoang qua", "thiếu máu não thoáng qua", "thieu mau nao thoang qua"]) or re.search(r'\btia\b', confirmed_str):
        result["C_BENH_LY_MAN_TINH_KEM_THEO"]["thieu_mau_cuc_bo_nao_thoang_qua_tia"] = True
        result["PHAN_LOAI_BENH_LY_NEN"]["has_underlying_disease"] = True

    # Phình động mạch chủ
    if any(k in confirmed_str for k in ["phình động mạch chủ", "phinh dong mach chu", "phình đmc"]) or re.search(r'\baaa\b', confirmed_str):
        result["C_BENH_LY_MAN_TINH_KEM_THEO"]["phinh_dong_mach_chu"] = True
        result["PHAN_LOAI_BENH_LY_NEN"]["has_underlying_disease"] = True

    # Bệnh mạch máu ngoại vi
    if any(k in confirmed_str for k in ["mạch máu ngoại vi", "mach mau ngoai vi", "mạch ngoại biên", "mach ngoai bien"]) or re.search(r'\bpad\b', confirmed_str):
        result["C_BENH_LY_MAN_TINH_KEM_THEO"]["benh_mach_mau_ngoai_vi"] = True
        result["PHAN_LOAI_BENH_LY_NEN"]["has_underlying_disease"] = True
        
    # Suy thận
    if any(k in confirmed_str for k in ["suy thận", "suy than", "bệnh thận mạn", "benh than man"]) or re.search(r'\bckd\b', confirmed_str):
        result["C_BENH_LY_MAN_TINH_KEM_THEO"]["suy_than"] = True
        result["PHAN_LOAI_BENH_LY_NEN"]["has_underlying_disease"] = True

    # Tăng Cholesterol máu gia đình
    if any(k in confirmed_str for k in ["tăng cholesterol máu gia đình", "tang cholesterol mau gia dinh", "tăng cholesterol gia đình", "tang cholesterol gia dinh", "cholesterol gia đình"]) or re.search(r'\bfh\b', confirmed_str):
        result["C_BENH_LY_MAN_TINH_KEM_THEO"]["tang_cholesterol_mau_gia_dinh"] = True
        result["PHAN_LOAI_BENH_LY_NEN"]["has_underlying_disease"] = True

    # --- 8. Cholesterol toàn phần ---
    # Thường ở dạng: Cholesterol toàn phần*, Total Cholesterol, v.v.
    chol_val, _ = extract_lab_measurement(
        text, 
        r'Cholesterol\s*toàn\s*phần|Total\s*Cholesterol|Cholesterol\*(?!\s*niệu)|Cholesterol\b(?!\s*[\-\.]?\s*(?:HDL|LDL|VLDL))'
    )
    if chol_val is not None:
        result["A_CHI_SO_SINH_LY_CO_BAN"]["cholesterol_toan_phan"] = chol_val

    # --- 9. HDL-Cholesterol ---
    hdl_val, _ = extract_lab_measurement(
        text, 
        r'HDL(?:-|\s*)Cholesterol|HDL\s*[\.\-]?\s*C\b'
    )
    if hdl_val is not None:
        result["A_CHI_SO_SINH_LY_CO_BAN"]["hdl_cholesterol"] = hdl_val

    # --- 9.1. Non-HDL-Cholesterol (Tự động tính = Cholesterol toàn phần - HDL-Cholesterol) ---
    chol_val = result["A_CHI_SO_SINH_LY_CO_BAN"].get("cholesterol_toan_phan")
    hdl_val = result["A_CHI_SO_SINH_LY_CO_BAN"].get("hdl_cholesterol")
    if chol_val is not None and hdl_val is not None:
        result["A_CHI_SO_SINH_LY_CO_BAN"]["non_hdl_cholesterol"] = round(chol_val - hdl_val, 2)
    else:
        result["A_CHI_SO_SINH_LY_CO_BAN"]["non_hdl_cholesterol"] = None

    # --- 10. eGFR & ACR ---
    #10.1. Trích xuất eGFR trực tiếp nếu có
    egfr_val, _ = extract_lab_measurement(text, r'eGFR|Độ thanh thải cầu thận|Mức lọc cầu thận eGFR')
    if egfr_val is None:
        # Bắt dạng inline như: "Mức lọc cầu thận eGFR = 82.4 ml/phút/1.73 m2"
        egfr_match = re.search(r'(?:eGFR|Độ thanh thải cầu thận|Mức lọc cầu thận eGFR)[^0-9\n]*[=:]?\s*(\d+(?:\.\d+)?)', text, re.IGNORECASE)
        if egfr_match:
            egfr_val = float(egfr_match.group(1))
    if egfr_val is not None:
        result["C_BENH_LY_MAN_TINH_KEM_THEO"]["egfr"] = egfr_val

    # 10.2. Trích xuất ACR trực tiếp nếu có
    acr_val, _ = extract_lab_measurement(text, r'\bACR\b|Tỷ lệ Albumin/Creatinin')
    if acr_val is None:
        acr_match = re.search(r'(?:\bACR\b|Tỷ lệ Albumin/Creatinin)[^0-9\n]*[=:]?\s*(\d+(?:\.\d+)?)', text, re.IGNORECASE)
        if acr_match:
            acr_val = float(acr_match.group(1))

    # 10.3. Bóc tách Albumin niệu & Creatinin niệu để tự động tính ACR (chuẩn mg/g)
    cre_u_val, cre_u_unit = extract_lab_measurement(text, r'Creatinin\s*niệu|Creatinin\s*\(niệu\)|Creatinine\s*niệu')
    alb_u_val, alb_u_unit = extract_lab_measurement(text, r'Albumin\s*niệu|Microalbumin\s*niệu|Albumin\s*\(niệu\)|Microalbumin\b')

    if alb_u_val is not None and cre_u_val is not None:
        calculated_acr = calculate_acr(alb_u_val, alb_u_unit or "mg/L", cre_u_val, cre_u_unit or "mmol/L")
        if calculated_acr is not None:
            # Ưu tiên giá trị tính từ xét nghiệm thực tế
            result["C_BENH_LY_MAN_TINH_KEM_THEO"]["acr"] = calculated_acr
    elif acr_val is not None:
        result["C_BENH_LY_MAN_TINH_KEM_THEO"]["acr"] = acr_val

    # 10.4. Tự động tính eGFR nếu chưa có từ Creatinin huyết thanh (máu) + Tuổi + Giới tính
    if result["C_BENH_LY_MAN_TINH_KEM_THEO"]["egfr"] is None:
        cre_b_val, cre_b_unit = extract_lab_measurement(text, r'Creatinin\s*huyết\s*thanh|Creatinin\s*máu|SCr|Creatinin\*(?!\s*niệu)')
        if cre_b_val is not None:
            age_val = result["A_CHI_SO_SINH_LY_CO_BAN"].get("tuoi")
            gender_val = result["A_CHI_SO_SINH_LY_CO_BAN"].get("gioi_tinh") or "Nam"
            calculated_egfr = calculate_egfr(cre_b_val, cre_b_unit or "µmol/L", age_val, gender_val)
            if calculated_egfr is not None:
                result["C_BENH_LY_MAN_TINH_KEM_THEO"]["egfr"] = calculated_egfr

    # 10.5. Đánh giá tổn thương thận / vi đạm niệu dựa trên ACR hoặc Albumin niệu
    current_acr = result["C_BENH_LY_MAN_TINH_KEM_THEO"].get("acr")
    if current_acr is not None:
        if current_acr >= 30:  # ACR >= 30 mg/g là có Microalbumin niệu (tiêu chuẩn y khoa)
            result["TON_THUONG_CO_QUAN_DICH"]["albumin_microalbumin_nieu"] = True
            result["PHAN_LOAI_BENH_LY_NEN"]["has_underlying_disease"] = True
    elif alb_u_val is not None:
        if alb_u_val >= 20:  # Albumin niệu >= 20-30 mg/L
            result["TON_THUONG_CO_QUAN_DICH"]["albumin_microalbumin_nieu"] = True
            result["PHAN_LOAI_BENH_LY_NEN"]["has_underlying_disease"] = True

    # --- 11. Huyết áp tâm thu SBP ---
    sbp_match = re.search(r'(?:Huyết áp tâm thu|SBP)[^0-9\n]*[:=]?\s*(\d+)', text, re.IGNORECASE)
    if sbp_match:
        sbp_val = int(sbp_match.group(1))
        result["A_CHI_SO_SINH_LY_CO_BAN"]["huyet_ap_tam_thu_sbp"] = sbp_val

    # --- 12. Mã nhóm chăm sóc ---
    care_match = re.search(r'(?:Care Group Code|Mã nhóm chăm sóc):\s*([a-zA-Z0-9]+)', text, re.IGNORECASE)
    if care_match:
        result["D_THONG_TIN_NHOM_CHAM_SOC"]["ma_nhom_cham_soc"] = care_match.group(1)

    return result


def extract_data_provenance(pages: List[Dict[str, Any]], final_data: Dict[str, Any]) -> Tuple[List[Dict[str, Any]], Dict[int, List[Dict[str, Any]]]]:
    r"""
    Theo dõi chi tiết nguồn gốc (provenance/evidence) của từng trường dữ liệu:
    Xác định chính xác từng giá trị được lấy từ trang nào, file ảnh nào, và dòng văn bản gốc nào.
    
    Args:
        pages: Danh sách các trang dạng [{"page_index": 1, "filename": "...", "text": "..."}]
        final_data: Cấu trúc JSON thông tin y khoa đã bóc tách được.
        
    Returns:
        Tuple gồm:
        - provenance_list: Danh sách chi tiết nguồn gốc của từng trường dữ liệu (sắp xếp theo trang).
        - page_findings_map: Từ điển gom nhóm các dữ liệu trích xuất theo từng trang.
    """
    provenance_list = []
    # Chuẩn hóa trường page_index cho mỗi trang (hỗ trợ cả page và page_index)
    pages = [
        {**p, "page_index": p.get("page_index", p.get("page", idx + 1))}
        for idx, p in enumerate(pages)
    ]
    page_findings_map = {p["page_index"]: [] for p in pages}

    def add_provenance(field_key: str, section: str, display_name: str, val: Any, page_idx: int, filename: str, snippet: str, method: str = "Trích xuất trực tiếp"):
        item = {
            "truong": field_key,
            "muc": section,
            "ten_hien_thi": display_name,
            "gia_tri": val,
            "trang": page_idx,
            "file_anh": filename,
            "doan_trich": snippet,
            "phuong_thuc": method
        }
        provenance_list.append(item)
        if page_idx in page_findings_map:
            page_findings_map[page_idx].append({
                "truong": field_key,
                "ten_hien_thi": display_name,
                "gia_tri": val,
                "doan_trich": snippet,
                "phuong_thuc": method
            })

    def find_evidence_line(txt: str, pattern: str) -> str:
        for line in txt.splitlines():
            if re.search(pattern, line, re.IGNORECASE):
                return line.strip()
        return ""

    # 1. Thông tin cá nhân
    info_ca_nhan = final_data.get("THONG_TIN_CA_NHAN", {})
    name = info_ca_nhan.get("ho_va_ten")
    if name:
        for p in pages:
            ev = find_evidence_line(p["text"], re.escape(name))
            if ev:
                add_provenance("ho_va_ten", "THONG_TIN_CA_NHAN", "Họ và tên", name, p["page_index"], p["filename"], ev)
                break

    ma_bn = info_ca_nhan.get("ma_benh_nhan")
    if ma_bn:
        for p in pages:
            ev = find_evidence_line(p["text"], re.escape(ma_bn))
            if ev:
                add_provenance("ma_benh_nhan", "THONG_TIN_CA_NHAN", "Mã bệnh nhân", ma_bn, p["page_index"], p["filename"], ev)
                break

    ngay_sinh = info_ca_nhan.get("ngay_sinh")
    if ngay_sinh:
        for p in pages:
            ev = find_evidence_line(p["text"], r'NS:|Năm sinh:|Ngày sinh:')
            if ev:
                add_provenance("ngay_sinh", "THONG_TIN_CA_NHAN", "Ngày sinh / Năm sinh", ngay_sinh, p["page_index"], p["filename"], ev)
                break

    cccd = info_ca_nhan.get("cccd_cmnd")
    if cccd:
        for p in pages:
            ev = find_evidence_line(p["text"], re.escape(str(cccd)))
            if ev:
                add_provenance("cccd_cmnd", "THONG_TIN_CA_NHAN", "Số CCCD/CMND", cccd, p["page_index"], p["filename"], ev)
                break

    # 2. Thông tin liên hệ & địa chỉ
    info_dc = final_data.get("THONG_TIN_LIEN_HE_AND_DIA_CHI", {})
    addr = info_dc.get("dia_chi_day_du")
    if addr:
        for p in pages:
            ev = find_evidence_line(p["text"], r'Địa chỉ:')
            if ev:
                add_provenance("dia_chi_day_du", "THONG_TIN_LIEN_HE_AND_DIA_CHI", "Địa chỉ đầy đủ", addr, p["page_index"], p["filename"], ev)
                break

    tinh_tp = info_dc.get("tinh_thanh_pho")
    if tinh_tp:
        for p in pages:
            ev = find_evidence_line(p["text"], re.escape(tinh_tp))
            if ev:
                add_provenance("tinh_thanh_pho", "THONG_TIN_LIEN_HE_AND_DIA_CHI", "Tỉnh / Thành phố", tinh_tp, p["page_index"], p["filename"], ev, "Bóc tách từ địa chỉ")
                break

    sdt = info_dc.get("so_dien_thoai")
    if sdt:
        for p in pages:
            ev = find_evidence_line(p["text"], re.escape(str(sdt)))
            if ev:
                add_provenance("so_dien_thoai", "THONG_TIN_LIEN_HE_AND_DIA_CHI", "Số điện thoại", sdt, p["page_index"], p["filename"], ev)
                break

    # 3. Chỉ số sinh lý cơ bản
    sinh_ly = final_data.get("A_CHI_SO_SINH_LY_CO_BAN", {})
    tuoi = sinh_ly.get("tuoi")
    if tuoi:
        for p in pages:
            ev = find_evidence_line(p["text"], r'NS:|Năm sinh:|Tuổi:')
            if ev:
                add_provenance("tuoi", "A_CHI_SO_SINH_LY_CO_BAN", "Tuổi bệnh nhân", tuoi, p["page_index"], p["filename"], ev, "Tính từ năm sinh" if "NS:" in ev else "Trích xuất trực tiếp")
                break

    gt = sinh_ly.get("gioi_tinh")
    if gt:
        for p in pages:
            ev = find_evidence_line(p["text"], r'GT:|Giới tính:')
            if ev:
                add_provenance("gioi_tinh", "A_CHI_SO_SINH_LY_CO_BAN", "Giới tính", gt, p["page_index"], p["filename"], ev)
                break

    sbp = sinh_ly.get("huyet_ap_tam_thu_sbp")
    if sbp is not None:
        for p in pages:
            ev = find_evidence_line(p["text"], r'Huyết áp tâm thu|SBP')
            if ev:
                add_provenance("huyet_ap_tam_thu_sbp", "A_CHI_SO_SINH_LY_CO_BAN", "Huyết áp tâm thu SBP", sbp, p["page_index"], p["filename"], ev)
                break

    chol = sinh_ly.get("cholesterol_toan_phan")
    if chol is not None:
        for p in pages:
            c_val, _ = extract_lab_measurement(p["text"], r'Cholesterol\s*toàn\s*phần|Total\s*Cholesterol|Cholesterol\*')
            if c_val == chol:
                ev = find_evidence_line(p["text"], r'Cholesterol\s*toàn\s*phần|Total\s*Cholesterol|Cholesterol\*')
                add_provenance("cholesterol_toan_phan", "A_CHI_SO_SINH_LY_CO_BAN", "Cholesterol toàn phần", chol, p["page_index"], p["filename"], ev)
                break

    hdl = sinh_ly.get("hdl_cholesterol")
    if hdl is not None:
        for p in pages:
            h_val, _ = extract_lab_measurement(p["text"], r'HDL(?:-|\s*)Cholesterol|HDL\s*[\.\-]?\s*C\b')
            if h_val == hdl:
                ev = find_evidence_line(p["text"], r'HDL(?:-|\s*)Cholesterol|HDL\s*[\.\-]?\s*C\b')
                add_provenance("hdl_cholesterol", "A_CHI_SO_SINH_LY_CO_BAN", "HDL-Cholesterol", hdl, p["page_index"], p["filename"], ev)
                break

    non_hdl = sinh_ly.get("non_hdl_cholesterol")
    if non_hdl is not None:
        first_lab_page = provenance_list[-1]["trang"] if provenance_list else 1
        first_lab_file = provenance_list[-1]["file_anh"] if provenance_list else ""
        add_provenance(
            "non_hdl_cholesterol", "A_CHI_SO_SINH_LY_CO_BAN", "Non-HDL-Cholesterol", non_hdl, 
            first_lab_page, first_lab_file,
            f"Tự động tính toán: Cholesterol toàn phần ({chol}) - HDL ({hdl}) = {non_hdl} mmol/L",
            "Tự động tính toán y khoa"
        )

    # 4. Tiền sử bệnh lý
    ts = final_data.get("CHI_SO_AND_TIEN_SU_SUC_KHOE", {}).get("tien_su_benh_ly")
    if ts:
        for p in pages:
            ev = find_evidence_line(p["text"], r'Chẩn đoán|Tiền sử')
            if ev:
                add_provenance("tien_su_benh_ly", "CHI_SO_AND_TIEN_SU_SUC_KHOE", "Tiền sử bệnh lý / Chẩn đoán", ts, p["page_index"], p["filename"], ev)
                break

    # 5. eGFR & ACR
    man_tinh = final_data.get("C_BENH_LY_MAN_TINH_KEM_THEO", {})
    egfr = man_tinh.get("egfr") if man_tinh.get("egfr") is not None else man_tinh.get("eGFR")
    if egfr is not None:
        found_egfr = False
        for p in pages:
            if re.search(r'eGFR|Độ thanh thải', p["text"], re.IGNORECASE):
                ev = find_evidence_line(p["text"], r'eGFR|Độ thanh thải')
                add_provenance("egfr", "C_BENH_LY_MAN_TINH_KEM_THEO", "Mức lọc cầu thận eGFR", egfr, p["page_index"], p["filename"], ev, "Trích xuất trực tiếp")
                found_egfr = True
                break
        if not found_egfr:
            for p in pages:
                cr_b, _ = extract_lab_measurement(p["text"], r'Creatinin\s*huyết\s*thanh|Creatinin\s*máu|SCr|Creatinin\*(?!\s*niệu)')
                if cr_b:
                    ev = find_evidence_line(p["text"], r'Creatinin\s*huyết\s*thanh|Creatinin\s*máu|Creatinin\*')
                    add_provenance("egfr", "C_BENH_LY_MAN_TINH_KEM_THEO", "Mức lọc cầu thận eGFR", egfr, p["page_index"], p["filename"], f"Tự động tính theo CKD-EPI 2021 từ SCr: {cr_b} ({ev})", "Tự động tính toán CKD-EPI")
                    break

    acr = man_tinh.get("acr")
    if acr is not None:
        for p in pages:
            alb, alb_u = extract_lab_measurement(p["text"], r'Albumin\s*niệu')
            cre, cre_u = extract_lab_measurement(p["text"], r'Creatinin\s*niệu')
            if alb and cre:
                ev_alb = find_evidence_line(p["text"], r'Albumin\s*niệu')
                ev_cre = find_evidence_line(p["text"], r'Creatinin\s*niệu')
                add_provenance(
                    "acr", "C_BENH_LY_MAN_TINH_KEM_THEO", "Tỷ lệ ACR (Albumin/Creatinin niệu)", acr, 
                    p["page_index"], p["filename"], 
                    f"Tính từ Albumin niệu: '{ev_alb}' & Creatinin niệu: '{ev_cre}'",
                    f"Tự động tính toán: ({alb} * 8.84) / {cre} = {acr} mg/g"
                )
                break

    # Vi đạm niệu
    if final_data.get("TON_THUONG_CO_QUAN_DICH", {}).get("albumin_microalbumin_nieu") is True:
        target_p = None
        for p in pages:
            if re.search(r'Albumin\s*niệu', p["text"], re.IGNORECASE):
                target_p = p
                break
        if target_p:
            add_provenance(
                "albumin_microalbumin_nieu", "TON_THUONG_CO_QUAN_DICH", "Tổn thương thận / Microalbumin niệu", True,
                target_p["page_index"], target_p["filename"],
                f"Đánh giá từ ACR = {acr} mg/g (>= 30 mg/g -> có vi đạm niệu)" if acr else "Đánh giá từ chỉ số Albumin niệu",
                "Suy luận y khoa chuẩn KDIGO"
            )

    # 6. Các bệnh lý mạn tính kèm theo (chỉ lấy các bệnh = True)
    chronic_map = {
        "roi_loan_chuyen_hoa_mo_mau": ("Rối loạn chuyển hóa mỡ máu", r'rối loạn chuyển hóa (?:lipid|mỡ máu)|mỡ máu'),
        "vua_xo_mach_mau": ("Vữa xơ mạch máu", r'xơ vữa|vữa xơ'),
        "tang_huyet_ap": ("Tăng huyết áp", r'tăng huyết áp|hypertension'),
        "dai_thao_duong": ("Đái tháo đường", r'đái tháo đường|tiểu đường|diabetes'),
        "suy_than": ("Suy thận", r'suy thận|bệnh thận mạn|ckd'),
        "benh_ly_mach_vanh": ("Bệnh lý mạch vành", r'mạch vành|cad'),
        "nhoi_mau_co_tim": ("Nhồi máu cơ tim", r'nhồi máu cơ tim'),
        "dot_quy_nao": ("Đột quỵ não", r'đột quỵ|tai biến mạch máu não|stroke'),
        "phinh_dong_mach_chu": ("Phình động mạch chủ", r'phình động mạch chủ|aaa'),
        "benh_mach_mau_ngoai_vi": ("Bệnh mạch máu ngoại vi", r'mạch máu ngoại vi|pad'),
        "tang_cholesterol_mau_gia_dinh": ("Tăng Cholesterol máu gia đình", r'cholesterol.*gia đình|fh')
    }
    for field_key, (disp_name, pat) in chronic_map.items():
        if man_tinh.get(field_key) is True:
            for p in pages:
                ev = find_evidence_line(p["text"], pat)
                if ev:
                    add_provenance(field_key, "C_BENH_LY_MAN_TINH_KEM_THEO", disp_name, True, p["page_index"], p["filename"], ev, "Nhận diện từ chẩn đoán y khoa")
                    break

    # Sắp xếp theo trang tăng dần
    provenance_list.sort(key=lambda x: x["trang"])

    return provenance_list, page_findings_map
