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
                with st.spinner(f"Đang xử lý `{uploaded_file.name}`..."):
                    try:
                        file_bytes = uploaded_file.getvalue()
                        resp = api_client.upload_document(file_bytes, uploaded_file.name)
                        pages = resp.get("pages_processed", 0)
                        chunks = resp.get("chunks_created", 0)
                        st.success(
                            f"✅ Đã nạp thành công `{uploaded_file.name}`!\n\n"
                            f"- Số trang: **{pages}**\n- Số chunks: **{chunks}**"
                        )
                        uploaded = True
                    except Exception as exc:
                        st.error(f"❌ Nạp tài liệu thất bại: {exc}")

        st.divider()
        st.caption("Phát triển với FastAPI, Streamlit, LangChain & Qdrant.")

    return {
        "top_k": top_k,
        "reset_chat": reset_chat,
        "uploaded": uploaded,
    }

