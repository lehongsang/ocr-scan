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
    description="Hệ thống API OCR đa năng: Trích xuất Đơn thuốc (Prescription Drug Matching), Gemini Vision (Multi-Image), Bệnh án y tế (PDF) & Căn cước công dân (CCCD).",
    version="2.3.0"
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
            elif "anyOf" in prop:
                for sub in prop.get("anyOf", []):
                    if sub.get("type") == "array" and "items" in sub:
                        sub["items"] = {"type": "string", "format": "binary"}
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

        # Bước 3: Định vị chi tiết nguồn gốc dữ liệu (trang nào, dòng nào, file nào)
        from src.parser import extract_data_provenance
        raw_pages = result.get("results", [])
        provenance_list, page_findings_map = extract_data_provenance(raw_pages, structured_data)

        # Bổ sung danh sách chi tiết nguồn gốc vào response
        structured_data["CHI_TIET_TRICH_XUAT"] = provenance_list

        # Bước 4: Trả kèm toàn bộ text đã quét ra được của từng trang ảnh và text tổng hợp
        structured_data["RAW_OCR_PAGES"] = [
            {
                "page": item["page_index"],
                "filename": item["filename"],
                "char_count": item.get("char_count", len(item.get("text", ""))),
                "du_lieu_tim_thay": page_findings_map.get(item["page_index"], []),
                "text": item.get("text", "")
            }
            for item in raw_pages
        ]
        structured_data["RAW_OCR_TEXT"] = final_text

        return structured_data

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi khi xử lý OCR bệnh án từ ảnh: {str(e)}")

# ==========================================
# 5. API OCR ĐƠN THUỐC / TOA THUỐC (ẢNH & PDF)
# ==========================================
@app.post("/ocr/prescription", summary="OCR & Trích xuất tên thuốc từ Đơn thuốc (Ảnh / PDF)")
async def perform_ocr_prescription(
    files: List[UploadFile] = File(..., description="Chọn một hoặc nhiều tệp tin ảnh hoặc PDF đơn thuốc (JPG, PNG, PDF...)"),
    engine: str = Form("gemini", description="Engine OCR ('gemini' cho độ chính xác cao nhất cả chữ viết tay, hoặc 'rapidocr')"),
    threshold: float = Form(75.0, description="Ngưỡng so khớp tên thuốc với danh mục 44.000+ thuốc (0-100)")
):
    """
    Tiếp nhận ảnh chụp hoặc file PDF đơn thuốc:
    1. Quét OCR nhận diện văn bản (Gemini Vision chuyên gia y tế hoặc RapidOCR).
    2. Bóc tách danh sách các thuốc kê trong đơn (tên thuốc, hàm lượng, số lượng, cách dùng).
    3. Tự động đối chiếu (compare) với danh mục chuẩn Cục Quản lý Dược (DAV) để chuẩn hóa tên thuốc, hoạt chất và dạng bào chế.
    4. Trả về mảng danh sách tên thuốc `drug_names` cùng chi tiết thuốc `medications`.
    """
    from src.prescription_parser import process_prescription_document

    upload_items: List[UploadFile] = [f for f in files if getattr(f, "filename", None)]
    if not upload_items:
        raise HTTPException(
            status_code=400,
            detail="Vui lòng chọn ít nhất một tệp tin ảnh hoặc PDF đơn thuốc."
        )

    try:
        # Nếu chỉ có 1 file (phổ biến nhất)
        if len(upload_items) == 1:
            target_file = upload_items[0]
            content = await target_file.read()
            if not content:
                raise HTTPException(status_code=400, detail=f"Tệp tin '{target_file.filename}' bị rỗng.")
            
            return process_prescription_document(
                file_bytes=content,
                filename=target_file.filename,
                engine_type=engine,
                threshold=threshold
            )
        else:
            # Nhiều trang ảnh ghép lại
            # Nếu gửi nhiều file ảnh, gộp các ảnh lại
            image_items_bytes = []
            for f in upload_items:
                c = await f.read()
                if c:
                    image_items_bytes.append((f.filename, c))

            if not image_items_bytes:
                raise HTTPException(status_code=400, detail="Tất cả các tệp tải lên đều rỗng.")

            from src.prescription_parser import extract_prescription_gemini, DrugCatalogMatcher
            matcher = DrugCatalogMatcher.get_instance()
            
            extracted_data = extract_prescription_gemini(image_items_bytes)
            raw_meds = extracted_data.get("medications", [])
            matched_medications = []
            drug_names_list = []

            for item in raw_meds:
                raw_name = item.get("raw_name") or ""
                full_query = raw_name
                if item.get("strength") and item.get("strength") not in raw_name:
                    full_query = f"{raw_name} {item.get('strength')}"

                match_res = matcher.match_drug_name(full_query, threshold=threshold)
                if not match_res.get("matched") and raw_name != full_query:
                    match_res = matcher.match_drug_name(raw_name, threshold=threshold)

                final_drug_name = match_res.get("drug_name") if match_res.get("matched") else raw_name
                
                matched_item = {
                    "stt": item.get("stt", ""),
                    "raw_name": raw_name,
                    "matched_name": final_drug_name,
                    "base_name": match_res.get("base_name", ""),
                    "active_ingredient": match_res.get("active_ingredient", ""),
                    "strength": item.get("strength") or match_res.get("strength", ""),
                    "dosage_form": match_res.get("dosage_form", ""),
                    "quantity": item.get("quantity") or match_res.get("quantity", ""),
                    "usage": item.get("usage") or match_res.get("usage", ""),
                    "confidence": match_res.get("confidence", 0.0),
                    "match_type": match_res.get("match_type", "none"),
                    "is_verified": match_res.get("matched", False)
                }
                matched_medications.append(matched_item)
                if final_drug_name and final_drug_name not in drug_names_list:
                    drug_names_list.append(final_drug_name)

            return {
                "status": "success",
                "total_medications": len(matched_medications),
                "drug_names": drug_names_list,
                "prescription_info": extracted_data.get("prescription_info", {}),
                "medications": matched_medications,
                "raw_ocr_text": extracted_data.get("raw_text", ""),
                "engine_used": engine
            }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi khi xử lý OCR đơn thuốc: {str(e)}")

# ==========================================
# 6. HEALTH CHECK
# ==========================================
@app.get("/health", summary="Kiểm tra trạng thái server")
async def health_check():
    """
    Kiểm tra trạng thái hoạt động của server OCR.
    """
    return {
        "status": "healthy",
        "supported_apis": [
            {"endpoint": "/ocr/prescription", "method": "POST", "description": "OCR Đơn thuốc / Toa thuốc & Trích xuất tên thuốc (Ảnh/PDF)"},
            {"endpoint": "/ocr/images", "method": "POST", "description": "OCR ảnh Hồ sơ bệnh án bằng Gemini Vision (Chọn 1 hoặc nhiều ảnh)"},
            {"endpoint": "/ocr/pdf", "method": "POST", "description": "OCR Hồ sơ Bệnh án Y tế (PDF)"},
            {"endpoint": "/ocr/cccd", "method": "POST", "description": "OCR Căn cước công dân 1 & 2 mặt (Image/QR/PDF)"}
        ]
    }

if __name__ == "__main__":
    # Chạy server FastAPI ở cổng 8009 (tự động reload khi sửa code)
    uvicorn.run("src.server:app", host="0.0.0.0", port=8009, reload=True)


