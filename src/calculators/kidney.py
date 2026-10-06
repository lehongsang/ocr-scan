import math
import re
from typing import Optional

def calculate_egfr(
    scr_val: float,
    scr_unit: str = "µmol/L",
    age: Optional[int] = None,
    gender: str = "Nam"
) -> Optional[float]:
    """
    Tính mức lọc cầu thận ước tính eGFR theo công thức CKD-EPI 2021:
    eGFR = 142 × min(SCr/κ, 1)^α × max(SCr/κ, 1)^−1.200 × 0.9938^Tuổi × Hệ số giới
    
    Tham số:
    - scr_val: Nồng độ Creatinin huyết thanh (máu).
    - scr_unit: Đơn vị của SCr (chuẩn là 'mg/dL' hoặc 'µmol/L' / 'umol/L').
    - age: Tuổi của bệnh nhân (năm, áp dụng cho người >= 18 tuổi).
    - gender: Giới tính ('Nam' hoặc 'Nữ').
    
    Quy ước hệ số:
    - Nữ: κ = 0.7, α = -0.241, Hệ số giới = 1.012
    - Nam: κ = 0.9, α = -0.302, Hệ số giới = 1.0
    - Nếu kết quả là µmol/L: SCr (mg/dL) = SCr (µmol/L) ÷ 88.4
    
    Trả về:
    - Giá trị eGFR làm tròn 1 chữ số thập phân (đơn vị mL/min/1.73 m²), hoặc None nếu thiếu dữ liệu.
    """
    if scr_val is None or scr_val <= 0 or age is None or age < 18:
        return None

    # Chuẩn hóa đơn vị SCr về mg/dL
    unit = (scr_unit or "µmol/l").lower().strip()
    if "µmol" in unit or "umol" in unit or "um" in unit or "µm" in unit:
        scr_mg_dl = scr_val / 88.4
    elif "mg/dl" in unit or "mg%" in unit:
        scr_mg_dl = scr_val
    elif "mmol" in unit:
        # 1 mmol/L = 1000 µmol/L
        scr_mg_dl = (scr_val * 1000.0) / 88.4
    else:
        # Nếu giá trị lớn hơn 20, nhiều khả năng là µmol/L (giá trị bình thường khoảng 40-120 µmol/L)
        if scr_val > 20:
            scr_mg_dl = scr_val / 88.4
        else:
            scr_mg_dl = scr_val

    # Xác định giới tính
    gender_str = (gender or "").lower().strip()
    is_female = any(k in gender_str for k in ["nữ", "nu", "female", "f", "gái"])

    kappa = 0.7 if is_female else 0.9
    alpha = -0.241 if is_female else -0.302
    gender_factor = 1.012 if is_female else 1.0

    scr_k = scr_mg_dl / kappa
    min_part = min(scr_k, 1.0) ** alpha
    max_part = max(scr_k, 1.0) ** -1.200
    age_part = 0.9938 ** age

    egfr = 142.0 * min_part * max_part * age_part * gender_factor
    return round(egfr, 1)


def calculate_acr(
    alb_val: float,
    alb_unit: str = "mg/L",
    cre_val: float = 0.0,
    cre_unit: str = "mmol/L"
) -> Optional[float]:
    """
    Tính toán tỷ lệ Albumin/Creatinin niệu (ACR) theo công thức chuẩn quy đổi về mg/g:
    
    Bảng công thức quy đổi:
    1. Albumin (mg/L)   & Creatinin (g/L):    ACR (mg/g) = Albumin ÷ Creatinin
    2. Albumin (mg/L)   & Creatinin (mmol/L): ACR (mg/g) = Albumin × 8.84 ÷ Creatinin
    3. Albumin (mg/L)   & Creatinin (mg/dL):  ACR (mg/g) = Albumin × 100 ÷ Creatinin
    4. Albumin (mg/dL)  & Creatinin (mg/dL):  ACR (mg/g) = Albumin × 1000 ÷ Creatinin
    5. Albumin (mg/L)   & Creatinin (µmol/L): ACR (mg/g) = Albumin × 8840 ÷ Creatinin
    
    Tham số:
    - alb_val: Giá trị Albumin niệu.
    - alb_unit: Đơn vị Albumin niệu ('mg/L', 'mg/dL', 'g/L', 'µg/mL').
    - cre_val: Giá trị Creatinin niệu.
    - cre_unit: Đơn vị Creatinin niệu ('g/L', 'mmol/L', 'mg/dL', 'µmol/L').
    
    Trả về:
    - Giá trị ACR làm tròn 2 chữ số thập phân (đơn vị mg/g), hoặc None nếu thiếu dữ liệu.
    """
    if alb_val is None or alb_val < 0 or cre_val is None or cre_val <= 0:
        return None

    alb_u = (alb_unit or "mg/l").lower().strip()
    cre_u = (cre_unit or "mmol/l").lower().strip()

    # Chuẩn hóa Albumin về mg/L nếu đang ở đơn vị khác
    # 1 g/L = 1000 mg/L; 1 µg/mL = 1 mg/L
    if "g/l" in alb_u and "mg" not in alb_u and "µg" not in alb_u:
        alb_mg_l = alb_val * 1000.0
    elif "mg/dl" in alb_u:
        # 1 mg/dL = 10 mg/L
        alb_mg_l = alb_val * 10.0
    else:
        alb_mg_l = alb_val

    # Tính ACR theo đơn vị của Creatinin niệu
    if "mmol" in cre_u:
        acr = (alb_mg_l * 8.84) / cre_val
    elif "µmol" in cre_u or "umol" in cre_u:
        cre_mmol = cre_val / 1000.0
        acr = (alb_mg_l * 8.84) / cre_mmol if cre_mmol > 0 else 0
    elif "g/l" in cre_u and "mg" not in cre_u and "µg" not in cre_u:
        acr = alb_mg_l / cre_val
    elif "mg/dl" in cre_u:
        # Albumin (mg/L) và Creatinin (mg/dL) -> ACR = Albumin * 100 / Creatinin
        acr = (alb_mg_l * 100.0) / cre_val
    else:
        # Fallback thông minh dựa trên độ lớn giá trị nếu không rõ đơn vị
        if cre_val > 50:  # Khả năng là µmol/L hoặc mg/dL
            cre_mmol = cre_val / 1000.0
            acr = (alb_mg_l * 8.84) / cre_mmol if cre_mmol > 0 else 0
        else:  # Khả năng là mmol/L (giá trị thường từ 3 - 25 mmol/L)
            acr = (alb_mg_l * 8.84) / cre_val

    return round(acr, 2)
