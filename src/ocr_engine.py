import pytesseract
from PIL import Image
import fitz
import numpy as np
from concurrent.futures import ThreadPoolExecutor  # Thay thế Process bằng ThreadPool để giảm độ trễ khởi tạo tiến trình trên Windows
from src.pdf_processor import render_page_to_image
from src.utils import logger
from src.config import MAX_WORKERS, OCR_LANG, PDF_RENDER_DPI, TESSERACT_CMD, OCR_ENGINE

# Khởi tạo một đối tượng RapidOCR duy nhất cho toàn bộ chương trình (Thread-safe)
_rapid_ocr_engine = None

def get_rapid_ocr_engine():
    global _rapid_ocr_engine
    if _rapid_ocr_engine is None:
        from rapidocr_onnxruntime import RapidOCR
        # Khởi tạo engine dùng chung
        _rapid_ocr_engine = RapidOCR()
    return _rapid_ocr_engine

def ocr_page_worker_thread(pdf_path: str, page_num: int, dpi: int, lang: str, tesseract_cmd: str, engine_type: str) -> str:
    """
    Hàm xử lý OCR cho một trang duy nhất, chạy độc lập trên một luồng (thread).
    """
    try:
        # Render trang PDF trực tiếp trong bộ nhớ
        img = render_page_to_image(pdf_path, page_num, dpi)
        
        if engine_type == "rapidocr":
            engine = get_rapid_ocr_engine()
            img_np = np.array(img)
            result, _ = engine(img_np)
            if result:
                return "\n".join([line[1] for line in result]).strip()
            return ""
            
        else:  # tesseract
            if tesseract_cmd and tesseract_cmd != "tesseract":
                pytesseract.pytesseract.tesseract_cmd = tesseract_cmd
                
            img_gray = img.convert('L')
            custom_config = '--psm 3'
            text = pytesseract.image_to_string(img_gray, lang=lang, config=custom_config)
            return text.strip()
            
    except pytesseract.TesseractNotFoundError:
        return (
            "Không tìm thấy Tesseract OCR. "
            "Vui lòng cài đặt Tesseract OCR và cấu hình đúng đường dẫn trong src/config.py"
        )
    except Exception as e:
        logger.error(f"Lỗi OCR trang {page_num + 1}: {e}")
        return f"[Lỗi Trang {page_num + 1}]: {str(e)}"

def ocr_pdf_parallel(pdf_path: str, dpi: int = PDF_RENDER_DPI, lang: str = OCR_LANG, tesseract_cmd: str = TESSERACT_CMD, engine_type: str = OCR_ENGINE) -> dict:
    """
    Thực hiện OCR song song toàn bộ file PDF bằng ThreadPoolExecutor.
    Cực kỳ thích hợp cho Windows vì không mất chi phí spawn process mới và nạp lại mô hình.
    """
    try:
        doc = fitz.open(pdf_path)
        total_pages = len(doc)
        doc.close()
    except Exception as e:
        logger.error(f"Không thể mở file PDF: {e}")
        return {}
        
    if total_pages == 0:
        return {}
        
    # Tải trước mô hình RapidOCR trên luồng chính để đảm bảo khởi tạo an toàn
    if engine_type == "rapidocr":
        logger.info("Đang nạp mô hình OCR vào bộ nhớ (chỉ tốn thời gian ở lần chạy đầu tiên)...")
        get_rapid_ocr_engine()
        
    logger.info(f"Bắt đầu OCR song song {total_pages} trang bằng {engine_type} với {min(total_pages, MAX_WORKERS)} threads...")
    
    results = {}
    num_workers = min(total_pages, MAX_WORKERS)
    
    # Sử dụng ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=num_workers) as executor:
        futures = []
        for page_num in range(total_pages):
            f = executor.submit(
                ocr_page_worker_thread,
                pdf_path,
                page_num,
                dpi,
                lang,
                tesseract_cmd,
                engine_type
            )
            futures.append((page_num + 1, f))
            
        # Thu thập kết quả
        for page_num_1indexed, f in futures:
            results[page_num_1indexed] = f.result()
            
    return results

def ocr_image_file(image_path: str, lang: str = OCR_LANG, tesseract_cmd: str = TESSERACT_CMD, engine_type: str = OCR_ENGINE) -> str:
    """
    Thực hiện OCR trực tiếp trên một file ảnh (PNG, JPG, v.v.) thay vì file PDF.
    """
    try:
        img = Image.open(image_path)
        if engine_type == "rapidocr":
            engine = get_rapid_ocr_engine()
            img_np = np.array(img)
            result, _ = engine(img_np)
            if result:
                return "\n".join([line[1] for line in result]).strip()
            return ""
        else:
            if tesseract_cmd and tesseract_cmd != "tesseract":
                pytesseract.pytesseract.tesseract_cmd = tesseract_cmd
            img_gray = img.convert('L')
            custom_config = '--psm 3'
            text = pytesseract.image_to_string(img_gray, lang=lang, config=custom_config)
            return text.strip()
    except Exception as e:
        logger.error(f"Lỗi OCR file ảnh {image_path}: {e}")
        return f"[Lỗi OCR File Ảnh]: {str(e)}"
