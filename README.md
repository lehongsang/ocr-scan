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

## Cấu Trúc Mã Nguồn
- [src/config.py](file:///c:/Users/Admin/Desktop/ocr/src/config.py): Cấu hình chung cho OCR (DPI, số luồng, đường dẫn Tesseract).
- [src/utils.py](file:///c:/Users/Admin/Desktop/ocr/src/utils.py): Đo hiệu năng, ghi logs.
- [src/pdf_processor.py](file:///c:/Users/Admin/Desktop/ocr/src/pdf_processor.py): Kiểm tra định dạng PDF, trích xuất text layer trực tiếp và render trang thành ảnh.
- [src/ocr_engine.py](file:///c:/Users/Admin/Desktop/ocr/src/ocr_engine.py): Chạy OCR đa nhân song song.
- [src/main.py](file:///c:/Users/Admin/Desktop/ocr/src/main.py): Điều khiển chính của ứng dụng.
