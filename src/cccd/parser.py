import re
from typing import Dict, Any, Optional
from datetime import datetime

def parse_cccd_qr_data(qr_text: str) -> Optional[Dict[str, Any]]:
    """
    Phân tích chuỗi dữ liệu thô từ mã QR của CCCD / Căn cước Việt Nam.
    Định dạng chuẩn QR CCCD gắn chip (phân tách bởi ký tự '|'):
    [Số 12 số]|[Số CMND cũ 9 số (nếu có)]|[Họ và tên]|[Ngày sinh ddmmyyyy]|[Giới tính]|[Nơi thường trú / Cư trú]|[Ngày cấp ddmmyyyy]
    """
    if not qr_text or not isinstance(qr_text, str):
        return None

    parts = [p.strip() for p in qr_text.split("|")]
    if len(parts) < 6:
        return None

    id_number = parts[0] if len(parts[0]) in [9, 12] else None
    old_id = parts[1] if len(parts) > 1 and parts[1] else None
    full_name = parts[2] if len(parts) > 2 else None
    
    # Format ngày sinh từ ddmmyyyy sang dd/mm/yyyy
    dob_raw = parts[3] if len(parts) > 3 else None
    dob = None
    if dob_raw and len(dob_raw) == 8 and dob_raw.isdigit():
        dob = f"{dob_raw[0:2]}/{dob_raw[2:4]}/{dob_raw[4:8]}"
    elif dob_raw:
        dob = dob_raw

    gender = parts[4] if len(parts) > 4 else None
    residence = parts[5] if len(parts) > 5 else None

    # Ngày cấp
    issue_date = None
    if len(parts) > 6 and parts[6]:
        issue_raw = parts[6]
        if len(issue_raw) == 8 and issue_raw.isdigit():
            issue_date = f"{issue_raw[0:2]}/{issue_raw[2:4]}/{issue_raw[4:8]}"
        else:
            issue_date = issue_raw

    return {
        "id_number": id_number,
        "old_id_number": old_id,
        "full_name": full_name,
        "date_of_birth": dob,
        "gender": gender,
        "nationality": "Việt Nam",
        "place_of_residence": residence,
        "issue_date": issue_date,
        "card_type": "cccd_chip",
        "scanned_qr": True
    }

def is_address_like(line: str) -> bool:
    """Kiểm tra xem 1 dòng text có cấu trúc của địa danh hành chính hay không."""
    if not line:
        return False
    l = line.lower()
    
    # Loại trừ toàn bộ các dòng tiêu đề, nhãn, ngày tháng, quốc hiệu
    label_stop_words = [
        "giá trị đến", "gia tri den", "giattden", "expiry", "expin", "căn cước", "can cuoc",
        "quốc tịch", "quoc tich", "nationality", "giới tính", "gioi tinh", "sex", "gender",
        "họ và tên", "ho va ten", "họ, chữ đệm", "ho, chu dem", "khai sinh", "full name",
        "ngày, tháng, năm sinh", "ngay, thang, nam sinh", "ngày sinh", "ngay sinh", "date of birth", "dateofbirth",
        "ngày, tháng, năm cấp", "ngay, thang, nam cap", "ngày cấp", "ngay cap", "date of issue", "dateofissue",
        "ngày, tháng, năm hết hạn", "ngay, thang, nam het han", "ngày hết hạn", "ngay het han", "date of expiry", "dateofexpiry",
        "cộng hòa", "độc lập", "tự do", "hạnh phúc", "socialist", "republic", "vietnam", "viet nam",
        "independence", "freedom", "happiness", "số định danh", "so dinh danh", "personal identification",
        "personalidentification", "bộ công an", "ministry", "public security", "publicsecurity", "cục trưởng", "cục cảnh sát"
    ]
    if any(sw in l for sw in label_stop_words):
        return False

    # Các từ khóa hành chính
    admin_patterns = [
        r'\btỉnh\b', r'\bthành phố\b', r'\btp\b', r'\bquận\b', r'\bhuyện\b', r'\bthị xã\b', r'\btx\b', 
        r'\bxã\b', r'\bphường\b', r'\bthị trấn\b', r'\btt\b', r'\bthôn\b', r'\btổ\s*\d+\b', r'\btổ\s*dân\s*phố\b',
        r'\btodanphoso\b', r'\btodangphoso\b', r'\bto\s*dan\s*pho\b', r'\bấp\b', r'\bbản\b', r'\bphố\b', r'\bđường\b',
        r'nam\s*định', r'lào\s*cai', r'hà\s*nội', r'hải\s*phòng', r'đà\s*nẵng', r'hồ\s*chí\s*minh',
        r'nam\s*dinh', r'lao\s*cai', r'ha\s*noi', r'hai\s*phong', r'da\s*nang', r'ho\s*chi\s*minh',
        r'thái\s*bình', r'thai\s*binh', r'bắc\s*ninh', r'bac\s*ninh', r'thanh\s*hóa', r'thanh\s*hoa',
        r'văn\s*bàn', r'van\s*ban', r'laocai', r'namdinh', r'hanoi'
    ]
    if any(re.search(p, l) for p in admin_patterns):
        return True
        
    return False

