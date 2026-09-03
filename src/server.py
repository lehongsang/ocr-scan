import os
import sys
import shutil
import tempfile
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

# Thêm thư mục gốc của dự án vào sys.path để import từ src
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.main import process_pdf
from src.config import PDF_RENDER_DPI, OCR_LANG, OCR_ENGINE
from src.cccd import process_cccd_image

app = FastAPI(
    title="OCR & Document Intelligence API",
    description="Hệ thống API OCR đa năng: Trích xuất Bệnh án y tế (PDF) & Căn cước công dân (CCCD).",
    version="2.0.0"
)

# Cho phép CORS để các client khác gọi được
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ==========================================
# 1. API OCR BỆNH ÁN / PDF TÀI LIỆU
# ==========================================
@app.post("/ocr/pdf", summary="OCR & Trích xuất Bệnh án từ PDF")
@app.post("/ocr", summary="[Legacy] Alias cho OCR PDF Bệnh án", include_in_schema=False)
async def perform_ocr_pdf(
    file: UploadFile = File(..., description="Tệp tin PDF hoặc ảnh bệnh án"),
    force_ocr: bool = Form(False, description="Bắt buộc chạy OCR ngay cả khi PDF có text"),
    dpi: int = Form(PDF_RENDER_DPI, description="Độ phân giải render PDF"),
    lang: str = Form(OCR_LANG, description="Ngôn ngữ OCR"),
    engine: str = Form(OCR_ENGINE, description="Engine OCR (rapidocr / tesseract)")
):
    """
    Tiếp nhận tệp tin PDF/Ảnh bệnh án và trích xuất cấu trúc dữ liệu y khoa chuẩn dưới dạng JSON.
    """
    suffix = os.path.splitext(file.filename)[1] if file.filename else ".pdf"
    # Tạo tệp tạm để ghi file tải lên
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        shutil.copyfileobj(file.file, tmp)
        tmp_path = tmp.name

    try:
        output_txt_path = tmp_path + "_extracted.txt"
        json_path = tmp_path + "_extracted_fields.json"
        
        # Thực hiện trích xuất & OCR
        process_pdf(
            pdf_path=tmp_path,
            output_txt_path=output_txt_path,
            force_ocr=force_ocr,
            dpi=dpi,
            lang=lang,
            engine_type=engine
        )
        
        # Đọc dữ liệu JSON kết quả
        if not os.path.exists(json_path):
            raise HTTPException(
                status_code=500,
                detail="OCR hoàn thành nhưng không tìm thấy file cấu trúc JSON đầu ra."
            )
            
        import json
        with open(json_path, "r", encoding="utf-8") as f:
            structured_data = json.load(f)
            
        # Dọn dẹp tệp tạm thời
        for path in [tmp_path, output_txt_path, json_path]:
            if os.path.exists(path):
                os.remove(path)
                
        return structured_data
        
    except Exception as e:
        # Dọn dẹp tệp tạm thời nếu xảy ra lỗi
        for path in [tmp_path, tmp_path + "_extracted.txt", tmp_path + "_extracted_fields.json"]:
            if os.path.exists(path):
                try:
                    os.remove(path)
                except Exception:
                    pass
        raise HTTPException(status_code=500, detail=f"Lỗi xử lý OCR PDF: {str(e)}")

# ==========================================
# 2. API OCR CĂN CƯỚC CÔNG DÂN (CCCD)
# ==========================================
@app.post("/ocr/cccd", summary="OCR & Trích xuất thông tin Căn cước công dân (CCCD)")
async def perform_ocr_cccd(
    file: UploadFile = File(..., description="Ảnh chụp Căn cước công dân (JPG, PNG, WEBP, PDF 1 trang)")
):
    """
    Tiếp nhận ảnh chụp CCCD (mặt trước / gắn chip / mã vạch / CMND) và trả về thông tin định danh cá nhân có cấu trúc.
    Tự động kết hợp quét QR Code tốc độ cao và AI OCR tiếng Việt.
    """
    try:
        image_bytes = await file.read()
        if not image_bytes:
            raise HTTPException(status_code=400, detail="Tệp tin tải lên rỗng.")
            
        # Xử lý trích xuất CCCD
        result = process_cccd_image(image_bytes)
        return result
        
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi xử lý OCR CCCD: {str(e)}")

# ==========================================
# 3. HEALTH CHECK
# ==========================================
@app.get("/health", summary="Kiểm tra trạng thái server")
async def health_check():
    """
    Kiểm tra trạng thái hoạt động của server OCR.
    """
    return {
        "status": "healthy",
        "supported_apis": [
            {"endpoint": "/ocr/pdf", "description": "OCR Hồ sơ Bệnh án Y tế (PDF)"},
            {"endpoint": "/ocr/cccd", "description": "OCR Căn cước công dân (Image/QR)"}
        ]
    }

if __name__ == "__main__":
    # Chạy server FastAPI ở cổng 8009
    uvicorn.run(app, host="0.0.0.0", port=8009)

