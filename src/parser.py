import re
import os
import json
import requests
from typing import Dict, Any
from src.config import GEMINI_API_KEY, GEMINI_API_URL

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

def fill_missing_fields(data: dict, schema_dict: dict) -> dict:
    """
    Điền các trường bị thiếu trong kết quả trả về từ Gemini bằng giá trị mặc định (null hoặc false/true)
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
            
            # Kiểm tra xem trường đó có trong kết quả trả về của Gemini không
            if field_name in gemini_section:
                val = gemini_section[field_name]
                filled_data[section_name][field_name] = val
            else:
                # Nếu không có trường này trong kết quả của Gemini, ta gán giá trị mặc định
                if field_type == "boolean":
                    filled_data[section_name][field_name] = False
                else:
                    filled_data[section_name][field_name] = None
                    
    return filled_data

def parse_medical_fields_gemini(text: str, schema_path: str) -> Dict[str, Any]:
    """
    Gửi văn bản hồ sơ bệnh án cùng với cấu trúc schema.json tới Gemini API để nhận diện chính xác
    các trường thông tin có cấu trúc dưới dạng JSON.
    """
    try:
        # Đọc file schema.json
        if not os.path.exists(schema_path):
            return {"error": f"Không tìm thấy file schema tại: {schema_path}"}
            
        with open(schema_path, "r", encoding="utf-8") as f:
            schema_dict = json.load(f)
            
        # Chuyển đổi sang OpenAPI Schema
        gemini_schema = convert_to_gemini_schema(schema_dict)
        
        # Gọi API
        url = f"{GEMINI_API_URL}?key={GEMINI_API_KEY}"
        
        prompt = (
            "Bạn là một chuyên gia phân tích hồ sơ bệnh án. Hãy đọc kỹ văn bản kết quả xét nghiệm/khám bệnh sau đây "
            "và trích xuất chính xác toàn bộ các trường thông tin lâm sàng được định nghĩa trong schema JSON.\n"
            "Yêu cầu:\n"
            "- Điền giá trị đúng kiểu dữ liệu quy định trong schema (ví dụ: integer, float, boolean, enum, string).\n"
            "- Trả về định dạng JSON khớp 100% với cấu trúc schema.\n"
            "- Chỉ trích xuất từ dữ liệu thực tế của hồ sơ bệnh nhân, không tự bịa ra thông tin.\n\n"
            f"VĂN BẢN HỒ SƠ Y TẾ:\n{text}"
        )
        
        payload = {
            "contents": [{
                "parts": [{
                    "text": prompt
                }]
            }],
            "generationConfig": {
                "responseMimeType": "application/json",
                "responseSchema": gemini_schema
            }
        }
        
        headers = {
            "Content-Type": "application/json"
        }
        
        response = requests.post(url, json=payload, headers=headers, timeout=30)
        
        if response.status_code == 200:
            resp_json = response.json()
            candidates = resp_json.get("candidates", [])
            if candidates:
                text_content = candidates[0].get("content", {}).get("parts", [{}])[0].get("text", "")
                gemini_data = json.loads(text_content)
                # Điền đầy đủ các trường bị thiếu từ schema gốc
                return fill_missing_fields(gemini_data, schema_dict)
            else:
                return {"error": "API trả về phản hồi rỗng từ Gemini."}
        else:
            return {"error": f"Lỗi gọi Gemini API (Status {response.status_code}): {response.text}"}
            
    except Exception as e:
        return {"error": f"Lỗi kết nối hoặc xử lý trích xuất qua Gemini: {str(e)}"}

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
    egfr_match = re.search(r'(?:eGFR|Độ thanh thải cầu thận)[^\n]*\n(?:[A-Z\s]*\n)?\s*(\d+(?:\.\d+)?)', text, re.IGNORECASE)
    if egfr_match:
        result["C_BENH_LY_MAN_TINH_KEM_THEO"]["egfr"] = int(float(egfr_match.group(1)))

    acr_match = re.search(r'(?:ACR|Tỷ lệ Albumin/Creatinin)[^\n]*\n(?:[A-Z\s]*\n)?\s*(\d+(?:\.\d+)?)', text, re.IGNORECASE)
    if acr_match:
        result["C_BENH_LY_MAN_TINH_KEM_THEO"]["acr"] = int(float(acr_match.group(1)))

    # --- 11. Huyết áp tâm thu SBP ---
    sbp_match = re.search(r'(?:Huyết áp tâm thu|SBP):\s*(\d+)', text, re.IGNORECASE)
    if sbp_match:
        result["A_CHI_SO_SINH_LY_CO_BAN"]["huyet_ap_tam_thu_sbp"] = int(sbp_match.group(1))

    # --- 12. Mã nhóm chăm sóc ---
    care_match = re.search(r'(?:Care Group Code|Mã nhóm chăm sóc):\s*([a-zA-Z0-9]+)', text, re.IGNORECASE)
    if care_match:
        result["D_THONG_TIN_NHOM_CHAM_SOC"]["ma_nhom_cham_soc"] = care_match.group(1)

    return result
