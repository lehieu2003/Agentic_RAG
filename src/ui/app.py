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
from src.ui.components.chat import render_assistant_message
from src.ui.components.sidebar import render_sidebar
from src.ui.styles import CHATGPT_CUSTOM_CSS




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

    # Inject ChatGPT styling
    st.markdown(CHATGPT_CUSTOM_CSS, unsafe_allow_html=True)

    api_base_url = os.environ.get("API_BASE_URL", "http://localhost:8000/api/v1")
    api_client = ApiClient(base_url=api_base_url)

    # Render sidebar
    sidebar_state = render_sidebar(api_client)
    if sidebar_state.get("reset_chat"):
        reset_session_state(st.session_state)
        st.rerun()

    # Empty State Hero (ChatGPT Minimalist Greeting - No prompt suggestions)
    if not st.session_state["messages"]:
        st.markdown(
            """
            <div class="gpt-hero-container">
                <div class="gpt-hero-icon">🤖</div>
                <div class="gpt-hero-title">Tôi có thể giúp gì cho bạn hôm nay?</div>
                <div class="gpt-hero-subtitle">
                    Hỏi bất kỳ điều gì về thông số kỹ thuật, quy trình bảo dưỡng hoặc cách xử lý sự cố từ các tài liệu kỹ thuật đã nạp.
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    # Render Chat History
    for msg in st.session_state["messages"]:
        role = msg.get("role", "user")
        avatar = "👤" if role == "user" else "🤖"
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
        user_input = st.chat_input("Nhập câu hỏi của bạn về tài liệu...")
        if user_input:
            prompt = user_input.strip()

    if prompt:
        # 1. Add and render user message
        st.session_state["messages"].append({"role": "user", "content": prompt})
        with st.chat_message("user", avatar="👤"):
            st.markdown(prompt)

        # 2. Query backend and render assistant response
        with st.chat_message("assistant", avatar="🤖"):
            with st.spinner("Đang tìm kiếm tài liệu và sinh câu trả lời..."):
                try:
                    top_k = sidebar_state.get("top_k", 3)
                    response = api_client.query(prompt, top_k=top_k)
                    render_assistant_message(response, api_base_url=api_base_url)
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
