# -*- coding: utf-8 -*-
"""
Giao diện Web hiện đại cho ứng dụng OCR chọn nhiều ảnh (Multi-image OCR)
Sử dụng Gemini Vision API để bóc tách toàn bộ văn bản trong ảnh.
"""

def get_html_ui() -> str:
    return """<!DOCTYPE html>
<html lang="vi">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Hệ Thống OCR Đa Ảnh | Gemini Vision</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@300;400;500;600;700;800&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
    <style>
        :root {
            --bg-primary: #0a0e17;
            --bg-secondary: #121826;
            --bg-card: rgba(22, 30, 49, 0.75);
            --bg-card-hover: rgba(30, 41, 67, 0.85);
            --border-color: rgba(255, 255, 255, 0.08);
            --border-active: rgba(99, 102, 241, 0.5);
            --primary: #6366f1;
            --primary-gradient: linear-gradient(135deg, #6366f1 0%, #a855f7 50%, #ec4899 100%);
            --text-main: #f8fafc;
            --text-muted: #94a3b8;
            --success: #10b981;
            --error: #ef4444;
            --radius-lg: 16px;
            --radius-md: 12px;
            --radius-sm: 8px;
            --transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1);
        }

        * {
            box-sizing: border-box;
            margin: 0;
            padding: 0;
        }

        body {
            font-family: 'Plus Jakarta Sans', sans-serif;
            background-color: var(--bg-primary);
            color: var(--text-main);
            min-height: 100vh;
            display: flex;
            flex-direction: column;
            overflow-x: hidden;
            background-image: 
                radial-gradient(circle at 15% 20%, rgba(99, 102, 241, 0.12) 0%, transparent 40%),
                radial-gradient(circle at 85% 80%, rgba(168, 85, 247, 0.12) 0%, transparent 40%);
            background-attachment: fixed;
        }

        header {
            border-bottom: 1px solid var(--border-color);
            backdrop-filter: blur(12px);
            background: rgba(10, 14, 23, 0.8);
            position: sticky;
            top: 0;
            z-index: 50;
            padding: 16px 32px;
            display: flex;
            align-items: center;
            justify-content: space-between;
        }

        .brand {
            display: flex;
            align-items: center;
            gap: 12px;
            text-decoration: none;
        }

        .brand-icon {
            width: 40px;
            height: 40px;
            background: var(--primary-gradient);
            border-radius: 10px;
            display: flex;
            align-items: center;
            justify-content: center;
            box-shadow: 0 4px 15px rgba(99, 102, 241, 0.4);
        }

        .brand-icon svg {
            width: 22px;
            height: 22px;
            fill: white;
        }

        .brand-text h1 {
            font-size: 1.15rem;
            font-weight: 700;
            letter-spacing: -0.02em;
            background: linear-gradient(135deg, #ffffff 30%, #cbd5e1 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }

        .brand-text p {
            font-size: 0.75rem;
            color: var(--text-muted);
        }

        .badge-live {
            display: inline-flex;
            align-items: center;
            gap: 6px;
            background: rgba(16, 185, 129, 0.12);
            color: var(--success);
            padding: 5px 12px;
            border-radius: 30px;
            font-size: 0.75rem;
            font-weight: 600;
            border: 1px solid rgba(16, 185, 129, 0.3);
        }

        .badge-live::before {
            content: "";
            width: 7px;
            height: 7px;
            border-radius: 50%;
            background: var(--success);
            box-shadow: 0 0 8px var(--success);
            animation: pulse 2s infinite;
        }

        @keyframes pulse {
            0%, 100% { opacity: 1; transform: scale(1); }
            50% { opacity: 0.4; transform: scale(0.85); }
        }

        main {
            flex: 1;
            max-width: 1280px;
            width: 100%;
            margin: 0 auto;
            padding: 32px 24px;
            display: grid;
            grid-template-columns: 1fr 1.1fr;
            gap: 28px;
        }

        @media (max-width: 960px) {
            main {
                grid-template-columns: 1fr;
            }
        }

        .card {
            background: var(--bg-card);
            border: 1px solid var(--border-color);
            border-radius: var(--radius-lg);
            padding: 24px;
            backdrop-filter: blur(16px);
            box-shadow: 0 8px 32px rgba(0, 0, 0, 0.25);
            display: flex;
            flex-direction: column;
            gap: 20px;
            transition: var(--transition);
        }

        .card-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            border-bottom: 1px solid var(--border-color);
            padding-bottom: 14px;
        }

        .card-title {
            font-size: 1.05rem;
            font-weight: 700;
            display: flex;
            align-items: center;
            gap: 10px;
            color: #f1f5f9;
        }

        .card-title svg {
            width: 20px;
            height: 20px;
            stroke: var(--primary);
        }

        /* Dropzone */
        .dropzone {
            border: 2px dashed rgba(99, 102, 241, 0.35);
            border-radius: var(--radius-md);
            padding: 42px 20px;
            text-align: center;
            cursor: pointer;
            background: rgba(15, 23, 42, 0.4);
            transition: var(--transition);
            position: relative;
        }

        .dropzone:hover, .dropzone.dragover {
            border-color: var(--primary);
            background: rgba(99, 102, 241, 0.08);
            transform: translateY(-2px);
        }

        .dropzone input[type="file"] {
            position: absolute;
            inset: 0;
            opacity: 0;
            cursor: pointer;
            width: 100%;
            height: 100%;
        }

        .dropzone-icon {
            width: 58px;
            height: 58px;
            margin: 0 auto 16px;
            background: rgba(99, 102, 241, 0.15);
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            color: var(--primary);
            transition: var(--transition);
        }

        .dropzone:hover .dropzone-icon {
            transform: scale(1.1);
            background: var(--primary-gradient);
            color: white;
        }

        .dropzone h3 {
            font-size: 1.05rem;
            font-weight: 600;
            margin-bottom: 8px;
        }

        .dropzone p {
            font-size: 0.8rem;
            color: var(--text-muted);
        }

        /* File List Preview */
        .file-list {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(130px, 1fr));
            gap: 12px;
            max-height: 260px;
            overflow-y: auto;
            padding: 4px;
        }

        .file-item {
            background: rgba(15, 23, 42, 0.6);
            border: 1px solid var(--border-color);
            border-radius: var(--radius-sm);
            padding: 8px;
            position: relative;
            display: flex;
            flex-direction: column;
            gap: 6px;
            transition: var(--transition);
        }

        .file-item:hover {
            border-color: var(--border-active);
        }

        .file-thumb {
            width: 100%;
            height: 85px;
            object-fit: cover;
            border-radius: 4px;
            background: #000;
        }

        .file-info {
            font-size: 0.72rem;
            color: var(--text-muted);
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
        }

        .file-remove {
            position: absolute;
            top: 4px;
            right: 4px;
            background: rgba(239, 68, 68, 0.85);
            color: white;
            border: none;
            border-radius: 50%;
            width: 20px;
            height: 20px;
            font-size: 13px;
            display: flex;
            align-items: center;
            justify-content: center;
            cursor: pointer;
            opacity: 0.8;
            transition: var(--transition);
        }

        .file-remove:hover {
            opacity: 1;
            transform: scale(1.1);
        }

        /* Primary Button */
        .btn-primary {
            background: var(--primary-gradient);
            color: white;
            border: none;
            border-radius: var(--radius-md);
            padding: 14px 24px;
            font-size: 0.95rem;
            font-weight: 700;
            cursor: pointer;
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 10px;
            box-shadow: 0 4px 20px rgba(99, 102, 241, 0.35);
            transition: var(--transition);
            margin-top: auto;
        }

        .btn-primary:hover:not(:disabled) {
            transform: translateY(-2px);
            box-shadow: 0 6px 28px rgba(99, 102, 241, 0.5);
        }

        .btn-primary:disabled {
            opacity: 0.5;
            cursor: not-allowed;
            transform: none;
        }

        /* Results Pane */
        .results-pane {
            display: flex;
            flex-direction: column;
            gap: 16px;
            height: 100%;
        }

        .tab-bar {
            display: flex;
            gap: 8px;
            border-bottom: 1px solid var(--border-color);
            padding-bottom: 8px;
        }

        .tab-btn {
            background: transparent;
            border: none;
            color: var(--text-muted);
            font-family: inherit;
            font-size: 0.85rem;
            font-weight: 600;
            padding: 6px 14px;
            border-radius: var(--radius-sm);
            cursor: pointer;
            transition: var(--transition);
        }

        .tab-btn:hover {
            color: white;
            background: rgba(255, 255, 255, 0.05);
        }

        .tab-btn.active {
            color: white;
            background: var(--primary);
        }

        .result-actions {
            display: flex;
            gap: 8px;
            margin-left: auto;
        }

        .btn-sm {
            background: rgba(255, 255, 255, 0.07);
            border: 1px solid var(--border-color);
            color: #e2e8f0;
            font-family: inherit;
            font-size: 0.75rem;
            font-weight: 600;
            padding: 6px 12px;
            border-radius: 6px;
            cursor: pointer;
            display: inline-flex;
            align-items: center;
            gap: 6px;
            transition: var(--transition);
        }

        .btn-sm:hover {
            background: rgba(255, 255, 255, 0.15);
            border-color: rgba(255, 255, 255, 0.2);
        }

        .output-box {
            flex: 1;
            background: #0d1117;
            border: 1px solid var(--border-color);
            border-radius: var(--radius-md);
            padding: 18px;
            font-family: 'JetBrains Mono', monospace;
            font-size: 0.84rem;
            line-height: 1.6;
            color: #e6edf3;
            overflow-y: auto;
            max-height: 540px;
            min-height: 380px;
            white-space: pre-wrap;
            position: relative;
        }

        .output-empty {
            height: 100%;
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            color: var(--text-muted);
            text-align: center;
            gap: 12px;
            font-family: 'Plus Jakarta Sans', sans-serif;
        }

        .output-empty svg {
            width: 48px;
            height: 48px;
            stroke: rgba(255, 255, 255, 0.15);
        }

        /* Per-image result card */
        .page-result-card {
            background: rgba(15, 23, 42, 0.8);
            border: 1px solid var(--border-color);
            border-radius: var(--radius-sm);
            padding: 14px;
            margin-bottom: 12px;
        }

        .page-result-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 8px;
            font-size: 0.75rem;
            font-weight: 700;
            color: #818cf8;
        }

        .page-result-badge {
            background: rgba(16, 185, 129, 0.15);
            color: var(--success);
            padding: 2px 8px;
            border-radius: 4px;
            font-size: 0.7rem;
        }

        .page-result-text {
            white-space: pre-wrap;
            font-family: 'JetBrains Mono', monospace;
            font-size: 0.82rem;
            color: #cbd5e1;
            background: #0a0e17;
            padding: 10px;
            border-radius: 6px;
            max-height: 220px;
            overflow-y: auto;
        }

        /* Spinner & Progress */
        .spinner {
            width: 18px;
            height: 18px;
            border: 2px solid rgba(255, 255, 255, 0.3);
            border-top-color: white;
            border-radius: 50%;
            animation: spin 0.8s linear infinite;
            display: inline-block;
        }

        @keyframes spin {
            to { transform: rotate(360deg); }
        }

        .progress-bar-container {
            width: 100%;
            background: rgba(255, 255, 255, 0.08);
            border-radius: 10px;
            height: 6px;
            overflow: hidden;
            display: none;
        }

        .progress-bar-inner {
            height: 100%;
            width: 30%;
            background: var(--primary-gradient);
            border-radius: 10px;
            animation: progressIndeterminate 1.5s infinite ease-in-out;
        }

        @keyframes progressIndeterminate {
            0% { transform: translateX(-100%); width: 30%; }
            50% { width: 60%; }
            100% { transform: translateX(350%); width: 30%; }
        }
    </style>
</head>
<body>
    <header>
        <div class="brand">
            <div class="brand-icon">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <path d="M4 7V4h3M17 4h3v3M4 17v3h3M20 17v3h-3M9 12h6M12 9v6" stroke-linecap="round"/>
                </svg>
            </div>
            <div class="brand-text">
                <h1>Hệ Thống OCR Đa Ảnh (Multi-Image)</h1>
                <p>Gemini Vision API • Tự động trích xuất toàn bộ văn bản trong ảnh</p>
            </div>
        </div>
        <div class="badge-live">
            <span>Gemini Vision</span>
        </div>
    </header>

    <main>
        <!-- Cột Bên Trái: Tải ảnh (Choose Files) -->
        <section class="card">
            <div class="card-header">
                <div class="card-title">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <rect x="3" y="3" width="18" height="18" rx="2" ry="2"/>
                        <circle cx="8.5" cy="8.5" r="1.5"/>
                        <polyline points="21 15 16 10 5 21"/>
                    </svg>
                    <span>Chọn Tập Tin Ảnh (Choose Files)</span>
                </div>
                <span id="fileCountBadge" style="font-size: 0.75rem; color: var(--text-muted);">0 tệp đã chọn</span>
            </div>

            <div class="dropzone" id="dropzone">
                <input type="file" id="fileInput" multiple accept="image/png,image/jpeg,image/webp,image/bmp,image/tiff">
                <div class="dropzone-icon">
                    <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
                        <polyline points="17 8 12 3 7 8"/>
                        <line x1="12" y1="3" x2="12" y2="15"/>
                    </svg>
                </div>
                <h3>Kéo thả hoặc Nhấp để Chọn Ảnh</h3>
                <p>Có thể chọn cùng lúc nhiều ảnh (JPG, PNG, WEBP, BMP...)</p>
            </div>

            <!-- Danh sách preview file -->
            <div class="file-list" id="fileList" style="display: none;"></div>

            <div class="progress-bar-container" id="progressBar">
                <div class="progress-bar-inner"></div>
            </div>

            <button type="button" class="btn-primary" id="btnSubmit" disabled>
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <polygon points="5 3 19 12 5 21 5 3"/>
                </svg>
                <span>Bắt Đầu Quét OCR Toàn Bộ</span>
            </button>
        </section>

        <!-- Cột Bên Phải: Toàn Bộ Text OCR Được -->
        <section class="card results-pane">
            <div class="card-header">
                <div class="card-title">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <polyline points="4 7 4 4 20 4 20 7"/>
                        <line x1="9" y1="20" x2="15" y2="20"/>
                        <line x1="12" y1="4" x2="12" y2="20"/>
                    </svg>
                    <span>Toàn Bộ Văn Bản Đọc Được</span>
                </div>
                <div class="result-actions">
                    <button class="btn-sm" id="btnCopy" title="Sao chép">
                        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                            <rect x="9" y="9" width="13" height="13" rx="2" ry="2"/>
                            <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/>
                        </svg>
                        <span>Sao chép</span>
                    </button>
                    <button class="btn-sm" id="btnDownload" title="Tải về .txt">
                        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                            <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
                            <polyline points="7 10 12 15 17 10"/>
                            <line x1="12" y1="15" x2="12" y2="3"/>
                        </svg>
                        <span>Tải .TXT</span>
                    </button>
                </div>
            </div>

            <div class="tab-bar">
                <button class="tab-btn active" data-tab="combined">Văn Bản Tổng Hợp</button>
                <button class="tab-btn" data-tab="pages">Từng Trang Ảnh</button>
                <button class="tab-btn" data-tab="raw">JSON Thô</button>
            </div>

            <div class="output-box" id="outputBox">
                <div class="output-empty">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
                        <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
                        <polyline points="14 2 14 8 20 8"/>
                        <line x1="16" y1="13" x2="8" y2="13"/>
                        <line x1="16" y1="17" x2="8" y2="17"/>
                        <polyline points="10 9 9 9 8 9"/>
                    </svg>
                    <p>Chưa có dữ liệu. Vui lòng chọn ảnh và nhấn "Bắt Đầu Quét OCR Toàn Bộ".</p>
                </div>
            </div>
        </section>
    </main>

    <script>
        let selectedFiles = [];
        let lastResultData = null;
        let currentTab = "combined";

        const fileInput = document.getElementById("fileInput");
        const dropzone = document.getElementById("dropzone");
        const fileList = document.getElementById("fileList");
        const fileCountBadge = document.getElementById("fileCountBadge");
        const btnSubmit = document.getElementById("btnSubmit");
        const progressBar = document.getElementById("progressBar");
        const outputBox = document.getElementById("outputBox");

        // Drag & drop
        ["dragenter", "dragover"].forEach(name => {
            dropzone.addEventListener(name, (e) => {
                e.preventDefault();
                dropzone.classList.add("dragover");
            });
        });

        ["dragleave", "drop"].forEach(name => {
            dropzone.addEventListener(name, (e) => {
                e.preventDefault();
                dropzone.classList.remove("dragover");
            });
        });

        dropzone.addEventListener("drop", (e) => {
            if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
                addFiles(Array.from(e.dataTransfer.files));
            }
        });

        fileInput.addEventListener("change", (e) => {
            if (e.target.files && e.target.files.length > 0) {
                addFiles(Array.from(e.target.files));
            }
        });

        function addFiles(files) {
            const validImages = files.filter(f => f.type.startsWith("image/"));
            if (validImages.length === 0) {
                alert("Vui lòng chỉ chọn các tệp tin hình ảnh (PNG, JPG, WEBP, BMP, ...)");
                return;
            }
            selectedFiles = [...selectedFiles, ...validImages];
            renderFileList();
        }

        function removeFile(index) {
            selectedFiles.splice(index, 1);
            renderFileList();
        }

        function renderFileList() {
            fileList.innerHTML = "";
            fileCountBadge.textContent = `${selectedFiles.length} tệp đã chọn`;
            
            if (selectedFiles.length === 0) {
                fileList.style.display = "none";
                btnSubmit.disabled = true;
                return;
            }

            fileList.style.display = "grid";
            btnSubmit.disabled = false;

            selectedFiles.forEach((file, idx) => {
                const item = document.createElement("div");
                item.className = "file-item";
                
                const thumb = document.createElement("img");
                thumb.className = "file-thumb";
                thumb.src = URL.createObjectURL(file);
                
                const info = document.createElement("div");
                info.className = "file-info";
                info.title = file.name;
                info.textContent = `${idx + 1}. ${file.name}`;

                const rmBtn = document.createElement("button");
                rmBtn.className = "file-remove";
                rmBtn.innerHTML = "×";
                rmBtn.title = "Xóa ảnh này";
                rmBtn.onclick = (e) => {
                    e.stopPropagation();
                    removeFile(idx);
                };

                item.appendChild(rmBtn);
                item.appendChild(thumb);
                item.appendChild(info);
                fileList.appendChild(item);
            });
        }

        // Tabs kết quả
        document.querySelectorAll(".tab-btn").forEach(btn => {
            btn.addEventListener("click", () => {
                document.querySelectorAll(".tab-btn").forEach(b => b.classList.remove("active"));
                btn.classList.add("active");
                currentTab = btn.dataset.tab;
                renderResultsView();
            });
        });

        // Submit OCR (Chỉ truyền files)
        btnSubmit.addEventListener("click", async () => {
            if (selectedFiles.length === 0) return;

            btnSubmit.disabled = true;
            btnSubmit.innerHTML = `<span class="spinner"></span> <span>Đang xử lý ${selectedFiles.length} ảnh bằng Gemini Vision...</span>`;
            progressBar.style.display = "block";

            outputBox.innerHTML = `
                <div class="output-empty">
                    <span class="spinner" style="width: 32px; height: 32px; border-width: 3px;"></span>
                    <p>Đang gửi ảnh tới mô hình <strong>Gemini Vision</strong>...</p>
                    <p style="font-size: 0.75rem; color: #64748b;">Hệ thống đang trích xuất toàn bộ văn bản có trong ảnh...</p>
                </div>
            `;

            const formData = new FormData();
            selectedFiles.forEach(file => {
                formData.append("files", file);
            });

            try {
                const response = await fetch("/ocr/images", {
                    method: "POST",
                    body: formData
                });

                if (!response.ok) {
                    const err = await response.json();
                    throw new Error(err.detail || `Lỗi HTTP ${response.status}`);
                }

                lastResultData = await response.json();
                renderResultsView();

            } catch (err) {
                outputBox.innerHTML = `
                    <div style="color: var(--error); padding: 14px; background: rgba(239, 68, 68, 0.1); border-radius: 8px;">
                        <strong>⚠️ Đã xảy ra lỗi khi quét OCR:</strong>
                        <p style="margin-top: 6px; font-family: monospace;">${err.message}</p>
                    </div>
                `;
            } finally {
                btnSubmit.disabled = false;
                btnSubmit.innerHTML = `
                    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <polygon points="5 3 19 12 5 21 5 3"/>
                    </svg>
                    <span>Bắt Đầu Quét OCR Toàn Bộ</span>
                `;
                progressBar.style.display = "none";
            }
        });

        function renderResultsView() {
            if (!lastResultData) return;

            if (currentTab === "combined") {
                outputBox.textContent = lastResultData.combined_text || "Không tìm thấy văn bản nào trong ảnh.";
            } else if (currentTab === "pages") {
                outputBox.innerHTML = "";
                const results = lastResultData.results || [];
                if (results.length === 0) {
                    outputBox.textContent = "Không có trang nào.";
                    return;
                }
                results.forEach(res => {
                    const card = document.createElement("div");
                    card.className = "page-result-card";
                    card.innerHTML = `
                        <div class="page-result-header">
                            <span>TRANG ${res.page_index}: ${res.filename}</span>
                            <span class="page-result-badge">${res.execution_time_seconds || 0}s • ${res.char_count || 0} ký tự</span>
                        </div>
                        <div class="page-result-text">${res.text || "(Trang rỗng)"}</div>
                    `;
                    outputBox.appendChild(card);
                });
            } else if (currentTab === "raw") {
                outputBox.textContent = JSON.stringify(lastResultData, null, 2);
            }
        }

        // Copy button
        document.getElementById("btnCopy").addEventListener("click", () => {
            if (!lastResultData) return;
            const textToCopy = (currentTab === "raw") 
                ? JSON.stringify(lastResultData, null, 2)
                : lastResultData.combined_text;
            navigator.clipboard.writeText(textToCopy).then(() => {
                const btn = document.getElementById("btnCopy");
                const oldText = btn.innerHTML;
                btn.innerHTML = `<span>✓ Đã chép!</span>`;
                setTimeout(() => { btn.innerHTML = oldText; }, 2000);
            });
        });

        // Download button
        document.getElementById("btnDownload").addEventListener("click", () => {
            if (!lastResultData) return;
            const textToSave = (currentTab === "raw") 
                ? JSON.stringify(lastResultData, null, 2)
                : lastResultData.combined_text;
            const blob = new Blob([textToSave], { type: "text/plain;charset=utf-8" });
            const url = URL.createObjectURL(blob);
            const a = document.createElement("a");
            a.href = url;
            a.download = `ocr_result_${Date.now()}.${currentTab === "raw" ? "json" : "txt"}`;
            a.click();
            URL.revokeObjectURL(url);
        });
    </script>
</body>
</html>
"""