def clean_address_line(line: str) -> str:
    """Làm sạch các từ khóa nhãn bị dính vào địa chỉ."""
    cleaned = line
    cleaned = re.sub(r'(?:Giới tính|Gioi tinh|Sex|Quốc tịch|Quoc tich|Nationality|Có giá trị đến|Co gia tri den|Date of expiry|Place of birth|Place of residence|Nơi đăng ký|Nơi cư trú|Nơi thường trú).*$', '', cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r'^[,\s.:/-]+', '', cleaned)
    return cleaned.strip()

def parse_cccd_text(ocr_text: str) -> Dict[str, Any]:
    """
    Trích xuất các trường thông tin từ văn bản OCR của thẻ Căn cước (2024) / CCCD (2021) / CMND.
    """
    data = {
        "id_number": None,
        "full_name": None,
        "date_of_birth": None,
        "gender": None,
        "nationality": "Việt Nam",
        "place_of_origin": None,
        "place_of_residence": None,
        "date_of_expiry": None,
        "issue_date": None,
        "place_of_issue": None,
        "personal_identification": None,
        "card_type": "cccd"
    }

    if not ocr_text:
        return data

    lines = [line.strip() for line in ocr_text.split("\n") if line.strip()]

    # 1. Trích xuất Số định danh cá nhân / Số CCCD / CMND (12 chữ số cho CCCD/Căn cước, 9 chữ số cho CMND)
    id_pattern = re.compile(
        r'(?:Số định danh cá nhân|So dinh danh ca nhan|Personal identification number|Personalidentificationnumber|Sodinhdanhcanhan|Số|So|No|SỐ|s6|so/no)\s*[:./]?\s*([0-9]{9,12})', 
        re.IGNORECASE
    )
    standalone_12_digits = re.compile(r'\b([0-9]{12})\b')
    standalone_9_digits = re.compile(r'\b([0-9]{9})\b')

    for line in lines:
        m = id_pattern.search(line)
        if m:
            data["id_number"] = m.group(1)
            break
    
    if not data["id_number"]:
        for line in lines:
            m = standalone_12_digits.search(line)
            if m:
                data["id_number"] = m.group(1)
                break
                
    if not data["id_number"]:
        for line in lines:
            m = standalone_9_digits.search(line)
            if m:
                data["id_number"] = m.group(1)
                data["card_type"] = "cmnd_9_so"
                break

    # 2. Ngày sinh (Date of birth) & Ngày hết hạn (Date of expiry)
    dob_pattern = re.compile(
        r'(?:ngày,?\s*tháng,?\s*năm sinh|ngay,?\s*thang,?\s*nam sinh|date of birth|dateofbirth|ngày sinh|ngay sinh|ngaysinh|sinh)\s*[:./]?\s*(\d{1,2}[/-]\d{1,2}[/-]\d{4})', 
        re.IGNORECASE
    )
    expiry_pattern = re.compile(
        r'(?:ngày,?\s*tháng,?\s*năm hết hạn|ngay,?\s*thang,?\s*nam het han|date of expiry|dateofexpiry|dateofexpiy|date\s*otbxpiry|otbxpiry|hết hạn|het han|hethan|giá trị đến|gia tri den|giattden|cogiatden|cogiatiden|cogiat|có giá trị đến|co gia tri den|expiry|expin)\s*[:./]?\s*(\d{1,2}[/-]\d{1,2}[/-]\d{4}|Không thời hạn|Khong thoi han)', 
        re.IGNORECASE
    )

    for i, line in enumerate(lines):
        m_dob = dob_pattern.search(line)
        if m_dob and not data["date_of_birth"]:
            data["date_of_birth"] = m_dob.group(1).replace('-', '/')
        elif not data["date_of_birth"] and any(k in line.lower() for k in ["date of birth", "dateofbirth", "nam sinh", "năm sinh"]):
            # Nếu ngày nằm ở dòng tiếp theo
            if i + 1 < len(lines):
                m_d = re.search(r'\b(\d{1,2}[/-]\d{1,2}[/-]\d{4})\b', lines[i + 1])
                if m_d:
                    data["date_of_birth"] = m_d.group(1).replace('-', '/')
            
        m_exp = expiry_pattern.search(line)
        if m_exp and not data["date_of_expiry"]:
            val = m_exp.group(1).strip()
            if "không" in val.lower() or "khong" in val.lower():
                data["date_of_expiry"] = "Không thời hạn"
            else:
                data["date_of_expiry"] = val.replace('-', '/')
        elif not data["date_of_expiry"] and any(k in line.lower() for k in ["date of expiry", "dateofexpiry", "dateofexpiy", "otbxpiry", "het han", "hết hạn", "gia tri den", "cogiat", "có giá trị"]):
            # Tìm ngày ở dòng hiện tại, dòng trước hoặc sau
            m_curr = re.search(r'(\d{1,2}[/-]\d{1,2}[/-]\d{4})', line)
            if m_curr:
                data["date_of_expiry"] = m_curr.group(1).replace('-', '/')
            elif i + 1 < len(lines):
                m_e = re.search(r'(\d{1,2}[/-]\d{1,2}[/-]\d{4})', lines[i + 1])
                if m_e:
                    data["date_of_expiry"] = m_e.group(1).replace('-', '/')
            elif i > 0:
                m_e = re.search(r'(\d{1,2}[/-]\d{1,2}[/-]\d{4})', lines[i - 1])
                if m_e:
                    data["date_of_expiry"] = m_e.group(1).replace('-', '/')

    # Fallback tìm ngày sinh từ tất cả các ngày
    if not data["date_of_birth"]:
        current_year = datetime.now().year
        date_regex = re.compile(r'\b(\d{1,2}[/-]\d{1,2}[/-]\d{4})\b')
        for line in lines:
            for d in date_regex.findall(line):
                formatted = d.replace('-', '/')
                parts = formatted.split('/')
                if len(parts) == 3:
                    try:
                        day, month, year = int(parts[0]), int(parts[1]), int(parts[2])
                        if 1 <= day <= 31 and 1 <= month <= 12 and 1920 <= year <= current_year - 10:
                            data["date_of_birth"] = formatted
                            break
                    except ValueError:
                        pass
            if data["date_of_birth"]:
                break

    # Fallback cho ngày hết hạn: Tìm ngày có năm trong tương lai (> năm hiện tại - 2)
    if not data["date_of_expiry"]:
        current_year = datetime.now().year
        date_regex = re.compile(r'\b(\d{1,2}[/-]\d{1,2}[/-]\d{4})\b')
        for line in lines:
            for d in date_regex.findall(line):
                formatted = d.replace('-', '/')
                parts = formatted.split('/')
                if len(parts) == 3:
                    try:
                        day, month, year = int(parts[0]), int(parts[1]), int(parts[2])
                        if 1 <= day <= 31 and 1 <= month <= 12 and year >= current_year - 1:
                            if formatted != data.get("date_of_birth") and formatted != data.get("issue_date"):
                                data["date_of_expiry"] = formatted
                                break
                    except ValueError:
                        pass
            if data["date_of_expiry"]:
                break

    # 3. Giới tính (Sex/Gender)
    gender_pattern = re.compile(r'(?:Giới tính|Gioi tinh|Sex|Gioitinh)\s*[:./]?\s*(Nam|Nữ|Nu|Male|Female)', re.IGNORECASE)
    for line in lines:
        m = gender_pattern.search(line)
        if m:
            g = m.group(1).strip()
            if g.lower() in ["nam", "male"]:
                data["gender"] = "Nam"
            elif g.lower() in ["nữ", "nu", "female"]:
                data["gender"] = "Nữ"
            break
            
    if not data["gender"]:
        for line in lines:
            if re.search(r'\bNam\b', line) and not re.search(r'Việt Nam|Viet Nam|VIETNAM', line, re.IGNORECASE):
                data["gender"] = "Nam"
                break
            elif re.search(r'\bNữ\b|\bNu\b', line):
                data["gender"] = "Nữ"
                break

    # 4. Họ và tên (Full name)
    name_keywords = [
        "họ, chữ đệm và tên khai sinh", "ho, chu dem va ten khai sinh",
        "họ, chữ đệm", "ho, chu dem", "chữ đệm và tên", "chu dem va ten",
        "tên khai sinh", "ten khai sinh", "họ và tên", "ho va ten",
        "full name", "fullname", "họ tên", "ho ten", "chirdem", "chữ đệm",
        "khai sinh", "khaisinh", "tenkhai", "ho,chi", "ho, chu"
    ]
    excluded_headers = [
        "CỘNG HÒA", "VIỆT NAM", "ĐỘC LẬP", "HẠNH PHÚC", "CĂN CƯỚC", "CÔNG DÂN", 
        "IDENTITY", "CARD", "CONG HOA", "VIET NAM", "DOC LAP", "HANH PHUC", 
        "CAN CUOC", "CONG DAN", "CONGDAN", "SOCIALIST", "REPUBLIC", "CONGHOA",
        "PERSONAL", "IDENTIFICATION", "NUMBER", "DATE", "BIRTH", "SEX", "NATIONALITY"
    ]

    for i, line in enumerate(lines):
        line_lower = line.lower()
        for kw in name_keywords:
            if kw in line_lower:
                if ":" in line or "." in line:
                    candidate = re.split(r'[:.]', line, maxsplit=1)[1].strip()
                    if candidate and not any(k in candidate.lower() for k in ["họ", "tên", "full", "name", "khai sinh"]):
                        data["full_name"] = candidate
                        break
                if not data["full_name"] and i + 1 < len(lines):
                    next_line = lines[i + 1].strip()
                    if len(next_line) >= 2 and not any(c.isdigit() for c in next_line):
                        if not any(ex in next_line.upper() for ex in excluded_headers):
                            data["full_name"] = next_line
                            break
        if data["full_name"]:
            break

    if not data["full_name"]:
        for line in lines:
            words = line.split()
            if line.isupper() and 1 <= len(words) <= 5 and not any(c.isdigit() for c in line):
                if not any(ex in line for ex in excluded_headers) and not is_address_like(line) and len(line) >= 4:
                    data["full_name"] = line
                    break

    # 5. Nơi đăng ký khai sinh (Place of birth / Place of origin)
    origin_keywords = [
        "nơi đăng ký khai sinh", "noi dang ky khai sinh", "noidang kykhai sinh", "noidangkykhaisinh",
        "place of birth", "placeofbirth", "quê quán", "que quan", "quequan", "place of origin", "placeoforigin"
    ]
    for i, line in enumerate(lines):
        line_lower = line.lower()
        for kw in origin_keywords:
            if kw in line_lower:
                if ":" in line or "." in line:
                    candidate = re.split(r'[:.]', line, maxsplit=1)[1].strip()
                    if candidate and len(candidate) > 3 and not any(k in candidate.lower() for k in ["quê", "origin", "quán", "birth", "khai sinh"]):
                        data["place_of_origin"] = candidate
                        break
                # Kiểm tra dòng trước hoặc dòng sau
                if not data["place_of_origin"]:
                    if i + 1 < len(lines):
                        next_l = lines[i + 1].strip()
                        if is_address_like(next_l) or (len(next_l) > 3 and not any(ex in next_l.upper() for ex in excluded_headers)):
                            data["place_of_origin"] = next_l
                            break
                    if i > 0:
                        prev_l = lines[i - 1].strip()
                        if is_address_like(prev_l) or (len(prev_l) > 3 and not any(ex in prev_l.upper() for ex in excluded_headers)):
                            data["place_of_origin"] = prev_l
                            break
        if data["place_of_origin"]:
            break

    # 6. Nơi cư trú / Nơi thường trú (Place of residence)
    residence_keywords = [
        "nơi cư trú", "noi cu tru", "noicutru", "place of residence", "placeofresidence",
        "nơi thường trú", "noi thuong tru", "noithuongtru"
    ]
    for i, line in enumerate(lines):
        line_lower = line.lower()
        for kw in residence_keywords:
            if kw in line_lower:
                if ":" in line or "." in line:
                    candidate = re.split(r'[:.]', line, maxsplit=1)[1].strip()
                    if candidate and len(candidate) > 3 and not any(k in candidate.lower() for k in ["residence", "cư trú", "thường trú"]):
                        data["place_of_residence"] = candidate
                        break
                # Tìm dòng địa chỉ sau hoặc trước
                if not data["place_of_residence"]:
                    res_parts = []
                    for offset in [1, 2, -1, -2]:
                        idx = i + offset
                        if 0 <= idx < len(lines):
                            cand = lines[idx].strip()
                            if is_address_like(cand) and cand != data["place_of_origin"]:
                                res_parts.append(cand)
                    if res_parts:
                        data["place_of_residence"] = ", ".join(res_parts)
                        break
        if data["place_of_residence"]:
            break

    # Thu thập tất cả các địa chỉ hợp lệ nếu chưa tìm được
    address_candidates = []
    for line in lines:
        cleaned = clean_address_line(line)
        if cleaned and is_address_like(cleaned):
            if not any(ex in cleaned.upper() for ex in excluded_headers) and cleaned != data["full_name"]:
                address_candidates.append(cleaned)

    if not data["place_of_origin"] and address_candidates:
        data["place_of_origin"] = address_candidates[0]
        
    if not data["place_of_residence"] and len(address_candidates) >= 2:
        data["place_of_residence"] = address_candidates[1]

    # Kiểm tra mặt sau phụ trợ nếu có
    back_part = parse_cccd_back_text(ocr_text)
    if back_part.get("issue_date") and not data["issue_date"]:
        data["issue_date"] = back_part["issue_date"]
    if back_part.get("place_of_issue") and not data["place_of_issue"]:
        data["place_of_issue"] = back_part["place_of_issue"]
    if back_part.get("place_of_origin") and not data["place_of_origin"]:
        data["place_of_origin"] = back_part["place_of_origin"]
    if back_part.get("place_of_residence") and not data["place_of_residence"]:
        data["place_of_residence"] = back_part["place_of_residence"]

    return data

