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

# 2. Danh mục Quận / Huyện / Thị xã / Thành phố trực thuộc tỉnh toàn quốc
DISTRICTS_VN = [
    # Hà Nội
    "Ba Đình", "Hoàn Kiếm", "Tây Hồ", "Long Biên", "Cầu Giấy", "Đống Đa", "Hai Bà Trưng",
    "Hoàng Mai", "Thanh Xuân", "Sóc Sơn", "Đông Anh", "Gia Lâm", "Nam Từ Liêm", "Thanh Trì",
    "Bắc Từ Liêm", "Mê Linh", "Hà Đông", "Sơn Tây", "Ba Vì", "Phúc Thọ", "Đan Phượng",
    "Hoài Đức", "Quốc Oai", "Thạch Thất", "Chương Mỹ", "Thanh Oai", "Thường Tín", "Phú Xuyên",
    "Ứng Hòa", "Mỹ Đức",
    # TP. Hồ Chí Minh
    "Quận 1", "Quận 2", "Quận 3", "Quận 4", "Quận 5", "Quận 6", "Quận 7", "Quận 8", "Quận 9",
    "Quận 10", "Quận 11", "Quận 12", "Bình Tân", "Bình Thạnh", "Gò Vấp", "Phú Nhuận", "Tân Bình",
    "Tân Phú", "Thủ Đức", "Củ Chi", "Hóc Môn", "Bình Chánh", "Nhà Bè", "Cần Giờ",
    # Hải Phòng
    "Hồng Bàng", "Ngô Quyền", "Lê Chân", "Hải An", "Kiến An", "Đồ Sơn", "Dương Kinh",
    "Thủy Nguyên", "An Dương", "An Lão", "Kiến Thụy", "Tiên Lãng", "Vĩnh Bảo", "Cát Hải", "Bạch Long Vĩ",
    # Đà Nẵng
    "Hải Châu", "Thanh Khê", "Sơn Trà", "Ngũ Hành Sơn", "Liên Chiểu", "Cẩm Lệ", "Hòa Vang", "Hoàng Sa",
    # Cần Thơ
    "Ninh Kiều", "Ô Môn", "Bình Thủy", "Cái Răng", "Thốt Nốt", "Vĩnh Thạnh", "Cờ Đỏ", "Phong Điền", "Thới Lai",
    # Bắc Ninh
    "Bắc Ninh", "Từ Sơn", "Yên Phong", "Quế Võ", "Tiên Du", "Thuận Thành", "Gia Bình", "Lương Tài",
    # Bắc Giang
    "Bắc Giang", "Việt Yên", "Hiệp Hòa", "Tân Yên", "Lạng Giang", "Lục Nam", "Lục Ngạn", "Sơn Động", "Yên Dũng", "Yên Thế",
    # Thái Bình
    "Thái Bình", "Quỳnh Phụ", "Hưng Hà", "Đông Hưng", "Thái Thụy", "Tiền Hải", "Kiến Xương", "Vũ Thư",
    # Nam Định
    "Nam Định", "Mỹ Lộc", "Vụ Bản", "Ý Yên", "Nghĩa Hưng", "Nam Trực", "Trực Ninh", "Xuân Trường", "Giao Thủy", "Hải Hậu",
    # Hải Dương
    "Hải Dương", "Chí Linh", "Kinh Môn", "Cẩm Giàng", "Ninh Giang", "Gia Lộc", "Kim Thành", "Nam Sách", "Thanh Hà", "Tứ Kỳ", "Bình Giang", "Thanh Miện",
    # Hưng Yên
    "Hưng Yên", "Mỹ Hào", "Văn Lâm", "Văn Giang", "Yên Mỹ", "Ân Thi", "Khoái Châu", "Kim Động", "Tiên Lữ", "Phù Cừ",
    # Vĩnh Phúc
    "Vĩnh Yên", "Phúc Yên", "Bình Xuyên", "Lập Thạch", "Sông Lô", "Tam Dương", "Tam Đảo", "Vĩnh Tường", "Yên Lạc",
    # Phú Thọ
    "Việt Trì", "Phú Thọ", "Đoan Hùng", "Hạ Hòa", "Thanh Ba", "Phù Ninh", "Lâm Thao", "Tam Nông", "Cẩm Khê", "Thanh Sơn", "Thanh Thủy", "Tân Sơn", "Yên Lập",
    # Quảng Ninh
    "Hạ Long", "Cẩm Phả", "Móng Cái", "Uông Bí", "Quảng Yên", "Đông Triều", "Vân Đồn", "Tiên Yên", "Ba Chẽ", "Bình Liêu", "Cô Tô", "Đầm Hà", "Hải Hà",
    # Lào Cai
    "Lào Cai", "Sa Pa", "Bát Xát", "Bảo Thắng", "Bảo Yên", "Bắc Hà", "Mường Khương", "Si Ma Cai", "Văn Bàn",
    # Yên Bái
    "Yên Bái", "Nghĩa Lộ", "Lục Yên", "Mù Cang Chải", "Trạm Tấu", "Trấn Yên", "Văn Chấn", "Văn Yên", "Yên Bình",
    # Hà Nam
    "Phủ Lý", "Duy Tiên", "Kim Bảng", "Thanh Liêm", "Bình Lục", "Lý Nhân",
    # Ninh Bình
    "Ninh Bình", "Tam Điệp", "Nho Quan", "Gia Viễn", "Hoa Lư", "Yên Khánh", "Kim Sơn", "Yên Mô",
    # Thanh Hóa
    "Thanh Hóa", "Sầm Sơn", "Bỉm Sơn", "Nghi Sơn", "Bá Thước", "Cẩm Thủy", "Đông Sơn", "Hà Trung", "Hậu Lộc", "Hoằng Hóa", "Lang Chánh", "Mường Lát", "Nga Sơn", "Ngọc Lặc", "Như Thanh", "Như Xuân", "Nông Cống", "Quan Hóa", "Quan Sơn", "Quảng Xương", "Thạch Thành", "Thiệu Hóa", "Thọ Xuân", "Thường Xuân", "Triệu Sơn", "Vĩnh Lộc", "Yên Định",
    # Nghệ An
    "Vinh", "Cửa Lò", "Thái Hòa", "Hoàng Mai", "Anh Sơn", "Con Cuông", "Diễn Châu", "Đô Lương", "Hưng Nguyên", "Kỳ Sơn", "Nam Đàn", "Nghi Lộc", "Nghĩa Đàn", "Quế Phong", "Quỳ Châu", "Quỳ Hợp", "Quỳnh Lưu", "Tân Kỳ", "Thanh Chương", "Tương Dương", "Yên Thành",
    # Hà Tĩnh
    "Hà Tĩnh", "Hồng Lĩnh", "Kỳ Anh", "Cẩm Xuyên", "Can Lộc", "Đức Thọ", "Hương Khê", "Hương Sơn", "Lộc Hà", "Nghi Xuân", "Thạch Hà", "Vũ Quang",
    # Quảng Bình
    "Đồng Hới", "Ba Đồn", "Bố Trạch", "Lệ Thủy", "Minh Hóa", "Quảng Ninh", "Quảng Trạch", "Tuyên Hóa",
    # Quảng Trị
    "Đông Hà", "Quảng Trị", "Cam Lộ", "Cồn Cỏ", "Đa Krông", "Gio Linh", "Hướng Hóa", "Hải Lăng", "Triệu Phong", "Vĩnh Linh",
    # Thừa Thiên Huế
    "Huế", "Hương Thủy", "Hương Trà", "A Lưới", "Nam Đông", "Phong Điền", "Phú Lộc", "Phú Vang", "Quảng Điền",
    # Quảng Nam
    "Tam Kỳ", "Hội An", "Điện Bàn", "Bắc Trà My", "Nam Trà My", "Đại Lộc", "Đông Giang", "Duy Xuyên", "Hiệp Đức", "Nam Giang", "Nông Sơn", "Núi Thành", "Phú Ninh", "Phước Sơn", "Quế Sơn", "Tây Giang", "Thăng Bình", "Tiên Phước",
    # Quảng Ngãi
    "Quảng Ngãi", "Ba Tơ", "Bình Sơn", "Đức Phổ", "Lý Sơn", "Minh Long", "Mộ Đức", "Nghĩa Hành", "Sơn Hà", "Sơn Tây", "Sơn Tịnh", "Trà Bồng", "Tư Nghĩa",
    # Bình Định
    "Quy Nhơn", "An Nhơn", "Hoài Nhơn", "An Lão", "Hoài Ân", "Phù Cát", "Phù Mỹ", "Tuy Phước", "Tây Sơn", "Vân Canh", "Vĩnh Thạnh",
    # Phú Yên
    "Tuy Hòa", "Sông Cầu", "Đông Hòa", "Đồng Xuân", "Phú Hòa", "Sơn Hòa", "Sông Hinh", "Tây Hòa", "Tuy An",
    # Khánh Hòa
    "Nha Trang", "Cam Ranh", "Ninh Hòa", "Vạn Ninh", "Diên Khánh", "Cam Lâm", "Khánh Vĩnh", "Khánh Sơn", "Trường Sa",
    # Ninh Thuận
    "Phan Rang - Tháp Chàm", "Bác Ái", "Ninh Hải", "Ninh Phước", "Ninh Sơn", "Thuận Bắc", "Thuận Nam",
    # Bình Thuận
    "Phan Thiết", "La Gi", "Bắc Bình", "Đức Linh", "Hàm Tân", "Hàm Thuận Bắc", "Hàm Thuận Nam", "Phú Quý", "Tánh Linh", "Tuy Phong",
    # Kon Tum
    "Kon Tum", "Đắk Glei", "Đắk Hà", "Đắk Tô", "Ia H'Drai", "Kon Plông", "Kon Rẫy", "Ngọc Hồi", "Sa Thầy", "Tu Mơ Rông",
    # Gia Lai
    "Pleiku", "An Khê", "Ayun Pa", "Chư Păh", "Chư Prông", "Chư Pưh", "Chư Sê", "Đắk Đoa", "Đắk Pơ", "Đức Cơ", "Ia Grai", "Ia Pa", "K'Bang", "Kông Chro", "Krông Pa", "Phú Thiện", "Mang Yang",
    # Đắk Lắk
    "Buôn Ma Thuột", "Buôn Hồ", "Buôn Đôn", "Cư Kuin", "Cư M'gar", "Ea H'leo", "Ea Kar", "Ea Súp", "Krông Ana", "Krông Bông", "Krông Búk", "Krông Năng", "Krông Pắc", "Lắk", "M'Đrắk",
    # Đắk Nông
    "Gia Nghĩa", "Cư Jút", "Đắk Glong", "Đắk Mil", "Đắk R'lấp", "Đắk Song", "Krông Nô", "Tuy Đức",
    # Lâm Đồng
    "Đà Lạt", "Bảo Lộc", "Bảo Lâm", "Cát Tiên", "Di Linh", "Đạ Huoai", "Đạ Tẻh", "Đam Rông", "Đơn Dương", "Đức Trọng", "Lạc Dương", "Lâm Hà",
    # Bình Phước
    "Đồng Xoài", "Bình Long", "Phước Long", "Bù Đăng", "Bù Đốp", "Bù Gia Mập", "Chơn Thành", "Đồng Phú", "Hớn Quản", "Lộc Ninh", "Phú Riềng",
    # Tây Ninh
    "Tây Ninh", "Hòa Thành", "Trảng Bàng", "Bến Cầu", "Châu Thành", "Dương Minh Châu", "Gò Dầu", "Tân Biên", "Tân Châu",
    # Bình Dương
    "Thủ Dầu Một", "Bến Cát", "Dĩ An", "Tân Uyên", "Thuận An", "Bắc Tân Uyên", "Bàu Bàng", "Dầu Tiếng", "Phú Giáo",
    # Đồng Nai
    "Biên Hòa", "Long Khánh", "Cẩm Mỹ", "Định Quán", "Long Thành", "Nhơn Trạch", "Tân Phú", "Thống Nhất", "Trảng Bom", "Vĩnh Cửu", "Xuân Lộc",
    # Bà Rịa - Vũng Tàu
    "Vũng Tàu", "Bà Rịa", "Phú Mỹ", "Châu Đức", "Côn Đảo", "Đất Đỏ", "Long Điền", "Xuyên Mộc",
    # Long An
    "Tân An", "Kiến Tường", "Bến Lức", "Cần Đước", "Cần Giuộc", "Châu Thành", "Đức Hòa", "Đức Huệ", "Mộc Hóa", "Tân Hưng", "Tân Thạnh", "Tân Trụ", "Thạnh Hóa", "Thủ Thừa", "Vĩnh Hưng",
    # Tiền Giang
    "Mỹ Tho", "Cai Lậy", "Gò Công", "Cái Bè", "Châu Thành", "Chợ Gạo", "Gò Công Đông", "Gò Công Tây", "Tân Phú Đông", "Tân Phước",
    # Bến Tre
    "Bến Tre", "Ba Tri", "Bình Đại", "Châu Thành", "Chợ Lách", "Giồng Trôm", "Mỏ Cày Bắc", "Mỏ Cày Nam", "Thạnh Phú",
    # Trà Vinh
    "Trà Vinh", "Duyên Hải", "Càng Long", "Cầu Kè", "Cầu Ngang", "Châu Thành", "Tiểu Cần", "Trà Cú",
    # Vĩnh Long
    "Vĩnh Long", "Bình Minh", "Bình Tân", "Long Hồ", "Mang Thít", "Tam Bình", "Trà Ôn", "Vũng Liêm",
    # Đồng Tháp
    "Cao Lãnh", "Sa Đéc", "Hồng Ngự", "Châu Thành", "Lai Vung", "Lấp Vò", "Tam Nông", "Tân Hồng", "Thanh Bình", "Tháp Mười",
    # An Giang
    "Long Xuyên", "Châu Đốc", "Tân Châu", "An Phú", "Châu Phú", "Châu Thành", "Chợ Mới", "Phú Tân", "Thoại Sơn", "Tịnh Biên", "Tri Tôn",
    # Kiên Giang
    "Rạch Giá", "Hà Tiên", "Phú Quốc", "An Biên", "An Minh", "Châu Thành", "Giang Thành", "Giồng Riềng", "Gò Quao", "Hòn Đất", "Kiên Hải", "Kiên Lương", "Tân Hiệp", "U Minh Thượng", "Vĩnh Thuận",
    # Hậu Giang
    "Vị Thanh", "Ngã Bảy", "Long Mỹ", "Châu Thành", "Châu Thành A", "Phụng Hiệp", "Vị Thủy",
    # Sóc Trăng
    "Sóc Trăng", "Ngã Năm", "Vĩnh Châu", "Châu Thành", "Cù Lao Dung", "Kế Sách", "Long Phú", "Mỹ Tú", "Mỹ Xuyên", "Thạnh Trị", "Trần Đề",
    # Bạc Liêu
    "Bạc Liêu", "Giá Rai", "Đông Hải", "Hòa Bình", "Hồng Dân", "Phước Long", "Vĩnh Lợi",
    # Cà Mau
    "Cà Mau", "Cái Nước", "Đầm Dơi", "Năm Căn", "Ngọc Hiển", "Phú Tân", "Thới Bình", "Trần Văn Thời", "U Minh"
]

