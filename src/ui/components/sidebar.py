"""Sidebar controls and document ingestion component for Streamlit UI."""

from typing import Any, Dict, Optional
import streamlit as st

from src.ui.api_client import ApiClient


def format_backend_status(health_info: Optional[Dict[str, Any]]) -> str:
    """Format backend health dictionary into human-readable status badge."""
    if health_info and health_info.get("status") == "ok":
        mode = health_info.get("retrieval_mode", "standard")
        return f"🟢 Online ({mode})"
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
        uploaded_file = st.file_uploader(
            "Tải lên tệp PDF kỹ thuật",
            type=["pdf"],
            key="pdf_uploader",
            help="Hệ thống hỗ trợ cả PDF text và PDF scan (OCR).",
        )

        uploaded = False
        if uploaded_file is not None:
            if st.button("🚀 Nạp vào hệ thống", use_container_width=True, type="primary"):
                with st.status(f"Đang xử lý `{uploaded_file.name}`...", expanded=True) as status:
                    try:
                        st.write("📥 **[1/4]** Tiếp nhận tệp và phân tích cấu trúc PDF...")
                        file_bytes = uploaded_file.getvalue()
                        resp = api_client.upload_document(file_bytes, uploaded_file.name)

                        pages = resp.get("pages_extracted") or resp.get("pages_processed", 0)
                        pages_digital = resp.get("pages_digital", pages)
                        pages_scanned = resp.get("pages_scanned_ocr", 0)
                        chunks = resp.get("chunks_indexed") or resp.get("chunks_created", 0)

                        st.write(
                            f"🔍 **[2/4]** Bóc tách xong **{pages} trang** "
                            f"({pages_digital} trang số, {pages_scanned} trang qua RapidOCR)"
                        )
                        st.write(
                            f"✂️ **[3/4]** Phân đoạn ngữ nghĩa thành **{chunks} chunks** "
                            f"(gối đầu 50 ký tự, bảo toàn số trang)"
                        )
                        st.write("🧠 **[4/4]** Tạo vector embedding 384 chiều & lưu trữ thành công vào Qdrant")

                        status.update(
                            label=f"✅ Nạp hoàn tất: {uploaded_file.name}!",
                            state="complete",
                            expanded=False,
                        )

                        col1, col2 = st.columns(2)
                        col1.metric("Số trang", pages)
                        col2.metric("Số Chunks", chunks)

                        if pages_scanned > 0:
                            st.info(f"💡 Phát hiện **{pages_scanned}** trang scan/ảnh và đã nhận diện tự động bằng RapidOCR.")

                        uploaded = True
                    except Exception as exc:
                        status.update(
                            label="❌ Nạp tài liệu thất bại!",
                            state="error",
                            expanded=True,
                        )
                        st.error(f"Chi tiết lỗi: {exc}")

        with st.expander("ℹ️ Quy trình xử lý tài liệu (Pipeline)", expanded=False):
            st.markdown(
                """
                1. **Bóc tách trang:** Dùng PyMuPDF đọc text số. Nếu trang `< 50` ký tự, tự động kích hoạt **RapidOCR (300 DPI)**.
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

