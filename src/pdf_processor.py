import fitz  # PyMuPDF
from PIL import Image
import io
from src.utils import logger

def is_digital_pdf(pdf_path: str) -> bool:
    """
    Kiểm tra xem file PDF có phải là tài liệu số chứa lớp text layer gốc hay không.
    Nếu hầu hết các trang đều chứa text dạng chữ số, ta không cần dùng OCR.
    """
    try:
        doc = fitz.open(pdf_path)
        digital_pages = 0
        total_pages = len(doc)
        
        for page in doc:
            # Lấy text thô từ trang
            text = page.get_text().strip()
            # Nếu trang có chứa văn bản (độ dài > 10 ký tự), coi là trang số
            if len(text) > 10:
                digital_pages += 1
                
        doc.close()
        # Nếu > 80% số trang có text layer, coi như đây là Digital PDF
        return (digital_pages / total_pages) > 0.8 if total_pages > 0 else False
    except Exception as e:
        logger.error(f"Lỗi khi kiểm tra PDF loại nào: {e}")
        return False

def extract_digital_text(pdf_path: str) -> dict:
    """
    Trích xuất text trực tiếp từ Digital PDF (Cực nhanh, dưới 0.1s).
    Trả về dict dạng: {page_num: "nội dung chữ"}
    """
    results = {}
    try:
        doc = fitz.open(pdf_path)
        for page_num in range(len(doc)):
            page = doc[page_num]
            text = page.get_text()
            results[page_num + 1] = text
        doc.close()
    except Exception as e:
        logger.error(f"Lỗi trích xuất chữ trực tiếp: {e}")
    return results

def render_page_to_image(pdf_path: str, page_num: int, dpi: int = 150) -> Image.Image:
    """
    Chuyển đổi một trang PDF thành đối tượng PIL Image mà không lưu ra ổ đĩa.
    page_num: 0-indexed
    """
    doc = fitz.open(pdf_path)
    page = doc[page_num]
    
    # Sử dụng matrix để định nghĩa DPI
    zoom = dpi / 72  # 72 là DPI mặc định của PDF
    mat = fitz.Matrix(zoom, zoom)
    
    pix = page.get_pixmap(matrix=mat, alpha=False)
    
    # Tạo PIL Image trực tiếp từ bytes để đạt tốc độ cao nhất (tránh ghi ổ cứng)
    img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
    
    doc.close()
    return img
