import sys
from typing import Optional

try:
    from pydantic import BaseModel, Field
    HAS_PYDANTIC = True
except ImportError:
    # Hỗ trợ fallback dùng dataclasses nếu người dùng chưa cài pydantic
    from dataclasses import dataclass, field
    HAS_PYDANTIC = False

if HAS_PYDANTIC:
    # ------------------ Cấu trúc bằng Pydantic ------------------
    class PhanLoaiBenhLyNen(BaseModel):
        has_underlying_disease: Optional[bool] = Field(None, description="True nếu 'Có bệnh lý nền', False nếu không")

    class ChiSoSinhLyCoBan(BaseModel):
        tuoi: Optional[int] = Field(None, description="Tuổi (tuổi)")
        gioi_tinh: Optional[str] = Field(None, description="Giới tính (Nam/Nữ)")
        hut_thuoc_la: Optional[bool] = Field(None, description="Hút thuốc lá (đang hút)")
        huyet_ap_tam_thu_sbp: Optional[int] = Field(None, description="Huyết áp tâm thu SBP (mmHg)")
        cholesterol_toan_phan: Optional[float] = Field(None, description="Cholesterol toàn phần (mmol/L)")
        hdl_cholesterol: Optional[float] = Field(None, description="HDL-Cholesterol (mmol/L)")

    class TonThuongCoQuanDich(BaseModel):
        phi_dai_that_trai: Optional[bool] = Field(None, description="Phì đại thất trái (Có/Không)")
        ton_thuong_day_mat: Optional[bool] = Field(None, description="Tổn thương đáy mắt (Có/Không)")
        albumin_microalbumin_nieu: Optional[bool] = Field(None, description="Albumin / Microalbumin niệu (Có/Không)")
        ton_thuong_tham_lang_tren_nao: Optional[bool] = Field(None, description="Tổn thương thầm lặng trên não (Có/Không)")

    class BenhLyManTinhKemTheo(BaseModel):
        egfr: Optional[int] = Field(None, description="Độ thanh thải cầu thận eGFR (mL/min/1.73m²)")
        acr: Optional[int] = Field(None, description="Tỷ lệ Albumin/Creatinin ACR (mg/g)")
        dai_thao_duong: Optional[bool] = Field(None, description="Đái tháo đường")
        dot_quy_nao: Optional[bool] = Field(None, description="Đột quỵ não")
        nhoi_mau_co_tim: Optional[bool] = Field(None, description="Nhồi máu cơ tim")
        hoi_chung_vanh_cap: Optional[bool] = Field(None, description="Hội chứng vành cấp")
        benh_ly_mach_vanh: Optional[bool] = Field(None, description="Bệnh lý mạch vành")
        thieu_mau_cuc_bo_nao_thoang_qua_tia: Optional[bool] = Field(None, description="Thiếu máu cục bộ não thoáng qua (TIA)")
        phinh_dong_mach_chu: Optional[bool] = Field(None, description="Phình động mạch chủ")
        benh_mach_mau_ngoai_vi: Optional[bool] = Field(None, description="Bệnh mạch máu ngoại vi")
        vua_xo_mach_mau: Optional[bool] = Field(None, description="Vữa xơ mạch máu")
        tang_cholesterol_mau_gia_dinh: Optional[bool] = Field(None, description="Tăng Cholesterol máu gia đình")

    class ThongTinCaNhan(BaseModel):
        ho_va_ten: Optional[str] = Field(None, description="Họ và tên")
        ngay_sinh: Optional[str] = Field(None, description="Ngày sinh (dd/mm/yyyy)")
        gioi_tinh: Optional[str] = Field(None, description="Giới tính (Nam/Nữ/Khác)")
        cccd_cmnd: Optional[str] = Field(None, description="CCCD/CMND (mã số định danh)")
        trang_thai_ho_so: Optional[str] = Field(None, description="Trạng thái hồ sơ (Hoạt động/Tạm dừng)")

    class ThongTinLienHeDiaChi(BaseModel):
        so_dien_thoai: Optional[str] = Field(None, description="Số điện thoại")
        email: Optional[str] = Field(None, description="Địa chỉ Email")
        tinh_thanh_pho: Optional[str] = Field(None, description="Tỉnh / Thành phố")
        quan_huyen: Optional[str] = Field(None, description="Quận / Huyện")
        so_nha_ten_duong: Optional[str] = Field(None, description="Số nhà, tên đường (Thôn, xóm)")
        dia_chi_day_du: Optional[str] = Field(None, description="Địa chỉ đầy đủ")

    class ChiSoTienSuSucKhoe(BaseModel):
        chieu_cao: Optional[int] = Field(None, description="Chiều cao (cm)")
        can_nang: Optional[int] = Field(None, description="Cân nặng (kg)")
        nhom_mau: Optional[str] = Field(None, description="Nhóm máu (A+, O-, AB+, ...)")
        tien_su_benh_ly: Optional[str] = Field(None, description="Tiền sử bệnh / Bệnh lý hiện tại")

    class ThongTinNhomChamSoc(BaseModel):
        ma_nhom_cham_soc: Optional[str] = Field(None, description="Mã nhóm chăm sóc (Care Group Code)")

    class PatientMedicalRecord(BaseModel):
        """
        Đối tượng bao trùm toàn bộ các trường thông tin y tế của bệnh nhân.
        """
        phan_loai_benh_nen: Optional[PhanLoaiBenhLyNen] = None
        chi_so_sinh_ly: Optional[ChiSoSinhLyCoBan] = None
        ton_thuong_co_quan: Optional[TonThuongCoQuanDich] = None
        benh_ly_man_tinh: Optional[BenhLyManTinhKemTheo] = None
        thong_tin_ca_nhan: Optional[ThongTinCaNhan] = None
        lien_he_dia_chi: Optional[ThongTinLienHeDiaChi] = None
        chi_so_tien_su: Optional[ChiSoTienSuSucKhoe] = None
        nhom_cham_soc: Optional[ThongTinNhomChamSoc] = None

