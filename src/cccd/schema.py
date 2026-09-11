from typing import Optional
from pydantic import BaseModel, Field

class QRData(BaseModel):
    scanned: bool = Field(False, description="Đã quét thành công mã QR hay chưa")
    raw_qr: Optional[str] = Field(None, description="Chuỗi thô đọc từ mã QR")
    old_id_number: Optional[str] = Field(None, description="Số CMND 9 số cũ (nếu có trong QR)")

class CCCDData(BaseModel):
    id_number: Optional[str] = Field(None, description="Số Căn cước công dân (12 chữ số) / CMND")
    full_name: Optional[str] = Field(None, description="Họ và tên")
    date_of_birth: Optional[str] = Field(None, description="Ngày sinh (dd/mm/yyyy)")
    gender: Optional[str] = Field(None, description="Giới tính (Nam/Nữ)")
    nationality: Optional[str] = Field("Việt Nam", description="Quốc tịch")
    place_of_origin: Optional[str] = Field(None, description="Quê quán / Nơi đăng ký khai sinh")
    place_of_residence: Optional[str] = Field(None, description="Nơi thường trú")
    date_of_expiry: Optional[str] = Field(None, description="Có giá trị đến / Ngày hết hạn (dd/mm/yyyy hoặc Không thời hạn)")
    issue_date: Optional[str] = Field(None, description="Ngày cấp / Thời gian cấp (dd/mm/yyyy)")
    place_of_issue: Optional[str] = Field(None, description="Nơi cấp / Cơ quan cấp (ví dụ: CỤC TRƯỞNG CỤC CẢNH SÁT QUẢN LÝ HÀNH CHÍNH VỀ TRẬT TỰ XÃ HỘI)")
    personal_identification: Optional[str] = Field(None, description="Đặc điểm nhân dạng / Dấu vết riêng")
    ethnicity: Optional[str] = Field(None, description="Dân tộc (đối với CMND)")
    religion: Optional[str] = Field(None, description="Tôn giáo (đối với CMND)")
    mrz: Optional[str] = Field(None, description="Mã MRZ đọc từ mặt sau thẻ (nếu có)")
    card_side: Optional[str] = Field("both", description="Mặt thẻ được xử lý: front, back, both")
    card_type: Optional[str] = Field(None, description="Loại thẻ: cccd_chip (gắn chip), cccd_barcode (mã vạch), cmnd (9/12 số)")
    qr_data: Optional[QRData] = Field(default_factory=QRData, description="Thông tin quét từ mã QR")
    raw_text: Optional[str] = Field(None, description="Toàn bộ nội dung text OCR được")
