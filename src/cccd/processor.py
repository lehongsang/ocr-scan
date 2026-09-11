import os
import sys
import re
import cv2
import numpy as np
from PIL import Image
from typing import Union, Dict, Any, Optional

# Đảm bảo đường dẫn gốc dự án luôn có trong sys.path
_PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from src.ocr_engine import get_rapid_ocr_engine
from src.pdf_processor import render_page_to_image
from src.utils import logger
from .parser import parse_cccd_qr_data, parse_cccd_text, parse_cccd_back_text, detect_card_side, merge_cccd_results
from .corrector import correct_vietnamese_ocr_typos, correct_place_of_issue
from .schema import CCCDData, QRData
import fitz  # PyMuPDF



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
    1. Thử quét trên cả 4 hướng xoay: 0, 90, 180, 270 độ.
    2. Quét toàn ảnh và các vùng crop trọng điểm (góc trên-phải, góc dưới-phải).
    3. Thử qua nhiều bộ lọc binarization: Grayscale, CLAHE, Adaptive Threshold, OTSU, Unsharp Mask.
    """
    rotations = [
        (image_np, 0),
        (cv2.rotate(image_np, cv2.ROTATE_90_CLOCKWISE), 90),
        (cv2.rotate(image_np, cv2.ROTATE_180), 180),
        (cv2.rotate(image_np, cv2.ROTATE_90_COUNTERCLOCKWISE), 270),
    ]

    for cur_img, angle in rotations:
        h, w = cur_img.shape[:2]

        # Vùng trọng điểm chứa QR trên CCCD 2021 (trên-phải) và Căn cước 2024 (dưới-phải)
        regions = [
            cur_img,                                                    # Toàn bộ ảnh
            cur_img[0:int(h*0.65), int(w*0.45):w],                     # Góc trên bên phải (CCCD chip 2021)
            cur_img[int(h*0.35):h, int(w*0.45):w],                     # Góc dưới bên phải (Căn cước 2024 mặt sau)
            cur_img[0:int(h*0.65), 0:int(w*0.65)],                     # Góc trên bên trái
            cur_img[int(h*0.35):h, 0:int(w*0.65)],                     # Góc dưới bên trái
        ]

        for region in regions:
            if region is None or region.size == 0:
                continue

            for scale in [1.0, 1.5, 2.0]:
                resized = region if scale == 1.0 else cv2.resize(region, (0, 0), fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
                
                # 1. Thử trực tiếp ảnh màu
                success, text = try_zxing_decode(resized)
                if success:
                    return True, text, angle

                gray = cv2.cvtColor(resized, cv2.COLOR_BGR2GRAY) if len(resized.shape) == 3 else resized

                # 2. Thử Grayscale
                success, text = try_zxing_decode(gray)
                if success:
                    return True, text, angle

                # 3. Adaptive Threshold (Khắc phục ảnh bị lóa sáng / nền có vân hoa văn)
                ad_thresh = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 21, 5)
                success, text = try_zxing_decode(ad_thresh)
                if success:
                    return True, text, angle

                # 4. CLAHE tăng tương phản
                clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8)).apply(gray)
                success, text = try_zxing_decode(clahe)
                if success:
                    return True, text, angle

                # 5. Otsu Threshold
                _, otsu = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
                success, text = try_zxing_decode(otsu)
                if success:
                    return True, text, angle

    # Fallback OpenCV QRCodeDetector
    for cur_img, angle in rotations:
        try:
            detector = cv2.QRCodeDetector()
            gray_full = cv2.cvtColor(cur_img, cv2.COLOR_BGR2GRAY) if len(cur_img.shape) == 3 else cur_img
            data, _, _ = detector.detectAndDecode(gray_full)
            if data and len(data.strip()) > 5:
                return True, data.strip(), angle
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

def _convert_to_cv2_image(image_input: Union[str, bytes, np.ndarray, Image.Image]) -> np.ndarray:
    """Chuyển đổi các định dạng đầu vào khác nhau thành numpy BGR image."""
    if isinstance(image_input, str):
        if image_input.lower().endswith(".pdf"):
            pil_img = render_page_to_image(image_input, 0, dpi=300)
            return cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)
        else:
            image_np = cv2.imread(image_input)
            if image_np is None:
                pil_img = Image.open(image_input).convert("RGB")
                return cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)
            return image_np
    elif isinstance(image_input, bytes):
        if image_input.startswith(b"%PDF"):
            doc = fitz.open(stream=image_input, filetype="pdf")
            page = doc[0]
            pix = page.get_pixmap(dpi=300, alpha=False)
            pil_img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
            doc.close()
            return cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)
        nparr = np.frombuffer(image_input, np.uint8)
        return cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    elif isinstance(image_input, Image.Image):
        return cv2.cvtColor(np.array(image_input.convert("RGB")), cv2.COLOR_RGB2BGR)
    elif isinstance(image_input, np.ndarray):
        return image_input
    else:
        raise ValueError("Định dạng ảnh đầu vào không hợp lệ.")

def process_single_card_image(image_input: Union[str, bytes, np.ndarray, Image.Image]) -> Dict[str, Any]:
    """
    Xử lý một ảnh thẻ CCCD (có thể là mặt trước, mặt sau hoặc ảnh ghép 2 mặt):
    1. Quét QR code nâng cao trên 4 hướng xoay.
    2. OCR nội dung văn bản (tự xoay theo hướng tối ưu).
    3. Nhận diện mặt thẻ (front, back, both).
    4. Trích xuất thông tin nhân thân (mặt trước) và nơi cấp, ngày cấp, đặc điểm nhận dạng (mặt sau).
    5. Chuẩn hóa địa danh và cơ quan cấp.
    """
    image_np = _convert_to_cv2_image(image_input)
    if image_np is None:
        raise ValueError("Không thể giải mã hình ảnh CCCD.")

    # 1. Quét mã QR nâng cao
    qr_success, qr_raw, qr_angle = decode_qr_code_advanced(image_np)
    qr_info = parse_cccd_qr_data(qr_raw) if qr_success else None

    # 2. Chuẩn bị ảnh cho OCR theo hướng đúng
    h, w = image_np.shape[:2]
    if qr_success and qr_angle != 0:
        if qr_angle == 90:
            ocr_img = cv2.rotate(image_np, cv2.ROTATE_90_CLOCKWISE)
        elif qr_angle == 180:
            ocr_img = cv2.rotate(image_np, cv2.ROTATE_180)
        elif qr_angle == 270:
            ocr_img = cv2.rotate(image_np, cv2.ROTATE_90_COUNTERCLOCKWISE)
        else:
            ocr_img = image_np
    elif h > w:
        ocr_img = cv2.rotate(image_np, cv2.ROTATE_90_CLOCKWISE)
    else:
        ocr_img = image_np

    # 3. Thực hiện OCR Text
    raw_ocr_text = ocr_image_rapid(ocr_img)
    if len(raw_ocr_text.strip()) < 20 and ocr_img is not image_np:
        alt_text = ocr_image_rapid(image_np)
        if len(alt_text) > len(raw_ocr_text):
            raw_ocr_text = alt_text

    # 4. Nhận diện mặt thẻ
    card_side = detect_card_side(raw_ocr_text, qr_found=qr_success)

    # 5. Phân tích dữ liệu văn bản
    front_info = parse_cccd_text(raw_ocr_text)
    back_info = parse_cccd_back_text(raw_ocr_text)

    # 6. Chuẩn hóa địa chỉ & nơi cấp
    place_origin = qr_info.get("place_of_origin") if qr_info and qr_info.get("place_of_origin") else (front_info.get("place_of_origin") or back_info.get("place_of_origin"))
    place_residence = qr_info.get("place_of_residence") if qr_info and qr_info.get("place_of_residence") else (back_info.get("place_of_residence") or front_info.get("place_of_residence"))
    
    place_origin = correct_vietnamese_ocr_typos(place_origin)
    place_residence = correct_vietnamese_ocr_typos(place_residence)

    # Xác định ngày cấp & ngày hết hạn
    issue_date = qr_info.get("issue_date") if qr_info and qr_info.get("issue_date") else (back_info.get("issue_date") or front_info.get("issue_date"))
    date_of_expiry = back_info.get("date_of_expiry") or front_info.get("date_of_expiry")

    # Nơi cấp
    place_of_issue = back_info.get("place_of_issue") or front_info.get("place_of_issue")
    if not place_of_issue and card_side in ["back", "both"]:
        if "bộ công an" in raw_ocr_text.lower() or "ministry" in raw_ocr_text.lower() or "can cuoc" in raw_ocr_text.lower():
            place_of_issue = "BỘ CÔNG AN"
        elif "cảnh sát" in raw_ocr_text.lower() or "cuc truong" in raw_ocr_text.lower():
            place_of_issue = "CỤC TRƯỞNG CỤC CẢNH SÁT QUẢN LÝ HÀNH CHÍNH VỀ TRẬT TỰ XÃ HỘI"

    if place_of_issue:
        place_of_issue = correct_place_of_issue(place_of_issue)

    # Họ tên (nếu có dấu từ front thì ưu tiên, nếu OCR mất dấu mà MRZ có thì format MRZ)
    full_name = qr_info.get("full_name") if qr_info and qr_info.get("full_name") else front_info.get("full_name")
    if not full_name and back_info.get("mrz"):
        # Trích xuất từ MRZ dòng tên
        for mrz_l in back_info["mrz"].split("\n"):
            if "<<" in mrz_l and not any(c.isdigit() for c in mrz_l):
                clean_name = mrz_l.replace("<", " ").strip()
                full_name = re.sub(r'\s+', ' ', clean_name)
                break

    # Hợp nhất dữ liệu
    final_data = CCCDData(
        id_number=qr_info.get("id_number") if qr_info and qr_info.get("id_number") else front_info.get("id_number"),
        full_name=full_name,
        date_of_birth=qr_info.get("date_of_birth") if qr_info and qr_info.get("date_of_birth") else front_info.get("date_of_birth"),
        gender=qr_info.get("gender") if qr_info and qr_info.get("gender") else front_info.get("gender"),
        nationality=front_info.get("nationality", "Việt Nam"),
        place_of_origin=place_origin,
        place_of_residence=place_residence,
        date_of_expiry=date_of_expiry,
        issue_date=issue_date,
        place_of_issue=place_of_issue,
        personal_identification=back_info.get("personal_identification"),
        ethnicity=back_info.get("ethnicity"),
        religion=back_info.get("religion"),
        mrz=back_info.get("mrz"),
        card_side=card_side,
        card_type="can_cuoc_2024" if ("căn cước" in raw_ocr_text.lower() or "can cuoc" in raw_ocr_text.lower() or "identity card" in raw_ocr_text.lower()) and "công dân" not in raw_ocr_text.lower() and "cong dan" not in raw_ocr_text.lower() and "citizen" not in raw_ocr_text.lower() else (qr_info.get("card_type") if qr_info else front_info.get("card_type", "cccd_chip")),
        qr_data=QRData(
            scanned=qr_success,
            raw_qr=qr_raw if qr_success else None,
            old_id_number=qr_info.get("old_id_number") if qr_info else None
        ),
        raw_text=raw_ocr_text
    )

    return final_data.dict()

def process_cccd_both_sides(
    front_input: Union[str, bytes, np.ndarray, Image.Image],
    back_input: Union[str, bytes, np.ndarray, Image.Image]
) -> Dict[str, Any]:
    """
    Xử lý đồng thời 2 mặt thẻ CCCD (Mặt trước + Mặt sau):
    Tự động nhận diện và hoán đổi vị trí nếu người dùng gửi ngược mặt, sau đó hợp nhất dữ liệu hoàn chỉnh.
    """
    res1 = process_single_card_image(front_input)
    res2 = process_single_card_image(back_input)

    # Tự động xác định nếu gửi ngược ảnh (ảnh 1 là back, ảnh 2 là front)
    if res1.get("card_side") == "back" and res2.get("card_side") in ["front", "both"]:
        front_res, back_res = res2, res1
    else:
        front_res, back_res = res1, res2

    merged = merge_cccd_results(front_res, back_res)
    return CCCDData(**merged).dict()

def process_cccd_image(
    image_input: Union[str, bytes, np.ndarray, Image.Image],
    back_input: Optional[Union[str, bytes, np.ndarray, Image.Image]] = None
) -> Dict[str, Any]:
    """
    Hàm xử lý chính cho OCR CCCD:
    - Nếu truyền cả 2 ảnh (image_input + back_input): Tự động quét 2 mặt và hợp nhất.
    - Nếu truyền PDF có 2 trang trở lên: Tự động trích xuất trang 1 làm mặt trước, trang 2 làm mặt sau.
    - Nếu truyền 1 ảnh đơn: Tự động trích xuất đầy đủ thông tin (kể cả ảnh ghép 2 mặt).
    """
    # Trường hợp truyền rõ ràng 2 ảnh mặt trước và mặt sau
    if back_input is not None:
        return process_cccd_both_sides(image_input, back_input)

    # Kiểm tra nếu là file PDF nhiều trang
    try:
        if isinstance(image_input, str) and image_input.lower().endswith(".pdf"):
            doc = fitz.open(image_input)
            if len(doc) >= 2:
                img1 = render_page_to_image(image_input, 0, dpi=300)
                img2 = render_page_to_image(image_input, 1, dpi=300)
                doc.close()
                return process_cccd_both_sides(img1, img2)
            doc.close()
        elif isinstance(image_input, bytes) and image_input.startswith(b"%PDF"):
            doc = fitz.open(stream=image_input, filetype="pdf")
            if len(doc) >= 2:
                p1 = doc[0].get_pixmap(dpi=300, alpha=False)
                p2 = doc[1].get_pixmap(dpi=300, alpha=False)
                img1 = Image.frombytes("RGB", [p1.width, p1.height], p1.samples)
                img2 = Image.frombytes("RGB", [p2.width, p2.height], p2.samples)
                doc.close()
                return process_cccd_both_sides(img1, img2)
            doc.close()
    except Exception as e:
        logger.warning(f"Không thể xử lý PDF nhiều trang: {e}")

    # Mặc định xử lý ảnh đơn
    return process_single_card_image(image_input)