def parse_cccd_back_text(ocr_text: str) -> Dict[str, Any]:
    """
    Trích xuất các trường thông tin từ văn bản OCR của MẶT SAU thẻ Căn cước (2024) / CCCD (2021) / CMND:
    - issue_date: Ngày cấp
    - place_of_issue: Cơ quan cấp / Nơi cấp
    - place_of_origin: Nơi đăng ký khai sinh (Thẻ 2024)
    - place_of_residence: Nơi cư trú (Thẻ 2024)
    - date_of_expiry: Ngày hết hạn (Thẻ 2024)
    - personal_identification: Đặc điểm nhận dạng (CCCD cũ)
    - ethnicity: Dân tộc (CMND)
    - religion: Tôn giáo (CMND)
    - mrz: Dải mã MRZ 3 dòng
    """
    from .corrector import correct_place_of_issue

    data = {
        "issue_date": None,
        "place_of_issue": None,
        "place_of_origin": None,
        "place_of_residence": None,
        "date_of_expiry": None,
        "personal_identification": None,
        "ethnicity": None,
        "religion": None,
        "mrz": None
    }

    if not ocr_text:
        return data

    lines = [line.strip() for line in ocr_text.split("\n") if line.strip()]

    # 1. Ngày cấp (issue_date) & Ngày hết hạn (date_of_expiry)
    date_word_pattern = re.compile(
        r'(?:ngày|ngay)?\s*(\d{1,2})\s*(?:tháng|thang|thng|thg|t\.)\s*(\d{1,2})\s*(?:năm|nam|nm|n\.)\s*(\d{4})', 
        re.IGNORECASE
    )
    date_label_pattern = re.compile(
        r'(?:ngày[,\s]*tháng[,\s]*năm\s*cấp|ngay[,\s]*thang[,\s]*nam\s*cap|date of issue|dateofissue|ngày cấp|ngay cap)\s*[:./]?\s*(\d{1,2}[/-]\d{1,2}[/-]\d{4})',
        re.IGNORECASE
    )
    expiry_label_pattern = re.compile(
        r'(?:ngày[,\s]*tháng[,\s]*năm\s*hết hạn|ngay[,\s]*thang[,\s]*nam\s*het han|date of expiry|dateofexpiry|hết hạn|het han)\s*[:./]?\s*(\d{1,2}[/-]\d{1,2}[/-]\d{4}|Không thời hạn|Khong thoi han)',
        re.IGNORECASE
    )
    date_standalone_pattern = re.compile(r'\b(\d{1,2}[/-]\d{1,2}[/-]\d{4})\b')

    for i, line in enumerate(lines):
        line_lower = line.lower()
        # Bắt nhãn ngày cấp (Thẻ 2024: "Ngay, thang, nam cap / Date of issue" -> Dòng trước hoặc sau là 28/05/2026)
        if any(k in line_lower for k in ["date of issue", "dateofissue", "nam cap", "năm cấp", "ngày cấp", "ngay cap"]):
            m_iss = date_label_pattern.search(line)
            if m_iss:
                data["issue_date"] = m_iss.group(1).replace('-', '/')
            elif i > 0 and date_standalone_pattern.search(lines[i - 1]):
                data["issue_date"] = date_standalone_pattern.search(lines[i - 1]).group(1).replace('-', '/')
            elif i + 1 < len(lines) and date_standalone_pattern.search(lines[i + 1]):
                data["issue_date"] = date_standalone_pattern.search(lines[i + 1]).group(1).replace('-', '/')

        # Bắt nhãn ngày hết hạn (Thẻ 2024: "Ngay, thang, nam het han / Date of expiry" -> 01/03/2029)
        if any(k in line_lower for k in ["date of expiry", "dateofexpiry", "dateofexpiy", "expiy", "expiry", "nam het han", "năm hết hạn", "hết hạn", "het han", "hethan"]):
            m_exp = expiry_label_pattern.search(line)
            if m_exp:
                data["date_of_expiry"] = m_exp.group(1).replace('-', '/')
            elif i > 0 and date_standalone_pattern.search(lines[i - 1]):
                data["date_of_expiry"] = date_standalone_pattern.search(lines[i - 1]).group(1).replace('-', '/')
            elif i + 1 < len(lines) and date_standalone_pattern.search(lines[i + 1]):
                data["date_of_expiry"] = date_standalone_pattern.search(lines[i + 1]).group(1).replace('-', '/')

    # Fallback cho ngày cấp bằng date_word_pattern
    if not data["issue_date"]:
        for line in lines:
            m_word = date_word_pattern.search(line)
            if m_word and not any(k in line.lower() for k in ["sinh", "birth", "het han", "hết hạn"]):
                day, month, year = int(m_word.group(1)), int(m_word.group(2)), int(m_word.group(3))
                if 1 <= day <= 31 and 1 <= month <= 12 and 1990 <= year <= 2100:
                    data["issue_date"] = f"{day:02d}/{month:02d}/{year}"
                    break

    # 2. Nơi cấp / Cơ quan cấp (place_of_issue)
    authority_keywords = [
        "bộ công an", "bo cong an", "bocongan", "ministry of public security", "ministryofpublic", "public security", "publicsecurity",
        "cục trưởng", "cuc truong", "cuctruong", "cục cảnh sát", "cuc canh sat", "cuccanhsat", "cuctruongcuccanhsat",
        "quan lý hành chính", "quan ly hanh chinh", "quanlyhanhchinh", "trật tự xã hội", "trat tu xa hoi", "trattuxahoi",
        "giám đốc công an", "giam doc cong an", "giamdoccongan", "công an tỉnh", "cong an tinh",
        "công an thành phố", "cong an thanh pho", "director general", "directorgeneral", "police department", "policedepartment",
        "administrative management", "administrativemanagement"
    ]

    matched_auth_lines = []
    for i, line in enumerate(lines):
        line_lower = line.lower()
        if any(kw in line_lower for kw in authority_keywords):
            candidate_auth = line
            if i + 1 < len(lines):
                next_l = lines[i + 1].strip()
                if any(k in next_l.lower() for k in ["hành chính", "hanhchinh", "trật tự", "trattu", "xã hội", "xahoi", "dân cư", "dancu", "quản lý", "quanly", "cư trú", "cutru", "security", "social"]):
                    candidate_auth = f"{candidate_auth} {next_l}"
            matched_auth_lines.append(candidate_auth)

    if matched_auth_lines:
        data["place_of_issue"] = correct_place_of_issue(matched_auth_lines[0])
    else:
        if any("cảnh sát" in l.lower() or "canh sat" in l.lower() or "canhsat" in l.lower() for l in lines):
            data["place_of_issue"] = "CỤC TRƯỞNG CỤC CẢNH SÁT QUẢN LÝ HÀNH CHÍNH VỀ TRẬT TỰ XÃ HỘI"
        elif any("công an" in l.lower() or "cong an" in l.lower() or "congan" in l.lower() or "security" in l.lower() for l in lines):
            data["place_of_issue"] = "BỘ CÔNG AN"

    # 3. Nơi đăng ký khai sinh & Nơi cư trú ở Mặt Sau (Thẻ Căn Cước 2024)
    origin_keywords = ["nơi đăng ký khai sinh", "noi dang ky khai sinh", "noidang kykhai sinh", "place of birth", "placeofbirth"]
    residence_keywords = ["nơi cư trú", "noi cu tru", "noicutru", "place of residence", "placeofresidence"]

    for i, line in enumerate(lines):
        line_lower = line.lower()
        # Nơi khai sinh
        for kw in origin_keywords:
            if kw in line_lower:
                for offset in [-1, 1, -2, 2]:
                    idx = i + offset
                    if 0 <= idx < len(lines):
                        cand = lines[idx].strip()
                        if is_address_like(cand) and not any(k in cand.lower() for k in ["tổ dân phố", "to dan pho", "todan"]):
                            data["place_of_origin"] = cand
                            break
        # Nơi cư trú
        for kw in residence_keywords:
            if kw in line_lower:
                res_items = []
                for offset in [1, 2, -1, -2]:
                    idx = i + offset
                    if 0 <= idx < len(lines):
                        cand = lines[idx].strip()
                        if is_address_like(cand):
                            res_items.append(cand)
                if res_parts := list(dict.fromkeys(res_items)):
                    data["place_of_residence"] = ", ".join(res_parts)

    # 4. Đặc điểm nhận dạng / Dấu vết riêng (CCCD cũ)
    # LƯU Ý: Không bắt nhầm nhãn "Personal identification number" / "Số định danh cá nhân"
    ident_keywords = [
        "đặc điểm nhận dạng", "dac diem nhan dang", "đặc điểm nhân dạng", 
        "dấu vết riêng", "dau vet rieng", "dacdiemnhandang", "dacdiem", "nhandang",
        "personalidentification", "personal identification"
    ]
    ident_stop_words = [
        "number", "số", "cá nhân", "dinh danh", "ngày", "ngay", "date", 
        "cục trưởng", "cuc truong", "giám đốc", "giam doc", 
        "công an", "cục cảnh sát", "director", "i<vnm", "idvnm", "ngon tro", "finger"
    ]

    for i, line in enumerate(lines):
        line_lower = line.lower()
        if any(sw in line_lower for sw in ["number", "số", "cá nhân", "sodinhdanh", "personal identification number"]):
            continue
        for kw in ident_keywords:
            if kw in line_lower:
                ident_parts = []
                if ":" in line or "." in line:
                    cand = re.split(r'[:.]', line, maxsplit=1)[1].strip()
                    if cand and len(cand) > 3 and not any(sw in cand.lower() for sw in ident_stop_words):
                        ident_parts.append(cand)
                
                # Gom các dòng tiếp theo nếu là phần tiếp nối của đặc điểm nhận dạng
                for offset in [1, 2]:
                    idx = i + offset
                    if idx < len(lines):
                        next_l = lines[idx].strip()
                        if not any(sw in next_l.lower() for sw in ident_stop_words) and not re.search(r'\b\d{1,2}[/-]\d{1,2}[/-]\d{4}\b', next_l):
                            ident_parts.append(next_l)
                        else:
                            break

                if ident_parts:
                    raw_id_val = " ".join(ident_parts).strip()
                    # Chuẩn hóa các lỗi dính chữ OCR đặc thù của đặc điểm nhận dạng
                    clean_id = raw_id_val
                    clean_id = re.sub(r'notruoi|no\s*truoi|not\s*ruoi', 'Nốt ruồi ', clean_id, flags=re.IGNORECASE)
                    clean_id = re.sub(r'daumayphai|dau\s*may\s*phai|daumay\s*phai', 'đầu mày phải ', clean_id, flags=re.IGNORECASE)
                    clean_id = re.sub(r'daumaytrai|dau\s*may\s*trai|daumay\s*trai', 'đầu mày trái ', clean_id, flags=re.IGNORECASE)
                    clean_id = re.sub(r'duoimayphai|duoi\s*may\s*phai|duoimay\s*phai', 'đuôi mày phải ', clean_id, flags=re.IGNORECASE)
                    clean_id = re.sub(r'duoimaytrai|duoi\s*may\s*trai|duoimay\s*trai', 'đuôi mày trái ', clean_id, flags=re.IGNORECASE)
                    clean_id = re.sub(r'duoimatphai|duoi\s*mat\s*phai|duoimat\s*phai', 'dưới mắt phải ', clean_id, flags=re.IGNORECASE)
                    clean_id = re.sub(r'duoimattrai|duoi\s*mat\s*trai|duoimat\s*trai', 'dưới mắt trái ', clean_id, flags=re.IGNORECASE)
                    clean_id = re.sub(r'canhmuiphai|canh\s*mui\s*phai', 'cánh mũi phải ', clean_id, flags=re.IGNORECASE)
                    clean_id = re.sub(r'canhmuitrai|canh\s*mui\s*trai', 'cánh mũi trái ', clean_id, flags=re.IGNORECASE)
                    clean_id = re.sub(r'songmui|song\s*mui', 'sống mũi ', clean_id, flags=re.IGNORECASE)
                    clean_id = re.sub(r'mepphai|mep\s*phai', 'mép phải ', clean_id, flags=re.IGNORECASE)
                    clean_id = re.sub(r'meptrai|mep\s*trai', 'mép trái ', clean_id, flags=re.IGNORECASE)
                    clean_id = re.sub(r'duoitruoc|duoi\s*truoc', 'dưới trước ', clean_id, flags=re.IGNORECASE)
                    clean_id = re.sub(r'duoisau|duoi\s*sau', 'dưới sau ', clean_id, flags=re.IGNORECASE)
                    clean_id = re.sub(r'trentruoc|tren\s*truoc', 'trên trước ', clean_id, flags=re.IGNORECASE)
                    clean_id = re.sub(r'trensau|tren\s*sau', 'trên sau ', clean_id, flags=re.IGNORECASE)
                    clean_id = re.sub(r'daumay|dau\s*may', 'đầu mày ', clean_id, flags=re.IGNORECASE)
                    clean_id = re.sub(r'duoimay|duoi\s*may', 'đuôi mày ', clean_id, flags=re.IGNORECASE)
                    clean_id = re.sub(r'duoimat|duoi\s*mat', 'dưới mắt ', clean_id, flags=re.IGNORECASE)
                    clean_id = re.sub(r'C[.]?35cm|C35cm|C\.3,5cm|C\.3,5\s*cm', 'C.3,5 cm ', clean_id, flags=re.IGNORECASE)
                    clean_id = re.sub(r'C[.]?1cm|C1cm|C\.1cm', 'C.1 cm ', clean_id, flags=re.IGNORECASE)
                    clean_id = re.sub(r'C[.]?2cm|C2cm|C\.2cm', 'C.2 cm ', clean_id, flags=re.IGNORECASE)
                    clean_id = re.sub(r'C[.]?3cm|C3cm|C\.3cm', 'C.3 cm ', clean_id, flags=re.IGNORECASE)
                    clean_id = re.sub(r'C[.]?4cm|C4cm|C\.4cm', 'C.4 cm ', clean_id, flags=re.IGNORECASE)
                    clean_id = re.sub(r'C[.]?5cm|C5cm|C\.5cm', 'C.5 cm ', clean_id, flags=re.IGNORECASE)
                    clean_id = re.sub(r'\b(?:Date|Ngày|Tháng|Năm|Cục|Giám|Bộ)\b.*$', '', clean_id, flags=re.IGNORECASE).strip()
                    clean_id = re.sub(r'\s+', ' ', clean_id).strip()
                    data["personal_identification"] = clean_id if len(clean_id) > 1 else None
                    break
        if data["personal_identification"]:
            break

    # 5. Dân tộc & Tôn giáo (CMND)
    ethnic_pattern = re.compile(r'(?:dân tộc|dan toc|ethnicity)\s*[:.]?\s*([^\n,.;]+)', re.IGNORECASE)
    relig_pattern = re.compile(r'(?:tôn giáo|ton giao|religion)\s*[:.]?\s*([^\n,.;]+)', re.IGNORECASE)

    for line in lines:
        m_eth = ethnic_pattern.search(line)
        if m_eth and not data["ethnicity"]:
            raw_eth = m_eth.group(1).strip()
            clean_eth = re.split(r'(?:tôn giáo|ton giao|religion)', raw_eth, flags=re.IGNORECASE)[0].strip()
            data["ethnicity"] = clean_eth if clean_eth else None

        m_rel = relig_pattern.search(line)
        if m_rel and not data["religion"]:
            raw_rel = m_rel.group(1).strip()
            clean_rel = re.split(r'(?:dân tộc|dan toc|ethnicity)', raw_rel, flags=re.IGNORECASE)[0].strip()
            data["religion"] = clean_rel if clean_rel else None

    # 6. Dải mã MRZ
    mrz_lines = []
    for line in lines:
        cleaned_mrz_line = re.sub(r'\s+', '', line)
        if ("<<" in cleaned_mrz_line or cleaned_mrz_line.startswith("I<") or cleaned_mrz_line.startswith("ID") or cleaned_mrz_line.startswith("IR") or cleaned_mrz_line.startswith("LE<<") or cleaned_mrz_line.startswith("NGUYEN<<") or cleaned_mrz_line.startswith("BU<") or cleaned_mrz_line.startswith("BUI<")) and len(cleaned_mrz_line) >= 15:
            mrz_lines.append(cleaned_mrz_line)

    if len(mrz_lines) >= 2:
        data["mrz"] = "\n".join(mrz_lines)

    # Trích xuất bổ trợ ngày hết hạn từ dải mã MRZ (Dòng 2: YYMMDD[sex]YYMMDD)
    if not data["date_of_expiry"]:
        for line in lines:
            cleaned_l = re.sub(r'\s+', '', line)
            m_mrz_date = re.search(r'(\d{2})(\d{2})(\d{2})\d[MFX](\d{2})(\d{2})(\d{2})\d[A-Z]{3}', cleaned_l)
            if m_mrz_date:
                # Ngày hết hạn: YYMMDD -> DD/MM/20YY
                exp_yy, exp_mm, exp_dd = m_mrz_date.group(4), m_mrz_date.group(5), m_mrz_date.group(6)
                data["date_of_expiry"] = f"{exp_dd}/{exp_mm}/20{exp_yy}"
                break

    return data

