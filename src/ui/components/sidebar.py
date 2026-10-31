"""Sidebar controls and document ingestion component for Streamlit UI."""

from typing import Any, Dict, Optional
import streamlit as st

from src.ui.api_client import ApiClient


def format_backend_status(health_info: Optional[Dict[str, Any]]) -> str:
    """Format backend health dictionary into human-readable status badge."""
    if health_info and health_info.get("status") == "ok":
        mode = health_info.get("retrieval_mode", "standard")
        vstore = health_info.get("vector_store")
        extra = f" | Qdrant {vstore.capitalize()}" if vstore else ""
        return f"🟢 Online ({mode}{extra})"
    return "🔴 Offline"


def render_sidebar(api_client: ApiClient) -> Dict[str, Any]:
    """Render the sidebar controls including New Chat button, status, upload, and top_k slider.

    Returns:
        dict with keys:
            - "top_k": int
            - "reset_chat": bool
            - "uploaded": bool
    """
    with st.sidebar:
        st.title("🤖 Q&A Assistant")
        st.caption("Trợ lý hỏi đáp tài liệu kỹ thuật thông minh")

        reset_chat = st.button("➕ Cuộc trò chuyện mới", use_container_width=True, type="secondary")

        st.divider()

        # Backend Health Status
        health = api_client.check_health()
        status_label = format_backend_status(health)
        st.markdown(f"**Trạng thái API:** {status_label}")

        if not health:
            st.warning(
                "⚠️ Không thể kết nối tới FastAPI backend.\n\n"
                "Hãy chạy lệnh sau ở terminal:\n"
                "```bash\n.venv/bin/uvicorn src.api.main:app --port 8000\n```"
            )

        st.divider()

        # Search Depth Configuration
        st.subheader("⚙️ Cấu hình tìm kiếm")
        top_k = st.slider(
            "Độ sâu trích xuất (`top_k`)",
            min_value=1,
            max_value=10,
            value=3,
            step=1,
            help="Số đoạn văn bản liên quan nhất được truy xuất từ Qdrant.",
        )

        st.divider()

        # Document Ingestion Section
        st.subheader("📁 Nạp tài liệu mới")
        uploaded_files = st.file_uploader(
            "Chọn hoặc kéo thả tệp tài liệu",
            type=["pdf", "docx", "txt", "png", "jpg", "jpeg"],
            accept_multiple_files=True,
            key="multi_file_uploader",
            help="Hỗ trợ định dạng PDF, DOCX, TXT và Hình ảnh (PNG, JPG, JPEG)",
        )

        uploaded = False
        if uploaded_files:
            if st.button("🚀 Nạp vào hệ thống", use_container_width=True, type="primary"):
                total_files_count = len(uploaded_files)
                with st.status(f"Đang xử lý {total_files_count} tệp...", expanded=True) as status:
                    success_count = 0
                    total_pages = 0
                    total_chunks = 0
                    scanned_pages_total = 0

                    for idx, file in enumerate(uploaded_files, 1):
                        st.write(f"📥 **[{idx}/{total_files_count}]** Đang xử lý `{file.name}`...")
                        try:
                            file_bytes = file.getvalue()
                            resp = api_client.upload_document(file_bytes, file.name)
                            pages = resp.get("pages_extracted") or resp.get("pages_processed", 0)
                            pages_digital = resp.get("pages_digital", pages)
                            pages_scanned = resp.get("pages_scanned_ocr", 0)
                            chunks = resp.get("chunks_indexed") or resp.get("chunks_created", 0)

                            total_pages += pages
                            total_chunks += chunks
                            scanned_pages_total += pages_scanned
                            success_count += 1

                            st.write(
                                f"✅ `{file.name}`: **{pages}** trang "
                                f"({pages_digital} số, {pages_scanned} OCR) ➔ **{chunks}** chunks"
                            )
                        except Exception as exc:
                            st.error(f"❌ Lỗi khi xử lý `{file.name}`: {exc}")

                    if success_count > 0:
                        status.update(
                            label="Hoàn tất nạp tài liệu!",
                            state="complete",
                            expanded=False,
                        )
                        uploaded = True
                    else:
                        status.update(
                            label="Nạp tài liệu thất bại!",
                            state="error",
                            expanded=True,
                        )

                    col1, col2, col3 = st.columns(3)
                    col1.metric("Số tệp đã nạp", f"{success_count}/{total_files_count}")
                    col2.metric("Tổng số trang", total_pages)
                    col3.metric("Tổng số chunks", total_chunks)

                    if scanned_pages_total > 0:
                        st.info(f"💡 Phát hiện **{scanned_pages_total}** trang scan/ảnh và đã nhận diện tự động bằng RapidOCR.")

        with st.expander("ℹ️ Quy trình xử lý tài liệu (Pipeline)", expanded=False):
            st.markdown(
                """
                1. **Bóc tách trang:** Dùng PyMuPDF đọc text số (PDF), python-docx (Word), hoặc RapidOCR (Ảnh/Scanned).
                2. **Phân đoạn (Chunking):** Cắt nhỏ ~500 ký tự (overlap 50), bảo toàn `doc_name` và `page_number`.
                3. **Vector hóa:** Tạo vector 384 chiều bằng mô hình `all-MiniLM-L6-v2`.
                4. **Lưu trữ:** Lưu vào **Qdrant Vector DB** phục vụ tìm kiếm ngữ nghĩa và trích dẫn chuẩn xác.
                """
            )

        st.divider()
        st.caption("Phát triển với FastAPI, Streamlit, LangChain & Qdrant.")

    return {
        "top_k": top_k,
        "reset_chat": reset_chat,
        "uploaded": uploaded,
    }

