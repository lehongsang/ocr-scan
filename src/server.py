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
from src.ocr_engine import ocr_multiple_images

from fastapi.openapi.utils import get_openapi

app = FastAPI(
    title="OCR & Document Intelligence API",
    description="Hệ thống API OCR đa năng: Gemini Vision (Multi-Image), Trích xuất Bệnh án y tế (PDF) & Căn cước công dân (CCCD).",
    version="2.2.0"
)

def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema
    openapi_schema = get_openapi(
        title=app.title,
        version=app.version,
        description=app.description,
        routes=app.routes,
    )
    # Sửa lỗi Swagger UI không hiển thị nút 'Chọn tệp' cho danh sách file
    for schema in openapi_schema.get("components", {}).get("schemas", {}).values():
        for prop in schema.get("properties", {}).values():
            if prop.get("type") == "array" and "items" in prop:
                prop["items"] = {"type": "string", "format": "binary"}
    app.openapi_schema = openapi_schema
    return app.openapi_schema

app.openapi = custom_openapi

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
# 4. API OCR ẢNH BỆNH ÁN & TRÍCH XUẤT THÔNG TIN (GEMINI VISION)
# ==========================================
@app.post("/ocr/images", summary="OCR & Trích xuất Bệnh án từ ảnh (Choose Files)")
async def perform_ocr_images(
    files: List[UploadFile] = File(..., description="Chọn một hoặc nhiều file ảnh bệnh án (PNG, JPG, JPEG, WEBP, BMP...)")
):
    """
    Tiếp nhận 1 hoặc nhiều file ảnh bệnh án tải lên:
    1. Quét OCR đọc chữ bằng Gemini Vision.
    2. Tự động bóc tách và fill vào các trường bệnh nền, thông tin bệnh nhân, chỉ số sinh lý...
    3. Trả về cấu trúc JSON y khoa chuẩn giống hệt API OCR PDF (/ocr/pdf).
    """
    if not files:
        raise HTTPException(status_code=400, detail="Không có tệp tin ảnh nào được tải lên.")

    image_items = []
    for f in files:
        if not f.filename:
            continue
        content = await f.read()
        if content:
            image_items.append((f.filename, content))

    if not image_items:
        raise HTTPException(status_code=400, detail="Tất cả các tệp tin ảnh tải lên đều rỗng.")

    try:
        # Bước 1: Quét OCR toàn bộ các ảnh bằng Gemini Vision
        result = ocr_multiple_images(
            image_items=image_items,
            engine_type="gemini"
        )
        final_text = result.get("combined_text", "")

        # Bước 2: Bóc tách thông tin bệnh nhân, bệnh lý nền & chỉ số sinh lý (giống hệt OCR PDF)
        schema_path = os.path.join(os.path.dirname(__file__), "schema.json")
        from src.config import GEMINI_API_KEY
        if GEMINI_API_KEY and GEMINI_API_KEY != "YOUR_API_KEY":
            from src.parser import parse_medical_fields_gemini
            structured_data = parse_medical_fields_gemini(final_text, schema_path)
        else:
            from src.parser import parse_medical_fields
            structured_data = parse_medical_fields(final_text)

        return structured_data

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi khi xử lý OCR bệnh án từ ảnh: {str(e)}")

# ==========================================
# 5. HEALTH CHECK
# ==========================================
@app.get("/health", summary="Kiểm tra trạng thái server")
async def health_check():
    """
    Kiểm tra trạng thái hoạt động của server OCR.
    """
    return {
        "status": "healthy",
        "supported_apis": [
            {"endpoint": "/ocr/images", "method": "POST", "description": "OCR ảnh bằng Gemini Vision (Chọn 1 hoặc nhiều ảnh)"},
            {"endpoint": "/ocr/pdf", "method": "POST", "description": "OCR Hồ sơ Bệnh án Y tế (PDF)"},
            {"endpoint": "/ocr/cccd", "method": "POST", "description": "OCR Căn cước công dân 1 & 2 mặt (Image/QR/PDF)"}
        ]
    }

if __name__ == "__main__":
    # Chạy server FastAPI ở cổng 8009 (tự động reload khi sửa code)
    uvicorn.run("src.server:app", host="0.0.0.0", port=8009, reload=True)