# 3. Danh mục các Xã / Phường / Thị trấn / Địa danh phổ biến
COMMUNES_AND_WARDS_VN = [
    # Phường/Xã Hà Nội
    "Vĩnh Tuy", "Bạch Mai", "Bách Khoa", "Đồng Tâm", "Minh Khai", "Thanh Nhàn", "Cầu Dền", "Phố Huế",
    "Hàng Bài", "Hàng Bạc", "Tràng Tiền", "Cửa Nam", "Lý Thái Tổ", "Phan Chu Trinh", "Hàng Gai", "Hàng Đào",
    "Dịch Vọng", "Dịch Vọng Hậu", "Mai Dịch", "Nghĩa Tân", "Nghĩa Đô", "Quan Hoa", "Trung Hòa", "Yên Hòa",
    "Cát Linh", "Văn Miếu", "Quốc Tử Giám", "Hàng Bột", "Nam Đồng", "Trung Tự", "Kim Liên", "Phương Mai",
    "Khương Trung", "Khương Mai", "Khương Đình", "Nhân Chính", "Thanh Xuân Bắc", "Thanh Xuân Nam",
    # Hải Phòng
    "Đằng Lâm", "Thư Trung", "Cát Bi", "Đông Khê", "Lạc Viên", "Vạn Mỹ", "Lương Khánh Thiện",
    # Bắc Ninh
    "Quế Tân", "Bằng An", "Bồng Lai", "Cách Bi", "Chi Lăng", "Đức Long", "Hán Quảng", "Mộ Đạo",
    "Ngọc Xá", "Nhân Hòa", "Phù Chẩn", "Phù Lãng", "Phương Liễu", "Phượng Mao", "Việt Hùng", "Yên Giả",
    # Nam Định
    "Ninh Cường", "Liêm Hải", "Trực Chính", "Trực Hưng", "Trực Khang", "Trực Mỹ", "Trực Nội", "Trực Thanh", "Trực Thuận", "Trực Tuấn",
    # Thái Bình
    "An Ninh", "Đông Minh", "Đông Hoàng", "Đông Á", "Đông Tân", "Nam Trung", "Nam Chính", "Nam Thịnh", "Tây Giang", "Vũ Lăng",
    # TP. Hồ Chí Minh
    "Bến Nghé", "Bến Thành", "Cầu Kho", "Cầu Ông Lãnh", "Cô Giang", "Đa Kao", "Nguyễn Cư Trinh", "Nguyễn Thái Bình", "Phạm Ngũ Lão", "Tân Định",
    "An Phú", "Thảo Điền", "Hiệp Phú", "Linh Trung", "Linh Chiểu", "Linh Tây", "Tam Phú", "Bình Thọ",
    # Tây Nguyên & Miền núi
    "Ea Kao", "Tân Lợi", "Tân An", "Thắng Lợi", "Tự An", "Tân Lập", "Khánh Xuân",
    # Tên đường phố / danh nhân phổ biến
    "Nguyễn Huệ", "Lê Lợi", "Trần Hưng Đạo", "Phan Chu Trinh", "Phan Đình Phùng", "Nguyễn Trãi",
    "Quang Trung", "Điện Biên Phủ", "Trường Chinh", "Giải Phóng", "Võ Văn Kiệt", "Võ Nguyên Giáp",
    "Phạm Văn Đồng", "Hoàng Hoa Thám", "Lý Thường Kiệt", "Bà Triệu", "Lê Duẩn", "Nguyễn Thị Minh Khai",
    "Cách Mạng Tháng 8", "Nam Kỳ Khởi Nghĩa", "Pasteur", "Võ Thị Sáu", "Nguyễn Đình Chiểu", "Hoàng Diệu"
]

