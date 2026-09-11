import os
import sys
import shutil
import tempfile
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

# Thêm thư mục gốc của dự án vào sys.path để import từ src
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from typing import Optional, List
from src.main import process_pdf
from src.config import PDF_RENDER_DPI, OCR_LANG, OCR_ENGINE
from src.cccd import process_cccd_image, process_cccd_both_sides

app = FastAPI(
    title="OCR & Document Intelligence API",
    description="Hệ thống API OCR đa năng: Trích xuất Bệnh án y tế (PDF) & Căn cước công dân (CCCD) 2 mặt.",
    version="2.1.0"
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
# 2. API OCR CĂN CƯỚC CÔNG DÂN (CCCD 2 MẶT)
# ==========================================
@app.post("/ocr/cccd", summary="OCR & Trích xuất thông tin Căn cước công dân (CCCD 2 mặt)")
async def perform_ocr_cccd(
    front_file: UploadFile = File(..., description="Ảnh mặt trước CCCD / CMND"),
    back_file: UploadFile = File(..., description="Ảnh mặt sau CCCD / CMND")
):
    """
    Tiếp nhận ảnh chụp CCCD/CMND 2 mặt:
    - `front_file` (Bắt buộc): Ảnh mặt trước CCCD/CMND.
    - `back_file` (Bắt buộc): Ảnh mặt sau CCCD/CMND.
    Hệ thống tự động quét QR, bóc tách OCR, nhận diện loại thẻ và hợp nhất dữ liệu 2 mặt.
    """
    try:
        def is_upload(f):
            return f is not None and (isinstance(f, UploadFile) or hasattr(f, "read"))

        if not is_upload(front_file) or not is_upload(back_file):
            raise HTTPException(status_code=400, detail="Vui lòng tải lên đầy đủ cả 2 mặt: ảnh mặt trước (front_file) và ảnh mặt sau (back_file).")

        front_bytes = await front_file.read()
        back_bytes = await back_file.read()

        if not front_bytes:
            raise HTTPException(status_code=400, detail="Tệp tin ảnh mặt trước (front_file) bị rỗng.")
        if not back_bytes:
            raise HTTPException(status_code=400, detail="Tệp tin ảnh mặt sau (back_file) bị rỗng.")

        return process_cccd_both_sides(front_bytes, back_bytes)

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
            {"endpoint": "/ocr/cccd", "description": "OCR Căn cước công dân 1 & 2 mặt (Image/QR/PDF)"}
        ]
    }

if __name__ == "__main__":
    # Chạy server FastAPI ở cổng 8009
    uvicorn.run(app, host="0.0.0.0", port=8009)

