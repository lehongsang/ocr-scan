import re
import os
import json
import requests
from typing import Dict, Any, Optional
from src.config import GEMINI_API_KEY, GEMINI_API_URL, GEMINI_TEMPERATURE, GEMINI_MAX_OUTPUT_TOKENS

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

def extract_diagnostic_text(text: str) -> str:
    """
    Trích xuất đoạn văn bản Chẩn đoán / Tiền sử bệnh ngắn để gửi cho Gemini API.
    """
    diag_match = re.search(
        r'(?:Chẩn đoán|Chẩn đoán chính|Chẩn đoán sơ bộ|Tiền sử|Bệnh lý):\s*\n?\s*([^\n]+(?:\n[^\n]+){0,5})',
        text,
        re.IGNORECASE
    )
    if diag_match:
        return clean_value(diag_match.group(0))
    
    # Fallback: lấy các dòng chứa từ khóa y khoa
    lines = text.split('\n')
    diag_lines = [
        l.strip() for l in lines 
        if any(k in l.lower() for k in ["chẩn đoán", "tiền sử", "bệnh", "mạch", "tim", "xơ vữa", "tháo đường", "thận", "não", "vữa xơ"])
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
        # 2. Trích xuất đoạn chẩn đoán y khoa ngắn
        chandoan_text = extract_diagnostic_text(text)
        
        # 3. Tạo Schema thu gọn chỉ chứa các bệnh lý (boolean)
        disease_schema_dict = get_disease_only_schema(schema_dict)
        gemini_schema = convert_to_gemini_schema(disease_schema_dict)
        
        # 4. Gửi request Gemini API với prompt tối ưu & tham số sinh siêu tốc
        url = f"{GEMINI_API_URL}?key={GEMINI_API_KEY}"
        prompt = (
            "Bạn là chuyên gia y tế. Hãy phân tích đoạn chẩn đoán sau và xác định các bệnh lý có mặt "
            "(gán true cho các bệnh lý thực sự được chẩn đoán):\n\n"
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

def parse_medical_fields(text: str) -> Dict[str, Any]:
    """
    Phân tích văn bản thô (OCR hoặc trích xuất số) để chuyển đổi thành cấu trúc
    trường thông tin chi tiết dựa trên schema đã định nghĩa.
    """
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
            "hdl_cholesterol": None
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
            "dai_thao_duong": False,
            "nhoi_mau_co_tim": False,
            "benh_ly_mach_vanh": False,
            "phinh_dong_mach_chu": False,
            "vua_xo_mach_mau": False,
            "dot_quy_nao": False,
            "hoi_chung_vanh_cap": False,
            "thieu_mau_cuc_bo_nao_thoang_qua_tia": False,
            "benh_mach_mau_ngoai_vi": False,
            "tang_cholesterol_mau_gia_dinh": False
        },
        "THONG_TIN_CA_NHAN": {
            "ho_va_ten": None,
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

    # --- 1. Họ và tên ---
    name_match = re.search(r'(?:Họ và tên|Họ tên):\s*([^\n]+)', text, re.IGNORECASE)
    if name_match:
        result["THONG_TIN_CA_NHAN"]["ho_va_ten"] = clean_value(name_match.group(1))
    else:
        # Fallback tìm kiếm dòng đầu tiên dạng chữ IN HOA tên bệnh nhân (Ví dụ: NGUYỄN THỊ HỢP - BN000801164)
        first_lines = text.split('\n')[:5]
        for line in first_lines:
            match = re.match(r'^([A-ZÀÁÂÃÈÉÊÌÍÒÓÔÕÙÚÝĂĐĨŨƠƯ\s]+)(?:\s+-\s+BN\d+)?$', line.strip())
            if match:
                result["THONG_TIN_CA_NHAN"]["ho_va_ten"] = clean_value(match.group(1))
                break

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
    diag_match = re.search(r'Chẩn đoán:\s*\n?\s*([^\n]+)', text, re.IGNORECASE)
    diagnostics = ""
    if diag_match:
        diagnostics = clean_value(diag_match.group(1))
        result["CHI_SO_AND_TIEN_SU_SUC_KHOE"]["tien_su_benh_ly"] = diagnostics

    # Phân tích từ chẩn đoán để xác định bệnh lý mãn tính
    diag_lower = diagnostics.lower()
    
    # Vữa xơ mạch máu
    if any(k in diag_lower for k in ["xơ vữa", "xo vua", "vữa xơ", "vữa sơ"]):
        result["C_BENH_LY_MAN_TINH_KEM_THEO"]["vua_xo_mach_mau"] = True
        result["PHAN_LOAI_BENH_LY_NEN"]["has_underlying_disease"] = True
        
    # Đái tháo đường
    if any(k in diag_lower for k in ["đái tháo đường", "đái đường", "tiểu đường", "diabetes"]):
        result["C_BENH_LY_MAN_TINH_KEM_THEO"]["dai_thao_duong"] = True
        result["PHAN_LOAI_BENH_LY_NEN"]["has_underlying_disease"] = True

    # Đột quỵ
    if any(k in diag_lower for k in ["đột quỵ", "tai biến mạch máu não", "stroke"]):
        result["C_BENH_LY_MAN_TINH_KEM_THEO"]["dot_quy_nao"] = True
        result["PHAN_LOAI_BENH_LY_NEN"]["has_underlying_disease"] = True

    # Nhồi máu cơ tim
    if "nhồi máu cơ tim" in diag_lower:
        result["C_BENH_LY_MAN_TINH_KEM_THEO"]["nhoi_mau_co_tim"] = True
        result["PHAN_LOAI_BENH_LY_NEN"]["has_underlying_disease"] = True

    # Bệnh mạch vành
    if any(k in diag_lower for k in ["mạch vành", "cơn đau thắt ngực", "ngực crnn"]):
        result["C_BENH_LY_MAN_TINH_KEM_THEO"]["benh_ly_mach_vanh"] = True
        result["PHAN_LOAI_BENH_LY_NEN"]["has_underlying_disease"] = True
        
    # Suy thận
    if "suy thận" in diag_lower:
        result["PHAN_LOAI_BENH_LY_NEN"]["has_underlying_disease"] = True

    # --- 8. Cholesterol toàn phần ---
    # Thường ở dạng:
    # Cholesterol toàn phần*
    # [H hoặc L hoặc rỗng]
    # 6.15
    chol_match = re.search(r'Cholesterol toàn phần[^\n]*\n(?:[A-Z\s]*\n)?\s*(\d+(?:\.\d+)?)', text, re.IGNORECASE)
    if chol_match:
        val = float(chol_match.group(1))
        result["A_CHI_SO_SINH_LY_CO_BAN"]["cholesterol_toan_phan"] = val
        if val > 5.2:
            result["C_BENH_LY_MAN_TINH_KEM_THEO"]["tang_cholesterol_mau_gia_dinh"] = True

    # --- 9. HDL-Cholesterol ---
    hdl_match = re.search(r'HDL(?:-|\s*)Cholesterol[^\n]*\n(?:[A-Z\s]*\n)?\s*(\d+(?:\.\d+)?)', text, re.IGNORECASE)
    if hdl_match:
        result["A_CHI_SO_SINH_LY_CO_BAN"]["hdl_cholesterol"] = float(hdl_match.group(1))

    # --- 10. eGFR & ACR ---
    # 10.1. Trích xuất eGFR trực tiếp nếu có
    egfr_match = re.search(r'(?:eGFR|Độ thanh thải cầu thận|Mức lọc cầu thận eGFR)[^\n]*[=:]?\s*\n?(?:[A-Z\s]*\n)?\s*(\d+(?:\.\d+)?)', text, re.IGNORECASE)
    if egfr_match:
        result["C_BENH_LY_MAN_TINH_KEM_THEO"]["egfr"] = float(egfr_match.group(1))

    # 10.2. Trích xuất ACR trực tiếp nếu có
    acr_match = re.search(r'(?:ACR|Tỷ lệ Albumin/Creatinin)[^\n]*[=:]?\s*\n?(?:[A-Z\s]*\n)?\s*(\d+(?:\.\d+)?)', text, re.IGNORECASE)
    if acr_match:
        result["C_BENH_LY_MAN_TINH_KEM_THEO"]["acr"] = float(acr_match.group(1))

    # 10.3. Bóc tách Albumin niệu & Creatinin niệu để tự động tính ACR nếu chưa có
    cre_u_match = re.search(r'(?:Creatinin niệu|Creatinin\s*\(niệu\)|Creatinine niệu)[^\n]*\n?(?:[A-Z\s]*\n)?\s*(\d+(?:\.\d+)?)\s*\n?\s*(mmol/L|mg/dL|g/L|µmol/L|umol/L)?', text, re.IGNORECASE)
    alb_u_match = re.search(r'(?:Albumin niệu|Microalbumin niệu|Albumin\s*\(niệu\)|Microalbumin)[^\n]*\n?(?:[A-Z\s]*\n)?\s*(\d+(?:\.\d+)?)\s*\n?\s*(mg/L|mg/dL|g/L|µg/mL)?', text, re.IGNORECASE)

    if alb_u_match and cre_u_match:
        alb_val = float(alb_u_match.group(1))
        alb_unit = alb_u_match.group(2) or "mg/L"
        cre_val = float(cre_u_match.group(1))
        cre_unit = cre_u_match.group(2) or "mmol/L"

        calculated_acr = calculate_acr(alb_val, alb_unit, cre_val, cre_unit)
        if calculated_acr is not None:
            # Nếu chưa có acr hoặc ưu tiên giá trị tính từ xét nghiệm thực tế
            result["C_BENH_LY_MAN_TINH_KEM_THEO"]["acr"] = calculated_acr

    # 10.4. Tự động tính eGFR nếu chưa có từ Creatinin huyết thanh (máu) + Tuổi + Giới tính
    if result["C_BENH_LY_MAN_TINH_KEM_THEO"]["egfr"] is None:
        cre_b_match = re.search(r'(?:Creatinin huyết thanh|Creatinin máu|SCr|Creatinin\*(?!\s*niệu))[^\n]*\n?(?:[A-Z\s]*\n)?\s*(\d+(?:\.\d+)?)\s*\n?\s*(µmol/L|umol/L|mg/dL)?', text, re.IGNORECASE)
        if cre_b_match:
            scr_val = float(cre_b_match.group(1))
            scr_unit = cre_b_match.group(2) or "µmol/L"
            age_val = result["A_CHI_SO_SINH_LY_CO_BAN"].get("tuoi")
            gender_val = result["A_CHI_SO_SINH_LY_CO_BAN"].get("gioi_tinh") or "Nam"
            calculated_egfr = calculate_egfr(scr_val, scr_unit, age_val, gender_val)
            if calculated_egfr is not None:
                result["C_BENH_LY_MAN_TINH_KEM_THEO"]["egfr"] = calculated_egfr

    # 10.5. Đánh giá tổn thương thận / vi đạm niệu dựa trên ACR hoặc Albumin niệu
    current_acr = result["C_BENH_LY_MAN_TINH_KEM_THEO"].get("acr")
    if current_acr is not None:
        if current_acr >= 30:  # ACR >= 30 mg/g là có Microalbumin niệu (tiêu chuẩn y khoa)
            result["TON_THUONG_CO_QUAN_DICH"]["albumin_microalbumin_nieu"] = True
            result["PHAN_LOAI_BENH_LY_NEN"]["has_underlying_disease"] = True
    elif alb_u_match:
        alb_val = float(alb_u_match.group(1))
        if alb_val >= 20:  # Albumin niệu >= 20-30 mg/L
            result["TON_THUONG_CO_QUAN_DICH"]["albumin_microalbumin_nieu"] = True
            result["PHAN_LOAI_BENH_LY_NEN"]["has_underlying_disease"] = True

    # Đánh giá suy giảm chức năng thận nếu eGFR < 60
    current_egfr = result["C_BENH_LY_MAN_TINH_KEM_THEO"].get("egfr")
    if current_egfr is not None and current_egfr < 60:
        result["PHAN_LOAI_BENH_LY_NEN"]["has_underlying_disease"] = True

    # --- 11. Huyết áp tâm thu SBP ---
    sbp_match = re.search(r'(?:Huyết áp tâm thu|SBP):\s*(\d+)', text, re.IGNORECASE)
    if sbp_match:
        result["A_CHI_SO_SINH_LY_CO_BAN"]["huyet_ap_tam_thu_sbp"] = int(sbp_match.group(1))

    # --- 12. Mã nhóm chăm sóc ---
    care_match = re.search(r'(?:Care Group Code|Mã nhóm chăm sóc):\s*([a-zA-Z0-9]+)', text, re.IGNORECASE)
    if care_match:
        result["D_THONG_TIN_NHOM_CHAM_SOC"]["ma_nhom_cham_soc"] = care_match.group(1)

    return result
