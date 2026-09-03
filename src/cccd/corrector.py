import re
import difflib
import unicodedata

# 1. Danh sách 63 Tỉnh / Thành phố trực thuộc Trung ương của Việt Nam
PROVINCES_VN = [
    "An Giang", "Bà Rịa - Vũng Tàu", "Bắc Giang", "Bắc Kạn", "Bạc Liêu", "Bắc Ninh",
    "Bến Tre", "Bình Định", "Bình Dương", "Bình Phước", "Bình Thuận", "Cà Mau",
    "Cần Thơ", "Cao Bằng", "Đà Nẵng", "Đắk Lắk", "Đắk Nông", "Điện Biên",
    "Đồng Nai", "Đồng Tháp", "Gia Lai", "Hà Giang", "Hà Nam", "Hà Nội",
    "Hà Tĩnh", "Hải Dương", "Hải Phòng", "Hậu Giang", "Hòa Bình", "Hưng Yên",
    "Khánh Hòa", "Kiên Giang", "Kon Tum", "Lai Châu", "Lâm Đồng", "Lạng Sơn",
    "Lào Cai", "Long An", "Nam Định", "Nghệ An", "Ninh Bình", "Ninh Thuận",
    "Phú Thọ", "Phú Yên", "Quảng Bình", "Quảng Nam", "Quảng Ngãi", "Quảng Ninh",
    "Quảng Trị", "Sóc Trăng", "Sơn La", "Tây Ninh", "Thái Bình", "Thái Nguyên",
    "Thanh Hóa", "Thừa Thiên Huế", "Tiền Giang", "TP Hồ Chí Minh", "Trà Vinh",
    "Tuyên Quang", "Vĩnh Long", "Vĩnh Phúc", "Yên Bái"
]

# Các từ khóa cấp hành chính phổ biến
ADMIN_PREFIXES = {
    "thi tran": "Thị trấn",
    "thị trấn": "Thị trấn",
    "phuong": "Phường",
    "phường": "Phường",
    "xa": "Xã",
    "xã": "Xã",
    "huyen": "Huyện",
    "huyện": "Huyện",
    "quan": "Quận",
    "quận": "Quận",
    "tp": "TP",
    "thanh pho": "Thành phố",
    "thành phố": "Thành phố",
    "thon": "Thôn",
    "thôn": "Thôn",
    "to": "Tổ",
    "tổ": "Tổ"
}

def remove_accents(input_str: str) -> str:
    """Chuyển chuỗi tiếng Việt có dấu về không dấu để so khớp linh hoạt."""
    if not input_str:
        return ""
    nfkd_form = unicodedata.normalize('NFKD', input_str)
    return "".join([c for c in nfkd_form if not unicodedata.combining(c)]).replace('đ', 'd').replace('Đ', 'D')

def find_closest_province(query_segment: str, cutoff: float = 0.70) -> str:
    """
    Sử dụng Fuzzy Matching tìm kiếm tỉnh/thành phố gần nhất với từ OCR được.
    Ví dụ: 'lao cat' -> 'Lào Cai', 'nam dynh' -> 'Nam Định', 'ha noj' -> 'Hà Nội'.
    """
    if not query_segment or len(query_segment.strip()) < 3:
        return query_segment

    query_clean = query_segment.strip()
    query_no_accent = remove_accents(query_clean).lower()

    # 1. So khớp trực tiếp có dấu
    matches = difflib.get_close_matches(query_clean, PROVINCES_VN, n=1, cutoff=cutoff)
    if matches:
        return matches[0]

    # 2. So khớp không dấu (để bắt trường hợp OCR mất sạch dấu hoặc nhầm ký tự)
    best_province = None
    best_ratio = 0.0

    for prov in PROVINCES_VN:
        prov_no_accent = remove_accents(prov).lower()
        # Tính độ tương đồng Levenshtein/Ratcliff-Obershelp
        ratio = difflib.SequenceMatcher(None, query_no_accent, prov_no_accent).ratio()
        
        # Nếu query nằm hoàn toàn trong tên tỉnh hoặc ngược lại
        if query_no_accent in prov_no_accent or prov_no_accent in query_no_accent:
            ratio = max(ratio, 0.85)

        if ratio > best_ratio and ratio >= cutoff:
            best_ratio = ratio
            best_province = prov

    if best_province:
        return best_province

    return query_segment

def correct_vietnamese_ocr_typos(address_text: str) -> str:
    """
    Chuẩn hóa toàn diện địa chỉ tiếng Việt:
    1. Tách chuỗi theo dấu phẩy (,).
    2. Tự động sửa tiền tố hành chính (Thị trấn, Xã, Huyện, Tỉnh...).
    3. Dùng Fuzzy Matching để sửa các tên Tỉnh/Thành bị lỗi ký tự (như 'lao cat' -> 'Lào Cai').
    """
    if not address_text:
        return address_text

    # Xử lý các lỗi ký tự dính nhau hoặc dấu đặc thù
    text = address_text
    text = re.sub(r'\bTrurc\s*Ninh\b|\bTruc\s*Ninh\b|\bTrucNinh\b|\bTrurcNinh\b', 'Trực Ninh', text, flags=re.IGNORECASE)
    text = re.sub(r'\bNam\s*Dinh\b|\bNamDinh\b', 'Nam Định', text, flags=re.IGNORECASE)
    text = re.sub(r'\bTrurc\b|\bTruc\b', 'Trực', text, flags=re.IGNORECASE)
    text = re.sub(r'\bCupong\b|\bCuong\b', 'Cường', text, flags=re.IGNORECASE)
    text = re.sub(r'\bYen\b', 'Yên', text, flags=re.IGNORECASE)
    text = re.sub(r'\bKhanh\b', 'Khánh', text, flags=re.IGNORECASE)
    text = re.sub(r'\bVan\b', 'Văn', text, flags=re.IGNORECASE)
    text = re.sub(r'\bBan\b', 'Bàn', text, flags=re.IGNORECASE)

    parts = [p.strip() for p in text.split(",") if p.strip()]
    corrected_parts = []

    for idx, part in enumerate(parts):
        curr_part = part

        # Chuẩn hóa tiền tố hành chính ở đầu đoạn (Ví dụ: "thi tran Ninh Cuong" -> "Thị trấn Ninh Cường")
        for pfx_key, pfx_val in ADMIN_PREFIXES.items():
            pattern = re.compile(rf'^{pfx_key}\s+', re.IGNORECASE)
            if pattern.match(curr_part):
                curr_part = pattern.sub(f"{pfx_val} ", curr_part)
                break

        # Nếu là đoạn cuối cùng (thường là Tỉnh/Thành phố), chạy Fuzzy Matching
        if idx == len(parts) - 1 or len(parts) == 1:
            matched_province = find_closest_province(curr_part)
            if matched_province != curr_part:
                curr_part = matched_province

        corrected_parts.append(curr_part)

    return ", ".join(corrected_parts)
