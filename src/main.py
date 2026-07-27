import os
import sys
import argparse
import glob

# Cấu hình encoding utf-8 cho terminal để in tiếng Việt không lỗi
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

# Thêm thư mục gốc vào sys.path để chạy trực tiếp từ bất kỳ đâu
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.pdf_processor import is_digital_pdf, extract_digital_text
from src.ocr_engine import ocr_pdf_parallel
from src.utils import logger, timer
from src.config import TESSERACT_CMD, OCR_LANG, PDF_RENDER_DPI, OCR_ENGINE

def process_pdf(pdf_path: str, output_txt_path: str = None, force_ocr: bool = False, dpi: int = PDF_RENDER_DPI, lang: str = OCR_LANG, engine_type: str = OCR_ENGINE) -> str:
    """
    Hàm xử lý chính điều phối việc trích xuất văn bản từ file PDF/Ảnh:
    1. Kiểm tra loại PDF (Digital hay Scanned).
    2. Trích xuất trực tiếp nếu là Digital PDF (tiết kiệm thời gian, dưới 0.1s).
    3. Chạy OCR song song nếu là Scanned PDF hoặc khi người dùng bắt buộc (force_ocr).
    """
    ext = os.path.splitext(pdf_path.lower())[1]
    
    # Nếu là hình ảnh thông thường
    if ext in [".png", ".jpg", ".jpeg", ".bmp", ".tiff"]:
        from src.ocr_engine import ocr_image_file
        with timer(f"Xử lý file ảnh {os.path.basename(pdf_path)}"):
            final_text = ocr_image_file(pdf_path, lang=lang, tesseract_cmd=tesseract_cmd_val(), engine_type=engine_type)
    else:
        # Nếu là file PDF
        if not os.path.exists(pdf_path):
            logger.error(f"Không tìm thấy file PDF tại: {pdf_path}")
            return ""
            
        results = {}
        with timer(f"Xử lý file PDF {os.path.basename(pdf_path)}"):
            is_digital = False
            if not force_ocr:
                with timer("Kiểm tra định dạng PDF"):
                    is_digital = is_digital_pdf(pdf_path)
                
            if is_digital:
                logger.info("Phát hiện PDF kỹ thuật số (có lớp Text Layer). Bắt đầu trích xuất trực tiếp...")
                with timer("Trích xuất chữ trực tiếp"):
                    results = extract_digital_text(pdf_path)
            else:
                logger.info(f"Phát hiện PDF dạng ảnh (Scanned/Rasterized) hoặc chế độ bắt buộc OCR. Bắt đầu quét OCR song song bằng {engine_type}...")
                with timer(f"Xử lý OCR song song ({engine_type} + Multiprocessing)"):
                    results = ocr_pdf_parallel(pdf_path, dpi=dpi, lang=lang, engine_type=engine_type)
                    
        # Gộp kết quả đầu ra
        output_content = []
        for page_num in sorted(results.keys()):
            output_content.append(f"=== TRANG {page_num} ===\n{results[page_num]}\n")
        final_text = "\n".join(output_content)
    
    # Bước 2: Lưu kết quả ra file nếu được chỉ định
    if output_txt_path and final_text:
        try:
            with open(output_txt_path, "w", encoding="utf-8") as f:
                f.write(final_text)
            logger.info(f"Đã lưu kết quả văn bản thô thành công tại: {output_txt_path}")
            
            # Tự động gọi trích xuất trường thông tin có cấu trúc
            base, _ = os.path.splitext(output_txt_path)
            json_path = f"{base}_fields.json"
            schema_path = os.path.join(os.path.dirname(__file__), "schema.json")
            
            logger.info("Bắt đầu trích xuất trường thông tin bằng Gemini API...")
            from src.config import GEMINI_API_KEY
            if GEMINI_API_KEY and GEMINI_API_KEY != "YOUR_API_KEY":
                from src.parser import parse_medical_fields_gemini
                structured_data = parse_medical_fields_gemini(final_text, schema_path)
            else:
                logger.warning("Chưa cấu hình GEMINI_API_KEY, tự động chuyển sang chế độ phân tích Regex offline...")
                from src.parser import parse_medical_fields
                structured_data = parse_medical_fields(final_text)
                
            # Lưu file JSON kết quả
            import json
            with open(json_path, "w", encoding="utf-8") as f:
                json.dump(structured_data, f, indent=2, ensure_ascii=False)
            logger.info(f"Đã trích xuất và lưu trường dữ liệu thành công tại: {json_path}")
            
        except Exception as e:
            logger.error(f"Không thể hoàn thành lưu kết quả: {e}")
            
    return final_text

