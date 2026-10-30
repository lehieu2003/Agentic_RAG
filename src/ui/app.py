"""ChatGPT-style conversational Streamlit UI for Document Q&A Assistant."""

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
from src.ui.components.chat import (
    PROMPT_SUGGESTIONS,
    render_assistant_message,
)
from src.ui.components.sidebar import render_sidebar



def init_session_state(state: Dict[str, Any]) -> None:
    """Initialize session state keys for chat history and suggestions."""
    if "messages" not in state:
        state["messages"] = []
    if "pending_prompt" not in state:
        state["pending_prompt"] = None


def reset_session_state(state: Dict[str, Any]) -> None:
    """Clear message history and pending prompts."""
    state["messages"] = []
    state["pending_prompt"] = None


def main() -> None:
    """Main Streamlit application entrypoint."""
    st.set_page_config(
        page_title="Document Q&A Assistant",
        page_icon="🤖",
        layout="wide",
        initial_sidebar_state="expanded",
    )

    init_session_state(st.session_state)

    api_base_url = os.environ.get("API_BASE_URL", "http://localhost:8000/api/v1")
    api_client = ApiClient(base_url=api_base_url)

    # Render sidebar
    sidebar_state = render_sidebar(api_client)
    if sidebar_state.get("reset_chat"):
        reset_session_state(st.session_state)
        st.rerun()

    # Empty State & Prompt Suggestions
    if not st.session_state["messages"]:
        st.markdown(
            """
            <div style="text-align: center; padding: 40px 0 20px 0;">
                <h1 style="font-size: 2.2rem; margin-bottom: 8px;">🤖 Document Q&A Assistant</h1>
                <p style="color: #6c757d; font-size: 1.1rem; max-width: 650px; margin: 0 auto;">
                    Hỏi đáp thông minh dựa trên tài liệu kỹ thuật đã nạp. Mọi câu trả lời đều kèm trích dẫn chính xác và minh bạch.
                </p>
            </div>
            """,
            unsafe_allow_html=True,
        )

        st.markdown("#### 💡 Gợi ý câu hỏi bắt đầu")
        cols = st.columns(len(PROMPT_SUGGESTIONS))
        for idx, (col, suggestion) in enumerate(zip(cols, PROMPT_SUGGESTIONS)):
            with col:
                if st.button(f"📌 {suggestion}", key=f"sug_{idx}", use_container_width=True):
                    st.session_state["pending_prompt"] = suggestion
                    st.rerun()

    # Render Chat History
    for msg in st.session_state["messages"]:
        role = msg.get("role", "user")
        with st.chat_message(role):
            if role == "user":
                st.markdown(msg.get("content", ""))
            else:
                render_assistant_message(msg)

    # Handle Input (User chat_input or suggestion click)
    prompt = None
    if st.session_state.get("pending_prompt"):
        prompt = st.session_state["pending_prompt"]
        st.session_state["pending_prompt"] = None
    else:
        user_input = st.chat_input("Nhập câu hỏi của bạn về tài liệu...")
        if user_input:
            prompt = user_input.strip()

    if prompt:
        # 1. Add and render user message
        st.session_state["messages"].append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        # 2. Query backend and render assistant response
        with st.chat_message("assistant"):
            with st.spinner("Đang tìm kiếm tài liệu và sinh câu trả lời..."):
                try:
                    top_k = sidebar_state.get("top_k", 3)
                    response = api_client.query(prompt, top_k=top_k)
                    render_assistant_message(response)
                    st.session_state["messages"].append({
                        "role": "assistant",
                        "content": response.answer,
                        "citations": [c.model_dump() for c in response.citations],
                        "abstained": response.abstained,
                        "retrieved_chunks": [r.model_dump() for r in response.retrieved_chunks],
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
                    })


if __name__ == "__main__":
    main()
