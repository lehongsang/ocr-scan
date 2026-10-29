import sys
import io
import json
from PIL import Image, ImageDraw, ImageFont

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

from src.prescription_parser import process_prescription_document

def create_sample_prescription_image() -> bytes:
    """Tạo một ảnh đơn thuốc mẫu để kiểm thử"""
    img = Image.new("RGB", (900, 1150), color=(255, 255, 255))
    draw = ImageDraw.Draw(img)

    text_lines = [
        ("BỆNH VIỆN ĐA KHOA QUỐC TẾ", 40, 30),
        ("KHOA KHÁM BỆNH - PHÒNG KHÁM TAI MŨI HỌNG", 40, 60),
        ("----------------------------------------------------------------", 40, 85),
        ("ĐƠN THUỐC ĐIỀU TRỊ", 320, 120),
        ("Họ và tên bệnh nhân: Nguyễn Văn An - Tuổi: 35 - Giới tính: Nam", 50, 180),
        ("Địa chỉ: Ba Đình, Hà Nội", 50, 215),
        ("Chẩn đoán: Viêm họng cấp, sốt cao, viêm amidan mủ", 50, 250),
        ("----------------------------------------------------------------", 50, 285),
        ("CHỈ ĐỊNH DÙNG THUỐC:", 50, 320),
        ("1. Efferalgan 500mg - 10 viên", 70, 370),
        ("   Đường dùng: Uống. Uống sau ăn no. Uống khi sốt hơn 38*C.", 90, 400),
        ("2. Augmentin 1g x 14 viên", 70, 445),
        ("   Đường dùng: Uống. Uống sau bữa ăn. Sáng 1 viên, tối 1 viên.", 90, 475),
        ("3. Nexium 40mg - 14 viên", 70, 520),
        ("   Đường dùng: Uống. Uống trước ăn 30 phút. Uống 1 viên vào buổi sáng.", 90, 550),
        ("----------------------------------------------------------------", 50, 650),
        ("Lời dặn: Tái khám sau 5 ngày hoặc khi có dấu hiệu bất thường.", 50, 700),
        ("Ngày 21 tháng 10 năm 2026", 550, 780),
        ("Bác sĩ điều trị", 600, 810),
        ("BS. Trần Anh Tuấn", 590, 910),
    ]

    for line, x, y in text_lines:
        draw.text((x, y), line, fill=(0, 0, 0))

    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=95)
    return buf.getvalue()

def run_test():
    print("1. Đang tạo ảnh đơn thuốc mẫu...")
    img_bytes = create_sample_prescription_image()
    
    print("2. Đang gửi ảnh vào hệ thống OCR Đơn thuốc thuần Vision (Gemini Vision)...")
    result = process_prescription_document(
        file_bytes=img_bytes,
        filename="don_thuoc_mau.jpg"
    )

    print("\n========== KẾT QUẢ TRÍCH XUẤT ĐƠN THUỐC THUẦN VISION ==========")
    print(f"Trạng thái: {result.get('status')}")
    print(f"Engine sử dụng: {result.get('engine_used')}")
    print(f"Tổng số thuốc phát hiện: {result.get('total_medications')}")
    print(f"\nDANH SÁCH TÊN THUỐC (drug_names):")
    for name in result.get("drug_names", []):
        print(f"  * {name}")

    print(f"\nTHÔNG TIN ĐƠN THUỐC (prescription_info):")
    info = result.get("prescription_info", {})
    for k, v in info.items():
        print(f"  - {k}: {v}")

    print(f"\nBẢNG DỮ LIỆU THUỐC CHI TIẾT (8 trường chuẩn):")
    header = "STT | Tên thuốc | Tên hoạt chất | Hàm lượng | Đơn vị tính | Số lượng | Đường dùng | Cách dùng | Thời gian dùng"
    print(header)
    print("-" * len(header) * 2)

    for med in result.get("medications", []):
        row = f"{med.get('stt')} | {med.get('ten_thuoc')} | {med.get('ten_hoat_chat')} | {med.get('ham_luong')} | {med.get('don_vi_tinh')} | {med.get('so_luong')} | {med.get('duong_dung')} | {med.get('cach_dung')} | {med.get('thoi_gian_dung')}"
        print(row)

    print("\nJSON OUTPUT:")
    print(json.dumps(result.get("medications"), ensure_ascii=False, indent=2))

if __name__ == "__main__":
    run_test()