else:
    # ------------------ Cấu trúc bằng Dataclass ------------------
    @dataclass
    class PhanLoaiBenhLyNen:
        has_underlying_disease: Optional[bool] = None

    @dataclass
    class ChiSoSinhLyCoBan:
        tuoi: Optional[int] = None
        gioi_tinh: Optional[str] = None
        hut_thuoc_la: Optional[bool] = None
        huyet_ap_tam_thu_sbp: Optional[int] = None
        cholesterol_toan_phan: Optional[float] = None
        hdl_cholesterol: Optional[float] = None

    @dataclass
    class TonThuongCoQuanDich:
        phi_dai_that_trai: Optional[bool] = None
        ton_thuong_day_mat: Optional[bool] = None
        albumin_microalbumin_nieu: Optional[bool] = None
        ton_thuong_tham_lang_tren_nao: Optional[bool] = None

    @dataclass
    class BenhLyManTinhKemTheo:
        egfr: Optional[int] = None
        acr: Optional[int] = None
        dai_thao_duong: Optional[bool] = None
        dot_quy_nao: Optional[bool] = None
        nhoi_mau_co_tim: Optional[bool] = None
        hoi_chung_vanh_cap: Optional[bool] = None
        benh_ly_mach_vanh: Optional[bool] = None
        thieu_mau_cuc_bo_nao_thoang_qua_tia: Optional[bool] = None
        phinh_dong_mach_chu: Optional[bool] = None
        benh_mach_mau_ngoai_vi: Optional[bool] = None
        vua_xo_mach_mau: Optional[bool] = None
        tang_cholesterol_mau_gia_dinh: Optional[bool] = None

    @dataclass
    class ThongTinCaNhan:
        ho_va_ten: Optional[str] = None
        ngay_sinh: Optional[str] = None
        gioi_tinh: Optional[str] = None
        cccd_cmnd: Optional[str] = None
        trang_thai_ho_so: Optional[str] = None

    @dataclass
    class ThongTinLienHeDiaChi:
        so_dien_thoai: Optional[str] = None
        email: Optional[str] = None
        tinh_thanh_pho: Optional[str] = None
        quan_huyen: Optional[str] = None
        so_nha_ten_duong: Optional[str] = None
        dia_chi_day_du: Optional[str] = None

    @dataclass
    class ChiSoTienSuSucKhoe:
        chieu_cao: Optional[int] = None
        can_nang: Optional[int] = None
        nhom_mau: Optional[str] = None
        tien_su_benh_ly: Optional[str] = None

    @dataclass
    class ThongTinNhomChamSoc:
        ma_nhom_cham_soc: Optional[str] = None

    @dataclass
    class PatientMedicalRecord:
        phan_loai_benh_nen: Optional[PhanLoaiBenhLyNen] = None
        chi_so_sinh_ly: Optional[ChiSoSinhLyCoBan] = None
        ton_thuong_co_quan: Optional[TonThuongCoQuanDich] = None
        benh_ly_man_tinh: Optional[BenhLyManTinhKemTheo] = None
        thong_tin_ca_nhan: Optional[ThongTinCaNhan] = None
        lien_he_dia_chi: Optional[ThongTinLienHeDiaChi] = None
        chi_so_tien_su: Optional[ChiSoTienSuSucKhoe] = None
        nhom_cham_soc: Optional[ThongTinNhomChamSoc] = None