def detect_card_side(ocr_text: str, qr_found: bool = False) -> str:
    """
    Xác định mặt thẻ: 'front' (mặt trước), 'back' (mặt sau), hoặc 'both' (cả hai mặt / ảnh ghép).
    """
    if not ocr_text:
        return "front" if qr_found else "unknown"

    text_lower = ocr_text.lower()

    # Từ khóa mặt trước
    front_score = 0
    front_keywords = [
        "cộng hòa", "độc lập", "tự do", "hạnh phúc", "căn cước", "chứng minh nhân dân",
        "họ và tên", "ngày, tháng, năm sinh", "ngày sinh", "giới tính", "quốc tịch",
        "full name", "date of birth", "số định danh cá nhân", "nationality", "identity card"
    ]
    for kw in front_keywords:
        if kw in text_lower:
            front_score += 1

    # Từ khóa mặt sau
    back_score = 0
    back_keywords = [
        "nơi đăng ký khai sinh", "nơi cư trú", "ngày, tháng, năm cấp", "ngày, tháng, năm hết hạn",
        "bộ công an", "ministry of public security", "đặc điểm nhận dạng", "dấu vết riêng",
        "personal identification", "cục trưởng", "cục cảnh sát", "quản lý hành chính",
        "dân tộc", "tôn giáo", "place of birth", "place of residence", "date of issue", "date of expiry"
    ]
    for kw in back_keywords:
        if kw in text_lower:
            back_score += 1

    if front_score >= 2 and back_score >= 2:
        return "both"
    elif front_score > back_score:
        return "front"
    elif back_score > front_score:
        return "back"
    elif front_score > 0:
        return "front"
    elif back_score > 0:
        return "back"
    return "front"

