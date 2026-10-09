import unittest
import math
from src.calculators.kidney import calculate_egfr, calculate_acr
from src.pdf_processor import extract_digital_text
from src.parser import parse_medical_fields

class TestKidneyCalculators(unittest.TestCase):

    def test_egfr_male_standard(self):
        # Nam, 60 tuổi, Creatinin máu 1.2 mg/dL -> SCr/0.9 = 1.333
        egfr = calculate_egfr(scr_val=1.2, scr_unit="mg/dL", age=60, gender="Nam")
        self.assertIsNotNone(egfr)
        self.assertGreater(egfr, 0)
        # Nam 70 tuổi, SCr 69.7 µmol/L (=0.7885 mg/dL)
        egfr_male = calculate_egfr(scr_val=69.7, scr_unit="µmol/L", age=70, gender="Nam")
        self.assertAlmostEqual(egfr_male, 94.6, delta=1.0)

    def test_egfr_female_standard(self):
        # Nữ, 70 tuổi, Creatinin máu 69.7 µmol/L (=0.7885 mg/dL)
        # Theo phiếu BN Nguyễn Thị Hồng:
        # SCr = 69.7 / 88.4 = 0.78846 mg/dL
        # eGFR = 142 * 1.0 * (0.78846/0.7)^-1.200 * (0.9938^70) * 1.012 ≈ 80.6
        egfr = calculate_egfr(scr_val=69.7, scr_unit="µmol/L", age=70, gender="Nữ")
        self.assertIsNotNone(egfr)
        self.assertAlmostEqual(egfr, 80.6, delta=0.5)

    def test_egfr_invalid_inputs(self):
        # Tuổi dưới 18 không áp dụng công thức này
        self.assertIsNone(calculate_egfr(scr_val=1.0, scr_unit="mg/dL", age=16, gender="Nam"))
        # Thiếu thông tin
        self.assertIsNone(calculate_egfr(scr_val=0, scr_unit="mg/dL", age=50, gender="Nam"))
        self.assertIsNone(calculate_egfr(scr_val=1.0, scr_unit="mg/dL", age=None, gender="Nam"))

    def test_acr_standard_units(self):
        # 1. Albumin (mg/L) & Creatinin (g/L): Alb / Cre
        # 30 mg/L & 1.0 g/L -> ACR = 30.0 mg/g
        acr_1 = calculate_acr(alb_val=30.0, alb_unit="mg/L", cre_val=1.0, cre_unit="g/L")
        self.assertEqual(acr_1, 30.0)

        # 2. Albumin (mg/L) & Creatinin (mmol/L): Alb * 8.84 / Cre
        # 10 mg/L & 8.8 mmol/L (Ca thực tế BN Nguyễn Thị Hồng) -> 10 * 8.84 / 8.8 ≈ 10.05 mg/g
        acr_2 = calculate_acr(alb_val=10.0, alb_unit="mg/L", cre_val=8.8, cre_unit="mmol/L")
        self.assertAlmostEqual(acr_2, 10.05, delta=0.02)

        # 3. Albumin (mg/L) & Creatinin (mg/dL): Alb * 100 / Cre
        # 30 mg/L & 100 mg/dL -> 30 * 100 / 100 = 30.0 mg/g
        acr_3 = calculate_acr(alb_val=30.0, alb_unit="mg/L", cre_val=100.0, cre_unit="mg/dL")
        self.assertEqual(acr_3, 30.0)

        # 4. Albumin (mg/dL) & Creatinin (mg/dL): Alb * 1000 / Cre
        # 3 mg/dL & 100 mg/dL -> 3 * 1000 / 100 = 30.0 mg/g
        acr_4 = calculate_acr(alb_val=3.0, alb_unit="mg/dL", cre_val=100.0, cre_unit="mg/dL")
        self.assertEqual(acr_4, 30.0)

    def test_full_patient_pdf(self):
        import os
        pdf_path = r"C:\Users\Admin\Downloads\NGUYỄN THỊ HỒNG-BN000802016 - Copy.pdf"
        if os.path.exists(pdf_path):
            pages = extract_digital_text(pdf_path)
            full_text = "\n".join(pages.values())
            res = parse_medical_fields(full_text)
            
            # Kiểm tra eGFR
            self.assertEqual(res["C_BENH_LY_MAN_TINH_KEM_THEO"]["egfr"], 76.0)
            # Kiểm tra ACR
            self.assertEqual(res["C_BENH_LY_MAN_TINH_KEM_THEO"]["acr"], 10.05)
            # Kiểm tra thông tin bệnh nhân
            self.assertEqual(res["THONG_TIN_CA_NHAN"]["ho_va_ten"], "NGUYỄN THỊ HỒNG")
            self.assertEqual(res["THONG_TIN_CA_NHAN"]["ma_benh_nhan"], "BN000802016")
            self.assertEqual(res["THONG_TIN_CA_NHAN"]["gioi_tinh"], "Nữ")
            self.assertEqual(res["A_CHI_SO_SINH_LY_CO_BAN"]["tuoi"], 70)


if __name__ == "__main__":
    unittest.main()