def remove_accents(input_str: str) -> str:
    """Chuyển chuỗi tiếng Việt có dấu về không dấu để so khớp linh hoạt."""
    if not input_str:
        return ""
    nfkd_form = unicodedata.normalize('NFKD', input_str)
    return "".join([c for c in nfkd_form if not unicodedata.combining(c)]).replace('đ', 'd').replace('Đ', 'D')

# Xây dựng từ điển tra cứu tự động không dấu -> có dấu
ADMIN_MAP = {}
for item in PROVINCES_VN + DISTRICTS_VN + COMMUNES_AND_WARDS_VN:
    cleaned = item.strip()
    key = remove_accents(cleaned).lower()
    ADMIN_MAP[key] = cleaned

# Danh sách regex các tiền tố hành chính chuẩn hóa
PREFIX_PATTERNS = [
    (re.compile(r'\b(?:To\s*Dan\s*Pho\s*So|Todanphoso|To\s*dan\s*pho\s*so)\b', re.IGNORECASE), 'Tổ Dân Phố Số'),
    (re.compile(r'\b(?:To\s*Dan\s*Pho|Todanpho|To\s*dan\s*pho)\b', re.IGNORECASE), 'Tổ Dân Phố'),
    (re.compile(r'\b(?:Khu\s*Pho|Khupho|Khu\s*pho)\b', re.IGNORECASE), 'Khu Phố'),
    (re.compile(r'\b(?:Thi\s*Tran|Thitran|Thi\s*tran)\b', re.IGNORECASE), 'Thị trấn'),
    (re.compile(r'\b(?:Thi\s*Xa|Thixa|Thi\s*xa)\b', re.IGNORECASE), 'Thị xã'),
    (re.compile(r'\b(?:Thanh\s*Pho|Thanhpho|Thanh\s*pho)\b', re.IGNORECASE), 'Thành phố'),
    (re.compile(r'\b(?:Phuong|Phuong)\b', re.IGNORECASE), 'Phường'),
    (re.compile(r'\b(?:Huyen|Huyen)\b', re.IGNORECASE), 'Huyện'),
    (re.compile(r'\b(?:Quan|Quan)\b', re.IGNORECASE), 'Quận'),
    (re.compile(r'\b(?:Tinh|Tinh)\b', re.IGNORECASE), 'Tỉnh'),
    (re.compile(r'\b(?:Thon|Thon)\b', re.IGNORECASE), 'Thôn'),
    (re.compile(r'\b(?:Xom|Xom)\b', re.IGNORECASE), 'Xóm'),
    (re.compile(r'\b(?:Cum|Cum)\b', re.IGNORECASE), 'Cụm'),
    (re.compile(r'\b(?:Ap|Ap)\b', re.IGNORECASE), 'Ấp'),
    (re.compile(r'\b(?:Ban|Ban)\b', re.IGNORECASE), 'Bản'),
    (re.compile(r'\b(?:Duong|Duong)\b', re.IGNORECASE), 'Đường'),
    (re.compile(r'\b(?:Pho|Pho)\b', re.IGNORECASE), 'Phố'),
    (re.compile(r'\b(?:Ngo|Ngo)\b', re.IGNORECASE), 'Ngõ'),
    (re.compile(r'\b(?:Ngach|Ngach)\b', re.IGNORECASE), 'Ngách'),
    (re.compile(r'\b(?:Hem|Hem)\b', re.IGNORECASE), 'Hẻm'),
    (re.compile(r'\b(?:So|So)\b', re.IGNORECASE), 'Số'),
    (re.compile(r'\b(?:To|To)\b', re.IGNORECASE), 'Tổ'),
    (re.compile(r'\b(?:Xa|Xa)\b', re.IGNORECASE), 'Xã'),
]

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

    # 2. So khớp không dấu
    best_province = None
    best_ratio = 0.0

    for prov in PROVINCES_VN:
        prov_no_accent = remove_accents(prov).lower()
        ratio = difflib.SequenceMatcher(None, query_no_accent, prov_no_accent).ratio()
        
        if query_no_accent in prov_no_accent or prov_no_accent in query_no_accent:
            ratio = max(ratio, 0.85)

        if ratio > best_ratio and ratio >= cutoff:
            best_ratio = ratio
            best_province = prov

    if best_province:
        return best_province

    return query_segment

