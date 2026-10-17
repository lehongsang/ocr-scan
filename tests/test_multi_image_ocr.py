import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import io
import unittest
from PIL import Image, ImageDraw
from fastapi.testclient import TestClient
from src.server import app

def create_sample_image(text: str) -> bytes:
    """Tạo ảnh test có chứa văn bản dạng bytes"""
    img = Image.new("RGB", (500, 100), color=(255, 255, 255))
    draw = ImageDraw.Draw(img)
    draw.text((15, 30), text, fill=(0, 0, 0))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()

class TestMultiImageOCR(unittest.TestCase):

    def setUp(self):
        self.client = TestClient(app)


    def test_multi_image_ocr_gemini(self):
        img1_bytes = create_sample_image("Họ và tên: NGUYỄN VĂN AN\nTuổi: 65\nGiới tính: Nam")
        img2_bytes = create_sample_image("Chẩn đoán: Tăng huyết áp, Đái tháo đường")
        
        files = [
            ("files", ("trang_1.png", img1_bytes, "image/png")),
            ("files", ("trang_2.png", img2_bytes, "image/png"))
        ]
        
        response = self.client.post("/ocr/images", files=files)
        self.assertEqual(response.status_code, 200)
        resp_json = response.json()
        
        # Kiểm tra các section chuẩn giống hệt OCR PDF
        self.assertIn("PHAN_LOAI_BENH_LY_NEN", resp_json)
        self.assertIn("A_CHI_SO_SINH_LY_CO_BAN", resp_json)
        self.assertIn("C_BENH_LY_MAN_TINH_KEM_THEO", resp_json)
        self.assertIn("THONG_TIN_CA_NHAN", resp_json)
        self.assertTrue(resp_json["PHAN_LOAI_BENH_LY_NEN"]["has_underlying_disease"])
        self.assertTrue(resp_json["C_BENH_LY_MAN_TINH_KEM_THEO"]["tang_huyet_ap"])

        # Kiểm tra phần RAW_OCR_PAGES và RAW_OCR_TEXT của từng trang
        self.assertIn("RAW_OCR_PAGES", resp_json)
        self.assertIn("RAW_OCR_TEXT", resp_json)
        self.assertEqual(len(resp_json["RAW_OCR_PAGES"]), 2)
        self.assertEqual(resp_json["RAW_OCR_PAGES"][0]["page"], 1)
        self.assertEqual(resp_json["RAW_OCR_PAGES"][0]["filename"], "trang_1.png")
        self.assertIn("text", resp_json["RAW_OCR_PAGES"][0])
        self.assertEqual(resp_json["RAW_OCR_PAGES"][1]["page"], 2)
        self.assertEqual(resp_json["RAW_OCR_PAGES"][1]["filename"], "trang_2.png")

        # Kiểm tra nguồn dẫn chứng chi tiết của từng dữ liệu
        self.assertIn("CHI_TIET_TRICH_XUAT", resp_json)
        self.assertTrue(len(resp_json["CHI_TIET_TRICH_XUAT"]) > 0)
        self.assertIn("du_lieu_tim_thay", resp_json["RAW_OCR_PAGES"][0])
        
        # Kiểm tra xem có trích dẫn đúng trang của Họ và tên và Tăng huyết áp không
        fields_found = {item["truong"]: item["trang"] for item in resp_json["CHI_TIET_TRICH_XUAT"]}
        self.assertIn("ho_va_ten", fields_found)
        self.assertEqual(fields_found["ho_va_ten"], 1)
        self.assertIn("tang_huyet_ap", fields_found)
        self.assertEqual(fields_found["tang_huyet_ap"], 2)

if __name__ == "__main__":
    unittest.main()
