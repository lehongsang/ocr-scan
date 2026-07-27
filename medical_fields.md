# Danh Sách Các Trường Thông Tin Trong Biểu Mẫu Y Tế

Dưới đây là bảng tổng hợp các trường thông tin y tế được thiết kế dựa trên các ảnh chụp màn hình biểu mẫu giao diện của bạn:

---

## 1. PHÂN LOẠI BỆNH LÝ NỀN
* **Bệnh lý nền**: `Không có bệnh lý nền` / `Có bệnh lý nền` (Kiểu dữ liệu: Boolean)

---

## 2. A. CHỈ SỐ SINH LÝ CƠ BẢN
| Tên Trường | Mô tả | Đơn vị / Lựa chọn | Bắt buộc | Ví dụ mẫu |
| :--- | :--- | :--- | :---: | :--- |
| **Tuổi** | Tuổi của bệnh nhân | tuổi | Có | `45` |
| **Giới tính** | Giới tính | `Nam` / `Nữ` | Có | `Nam` |
| **Hút thuốc lá** | Tình trạng đang hút thuốc | `Có` / `Không` | Có | `Không` (Đang chọn) |
| **Huyết áp tâm thu (SBP)** | Huyết áp tâm thu | mmHg | Có | `145` |
| **Cholesterol toàn phần** | Hàm lượng Cholesterol toàn phần | mmol/L | Có | `7.0` |
| **HDL-Cholesterol** | Hàm lượng HDL-Cholesterol | mmol/L | Có | `1.5` |

---

## 3. TỔN THƯƠNG CƠ QUAN ĐÍCH (Hình 2)
| Tên Trường | Kiểu dữ liệu | Lựa chọn | Ví dụ mẫu |
| :--- | :--- | :--- | :--- |
| **Phì đại thất trái** | Boolean | `Có` / `Không` | `Không` |
| **Tổn thương đáy mắt** | Boolean | `Có` / `Không` | `Không` |
| **Albumin / Microalbumin niệu** | Boolean | `Có` / `Không` | `Không` |
| **Tổn thương thầm lặng trên não** | Boolean | `Có` / `Không` | `Không` |

---

## 4. C. BỆNH LÝ MẠN TÍNH KÈM THEO (CHRONIC DISEASES)
| Tên Trường | Mô tả | Đơn vị / Lựa chọn | Ví dụ mẫu |
| :--- | :--- | :--- | :--- |
| **Độ thanh thải cầu thận (eGFR)** | eGFR | mL/min/1.73m² | `35` |
| **Tỷ lệ Albumin/Creatinin (ACR)** | ACR | mg/g | `15` |
| **Đái tháo đường (Diabetes)** | Bệnh tiểu đường | `Có` / `Không` | `Không` |
| **Đột quỵ não (Stroke)** | Bệnh tai biến mạch máu não | `Có` / `Không` | `Không` |
| **Nhồi máu cơ tim** | Bệnh tim | `Có` / `Không` | `Không` |
| **Hội chứng vành cấp** | Hội chứng mạch vành cấp | `Có` / `Không` | `Không` |
| **Bệnh lý mạch vành** | Bệnh mạch vành | `Có` / `Không` | `Không` |
| **Thiếu máu cục bộ não thoáng qua (TIA)** | Thiếu máu não thoáng qua | `Có` / `Không` | `Không` |
| **Phình động mạch chủ** | Phình động mạch chủ | `Có` / `Không` | `Không` |
| **Bệnh mạch máu ngoại vi** | Bệnh mạch máu ngoại biên | `Có` / `Không` | `Không` |
| **Vữa xơ mạch máu** | Xơ vữa động mạch | `Có` / `Không` | `Không` |
| **Tăng Cholesterol máu gia đình** | Tăng cholesterol gia truyền | `Có` / `Không` | `Không` |

---

## 5. THÔNG TIN CÁ NHÂN (Hình 3)
| Tên Trường | Mô tả | Định dạng / Lựa chọn | Bắt buộc | Ví dụ mẫu |
| :--- | :--- | :--- | :---: | :--- |
| **Họ và tên** | Tên đầy đủ bệnh nhân | Chữ | Có | `Nguyễn Văn A` |
| **Ngày sinh** | Ngày tháng năm sinh | `dd/mm/yyyy` | Không | `21/07/2000` |
| **Giới tính** | Giới tính mở rộng | `Nam` / `Nữ` / `Khác` | Không | `Nam` |
| **CCCD/CMND** | Số căn cước / định danh | Số / Chữ | Không | `012345678901` |
| **Trạng thái hồ sơ** | Trạng thái hoạt động | `Hoạt động` / `Tạm dừng` | Có | `Hoạt động` |

---

## 6. THÔNG TIN LIÊN HỆ & ĐỊA CHỈ (Hình 3)
| Tên Trường | Mô tả | Định dạng / Lựa chọn | Ví dụ mẫu |
| :--- | :--- | :--- | :--- |
| **Số điện thoại** | Số điện thoại liên lạc | Số | `0912345678` |
| **Địa chỉ Email** | Thư điện tử | Email (`example@gmail.com`) | `example@gmail.com` |
| **Tỉnh / Thành phố** | Tỉnh hoặc TP trực thuộc TW | Lựa chọn (Dropdown) | `Hà Nội` |
| **Quận / Huyện** | Quận huyện trực thuộc tỉnh | Lựa chọn (Dropdown) | `Cầu Giấy` |
| **Số nhà, tên đường** | Thôn, xóm, số nhà, tên đường | Chữ | `123 Nguyễn Huệ` |
| **Địa chỉ đầy đủ** | Địa chỉ kết hợp hoặc tùy chỉnh | Chữ | `123 Nguyễn Huệ, Quận Cầu Giấy, Hà Nội` |

---

## 7. CHỈ SỐ & TIỀN SỬ SỨC KHỎE (Hình 3)
| Tên Trường | Mô tả | Đơn vị / Lựa chọn | Ví dụ mẫu |
| :--- | :--- | :--- | :--- |
| **Chiều cao** | Chiều cao bệnh nhân | cm | `170` |
| **Cân nặng** | Cân nặng bệnh nhân | kg | `65` |
| **Nhóm máu** | Hệ nhóm máu | `A+`, `A-`, `B+`, `B-`, `O+`, `O-`, `AB+`, `AB-` | `O+` |
| **Tiền sử bệnh lý** | Tiền sử bệnh hoặc bệnh hiện tại | Ghi chú văn bản (Textarea) | `Cao huyết áp nhẹ...` |

---

## 8. D. THÔNG TIN NHÓM CHĂM SÓC (TUỲ CHỌN)
* **Mã nhóm chăm sóc (Care Group Code)**: Định dạng chuỗi ký tự (vd: `DG8F2K9Q1M`)