def correct_segment(segment: str) -> str:
    """Chuẩn hóa một phân đoạn địa chỉ (ví dụ: 'Que Tan' hoặc 'To 24' hoặc 'Hai Ba Trung')."""
    seg = segment.strip()
    if not seg:
        return seg

    # 1. Chuẩn hóa PascalCase dính chữ: QueVo -> Que Vo, HaiBaTrung -> Hai Ba Trung
    seg = re.sub(r'([a-z])([A-Z])', r'\1 \2', seg)
    seg = re.sub(r'([A-Za-z])(\d)', r'\1 \2', seg)

    # 2. Chuẩn hóa các tiền tố hành chính (Tổ, Thôn, Xã, Phường...)
    for pat, rep in PREFIX_PATTERNS:
        seg = pat.sub(rep, seg)

    # 3. Kiểm tra xem toàn bộ segment (sau khi bỏ tiền tố nếu có) có khớp trong ADMIN_MAP không
    clean_seg = seg
    prefix_matched = ""
    for pfx in ["Tổ Dân Phố Số", "Tổ Dân Phố", "Khu Phố", "Thị trấn", "Thị xã", "Thành phố", "Phường", "Huyện", "Quận", "Tỉnh", "Thôn", "Xóm", "Cụm", "Ấp", "Bản", "Đường", "Phố", "Ngõ", "Ngách", "Hẻm", "Số", "Tổ", "Xã", "TP"]:
        if clean_seg.lower().startswith(pfx.lower() + " "):
            prefix_matched = clean_seg[:len(pfx) + 1]
            clean_seg = clean_seg[len(pfx) + 1:].strip()
            break

    no_accent_key = remove_accents(clean_seg).lower()
    if no_accent_key in ADMIN_MAP:
        return f"{prefix_matched}{ADMIN_MAP[no_accent_key]}".strip()

    # Tra cứu n-gram trượt từ 4 từ xuống 2 từ để bắt cụm địa danh lồng bên trong
    words = seg.split()
    n = len(words)
    i = 0
    new_words = []
    while i < n:
        matched = False
        for window in range(min(4, n - i), 1, -1):
            phrase = " ".join(words[i:i+window])
            phrase_key = remove_accents(phrase).lower()
            if phrase_key in ADMIN_MAP:
                new_words.append(ADMIN_MAP[phrase_key])
                i += window
                matched = True
                break
        if not matched:
            word_key = remove_accents(words[i]).lower()
            if len(word_key) >= 3 and word_key in ADMIN_MAP and len(ADMIN_MAP[word_key].split()) == 1:
                new_words.append(ADMIN_MAP[word_key])
            else:
                new_words.append(words[i])
            i += 1

    res = " ".join(new_words)

    # 4. Fuzzy match cấp tỉnh/thành nếu là đoạn cuối hoặc đoạn độc lập
    no_accent_res = remove_accents(res).lower()
    best_prov = None
    best_ratio = 0.0
    for prov in PROVINCES_VN:
        prov_no = remove_accents(prov).lower()
        if no_accent_res == prov_no:
            return prov
        ratio = difflib.SequenceMatcher(None, no_accent_res, prov_no).ratio()
        if ratio > best_ratio and ratio >= 0.75:
            best_ratio = ratio
            best_prov = prov
    if best_prov:
        return best_prov

    return res