def tesseract_cmd_val():
    try:
        from src.config import TESSERACT_CMD
        return TESSERACT_CMD
    except ImportError:
        return "tesseract"

def main():
    parser = argparse.ArgumentParser(description="Hệ thống trích xuất văn bản PDF & OCR siêu tốc (Hỗ trợ hàng loạt).")
    parser.add_argument("paths", type=str, nargs="+", help="Đường dẫn đến (các) file PDF/Ảnh hoặc thư mục chứa các tệp tin.")
    parser.add_argument("-o", "--output-dir", type=str, default=None, help="Thư mục đầu ra để lưu file kết quả. Mặc định là lưu cùng thư mục file gốc.")
    parser.add_argument("-f", "--force-ocr", action="store_true", help="Bắt buộc sử dụng OCR ngay cả khi PDF có lớp text.")
    parser.add_argument("-d", "--dpi", type=int, default=PDF_RENDER_DPI, help=f"DPI để render ảnh PDF (mặc định: {PDF_RENDER_DPI}).")
    parser.add_argument("-l", "--lang", type=str, default=OCR_LANG, help=f"Ngôn ngữ OCR (mặc định: {OCR_LANG}).")
    parser.add_argument("-e", "--engine", type=str, default=OCR_ENGINE, choices=["rapidocr", "tesseract"], help=f"Engine OCR sử dụng (mặc định: {OCR_ENGINE}).")
    
    args = parser.parse_args()
    
    # Thu thập tất cả các file cần xử lý
    files_to_process = []
    for path in args.paths:
        if os.path.isdir(path):
            # Nếu là thư mục, tìm mọi file PDF và ảnh bên trong
            for ext in ["*.pdf", "*.png", "*.jpg", "*.jpeg", "*.bmp", "*.tiff"]:
                files_to_process.extend(glob.glob(os.path.join(path, ext)))
                files_to_process.extend(glob.glob(os.path.join(path, ext.upper())))
        else:
            files_to_process.append(path)
            
    # Loại bỏ file trùng lặp
    files_to_process = sorted(list(set(files_to_process)))
    
    if not files_to_process:
        logger.warning("Không tìm thấy tệp tin PDF hoặc hình ảnh nào hợp lệ để xử lý.")
        return
        
    logger.info(f"Tìm thấy tổng cộng {len(files_to_process)} tệp tin cần xử lý.")
    
    for idx, file_path in enumerate(files_to_process):
        logger.info("-" * 50)
        logger.info(f"[{idx+1}/{len(files_to_process)}] Đang xử lý: {os.path.basename(file_path)}")
        
        # Xác định đường dẫn file text kết quả
        if args.output_dir:
            os.makedirs(args.output_dir, exist_ok=True)
            base_name = os.path.splitext(os.path.basename(file_path))[0]
            output_txt = os.path.join(args.output_dir, f"{base_name}_extracted.txt")
        else:
            base, _ = os.path.splitext(file_path)
            output_txt = f"{base}_extracted.txt"
            
        process_pdf(
            pdf_path=file_path,
            output_txt_path=output_txt,
            force_ocr=args.force_ocr,
            dpi=args.dpi,
            lang=args.lang,
            engine_type=args.engine
        )
        
    logger.info("=" * 50)
    logger.info("Hoàn thành xử lý hàng loạt!")

if __name__ == "__main__":
    main()
