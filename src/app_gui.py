import os
import sys
import time
import json
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QTextEdit, QLabel, QFileDialog, QComboBox,
    QCheckBox, QFrame, QSplitter, QProgressBar, QMessageBox, QTabWidget
)
from PySide6.QtGui import QFont, QIcon, QPixmap, QDragEnterEvent, QDropEvent
from PySide6.QtCore import Qt, QThread, Signal, QSize

# Thêm thư mục gốc vào sys.path để chạy từ bất kỳ đâu
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Tự cấu hình encoding để in text không lỗi
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from src.main import process_pdf
from src.ocr_engine import ocr_image_file
from src.parser import parse_medical_fields, parse_medical_fields_gemini

class OCRWorker(QThread):
    """
    Luồng phụ xử lý OCR và phân tích trường thông tin (Parser) để tránh làm đơ giao diện.
    """
    finished_signal = Signal(str, dict, float)  # Trả về: (Văn bản thô, Dữ liệu cấu trúc, thời gian chạy)

    def __init__(self, file_path: str, engine_type: str, force_ocr: bool):
        super().__init__()
        self.file_path = file_path
        self.engine_type = engine_type
        self.force_ocr = force_ocr

    def run(self):
        start_time = time.perf_counter()
        ext = os.path.splitext(self.file_path.lower())[1]
        
        try:
            if ext == ".pdf":
                # Xử lý tệp PDF
                text = process_pdf(
                    pdf_path=self.file_path,
                    output_txt_path=None,
                    force_ocr=self.force_ocr,
                    engine_type=self.engine_type
                )
            else:
                # Xử lý tệp hình ảnh
                text = ocr_image_file(
                    image_path=self.file_path,
                    engine_type=self.engine_type
                )
            
            # Cấu hình đường dẫn schema.json
            schema_path = os.path.join(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")), "src", "schema.json")
            if not os.path.exists(schema_path):
                schema_path = os.path.join(os.path.dirname(__file__), "schema.json")

            # Ưu tiên sử dụng Gemini API nếu có API Key
            from src.config import GEMINI_API_KEY
            if GEMINI_API_KEY and GEMINI_API_KEY != "YOUR_API_KEY":
                structured_data = parse_medical_fields_gemini(text, schema_path)
            else:
                structured_data = parse_medical_fields(text)
            
        except Exception as e:
            text = f"[Lỗi hệ thống]: {str(e)}"
            structured_data = {"error": f"Lỗi phân tích cú pháp: {str(e)}"}
            
        elapsed = time.perf_counter() - start_time
        self.finished_signal.emit(text, structured_data, elapsed)


class ModernOCRApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.selected_file_path = ""
        self.worker = None
        self.init_ui()

    def init_ui(self):
        self.setWindowTitle("Hệ Thống Trích Xuất & OCR PDF/Ảnh Y Tế Siêu Tốc")
        self.resize(1100, 750)
        self.setMinimumSize(850, 550)
        
        # Bật kéo thả tệp vào cửa sổ
        self.setAcceptDrops(True)

        # Áp dụng stylesheet giao diện tối màu (Dark Theme) hiện đại
        self.setStyleSheet("""
            QMainWindow {
                background-color: #1e1e2e;
            }
            QWidget {
                color: #cdd6f4;
                font-family: 'Segoe UI', Arial, sans-serif;
                font-size: 13px;
            }
            QFrame#leftPanel, QFrame#rightPanel {
                background-color: #252538;
                border-radius: 12px;
                border: 1px solid #313244;
            }
            QLabel {
                font-weight: 500;
            }
            QLabel#titleLabel {
                font-size: 18px;
                font-weight: bold;
                color: #cba6f7;
            }
            QPushButton {
                background-color: #89b4fa;
                color: #11111b;
                border: none;
                padding: 10px 20px;
                border-radius: 6px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #b4befe;
            }
            QPushButton:pressed {
                background-color: #74c7ec;
            }
            QPushButton#copyBtn {
                background-color: #313244;
                color: #cdd6f4;
                border: 1px solid #45475a;
                padding: 6px 14px;
            }
            QPushButton#copyBtn:hover {
                background-color: #45475a;
            }
            QPushButton#runBtn {
                background-color: #a6e3a1;
                font-size: 14px;
            }
            QPushButton#runBtn:hover {
                background-color: #94e2d5;
            }
            QPushButton#runBtn:disabled {
                background-color: #585b70;
                color: #7f849c;
            }
            QTextEdit {
                background-color: #181825;
                color: #a6e3a1;
                border: 1px solid #313244;
                border-radius: 8px;
                padding: 10px;
                font-family: 'Consolas', 'Courier New', monospace;
                font-size: 13px;
            }
            QComboBox {
                background-color: #181825;
                border: 1px solid #313244;
                border-radius: 6px;
                padding: 6px 12px;
                color: #cdd6f4;
            }
            QComboBox::drop-down {
                border: none;
            }
            QCheckBox {
                spacing: 8px;
            }
            QCheckBox::indicator {
                width: 18px;
                height: 18px;
                border-radius: 4px;
                border: 1px solid #313244;
                background-color: #181825;
            }
            QCheckBox::indicator:checked {
                background-color: #a6e3a1;
                border: 1px solid #a6e3a1;
            }
            QProgressBar {
                border: 1px solid #313244;
                border-radius: 6px;
                text-align: center;
                background-color: #181825;
            }
            QProgressBar::chunk {
                background-color: #cba6f7;
                border-radius: 5px;
            }
            QTabWidget::pane {
                border: 1px solid #313244;
                background: #181825;
                border-radius: 8px;
            }
            QTabBar::tab {
                background: #11111b;
                border: 1px solid #313244;
                padding: 8px 16px;
                border-top-left-radius: 6px;
                border-top-right-radius: 6px;
                color: #a6adc8;
            }
            QTabBar::tab:selected {
                background: #181825;
                color: #cba6f7;
                border-bottom-color: #181825;
                font-weight: bold;
            }
        """)

        # Main Layout
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QHBoxLayout(main_widget)
        main_layout.setContentsMargins(15, 15, 15, 15)

        # Sử dụng QSplitter để người dùng tự điều chỉnh độ rộng 2 phần
        splitter = QSplitter(Qt.Horizontal)
        main_layout.addWidget(splitter)

        # ----------------- PHẦN 1: BÊN TRÁI (CHỌN FILE & CONFIG) -----------------
        left_panel = QFrame()
        left_panel.setObjectName("leftPanel")
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(20, 20, 20, 20)
        left_layout.setSpacing(15)

        # Tiêu đề cột trái
        title_label = QLabel("Tài Liệu Đầu Vào")
        title_label.setObjectName("titleLabel")
        left_layout.addWidget(title_label)

        # Vùng Kéo thả & Chọn tệp
        self.drop_area = QFrame()
        self.drop_area.setStyleSheet("""
            QFrame {
                border: 2px dashed #45475a;
                border-radius: 10px;
                background-color: #181825;
            }
            QFrame:hover {
                border: 2px dashed #89b4fa;
            }
        """)
        drop_layout = QVBoxLayout(self.drop_area)
        drop_layout.setAlignment(Qt.AlignCenter)
        
        self.preview_label = QLabel("Kéo & thả file PDF/Ảnh vào đây\nhoặc nhấn nút chọn tệp bên dưới")
        self.preview_label.setAlignment(Qt.AlignCenter)
        self.preview_label.setStyleSheet("color: #a6adc8; font-size: 13px; line-height: 20px;")
        drop_layout.addWidget(self.preview_label)
        
        left_layout.addWidget(self.drop_area, stretch=1)

        # Nút chọn tệp
        self.select_btn = QPushButton("Chọn Tệp (PDF / Hình Ảnh)")
        self.select_btn.setCursor(Qt.PointingHandCursor)
        self.select_btn.clicked.connect(self.select_file)
        left_layout.addWidget(self.select_btn)

        # Label hiển thị đường dẫn đã chọn
        self.path_label = QLabel("Chưa chọn tệp tin nào.")
        self.path_label.setWordWrap(True)
        self.path_label.setStyleSheet("color: #bac2de; font-style: italic;")
        left_layout.addWidget(self.path_label)

        # Đường gạch ngang phân cách
        divider = QFrame()
        divider.setFrameShape(QFrame.HLine)
        divider.setStyleSheet("color: #313244;")
        left_layout.addWidget(divider)

        # Cấu hình OCR Engine
        engine_layout = QHBoxLayout()
        engine_label = QLabel("Công cụ OCR:")
        self.engine_combo = QComboBox()
        self.engine_combo.addItems(["RapidOCR (Khuyên dùng - Nhanh, Local)", "Tesseract OCR (Yêu cầu cài đặt)"])
        engine_layout.addWidget(engine_label)
        engine_layout.addWidget(self.engine_combo)
        left_layout.addLayout(engine_layout)

        # Checkbox bắt buộc OCR
        self.force_ocr_cb = QCheckBox("Ép buộc chạy OCR (bỏ qua Text Layer gốc)")
        self.force_ocr_cb.setToolTip("Sử dụng khi file PDF convert bị lỗi font hoặc chứa ảnh chụp chèn vào file Word")
        left_layout.addWidget(self.force_ocr_cb)

        # Thanh tiến trình
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        left_layout.addWidget(self.progress_bar)

        # Nút Bắt đầu OCR
        self.run_btn = QPushButton("Bắt Đầu Trích Xuất Chữ")
        self.run_btn.setObjectName("runBtn")
        self.run_btn.setCursor(Qt.PointingHandCursor)
        self.run_btn.setEnabled(False)
        self.run_btn.clicked.connect(self.start_ocr)
        left_layout.addWidget(self.run_btn)

        # ----------------- PHẦN 2: BÊN PHẢI (KẾT QUẢ ĐẦU RA - TABBED) -----------------
        right_panel = QFrame()
        right_panel.setObjectName("rightPanel")
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(20, 20, 20, 20)
        right_layout.setSpacing(15)

        # Header cột phải
        right_header = QHBoxLayout()
        output_title = QLabel("Kết Quả Trích Xuất")
        output_title.setStyleSheet("font-size: 16px; font-weight: bold; color: #89b4fa;")
        
        self.copy_btn = QPushButton("Sao Chép")
        self.copy_btn.setObjectName("copyBtn")
        self.copy_btn.setCursor(Qt.PointingHandCursor)
        self.copy_btn.clicked.connect(self.copy_to_clipboard)
        
        right_header.addWidget(output_title)
        right_header.addStretch()
        right_header.addWidget(self.copy_btn)
        right_layout.addLayout(right_header)

        # Sử dụng TabWidget để hiển thị cả Văn bản thô và Dữ liệu có cấu trúc
        self.tabs = QTabWidget()
        
        # Tab 1: Dữ liệu cấu trúc (Mặc định)
        self.structured_output = QTextEdit()
        self.structured_output.setPlaceholderText("Các trường thông tin y tế trích xuất dạng JSON (Tuổi, giới tính, huyết áp, cholesterol, bệnh lý kèm theo...) sẽ hiển thị tại đây...")
        self.tabs.addTab(self.structured_output, "Trường Dữ Liệu (JSON)")

        # Tab 2: Văn bản thô
        self.text_output = QTextEdit()
        self.text_output.setStyleSheet("QTextEdit { color: #cdd6f4; }")
        self.text_output.setPlaceholderText("Toàn bộ nội dung văn bản thô trích xuất từ tài liệu...")
        self.tabs.addTab(self.text_output, "Văn Bản Thô (Raw Text)")

        right_layout.addWidget(self.tabs)

        # Label hiển thị thời gian chạy và vị trí lưu tệp
        self.status_label = QLabel("Trạng thái: Sẵn sàng")
        self.status_label.setStyleSheet("color: #a6adc8;")
        right_layout.addWidget(self.status_label)

        # Thêm 2 panel vào Splitter
        splitter.addWidget(left_panel)
        splitter.addWidget(right_panel)
        
        # Đặt tỷ lệ mặc định cho 2 panel (45% bên trái, 55% bên phải)
        splitter.setSizes([450, 550])

    # ----------------- LOGIC XỬ LÝ -----------------

    def select_file(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Chọn Tệp Đầu Vào",
            "",
            "Tệp được hỗ trợ (*.pdf *.png *.jpg *.jpeg *.bmp *.tiff)"
        )
        if file_path:
            self.load_file(file_path)

    def load_file(self, file_path: str):
        self.selected_file_path = file_path
        self.path_label.setText(file_path)
        self.run_btn.setEnabled(True)
        self.status_label.setText("Trạng thái: Đã chọn tệp. Sẵn sàng quét.")

        # Hiển thị ảnh xem trước nếu tệp là định dạng ảnh
        ext = os.path.splitext(file_path.lower())[1]
        if ext in [".png", ".jpg", ".jpeg", ".bmp", ".tiff"]:
            pixmap = QPixmap(file_path)
            scaled_pixmap = pixmap.scaled(
                self.drop_area.size() - QSize(20, 20),
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation
            )
            self.preview_label.setPixmap(scaled_pixmap)
        else:
            self.preview_label.setText(f"Tài liệu PDF:\n{os.path.basename(file_path)}")

    # Sự kiện Kéo và thả file
    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent):
        urls = event.mimeData().urls()
        if urls:
            file_path = urls[0].toLocalFile()
            ext = os.path.splitext(file_path.lower())[1]
            if ext in [".pdf", ".png", ".jpg", ".jpeg", ".bmp", ".tiff"]:
                self.load_file(file_path)
                event.acceptProposedAction()
            else:
                QMessageBox.warning(
                    self,
                    "Định dạng không được hỗ trợ",
                    "Hệ thống chỉ hỗ trợ kéo thả tệp PDF hoặc hình ảnh (PNG, JPG, JPEG, BMP, TIFF)."
                )

    def start_ocr(self):
        if not self.selected_file_path:
            return

        engine_index = self.engine_combo.currentIndex()
        engine_type = "rapidocr" if engine_index == 0 else "tesseract"
        force_ocr = self.force_ocr_cb.isChecked()

        # Cập nhật UI trạng thái đang quét
        self.run_btn.setEnabled(False)
        self.select_btn.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, 0)
        self.status_label.setText("Trạng thái: Đang xử lý tài liệu và phân tích cấu trúc...")
        self.text_output.clear()
        self.structured_output.clear()

        # Tạo luồng xử lý riêng biệt
        self.worker = OCRWorker(self.selected_file_path, engine_type, force_ocr)
        self.worker.finished_signal.connect(self.ocr_finished)
        self.worker.start()

    def ocr_finished(self, text: str, structured_data: dict, elapsed_time: float):
        # Khôi phục trạng thái UI
        self.run_btn.setEnabled(True)
        self.select_btn.setEnabled(True)
        self.progress_bar.setVisible(False)
        
        # 1. Hiển thị văn bản thô
        self.text_output.setPlainText(text)
        
        # 2. Hiển thị dữ liệu dạng JSON có cấu trúc
        json_str = json.dumps(structured_data, indent=2, ensure_ascii=False)
        self.structured_output.setPlainText(json_str)
        self.tabs.setCurrentIndex(0)  # Tự động nhảy sang Tab dữ liệu cấu trúc
        
        # 3. Tự động lưu kết quả ra file JSON bên cạnh file gốc
        if self.selected_file_path:
            base, _ = os.path.splitext(self.selected_file_path)
            json_path = f"{base}_fields.json"
            try:
                with open(json_path, "w", encoding="utf-8") as f:
                    f.write(json_str)
                self.status_label.setText(
                    f"Trạng thái: Hoàn tất trong {elapsed_time:.2f}s. Đã xuất tệp trường dữ liệu: {os.path.basename(json_path)}"
                )
            except Exception as e:
                self.status_label.setText(f"Trạng thái: Hoàn tất ({elapsed_time:.2f}s) nhưng lỗi ghi tệp JSON: {e}")

    def copy_to_clipboard(self):
        # Kiểm tra xem đang mở tab nào để copy dữ liệu ở tab đó
        current_tab_idx = self.tabs.currentIndex()
        text = self.structured_output.toPlainText() if current_tab_idx == 0 else self.text_output.toPlainText()
        
        if text:
            clipboard = QApplication.clipboard()
            clipboard.setText(text)
            self.status_label.setText("Trạng thái: Đã sao chép văn bản của tab hiện tại vào Clipboard!")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = ModernOCRApp()
    window.show()
    sys.exit(app.exec())
