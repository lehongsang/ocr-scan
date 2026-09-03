import os
import cv2
import numpy as np
from PIL import Image
from typing import Union, Dict, Any

from src.ocr_engine import get_rapid_ocr_engine
from src.pdf_processor import render_page_to_image
from src.utils import logger
from .parser import parse_cccd_qr_data, parse_cccd_text
from .corrector import correct_vietnamese_ocr_typos
from .schema import CCCDData, QRData

try:
    import zxingcpp
    HAS_ZXING = True
except ImportError:
    HAS_ZXING = False

def try_zxing_decode(img_np: np.ndarray) -> tuple[bool, str]:
    """Sử dụng zxing-cpp quét mã QR với nhiều cấu hình."""
    if not HAS_ZXING or img_np is None:
        return False, ""
    try:
        # Thử đọc trực tiếp với mọi hướng và mọi binarizer
        for binarizer in [zxingcpp.Binarizer.LocalAverage, zxingcpp.Binarizer.GlobalHistogram, zxingcpp.Binarizer.FixedThreshold]:
            barcodes = zxingcpp.read_barcodes(
                img_np,
                formats=zxingcpp.BarcodeFormat.QRCode,
                try_rotate=True,
                try_downscale=True,
                try_invert=True,
                binarizer=binarizer
            )
            for b in barcodes:
                if b.text and len(b.text.strip()) > 5:
                    return True, b.text.strip()
    except Exception:
        pass
    return False, ""

def decode_qr_code_advanced(image_np: np.ndarray) -> tuple[bool, str, int]:
    """
    Bộ giải mã QR CCCD chuyên sâu:
    1. Quét toàn ảnh trên nhiều độ phân giải.
    2. Cắt vùng góc phần tư (nơi đặt mã QR trên CCCD) để zoom cận cảnh tăng độ tương phản.
    3. Thử qua các bộ lọc (Grayscale, CLAHE, Sharpen).
    """
    h, w = image_np.shape[:2]

    # 1. Quét trên ảnh gốc và ảnh resize chuẩn
    for scale in [1.0, 1500 / max(h, w) if max(h, w) > 1500 else 1.0, 0.5, 1.5]:
        if scale == 1.0:
            resized = image_np
        else:
            resized = cv2.resize(image_np, (0, 0), fx=scale, fy=scale, interpolation=cv2.INTER_AREA if scale < 1.0 else cv2.INTER_CUBIC)
            
        success, text = try_zxing_decode(resized)
        if success:
            return True, text, 0

    # 2. Cắt các góc thẻ (Góc trên-phải, dưới-phải, trên-trái, dưới-trái)
    quadrants = [
        image_np[0:int(h*0.6), int(w*0.5):w],       # Góc trên bên phải (CCCD gắn chip chuẩn ngang)
        image_np[int(h*0.4):h, int(w*0.5):w],       # Góc dưới bên phải (Ảnh bị xoay dọc)
        image_np[0:int(h*0.6), 0:int(w*0.5)],       # Góc trên bên trái
        image_np[int(h*0.4):h, 0:int(w*0.5)],       # Góc dưới bên trái
    ]

    for crop in quadrants:
        if crop.size == 0:
            continue
        # Upscale vùng crop lên 2x để mã QR rõ nét hơn
        upscaled = cv2.resize(crop, (0, 0), fx=2.0, fy=2.0, interpolation=cv2.INTER_CUBIC)
        success, text = try_zxing_decode(upscaled)
        if success:
            return True, text, 0
            
        # Thử với ảnh xám và CLAHE cho vùng crop
        gray = cv2.cvtColor(upscaled, cv2.COLOR_BGR2GRAY) if len(upscaled.shape) == 3 else upscaled
        clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
        enhanced = clahe.apply(gray)
        success, text = try_zxing_decode(enhanced)
        if success:
            return True, text, 0

    # 3. Fallback dùng OpenCV QRCodeDetector nếu zxing không bắt được
    try:
        detector = cv2.QRCodeDetector()
        gray_full = cv2.cvtColor(image_np, cv2.COLOR_BGR2GRAY) if len(image_np.shape) == 3 else image_np
        data, _, _ = detector.detectAndDecode(gray_full)
        if data and len(data.strip()) > 5:
            return True, data.strip(), 0
    except Exception:
        pass

    return False, "", 0

