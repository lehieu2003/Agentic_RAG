# tests/test_ui_app.py
import pytest
from unittest.mock import patch, MagicMock

def test_init_session_state():
    from src.ui.app import init_session_state
    mock_state = {}
    init_session_state(mock_state)
    assert "messages" in mock_state
    assert isinstance(mock_state["messages"], list)
    assert "pending_prompt" in mock_state
    assert mock_state["pending_prompt"] is None
    assert "session_id" in mock_state
    assert mock_state["session_id"] is None


def test_reset_session_state():
    from src.ui.app import reset_session_state
    mock_state = {
        "messages": [{"role": "user", "content": "hi"}],
        "pending_prompt": "hello",
        "session_id": "sess-1234",
    }
    reset_session_state(mock_state)
    assert mock_state["messages"] == []
    assert mock_state["pending_prompt"] is None
    assert mock_state["session_id"] is None


@patch("src.ui.app.ApiClient")
@patch("src.ui.app.render_sidebar")
@patch("src.ui.app.st")
def test_main_renders(mock_st, mock_render_sidebar, mock_api_client_cls):
    from src.ui.app import main
    mock_st.session_state = {"messages": [], "pending_prompt": None, "session_id": None}
    mock_st.chat_input.return_value = None
    mock_st.button.return_value = False
    mock_st.columns.return_value = [MagicMock(), MagicMock(), MagicMock()]
    mock_render_sidebar.return_value = {"top_k": 3, "reset_chat": False, "uploaded": False}

    main()
    mock_st.set_page_config.assert_called_once()
    mock_render_sidebar.assert_called_once()


@patch("src.ui.app.render_assistant_message")
@patch("src.ui.app.ApiClient")
@patch("src.ui.app.render_sidebar")
@patch("src.ui.app.st")
def test_main_queries_with_session_id(mock_st, mock_render_sidebar, mock_api_client_cls, mock_render_assistant):
    from src.ui.app import main
    from src.models import QAResponse

    mock_client = MagicMock()
    mock_api_client_cls.return_value = mock_client
    mock_resp = QAResponse(
        answer="Câu trả lời thử nghiệm",
        citations=[],
        abstained=False,
        retrieved_chunks=[],
        session_id="returned-session-5678",
    )
    mock_client.query.return_value = mock_resp

    mock_st.session_state = {"messages": [], "pending_prompt": None, "session_id": "existing-sess-123"}
    mock_st.chat_input.return_value = "Câu hỏi tiếp theo?"
    mock_st.button.return_value = False
    mock_st.columns.return_value = [MagicMock(), MagicMock(), MagicMock()]
    mock_render_sidebar.return_value = {"top_k": 4, "reset_chat": False, "uploaded": False}

    main()
    mock_client.query.assert_called_once_with(
        "Câu hỏi tiếp theo?",
        top_k=4,
        session_id="existing-sess-123",
    )
    assert mock_st.session_state["session_id"] == "returned-session-5678"
    assert len(mock_st.session_state["messages"]) == 2



