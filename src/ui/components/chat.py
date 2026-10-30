"""Chat display components and formatting helpers for Streamlit UI."""

from typing import Any, List, Union
import streamlit as st

from src.models import Citation, RetrievalResult, QAResponse

PROMPT_SUGGESTIONS: List[str] = [
    "Áp suất làm việc tối đa của bơm là bao nhiêu bar?",
    "Quy trình kiểm tra và bảo dưỡng hệ thống định kỳ gồm những bước nào?",
    "Các biện pháp an toàn cần tuân thủ khi vận hành thiết bị là gì?",
]


def format_citation_badge(c: Union[Citation, dict]) -> str:
    """Format a citation into a readable badge label."""
    if isinstance(c, Citation):
        doc_name = c.doc_name
        page_number = c.page_number
    elif isinstance(c, dict):
        doc_name = c.get("doc_name", "Unknown")
        page_number = c.get("page_number", "?")
    else:
        doc_name = getattr(c, "doc_name", "Unknown")
        page_number = getattr(c, "page_number", "?")

    return f"📄 [{doc_name}, Trang {page_number}]"


def render_citation_badges(citations: List[Union[Citation, dict]]) -> None:
    """Render citation badges under an assistant answer."""
    if not citations:
        return

    st.markdown("##### 📚 Nguồn trích dẫn")
    badges = " &nbsp; ".join([f"`{format_citation_badge(c)}`" for c in citations])
    st.markdown(badges)


def render_evidence_expander(chunks: List[Union[RetrievalResult, dict]]) -> None:
    """Render a collapsible expander with retrieved chunks and similarity scores."""
    if not chunks:
        return

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

            score_label = f"{score:.3f}" if isinstance(score, (int, float)) else str(score)
            st.markdown(f"**#{idx}** `{doc_name}` (Trang {page_number}) — *Score:* `{score_label}`")
            st.caption(text)
            if idx < len(chunks):
                st.divider()


def render_assistant_message(message: Union[dict, QAResponse]) -> None:
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
        render_citation_badges(citations)

    if retrieved_chunks:
        render_evidence_expander(retrieved_chunks)

