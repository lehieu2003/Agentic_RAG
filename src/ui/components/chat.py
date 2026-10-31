"""Chat display components and formatting helpers for Streamlit UI."""

from typing import Any, List, Optional, Union
import streamlit as st

from src.models import Citation, RetrievalResult, QAResponse

PROMPT_SUGGESTIONS: List[str] = [
    "Áp suất làm việc tối đa của bơm là bao nhiêu bar?",
    "Quy trình kiểm tra và bảo dưỡng hệ thống định kỳ gồm những bước nào?",
    "Các biện pháp an toàn cần tuân thủ khi vận hành thiết bị là gì?",
]


def format_citation_badge(
    doc_name: Union[str, Citation, dict],
    page: Optional[Union[int, str]] = None,
    api_base_url: str = "http://localhost:8000",
) -> str:
    """Format a citation into a clickable HTML badge linking to the document viewer.

    Supports calling as:
    - format_citation_badge(doc_name="doc.pdf", page=1, api_base_url="http://...")
    - format_citation_badge(citation_obj, api_base_url="http://...")
    - format_citation_badge(citation_dict, api_base_url="http://...")
    """
    if isinstance(doc_name, Citation):
        actual_doc = doc_name.doc_name
        actual_page = doc_name.page_number
        if isinstance(page, str) and page.startswith("http"):
            api_base_url = page
    elif isinstance(doc_name, dict):
        actual_doc = doc_name.get("doc_name", "Unknown")
        actual_page = doc_name.get("page_number", "?")
        if isinstance(page, str) and page.startswith("http"):
            api_base_url = page
    elif not isinstance(doc_name, str):
        actual_doc = getattr(doc_name, "doc_name", "Unknown")
        actual_page = getattr(doc_name, "page_number", "?")
        if isinstance(page, str) and page.startswith("http"):
            api_base_url = page
    else:
        actual_doc = doc_name
        actual_page = page if page is not None else "?"

    clean_base = api_base_url.rstrip("/")
    if clean_base.endswith("/api/v1"):
        url = f"{clean_base}/files/{actual_doc}#page={actual_page}"
    else:
        url = f"{clean_base}/api/v1/files/{actual_doc}#page={actual_page}"

    return (
        f'<a href="{url}" target="_blank" class="citation-badge" '
        f'title="Mở {actual_doc} tại trang {actual_page}">📄 {actual_doc} (Trang {actual_page}) ↗</a>'
    )


def render_citation_badges(
    citations: List[Union[Citation, dict]],
    api_base_url: str = "http://localhost:8000",
) -> None:
    """Render citation badges under an assistant answer."""
    if not citations:
        return

    st.markdown("##### 📚 Nguồn trích dẫn")
    badges = "".join([format_citation_badge(c, api_base_url=api_base_url) for c in citations])
    st.markdown(f'<div class="citation-container">{badges}</div>', unsafe_allow_html=True)


def render_evidence_expander(
    chunks: List[Union[RetrievalResult, dict]],
    api_base_url: str = "http://localhost:8000",
) -> None:
    """Render a collapsible expander with retrieved chunks and similarity scores."""
    if not chunks:
        return

    clean_base = api_base_url.rstrip("/")
    if not clean_base.endswith("/api/v1"):
        clean_base = f"{clean_base}/api/v1"

    with st.expander(f"🔍 Chi tiết {len(chunks)} đoạn trích dẫn (Evidence Chunks)", expanded=False):
        for idx, item in enumerate(chunks, 1):
            if isinstance(item, RetrievalResult):
                doc_name = item.chunk.doc_name
                page_number = item.chunk.page_number
                score = item.score
                text = item.chunk.text
            elif isinstance(item, dict):
                chunk_data = item.get("chunk", {})
                doc_name = chunk_data.get("doc_name", "Unknown")
                page_number = chunk_data.get("page_number", "?")
                score = item.get("score", 0.0)
                text = chunk_data.get("text", "")
            else:
                continue

            score_pct = f"{score * 100:.1f}%" if isinstance(score, (int, float)) else str(score)
            st.markdown(f"**#{idx}** `{doc_name}` (Trang {page_number}) &nbsp;·&nbsp; 🎯 *Độ tương đồng:* `{score_pct}`")
            if doc_name and doc_name != "Unknown":
                file_url = f"{clean_base}/files/{doc_name}#page={page_number}"
                st.markdown(f"[🔗 Mở tài liệu tại trang này]({file_url})")
            st.caption(text)
            if idx < len(chunks):
                st.divider()


def render_assistant_message(
    message: Union[dict, QAResponse],
    api_base_url: str = "http://localhost:8000",
) -> None:
    """Render full assistant message with text, abstention warning, badges, and evidence."""
    if isinstance(message, QAResponse):
        content = message.answer
        abstained = message.abstained
        citations = message.citations
        retrieved_chunks = message.retrieved_chunks
    elif isinstance(message, dict):
        content = message.get("content") or message.get("answer", "")
        abstained = bool(message.get("abstained", False))
        citations = message.get("citations", [])
        retrieved_chunks = message.get("retrieved_chunks", [])
    else:
        content = str(message)
        abstained = False
        citations = []
        retrieved_chunks = []

    if abstained:
        st.warning("⚠️ Thông tin không có trong tài liệu đã nạp. Hệ thống từ chối suy đoán để tránh sai lệch.")

    st.markdown(content)

    if not abstained and citations:
        render_citation_badges(citations, api_base_url=api_base_url)

    if retrieved_chunks:
        render_evidence_expander(retrieved_chunks, api_base_url=api_base_url)

