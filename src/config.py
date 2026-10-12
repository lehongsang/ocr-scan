import os
import multiprocessing

# Tự động nạp biến môi trường từ file .env
try:
    from dotenv import load_dotenv
    _env_path = os.path.join(os.path.dirname(__file__), "..", ".env")
    if os.path.exists(_env_path):
        load_dotenv(_env_path)
    else:
        load_dotenv()
except ImportError:
    pass

# Cấu hình API Key cho Gemini (Ưu tiên lấy từ biến môi trường/.env hoặc file api_key.txt cục bộ)
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "YOUR_API_KEY")

# Tự động nạp API Key từ file api_key.txt cục bộ nếu chưa có trong môi trường
_key_file = os.path.join(os.path.dirname(__file__), "..", "api_key.txt")
if (not GEMINI_API_KEY or GEMINI_API_KEY == "YOUR_API_KEY") and os.path.exists(_key_file):
    try:
        with open(_key_file, "r", encoding="utf-8") as f:
            GEMINI_API_KEY = f.read().strip()
    except Exception:
        pass

# Đường dẫn URL API của Gemini (tối ưu tốc độ sinh token: gemini-3.5-flash-lite)
GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-3.5-flash-lite:generateContent"

# Cấu hình tham số sinh tối ưu
GEMINI_TEMPERATURE = 0.0
GEMINI_MAX_OUTPUT_TOKENS = 512

# Lựa chọn Engine OCR: "rapidocr" hoặc "tesseract"
OCR_ENGINE = os.environ.get("OCR_ENGINE", "rapidocr")

# Đường dẫn đến file thực thi tesseract.exe (chỉ dùng nếu chọn OCR_ENGINE = "tesseract")
TESSERACT_CMD = os.environ.get("TESSERACT_CMD", r"tesseract")

# Ngôn ngữ OCR mặc định (vie = Tiếng Việt, eng = Tiếng Anh)
OCR_LANG = os.environ.get("OCR_LANG", "vie+eng")

# Số lượng tiến trình chạy song song (mặc định lấy số nhân CPU thực tế)
MAX_WORKERS = multiprocessing.cpu_count()

# Độ phân giải (DPI) khi render trang PDF thành hình ảnh để quét OCR
try:
    PDF_RENDER_DPI = int(os.environ.get("PDF_RENDER_DPI", 150))
except ValueError:
    PDF_RENDER_DPI = 150

