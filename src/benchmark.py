import os
import sys
import time

# Cấu hình encoding utf-8 cho terminal để in tiếng Việt không lỗi
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

# Thêm thư mục gốc vào sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.ocr_engine import ocr_pdf_parallel, get_rapid_ocr_engine
from src.pdf_processor import is_digital_pdf, extract_digital_text
from src.utils import logger

def run_benchmark(pdf_path: str):
    print("=" * 60)
    print(f"BENCHMARK OCR CHO FILE: {os.path.basename(pdf_path)}")
    print("=" * 60)
    
    if not os.path.exists(pdf_path):
        print(f"Lỗi: Không tìm thấy file tại {pdf_path}")
        return
        
    # Đo thời gian nạp model
    start = time.perf_counter()
    print("1. Đang nạp mô hình RapidOCR (chỉ chạy 1 lần duy nhất khi khởi động)...")
    get_rapid_ocr_engine()
    model_load_time = time.perf_counter() - start
    print(f"   => Thời gian nạp mô hình: {model_load_time:.2f} giây\n")
    
    # Chạy lần 1 (Cold Run - Lần đầu tiên chạy OCR trên luồng)
    print("2. Chạy OCR Lần 1 (Cold Run)...")
    start = time.perf_counter()
    results1 = ocr_pdf_parallel(pdf_path, engine_type="rapidocr")
    cold_ocr_time = time.perf_counter() - start
    print(f"   => Thời gian hoàn thành Lần 1: {cold_ocr_time:.2f} giây (tổng cộng {len(results1)} trang)")
    print(f"   => Tốc độ trung bình: {cold_ocr_time / len(results1) if results1 else 0:.2f} giây/trang\n")
    
    # Chạy lần 2 (Warm Run - Mô hình đã được compile/tải đầy đủ và sẵn sàng)
    print("3. Chạy OCR Lần 2 (Warm Run - Trạng thái hoạt động thực tế)...")
    start = time.perf_counter()
    results2 = ocr_pdf_parallel(pdf_path, engine_type="rapidocr")
    warm_ocr_time = time.perf_counter() - start
    print(f"   => Thời gian hoàn thành Lần 2: {warm_ocr_time:.2f} giây (tổng cộng {len(results2)} trang)")
    print(f"   => Tốc độ trung bình: {warm_ocr_time / len(results2) if results2 else 0:.2f} giây/trang\n")
    
    print("=" * 60)
    print("KẾT LUẬN HIỆU NĂNG:")
    print(f"- Khi chạy như một Service (FastAPI) hoặc giao diện Desktop:")
    print(f"  Thời gian trích xuất file {len(results2)} trang: ~{warm_ocr_time:.2f} giây")
    print(f"  Đạt yêu cầu 6 trang / 3 giây: {'VƯỢT CHỈ TIÊU (ĐẠT)' if warm_ocr_time <= 3.0 or (warm_ocr_time / len(results2) * 6 <= 3.0) else 'CẦN TỐI ƯU THÊM'}")
    print("=" * 60)

if __name__ == "__main__":
    # Sử dụng file demo1.pdf
    pdf_test = r"C:\Users\Admin\Desktop\navi-ocr\local_ai_ocr\demo\demo1.pdf"
    
    # Kiểm tra xem có file nào lớn hơn không
    other_pdf = r"C:\Users\Admin\Desktop\navi-ocr\local_ai_ocr\output\scan_result.pdf"
    if os.path.exists(other_pdf):
        import fitz
        doc = fitz.open(other_pdf)
        pages = len(doc)
        doc.close()
        if pages >= 3:
            pdf_test = other_pdf
            
    run_benchmark(pdf_test)

import os
import sys
import time

# Cấu hình encoding utf-8 cho terminal để in tiếng Việt không lỗi
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

# Thêm thư mục gốc vào sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.ocr_engine import ocr_pdf_parallel, get_rapid_ocr_engine
from src.pdf_processor import is_digital_pdf, extract_digital_text
from src.parser import parse_medical_fields, parse_medical_fields_gemini, extract_diagnostic_text
from src.utils import logger

def run_benchmark(pdf_path: str):
    print("=" * 65)
    print(f"BENCHMARK TỐI ƯU OCR & GEMINI TRÍCH XUẤT: {os.path.basename(pdf_path)}")
    print("=" * 65)
    
    if not os.path.exists(pdf_path):
        print(f"Lỗi: Không tìm thấy file tại {pdf_path}")
        return
        
    # 1. Đo thời gian nạp mô hình RapidOCR (Cold start)
    start = time.perf_counter()
    print("1. Kiểm tra / Nạp mô hình RapidOCR Engine...")
    get_rapid_ocr_engine()
    model_load_time = time.perf_counter() - start
    print(f"   => Thời gian nạp mô hình OCR: {model_load_time:.2f} giây\n")
    
    # 2. Xử lý OCR / Extract Text (t_ocr)
    start_total = time.perf_counter()
    start_ocr = time.perf_counter()
    
    is_digital = is_digital_pdf(pdf_path)
    if is_digital:
        results = extract_digital_text(pdf_path)
    else:
        results = ocr_pdf_parallel(pdf_path, engine_type="rapidocr")
        
    t_ocr = time.perf_counter() - start_ocr
    full_text = "\n".join([f"=== TRANG {k} ===\n{v}" for k, v in sorted(results.items())])
    print(f"2. [THỜI GIAN OCR / TEXT EXTRACTION] (t_ocr): {t_ocr:.4f} giây ({len(results)} trang)")
    
    # 3. Phân tách Regex Offline (t_regex)
    start_regex = time.perf_counter()
    regex_fields = parse_medical_fields(full_text)
    t_regex = time.perf_counter() - start_regex
    print(f"3. [THỜI GIAN REGEX EXTRACTION] (t_regex): {t_regex:.4f} giây")
    
    # 4. Phân loại Gemini API (t_gemini)
    start_gemini = time.perf_counter()
    final_fields = parse_medical_fields_gemini(full_text)
    t_gemini = time.perf_counter() - start_gemini
    print(f"4. [THỜI GIAN CALL GEMINI API] (t_gemini): {t_gemini:.4f} giây")
    
    t_total = time.perf_counter() - start_total
    
    print("\n" + "=" * 65)
    print("BẢNG TỔNG HỢP HIỆU NĂNG TOÀN TRÌNH:")
    print("-" * 65)
    print(f"  * Thời gian OCR quét file:        {t_ocr:.4f}s")
    print(f"  * Thời gian Bóc tách Regex:      {t_regex:.4f}s")
    print(f"  * Thời gian Gemini Phân loại:    {t_gemini:.4f}s")
    print(f"  * TỔNG THỜI GIAN PHẢN HỒI (Total): {t_total:.4f}s")
    print("-" * 65)
    print(f"   Đánh giá: {'ĐẠT CHỈ TIÊU VƯỢT TRỘI (< 3s)' if t_total <= 3.0 else 'CẦN THEO DÕI THÊM'}")
    print("=" * 65)

if __name__ == "__main__":
    # Tìm kiếm file PDF test
    pdf_test = r"C:\Users\Admin\Desktop\navi-ocr\local_ai_ocr\demo\demo1.pdf"
    
    if not os.path.exists(pdf_test):
        other_pdf = r"C:\Users\Admin\Desktop\navi-ocr\local_ai_ocr\output\scan_result.pdf"
        if os.path.exists(other_pdf):
            pdf_test = other_pdf
            
    run_benchmark(pdf_test)