def ocr_image_rapid(image_np: np.ndarray) -> str:
    """
    Thực hiện OCR văn bản trên ảnh sử dụng RapidOCR.
    """
    try:
        engine = get_rapid_ocr_engine()
        result, _ = engine(image_np)
        if result:
            return "\n".join([line[1] for line in result]).strip()
        return ""
    except Exception as e:
        logger.error(f"Lỗi khi OCR ảnh CCCD: {e}")
        return ""

def process_cccd_image(image_input: Union[str, bytes, np.ndarray, Image.Image]) -> Dict[str, Any]:
    """
    Hàm xử lý ảnh Căn cước công dân:
    1. Đọc và chuẩn hóa ảnh sang OpenCV format.
    2. Quét mã QR code chuyên sâu (Toàn ảnh + Crop góc QR + Upscale).
    3. Tự động xoay ảnh về chiều ngang nếu ảnh bị chụp dọc để OCR chính xác hơn.
    4. Phối hợp kết quả từ QR Code và Text OCR, tự động sửa lỗi chính tả địa danh.
    """
    # 1. Chuẩn hóa đầu vào sang numpy BGR image
    if isinstance(image_input, str):
        if image_input.lower().endswith(".pdf"):
            pil_img = render_page_to_image(image_input, 0, dpi=300)
            image_np = cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)
        else:
            image_np = cv2.imread(image_input)
            if image_np is None:
                pil_img = Image.open(image_input).convert("RGB")
                image_np = cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)
    elif isinstance(image_input, bytes):
        nparr = np.frombuffer(image_input, np.uint8)
        image_np = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    elif isinstance(image_input, Image.Image):
        image_np = cv2.cvtColor(np.array(image_input.convert("RGB")), cv2.COLOR_RGB2BGR)
    elif isinstance(image_input, np.ndarray):
        image_np = image_input
    else:
        raise ValueError("Định dạng ảnh đầu vào không hợp lệ.")

    if image_np is None:
        raise ValueError("Không thể giải mã hình ảnh CCCD.")

    # 2. Quét mã QR nâng cao
    qr_success, qr_raw, detected_angle = decode_qr_code_advanced(image_np)
    qr_info = parse_cccd_qr_data(qr_raw) if qr_success else None

    # 3. Chuẩn bị ảnh cho OCR:
    h, w = image_np.shape[:2]
    ocr_img = image_np
    if h > w:
        # Ảnh chụp dọc -> Xoay 90 độ để thẻ nằm ngang
        ocr_img = cv2.rotate(image_np, cv2.ROTATE_90_CLOCKWISE)

    # 4. Thực hiện OCR Text
    raw_ocr_text = ocr_image_rapid(ocr_img)
    if len(raw_ocr_text.strip()) < 20 and ocr_img is not image_np:
        raw_ocr_text = ocr_image_rapid(image_np)
        
    text_info = parse_cccd_text(raw_ocr_text)

    # 5. Phục hồi dấu tiếng Việt và sửa lỗi chính tả địa danh cho kết quả OCR
    place_origin = qr_info.get("place_of_origin") if qr_info and qr_info.get("place_of_origin") else text_info.get("place_of_origin")
    place_residence = qr_info.get("place_of_residence") if qr_info and qr_info.get("place_of_residence") else text_info.get("place_of_residence")
    
    place_origin = correct_vietnamese_ocr_typos(place_origin)
    place_residence = correct_vietnamese_ocr_typos(place_residence)

    # 6. Hợp nhất thông tin (Ưu tiên QR cho các trường chuẩn, bổ sung từ OCR)
    final_data = CCCDData(
        id_number=qr_info.get("id_number") if qr_info and qr_info.get("id_number") else text_info.get("id_number"),
        full_name=qr_info.get("full_name") if qr_info and qr_info.get("full_name") else text_info.get("full_name"),
        date_of_birth=qr_info.get("date_of_birth") if qr_info and qr_info.get("date_of_birth") else text_info.get("date_of_birth"),
        gender=qr_info.get("gender") if qr_info and qr_info.get("gender") else text_info.get("gender"),
        nationality=text_info.get("nationality", "Việt Nam"),
        place_of_origin=place_origin,
        place_of_residence=place_residence,
        date_of_expiry=text_info.get("date_of_expiry"),
        issue_date=qr_info.get("issue_date") if qr_info else None,
        card_type=qr_info.get("card_type") if qr_info else text_info.get("card_type"),
        qr_data=QRData(
            scanned=qr_success,
            raw_qr=qr_raw if qr_success else None,
            old_id_number=qr_info.get("old_id_number") if qr_info else None
        ),
        raw_text=raw_ocr_text
    )

    return final_data.dict()


