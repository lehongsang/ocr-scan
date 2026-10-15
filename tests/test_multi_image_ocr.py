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

if __name__ == "__main__":
    unittest.main()
