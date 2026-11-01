"""Modern conversational Streamlit UI for Document Q&A Assistant."""

import os
import sys
from pathlib import Path
from typing import Any, Dict

# Ensure project root is in sys.path when executed via `streamlit run src/ui/app.py`
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import streamlit as st

from src.ui.api_client import ApiClient
from src.ui.components.chat import PROMPT_SUGGESTIONS, render_assistant_message
from src.ui.components.sidebar import render_sidebar
from src.ui.styles import CHATGPT_CUSTOM_CSS


def init_session_state(state: Dict[str, Any]) -> None:
    """Initialize session state keys for chat history, suggestions, and session ID."""
    if "messages" not in state:
        state["messages"] = []
    if "pending_prompt" not in state:
        state["pending_prompt"] = None
    if "session_id" not in state:
        state["session_id"] = None


def reset_session_state(state: Dict[str, Any]) -> None:
    """Clear message history, pending prompts, and active session ID."""
    state["messages"] = []
    state["pending_prompt"] = None
    state["session_id"] = None


def main() -> None:
    """Main Streamlit application entrypoint."""
    st.set_page_config(
        page_title="Document Q&A Assistant",
        page_icon=":material/neurology:",
        layout="wide",
        initial_sidebar_state="expanded",
    )

    init_session_state(st.session_state)

    # Inject polished design system CSS
    st.markdown(CHATGPT_CUSTOM_CSS, unsafe_allow_html=True)

    api_base_url = os.environ.get("API_BASE_URL", "http://localhost:8000/api/v1")
    api_client = ApiClient(base_url=api_base_url)

    # Render sidebar controls
    sidebar_state = render_sidebar(api_client)
    if sidebar_state.get("reset_chat"):
        reset_session_state(st.session_state)
        st.rerun()

    # Empty State Hero Section with Clickable Prompt Suggestions
    if not st.session_state["messages"]:
        st.markdown(
            """
            <div class="hero-wrapper">
                <div class="hero-badge">Document Intelligence · TCVN & ISO Grounded</div>
                <div class="hero-title">Trợ lý Hỏi đáp & Phân tích Kỹ thuật</div>
                <div class="hero-subtitle">
                    Tra cứu thông số, đối chiếu tiêu chuẩn và tính toán công thức kỹ thuật chuyên sâu dựa trên các tài liệu đã nạp (PDF, DOCX, TXT, OCR).
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        st.markdown('<div class="suggestion-header">Gợi ý câu hỏi kỹ thuật thử nghiệm</div>', unsafe_allow_html=True)
        cols = st.columns(3)
        for idx, (col, sug) in enumerate(zip(cols, PROMPT_SUGGESTIONS[:3])):
            with col:
                btn_label = f"💬 {sug[:34]}..." if len(sug) > 36 else f"💬 {sug}"
                if st.button(btn_label, key=f"sug_{idx}", help=sug, width="stretch"):
                    st.session_state["pending_prompt"] = sug
                    st.rerun()

    # Render Chat History
    for msg in st.session_state["messages"]:
        role = msg.get("role", "user")
        avatar = ":material/person:" if role == "user" else ":material/neurology:"
        with st.chat_message(role, avatar=avatar):
            if role == "user":
                st.markdown(msg.get("content", ""))
            else:
                render_assistant_message(msg, api_base_url=api_base_url)

    # Handle Input (User chat_input or suggestion click)
    prompt = None
    if st.session_state.get("pending_prompt"):
        prompt = st.session_state["pending_prompt"]
        st.session_state["pending_prompt"] = None
    else:
        user_input = st.chat_input("Nhập câu hỏi của bạn về tài liệu kỹ thuật...")
        if user_input:
            prompt = user_input.strip()

    if prompt:
        # 1. Add and render user message
        st.session_state["messages"].append({"role": "user", "content": prompt})
        with st.chat_message("user", avatar=":material/person:"):
            st.markdown(prompt)

        # 2. Query backend and render assistant response
        with st.chat_message("assistant", avatar=":material/neurology:"):
            with st.spinner("Đang tìm kiếm tài liệu, đối chiếu tiêu chuẩn và tính toán..."):
                try:
                    top_k = sidebar_state.get("top_k", 3)
                    session_id = st.session_state.get("session_id")
                    response = api_client.query(prompt, top_k=top_k, session_id=session_id)
                    if response.session_id:
                        st.session_state["session_id"] = response.session_id
                    render_assistant_message(response, api_base_url=api_base_url)
                    st.session_state["messages"].append({
                        "role": "assistant",
                        "content": response.answer,
                        "citations": [c.model_dump() for c in response.citations],
                        "abstained": response.abstained,
                        "retrieved_chunks": [r.model_dump() for r in response.retrieved_chunks],
                        "reasoning_steps": getattr(response, "reasoning_steps", []) or [],
                        "session_id": response.session_id,
                    })
                except Exception as exc:
                    err_text = f"❌ Không thể thực hiện truy vấn: {exc}"
                    st.error(err_text)
                    st.session_state["messages"].append({
                        "role": "assistant",
                        "content": err_text,
                        "citations": [],
                        "abstained": False,
                        "retrieved_chunks": [],
                        "reasoning_steps": [],
                    })


if __name__ == "__main__":
    main()