def merge_cccd_results(front_data: Dict[str, Any], back_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Hợp nhất thông tin 2 mặt trước và sau thành 1 đối tượng CCCD hoàn chỉnh.
    """
    merged = dict(front_data) if front_data else {}

    # Bổ sung các trường từ mặt sau
    if back_data:
        # Nơi cấp luôn ưu tiên từ mặt sau
        if back_data.get("place_of_issue"):
            merged["place_of_issue"] = back_data["place_of_issue"]

        for k in ["issue_date", "date_of_expiry", "place_of_origin", "place_of_residence", "personal_identification", "ethnicity", "religion", "mrz"]:
            if back_data.get(k) and (not merged.get(k) or merged.get(k) in ["Ho, chudemvatenkhai sinh/Full name", "Ngay, thang, nam sinh/Dateofbirth."]):
                merged[k] = back_data[k]

        # Nếu quét được QR ở mặt sau
        if back_data.get("qr_data") and back_data["qr_data"].get("scanned"):
            merged["qr_data"] = back_data["qr_data"]
            if back_data.get("full_name"):
                merged["full_name"] = back_data["full_name"]
            if back_data.get("id_number"):
                merged["id_number"] = back_data["id_number"]
            if back_data.get("date_of_birth"):
                merged["date_of_birth"] = back_data["date_of_birth"]
            if back_data.get("gender"):
                merged["gender"] = back_data["gender"]
            if back_data.get("place_of_residence"):
                merged["place_of_residence"] = back_data["place_of_residence"]

        # Nếu mặt trước bị thiếu thông tin mà mặt sau có
        for key in ["id_number", "full_name", "date_of_birth", "gender", "nationality"]:
            if not merged.get(key) and back_data.get(key):
                merged[key] = back_data[key]

        # Xác định card_type chuẩn xác
        front_raw = merged.get("raw_text") or ""
        back_raw = back_data.get("raw_text") or ""
        combined_raw = f"{front_raw}\n{back_raw}".lower()

        if "chứng minh" in combined_raw or "cmnd" in combined_raw:
            merged["card_type"] = "cmnd_9_so" if (merged.get("id_number") and len(merged.get("id_number")) == 9) else "cmnd_12_so"
        elif ("công dân" in combined_raw or "cong dan" in combined_raw or "citizen" in combined_raw) and ("căn cước" in combined_raw or "can cuoc" in combined_raw):
            merged["card_type"] = "cccd_chip"
        elif "căn cước" in combined_raw or "can cuoc" in combined_raw or "personalidentification" in combined_raw or "identity card" in combined_raw:
            merged["card_type"] = "can_cuoc_2024"
        else:
            merged["card_type"] = "cccd_chip"

        # Ghép raw_text
        if back_raw and back_raw not in front_raw:
            merged["raw_text"] = f"{front_raw}\n--- MẶT SAU ---\n{back_raw}".strip()

    merged["card_side"] = "both"
    return merged




