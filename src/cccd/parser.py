import re
from typing import Dict, Any, Optional
from datetime import datetime

def parse_cccd_qr_data(qr_text: str) -> Optional[Dict[str, Any]]:
    """
    Phân tích chuỗi dữ liệu thô từ mã QR của CCCD gắn chip Việt Nam.
    Định dạng chuẩn QR CCCD gắn chip (phân tách bởi ký tự '|'):
    [Số CCCD 12 số]|[Số CMND cũ 9 số (nếu có)]|[Họ và tên]|[Ngày sinh ddmmyyyy]|[Giới tính]|[Nơi thường trú]|[Ngày cấp ddmmyyyy]
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
    l = line.lower()
    # Loại trừ các dòng nhãn ngày hết hạn hoặc tiêu đề
    if any(ex in l for k, ex in enumerate(["giá trị đến", "gia tri den", "giattden", "expiry", "expin", "căn cước", "can cuoc", "quốc tịch", "quoc tich", "giới tính", "gioi tinh"])):
        return False

    # Các từ khóa hành chính (dùng word boundary hoặc chuỗi rõ ràng)
    admin_patterns = [
        r'\btỉnh\b', r'\bthành phố\b', r'\btp\b', r'\bquận\b', r'\bhuyện\b', r'\bthị xã\b', r'\btx\b', 
        r'\bxã\b', r'\bphường\b', r'\bthị trấn\b', r'\btt\b', r'\bthôn\b', r'\btổ\s*\d+\b', r'\bấp\b', r'\bbản\b',
        r'nam\s*định', r'lào\s*cai', r'hà\s*nội', r'hải\s*phòng', r'đà\s*nẵng', r'hồ\s*chí\s*minh',
        r'nam\s*dinh', r'lao\s*cai', r'ha\s*noi', r'hai\s*phong', r'da\s*nang', r'ho\s*chi\s*minh',
        r'thái\s*bình', r'thai\s*binh', r'bắc\s*ninh', r'bac\s*ninh', r'thanh\s*hóa', r'thanh\s*hoa'
    ]
    if any(re.search(p, l) for p in admin_patterns):
        return True
        
    # Hoặc có cấu trúc phân tách bằng dấu phẩy
    if ',' in line and len(line.split()) >= 2:
        return True
    return False

def clean_address_line(line: str) -> str:
    """Làm sạch các từ khóa nhãn bị dính vào địa chỉ."""
    cleaned = line
    # Loại bỏ các từ khóa giới tính, quốc tịch, ngày hết hạn
    cleaned = re.sub(r'(?:Giới tính|Gioi tinh|Sex|Quốc tịch|Quoc tich|Nationality|Có giá trị đến|Co gia tri den|Date of expiry).*$', '', cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r'^[,\s.:-]+', '', cleaned)
    return cleaned.strip()

def parse_cccd_text(ocr_text: str) -> Dict[str, Any]:
    """
    Trích xuất các trường thông tin từ văn bản OCR của thẻ Căn cước công dân / CMND.
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
        "card_type": "cccd"
    }

    if not ocr_text:
        return data

    lines = [line.strip() for line in ocr_text.split("\n") if line.strip()]

    # 1. Trích xuất Số CCCD / CMND (12 chữ số cho CCCD, 9 chữ số cho CMND cũ)
    id_pattern = re.compile(r'(?:Số|So|No|SỐ|s6|so/no)\s*[:.]?\s*([0-9]{9,12})', re.IGNORECASE)
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

    # 2. Tìm tất cả các ngày tháng có dạng dd/mm/yyyy trong văn bản
    all_dates = []
    date_regex = re.compile(r'\b(\d{1,2}[/-]\d{1,2}[/-]\d{4})\b')
    for line in lines:
        for d in date_regex.findall(line):
            formatted_date = d.replace('-', '/')
            parts = formatted_date.split('/')
            if len(parts) == 3:
                day, month, year = int(parts[0]), int(parts[1]), int(parts[2])
                if 1 <= day <= 31 and 1 <= month <= 12 and 1900 <= year <= 2100:
                    all_dates.append((formatted_date, year, line))

    # Phân loại Ngày sinh vs Ngày hết hạn theo ngữ cảnh và năm
    dob_pattern = re.compile(r'(?:sinh|birth|ngày sinh|ngay sinh|ngaysinh)\s*[:.]?\s*(\d{1,2}[/-]\d{1,2}[/-]\d{4})', re.IGNORECASE)
    expiry_pattern = re.compile(r'(?:giá trị đến|gia tri den|giattden|expiry|expin|expiny|hết hạn|het han)\s*[:.]?\s*(\d{1,2}[/-]\d{1,2}[/-]\d{4}|Không thời hạn|Khong thoi han)', re.IGNORECASE)

    for line in lines:
        m_dob = dob_pattern.search(line)
        if m_dob and not data["date_of_birth"]:
            data["date_of_birth"] = m_dob.group(1).replace('-', '/')
            
        m_exp = expiry_pattern.search(line)
        if m_exp and not data["date_of_expiry"]:
            val = m_exp.group(1).strip()
            if "không" in val.lower() or "khong" in val.lower():
                data["date_of_expiry"] = "Không thời hạn"
            else:
                data["date_of_expiry"] = val.replace('-', '/')

    # Fallback cho ngày nếu regex trực tiếp bị nhỡ (ví dụ ngày nằm ở dòng riêng)
    current_year = datetime.now().year
    for dt, yr, origin_line in all_dates:
        if yr < current_year - 10:
            if not data["date_of_birth"]:
                data["date_of_birth"] = dt
        elif yr >= current_year:
            if not data["date_of_expiry"]:
                data["date_of_expiry"] = dt

    # 3. Giới tính (Sex/Gender)
    gender_pattern = re.compile(r'(?:Giới tính|Gioi tinh|Sex)\s*[:.]?\s*(Nam|Nữ|Nu|Male|Female)', re.IGNORECASE)
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
            if re.search(r'\bNam\b', line) and not re.search(r'Việt Nam|Viet Nam', line):
                data["gender"] = "Nam"
                break
            elif re.search(r'\bNữ\b|\bNu\b', line):
                data["gender"] = "Nữ"
                break

    # 4. Họ và tên (Full name)
    name_keywords = ["họ và tên", "ho va ten", "full name", "họ tên", "ho ten", "hova ten", "hovaten"]
    excluded_headers = [
        "CỘNG HÒA", "VIỆT NAM", "ĐỘC LẬP", "HẠNH PHÚC", "CĂN CƯỚC", "CÔNG DÂN", 
        "IDENTITY", "CARD", "CONG HOA", "VIET NAM", "DOC LAP", "HANH PHUC", 
        "CAN CUOC", "CONG DAN", "CONGDAN", "SOCIALIST", "REPUBLIC", "CONGHOA"
    ]

    for i, line in enumerate(lines):
        line_lower = line.lower()
        for kw in name_keywords:
            if kw in line_lower:
                if ":" in line or "." in line:
                    candidate = re.split(r'[:.]', line, maxsplit=1)[1].strip()
                    if candidate and not any(k in candidate.lower() for k in ["họ", "tên", "full", "name"]):
                        data["full_name"] = candidate
                        break
                elif i + 1 < len(lines):
                    next_line = lines[i + 1].strip()
                    if (next_line.isupper() or len(next_line.split()) >= 2) and not any(c.isdigit() for c in next_line):
                        if not any(ex in next_line.upper() for ex in excluded_headers):
                            data["full_name"] = next_line
                            break
        if data["full_name"]:
            break

    if not data["full_name"]:
        for line in lines:
            words = line.split()
            if line.isupper() and 2 <= len(words) <= 5 and not any(c.isdigit() for c in line):
                if not any(ex in line for ex in excluded_headers) and not is_address_like(line):
                    data["full_name"] = line
                    break

    # 5. Quê quán (Place of origin) & Nơi thường trú (Place of residence)
    # Ưu tiên tìm trực tiếp theo nhãn Quê quán
    origin_keywords = ["quê quán", "que quan", "quequan", "place of origin", "placeoforigin", "placeofonigin"]
    for i, line in enumerate(lines):
        line_lower = line.lower()
        for kw in origin_keywords:
            if kw in line_lower:
                if ":" in line or "." in line:
                    candidate = re.split(r'[:.]', line, maxsplit=1)[1].strip()
                    if candidate and len(candidate) > 3 and not any(k in candidate.lower() for k in ["quê", "origin", "quán"]):
                        data["place_of_origin"] = candidate
                        break
                elif i + 1 < len(lines):
                    next_l = lines[i + 1].strip()
                    if not any(k in next_l.lower() for k in ["nơi thường trú", "noithuongtru", "place of", "giá trị đến", "co gia"]):
                        data["place_of_origin"] = next_l
                        break
        if data["place_of_origin"]:
            break

    # Thu thập tất cả các địa chỉ tiềm năng
    address_candidates = []
    for line in lines:
        cleaned = clean_address_line(line)
        if cleaned and is_address_like(cleaned):
            if not any(ex in cleaned.upper() for ex in excluded_headers) and cleaned != data["full_name"]:
                if not any(k in cleaned.lower() for k in ["họ và tên", "ngày sinh", "date of", "có giá trị", "co gia"]):
                    address_candidates.append(cleaned)

    # Nếu chưa tìm được qua nhãn thì dùng danh sách địa chỉ
    if not data["place_of_origin"] and address_candidates:
        data["place_of_origin"] = address_candidates[0]
        
    if not data["place_of_residence"] and len(address_candidates) >= 2:
        data["place_of_residence"] = address_candidates[1]

    return data