def correct_vietnamese_ocr_typos(address_text: str) -> str:
    """
    Chuẩn hóa toàn diện địa chỉ tiếng Việt:
    1. Tách chuỗi theo dấu phẩy (,).
    2. Tự động chuẩn hóa tiền tố hành chính (Tổ dân phố, Thôn, Xã, Phường, Thị trấn, Huyện, Quận, Tỉnh...).
    3. Tra cứu tự động toàn bộ 63 Tỉnh/TP, 700+ Quận/Huyện/Thị xã và các Phường/Xã trên cả nước.
    4. Fuzzy matching tự động bù dấu và sửa lỗi sai lệch ký tự do OCR.
    """
    if not address_text:
        return address_text

    parts = [p.strip() for p in address_text.split(",") if p.strip()]
    corrected = [correct_segment(p) for p in parts]
    return ", ".join(corrected)

# Danh sách chuẩn các cơ quan cấp CCCD / CMND phổ biến
KNOWN_AUTHORITIES = [
    "CỤC TRƯỞNG CỤC CẢNH SÁT QUẢN LÝ HÀNH CHÍNH VỀ TRẬT TỰ XÃ HỘI",
    "CỤC TRƯỞNG CỤC CẢNH SÁT ĐKQL CƯ TRÚ VÀ DLQG VỀ DÂN CƯ",
    "CỤC CẢNH SÁT QUẢN LÝ HÀNH CHÍNH VỀ TRẬT TỰ XÃ HỘI",
    "CỤC CẢNH SÁT ĐKQL CƯ TRÚ VÀ DLQG VỀ DÂN CƯ",
    "BỘ CÔNG AN"
]

