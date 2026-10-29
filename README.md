# Hệ Thống Trích Xuất & OCR PDF Siêu Tốc (6 Trang / 3 Giây)

Dự án này tối ưu hóa việc trích xuất văn bản từ file PDF (đặc biệt là các file được chuyển đổi từ Word sang PDF) với mục tiêu xử lý 6 trang trong vòng dưới 3 giây.

## Cơ Chế Tối Ưu Tốc Độ

1. **Trích xuất trực tiếp (Digital Mode)**: Hầu hết file chuyển từ Word sang PDF đều chứa lớp văn bản gốc (Text Layer). Hệ thống sử dụng thư viện siêu tốc **PyMuPDF (fitz)** để lấy chữ trực tiếp trong chưa đầy **0.1 giây** cho 6 trang.
2. **OCR Song Song (Scanned Mode)**: Với các trang dạng ảnh quét (scanned) không có text layer, hệ thống sẽ tự động kích hoạt chế độ OCR. Bằng cách sử dụng **Multiprocessing (xử lý đa tiến trình)**, mỗi trang PDF được phân phối cho một nhân CPU khác nhau để chạy OCR độc lập thông qua **Tesseract OCR**, rút ngắn tổng thời gian xử lý xuống còn **1.2 - 2.5 giây** cho 6 trang (với CPU nhiều nhân).
3. **Không ghi ổ cứng (Zero Disk I/O)**: Các trang PDF khi convert sang ảnh sẽ được xử lý trực tiếp trên bộ nhớ RAM dưới dạng đối tượng Pillow Image trước khi đưa vào Tesseract, loại bỏ hoàn toàn độ trễ đọc/ghi đĩa.

---

## Hướng Dẫn Cài Đặt

### Bước 1: Cài đặt Tesseract OCR
Để sử dụng tính năng OCR cho các file dạng ảnh quét, bạn cần cài đặt phần mềm Tesseract OCR trên máy tính của mình.

