import os
import multiprocessing

# Cấu hình API Key cho Gemini (Ưu tiên lấy từ biến môi trường hoặc file api_key.txt cục bộ để bảo mật)
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "YOUR_API_KEY")

# Tự động nạp API Key từ file api_key.txt cục bộ nếu có
_key_file = os.path.join(os.path.dirname(__file__), "..", "api_key.txt")
if GEMINI_API_KEY == "YOUR_API_KEY" and os.path.exists(_key_file):
    try:
        with open(_key_file, "r", encoding="utf-8") as f:
            GEMINI_API_KEY = f.read().strip()
    except Exception:
        pass

# Đường dẫn URL API của Gemini (cho phép thay đổi endpoint hoặc phiên bản model)
GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-3.5-flash:generateContent"

# Lựa chọn Engine OCR: "rapidocr" hoặc "tesseract"
# - "rapidocr": Khuyên dùng. Chạy cực nhanh trên CPU qua ONNX Runtime, tự động chạy sau khi pip install, không cần cài thêm phần mềm ngoài.
# - "tesseract": Engine truyền thống, yêu cầu cài đặt Tesseract OCR nhị phân trên máy.
OCR_ENGINE = "rapidocr"

# Đường dẫn đến file thực thi tesseract.exe (chỉ dùng nếu chọn OCR_ENGINE = "tesseract")
# Ví dụ trên Windows: r"C:\Program Files\Tesseract-OCR\tesseract.exe"
TESSERACT_CMD = r"tesseract"

# Ngôn ngữ OCR mặc định (vie = Tiếng Việt, eng = Tiếng Anh)
# Có thể kết hợp: "vie+eng"
OCR_LANG = "vie+eng"

# Số lượng tiến trình chạy song song (mặc định lấy số nhân CPU thực tế)
MAX_WORKERS = multiprocessing.cpu_count()

# Độ phân giải (DPI) khi render trang PDF thành hình ảnh để quét OCR
# DPI càng cao thì càng nét nhưng xử lý càng lâu. 150-200 là tối ưu nhất cho cả tốc độ và độ chính xác.
PDF_RENDER_DPI = 150