def correct_place_of_issue(raw_issue_place: str) -> str:
    """
    Chuẩn hóa và sửa lỗi OCR cho nơi cấp / cơ quan cấp CCCD/CMND.
    """
    if not raw_issue_place:
        return raw_issue_place

    cleaned = raw_issue_place.strip()
    no_accent = remove_accents(cleaned).lower()

    # 1. Nhận diện các cụm từ Cục Cảnh sát QLHC về TTXH (CCCD Chip)
    if any(k in no_accent for k in [
        "quan ly hanh chinh", "quanlyhanhchinh", "trat tu xa hoi", "trattuxahoi", 
        "qlhc", "ttxh", "cuc truong cuc canh sat", "cuctruong cuc canh sat", "cuctruongcuccanhsat",
        "cuc canh sat", "cuccanhsat", "police department", "administrative management"
    ]):
        if "cuc truong" in no_accent or "cuctruong" in no_accent or "director" in no_accent or "canh sat" in no_accent:
            return "CỤC TRƯỞNG CỤC CẢNH SÁT QUẢN LÝ HÀNH CHÍNH VỀ TRẬT TỰ XÃ HỘI"
        return "CỤC CẢNH SÁT QUẢN LÝ HÀNH CHÍNH VỀ TRẬT TỰ XÃ HỘI"

    # 2. Nhận diện Cục CS ĐKQL Cư trú và DLQG về dân cư (CCCD mã vạch)
    if "cu tru" in no_accent or "dan cu" in no_accent or "dlqg" in no_accent or "dkql" in no_accent:
        if "cuc truong" in no_accent:
            return "CỤC TRƯỞNG CỤC CẢNH SÁT ĐKQL CƯ TRÚ VÀ DLQG VỀ DÂN CƯ"
        return "CỤC CẢNH SÁT ĐKQL CƯ TRÚ VÀ DLQG VỀ DÂN CƯ"

    # 3. Nhận diện Bộ Công An (Thẻ Căn cước mới 2024 & CCCD)
    if "bo cong an" in no_accent or "bocongan" in no_accent or "public security" in no_accent or "publicsecurity" in no_accent:
        return "BỘ CÔNG AN"

    # 4. Nhận diện Công an Tỉnh / TP hoặc Giám đốc Công an Tỉnh / TP
    if "cong an" in no_accent or "giam doc" in no_accent:
        for prov in PROVINCES_VN:
            prov_no_accent = remove_accents(prov).lower()
            if prov_no_accent in no_accent:
                if "giam doc" in no_accent:
                    if "tp" in prov.lower() or "thành phố" in prov.lower() or prov in ["Hà Nội", "Hải Phòng", "Đà Nẵng", "Cần Thơ", "TP Hồ Chí Minh"]:
                        return f"GIÁM ĐỐC CÔNG AN THÀNH PHỐ {prov.upper()}"
                    return f"GIÁM ĐỐC CÔNG AN TỈNH {prov.upper()}"
                else:
                    if "tp" in prov.lower() or "thành phố" in prov.lower() or prov in ["Hà Nội", "Hải Phòng", "Đà Nẵng", "Cần Thơ", "TP Hồ Chí Minh"]:
                        return f"CÔNG AN THÀNH PHỐ {prov.upper()}"
                    return f"CÔNG AN TỈNH {prov.upper()}"

    # Fuzzy match với KNOWN_AUTHORITIES
    for auth in KNOWN_AUTHORITIES:
        auth_no_accent = remove_accents(auth).lower()
        if difflib.SequenceMatcher(None, no_accent, auth_no_accent).ratio() >= 0.70:
            return auth

    return cleaned