#### 1. Trên Windows:
- Tải bản cài đặt Tesseract OCR tại: [Tesseract installer for Windows](https://github.com/UB-Mannheim/tesseract/wiki)
- Chạy file cài đặt, trong phần chọn ngôn ngữ, hãy tích chọn **Vietnamese** (hoặc thêm gói ngôn ngữ `vie`).
- Mặc định, Tesseract sẽ được cài tại `C:\Program Files\Tesseract-OCR\tesseract.exe`.
- Nếu thư mục cài đặt khác đi, hãy mở file `src/config.py` và sửa biến `TESSERACT_CMD` trỏ đúng vào file `tesseract.exe`.

#### 2. Trên Ubuntu/Linux:
```bash
sudo apt update
sudo apt install tesseract-ocr tesseract-ocr-vie -y
```

---

## Bước 2: Cài đặt thư viện Python
Trong thư mục dự án, chạy lệnh:
```bash
pip install -r requirements.txt
```

---

## Hướng Dẫn Sử Dụng

Chạy file `src/main.py` và truyền vào đường dẫn file PDF cần trích xuất:

### 1. Trích xuất tự động (tối ưu nhất)
Hệ thống sẽ tự nhận diện PDF dạng số để trích xuất trực tiếp hoặc tự chuyển đổi sang OCR nếu là PDF dạng ảnh quét:
```bash
python src/main.py "đường_dẫn_file.pdf"
```
*Kết quả văn bản trích xuất sẽ tự động được lưu cùng thư mục với tên file là `đường_dẫn_file_extracted.txt`.*

### 2. Ép buộc chạy OCR (Force OCR)
Nếu bạn muốn hệ thống luôn sử dụng quét hình ảnh OCR kể cả khi PDF có lớp text layer:
```bash
python src/main.py "đường_dẫn_file.pdf" --force-ocr
```

### 3. Tùy chỉnh DPI và chỉ định file đầu ra
```bash
python src/main.py "đường_dẫn_file.pdf" -o "output.txt" --dpi 150
```

---

---

## 4. API OCR Căn Cước Công Dân (CCCD 1 Mặt & 2 Mặt)

Hệ thống cung cấp endpoint chuyên sâu `/ocr/cccd` hỗ trợ quét nhận diện CCCD gắn chip, CCCD mã vạch, CMND:
- **Tự động nhận diện**: Mặt trước, mặt sau hoặc ảnh ghép 2 mặt / PDF 2 trang.
- **Trích xuất mặt trước**: Số CCCD/CMND, Họ tên, Ngày sinh, Giới tính, Quốc tịch, Quê quán, Nơi thường trú, Ngày hết hạn, Mã QR.
- **Trích xuất mặt sau**: **Nơi cấp / Cơ quan cấp (`place_of_issue`)**, **Ngày cấp / Thời gian cấp (`issue_date`)**, Đặc điểm nhận dạng (`personal_identification`), Dân tộc (`ethnicity`), Tôn giáo (`religion`), Mã MRZ (`mrz`).

### Khởi động Server API:
```bash
python src/server.py
```
*Server mặc định chạy tại `http://localhost:8009` (Swagger UI: `http://localhost:8009/docs`).*

### Cách gọi API:
1. **Quét cả 2 mặt (Mặt trước + Mặt sau):**
```bash
curl -X POST "http://localhost:8009/ocr/cccd" \
  -F "front_file=@/duong/dan/mat_truoc.jpg" \
  -F "back_file=@/duong/dan/mat_sau.jpg"
```

2. **Chỉ quét 1 mặt trước:**
```bash
curl -X POST "http://localhost:8009/ocr/cccd" \
  -F "front_file=@/duong/dan/mat_truoc.jpg"
```


---

## 5. OCR Đa Ảnh (Multi-Image OCR) & Gemini Vision API

Hệ thống hỗ trợ tải lên và quét OCR cùng lúc nhiều file ảnh (theo dạng **Choose Files** / Multi-file upload), chạy song song bằng mô hình **Gemini Vision** hoặc engine offline (**RapidOCR** / **Tesseract**).

### Giao Diện Web Trực Quan:
Truy cập trực tiếp: `http://localhost:8009/` trên trình duyệt:
- **Kéo thả hoặc Chọn nhiều ảnh** cùng lúc (JPG, PNG, WEBP, BMP...).
- **Xem trước ảnh thumbnail** và xóa từng ảnh tùy chọn.
- **Tự động OCR bằng Gemini Vision**: Đọc toàn bộ văn bản có trong ảnh, không cần cấu hình thêm.
- **Kết quả đa dạng**: Xem văn bản tổng hợp, xem theo từng trang ảnh, hoặc sao chép/tải về file `.txt` / `.json`.

### Gọi API Trực Tiếp (Chỉ cần truyền file ảnh):
```bash
curl -X POST "http://localhost:8009/ocr/images" \
  -F "files=@/duong/dan/anh1.jpg" \
  -F "files=@/duong/dan/anh2.png"
```

---

## 6. API OCR Đơn Thuốc / Toa Thuốc Thuần Vision (`/ocr/prescription`)

Hệ thống cung cấp endpoint chuyên biệt `/ocr/prescription` để quét và bóc tách thông tin từ **Đơn thuốc / Toa thuốc y tế** (chấp nhận cả ảnh chụp điện thoại và tệp PDF, hỗ trợ cả bản in vi tính lẫn chữ viết tay của bác sĩ).

### Đặc Điểm Nổi Bật:
1. **Thuần Vision & Phân tích trực tiếp (Zero-catalog Dependency)**: Không phụ thuộc vào database dữ liệu thuốc có sẵn, Gemini Vision đọc trực tiếp hình ảnh đơn thuốc, luận giải cả chữ viết tay và suy luận dược lý chuyên môn.
2. **Trích xuất 8 trường chuẩn cho từng loại thuốc**:
   - `ten_thuoc`: Tên thuốc / tên biệt dược ghi trên đơn.
   - `ten_hoat_chat`: Tên hoạt chất chính của thuốc (suy luận dược lý nếu đơn chỉ ghi tên biệt dược).
   - `ham_luong`: Hàm lượng / nồng độ thuốc.
   - `don_vi_tinh`: Đơn vị tính (viên, gói, ống, chai, lọ, hộp, tuýp...).
   - `so_luong`: Số lượng được kê.
   - `duong_dung`: Đường dùng (Uống, Tiêm bắp, Bôi, Nhỏ mắt...).
   - `cach_dung`: Hướng dẫn cách dùng, thao tác, quan hệ với bữa ăn (sau ăn no, trước ăn 30 phút...).
   - `thoi_gian_dung`: Lịch trình, thời điểm dùng trong ngày hoặc điều kiện sử dụng (uống khi sốt > 38*C, sáng 1 viên - tối 1 viên...).
3. **Thông tin đơn thuốc tổng quát (`prescription_info`)**: Trích xuất tên bệnh nhân, tuổi, giới tính, chẩn đoán bệnh, bác sĩ kê đơn, nơi khám, ngày kê đơn.

### Cách Gọi API:
```bash
curl -X POST "http://localhost:8009/ocr/prescription" \
  -F "files=@/duong/dan/don_thuoc.jpg"
```
*(Hoặc truyền file PDF: `-F "files=@/duong/dan/don_thuoc.pdf"`)*

### Cấu Trúc Response:
```json
{
  "status": "success",
  "total_medications": 1,
  "drug_names": [
    "Efferalgan"
  ],
  "prescription_info": {
    "patient_name": "Nguyễn Văn An",
    "age": "35",
    "gender": "Nam",
    "diagnosis": "Viêm họng cấp, sốt cao",
    "doctor_name": "BS. Trần Anh Tuấn",
    "facility_name": "BỆNH VIỆN ĐA KHOA QUỐC TẾ",
    "date": "21 tháng 10 năm 2026"
  },
  "medications": [
    {
      "stt": "1",
      "ten_thuoc": "Efferalgan",
      "ten_hoat_chat": "paracetamol",
      "ham_luong": "500mg",
      "don_vi_tinh": "viên",
      "so_luong": "10",
      "duong_dung": "Uống",
      "cach_dung": "uống sau ăn no",
      "thoi_gian_dung": "uống khi sốt hơn 38*C"
    }
  ],
  "raw_ocr_text": "...",
  "engine_used": "gemini"
}
```

---

## Cấu Trúc Mã Nguồn
- [src/server.py](file:///c:/Users/Admin/Desktop/ocr/src/server.py): FastAPI REST Server cung cấp các API: Đơn thuốc (`/ocr/prescription`), Hồ sơ Bệnh án (`/ocr/images`, `/ocr/pdf`) & CCCD (`/ocr/cccd`).
- [src/prescription_parser.py](file:///c:/Users/Admin/Desktop/ocr/src/prescription_parser.py): Engine phân tích đơn thuốc thuần Vision (8 trường dữ liệu chuẩn).
- [src/gemini_vision.py](file:///c:/Users/Admin/Desktop/ocr/src/gemini_vision.py): Gọi Gemini Vision OCR tài liệu và đơn thuốc y tế.
- [src/cccd/](file:///c:/Users/Admin/Desktop/ocr/src/cccd/): Module chuyên biệt cho OCR CCCD 2 mặt.
- [src/pdf_processor.py](file:///c:/Users/Admin/Desktop/ocr/src/pdf_processor.py): Kiểm tra định dạng PDF, trích xuất text layer và render PDF sang ảnh.
- [src/ocr_engine.py](file:///c:/Users/Admin/Desktop/ocr/src/ocr_engine.py): Chạy OCR engine cục bộ (RapidOCR / Tesseract).

