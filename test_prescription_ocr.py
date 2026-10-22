import sys
import io
import json
from PIL import Image, ImageDraw, ImageFont

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

from src.prescription_parser import process_prescription_document

def create_sample_prescription_image() -> bytes:
    """Tạo một ảnh đơn thuốc mẫu để kiểm thử"""
    # Kích thước ảnh giống trang A5/A4
    img = Image.new("RGB", (900, 1100), color=(255, 255, 255))
    draw = ImageDraw.Draw(img)

    text_lines = [
        ("BỆNH VIỆN ĐA KHOA QUỐC TẾ", 40, 30),
        ("KHOA KHÁM BỆNH - PHÒNG KHÁM TAI MŨI HỌNG", 40, 60),
        ("----------------------------------------------------------------", 40, 85),
        ("ĐƠN THUỐC ĐIỀU TRỊ", 320, 120),
        ("Họ và tên bệnh nhân: Nguyễn Văn An - Tuổi: 35 - Giới tính: Nam", 50, 180),
        ("Địa chỉ: Ba Đình, Hà Nội", 50, 215),
        ("Chẩn đoán: Viêm họng cấp, sốt nhẹ, viêm mũi dị ứng", 50, 250),
        ("----------------------------------------------------------------", 50, 285),
        ("CHỈ ĐỊNH DÙNG THUỐC:", 50, 320),
        ("1. Augmentin 1g x 14 viên", 70, 370),
        ("   Uống: Sáng 1 viên, tối 1 viên sau ăn", 90, 400),
        ("2. Panadol Extra 500mg - SL: 10 viên", 70, 445),
        ("   Uống: 1 viên khi sốt > 38.5 độ C", 90, 475),
        ("3. Nexium 40mg - Hộp 14 viên", 70, 520),
        ("   Uống: 1 viên vào buổi sáng trước khi ăn 30 phút", 90, 550),
        ("4. Klamentin 1g x 14 viên", 70, 595),
        ("   Uống: Sáng 1 viên, tối 1 viên", 90, 625),
        ("----------------------------------------------------------------", 50, 700),
        ("Lời dặn: Tái khám sau 5 ngày hoặc khi có dấu hiệu bất thường.", 50, 740),
        ("Ngày 21 tháng 10 năm 2026", 550, 800),
        ("Bác sĩ điều trị", 600, 830),
        ("BS. Trần Anh Tuấn", 590, 930),
    ]

    for line, x, y in text_lines:
        draw.text((x, y), line, fill=(0, 0, 0))

    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=95)
    return buf.getvalue()

def run_test():
    print("1. Đang tạo ảnh đơn thuốc mẫu...")
    img_bytes = create_sample_prescription_image()
    
    print("2. Đang gửi ảnh vào hệ thống OCR Đơn thuốc (Gemini Vision + DrugCatalogMatcher)...")
    result = process_prescription_document(
        file_bytes=img_bytes,
        filename="don_thuoc_mau.jpg",
        engine_type="gemini",
        threshold=75.0
    )

    print("\n========== KẾT QUẢ TRÍCH XUẤT ĐƠN THUỐC ==========")
    print(f"Trạng thái: {result.get('status')}")
    print(f"Tổng số thuốc phát hiện: {result.get('total_medications')}")
    print(f"\nDANH SÁCH TÊN THUỐC (drug_names):")
    for name in result.get("drug_names", []):
        print(f"  * {name}")

    print(f"\nTHÔNG TIN ĐƠN THUỐC:")
    info = result.get("prescription_info", {})
    for k, v in info.items():
        print(f"  - {k}: {v}")

    print(f"\nCHI TIẾT TỪNG THUỐC (medications):")
    for med in result.get("medications", []):
        print(f"  [{med.get('stt')}] {med.get('raw_name')}")
        print(f"      -> Tên chuẩn Cục QLD: {med.get('matched_name')} (Confidence: {med.get('confidence')})")
        print(f"      -> Hoạt chất: {med.get('active_ingredient')}")
        print(f"      -> Hàm lượng: {med.get('strength')} | Dạng: {med.get('dosage_form')}")
        print(f"      -> Số lượng: {med.get('quantity')} | Cách dùng: {med.get('usage')}")
        print(f"      -> Kiểu match: {med.get('match_type')}")
        print()

if __name__ == "__main__":
    run_test()
