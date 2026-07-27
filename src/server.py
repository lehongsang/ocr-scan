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

app = FastAPI(
    title="OCR & Text Extraction API",
    description="API trích xuất thông tin bệnh án từ file PDF và Hình ảnh sử dụng PyMuPDF & Tesseract/RapidOCR",
    version="1.0.0"
)

# Cho phép CORS để các client khác gọi được
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.post("/ocr")
async def perform_ocr(
    file: UploadFile = File(...),
    force_ocr: bool = Form(False),
    dpi: int = Form(PDF_RENDER_DPI),
    lang: str = Form(OCR_LANG),
    engine: str = Form(OCR_ENGINE)
):
    """
    Tiếp nhận tệp tin PDF/Ảnh và trích xuất cấu trúc dữ liệu bệnh án dưới dạng JSON.
    """
    suffix = os.path.splitext(file.filename)[1]
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
        raise HTTPException(status_code=500, detail=f"Lỗi xử lý OCR: {str(e)}")

@app.get("/health")
async def health_check():
    """
    Kiểm tra trạng thái hoạt động của server OCR.
    """
    return {"status": "healthy"}

if __name__ == "__main__":
    # Chạy server FastAPI ở cổng 8009
    uvicorn.run(app, host="0.0.0.0", port=8009)
