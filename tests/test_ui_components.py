# tests/test_ui_components.py
from unittest.mock import patch, MagicMock
from src.models import Citation, RetrievalResult, DocumentChunk, QAResponse
from src.ui.components.chat import (
    PROMPT_SUGGESTIONS,
    format_citation_badge,
    render_citation_badges,
    render_evidence_expander,
    render_assistant_message,
)

def test_prompt_suggestions_not_empty():
    assert len(PROMPT_SUGGESTIONS) >= 3
    assert any("áp suất" in p.lower() for p in PROMPT_SUGGESTIONS)

def test_format_citation_badge():
    c = Citation(doc_name="pump_maintenance_guide.pdf", page_number=2)
    badge = format_citation_badge(c)
    assert "pump_maintenance_guide.pdf" in badge
    assert "Trang 2" in badge

    # Also test dict format
    badge_dict = format_citation_badge({"doc_name": "manual.pdf", "page_number": 5})
    assert "manual.pdf" in badge_dict
    assert "Trang 5" in badge_dict

@patch("streamlit.markdown")
def test_render_citation_badges(mock_markdown):
    citations = [
        Citation(doc_name="doc1.pdf", page_number=1),
        Citation(doc_name="doc2.pdf", page_number=3),
    ]
    render_citation_badges(citations)
    assert mock_markdown.call_count >= 2

@patch("streamlit.expander")
@patch("streamlit.markdown")
@patch("streamlit.caption")
def test_render_evidence_expander(mock_caption, mock_markdown, mock_expander):
    mock_expander.return_value.__enter__.return_value = MagicMock()
    chunks = [
        RetrievalResult(
            chunk=DocumentChunk(
                chunk_id="c1",
                doc_name="doc1.pdf",
                page_number=1,
                text="Chunk text sample",
            ),
            score=0.88,
        )
    ]
    render_evidence_expander(chunks)
    mock_expander.assert_called_once()

@patch("streamlit.warning")
@patch("streamlit.markdown")
def test_render_assistant_message_abstained(mock_markdown, mock_warning):
    msg = {"content": "Không có thông tin.", "abstained": True, "citations": []}
    render_assistant_message(msg)
    mock_warning.assert_called_once()
    mock_markdown.assert_called_with("Không có thông tin.")

def test_sidebar_health_mapping():
    from src.ui.components.sidebar import format_backend_status
    assert "Online" in format_backend_status({"status": "ok", "retrieval_mode": "local"})
    assert "Offline" in format_backend_status(None)

@patch("streamlit.sidebar")
@patch("streamlit.button")
@patch("streamlit.slider")
@patch("streamlit.file_uploader")
def test_render_sidebar_basic(mock_uploader, mock_slider, mock_button, mock_sidebar):
    from src.ui.components.sidebar import render_sidebar
    mock_client = MagicMock()
    mock_client.check_health.return_value = {"status": "ok", "retrieval_mode": "local"}
    mock_slider.return_value = 4
    mock_button.return_value = False
    mock_uploader.return_value = None

    res = render_sidebar(mock_client)
    assert res["top_k"] == 4
    assert res["reset_chat"] is False
    assert res["uploaded"] is False

@patch("streamlit.sidebar")
@patch("streamlit.status")
@patch("streamlit.button")
@patch("streamlit.slider")
@patch("streamlit.file_uploader")
@patch("streamlit.columns")
def test_render_sidebar_upload_process(mock_columns, mock_uploader, mock_slider, mock_button, mock_status, mock_sidebar):
    from src.ui.components.sidebar import render_sidebar
    mock_client = MagicMock()
    mock_client.check_health.return_value = {"status": "ok", "retrieval_mode": "local"}
    mock_client.upload_document.side_effect = [
        {
            "filename": "manual.pdf",
            "pages_extracted": 3,
            "pages_digital": 2,
            "pages_scanned_ocr": 1,
            "chunks_indexed": 9,
            "status": "success",
        },
        {
            "filename": "notes.docx",
            "pages_extracted": 2,
            "pages_digital": 2,
            "pages_scanned_ocr": 0,
            "chunks_indexed": 4,
            "status": "success",
        },
    ]
    mock_slider.return_value = 3
    mock_button.return_value = True  # user clicked upload

    mock_file1 = MagicMock()
    mock_file1.name = "manual.pdf"
    mock_file1.getvalue.return_value = b"%PDF-dummy"

    mock_file2 = MagicMock()
    mock_file2.name = "notes.docx"
    mock_file2.getvalue.return_value = b"DOCX-dummy"

    mock_uploader.return_value = [mock_file1, mock_file2]
    mock_status_ctx = MagicMock()
    mock_status.return_value.__enter__.return_value = mock_status_ctx
    mock_columns.return_value = [MagicMock(), MagicMock(), MagicMock()]

    res = render_sidebar(mock_client)
    assert res["uploaded"] is True
    assert mock_client.upload_document.call_count == 2
    mock_client.upload_document.assert_any_call(b"%PDF-dummy", "manual.pdf")
    mock_client.upload_document.assert_any_call(b"DOCX-dummy", "notes.docx")
    mock_status.assert_called_once()
    mock_status_ctx.update.assert_called_once_with(
        label="Hoàn tất nạp tài liệu!",
        state="complete",
        expanded=False,
    )

    # Check uploader args
    _, kwargs = mock_uploader.call_args
    assert kwargs.get("accept_multiple_files") is True
    assert set(kwargs.get("type", [])) == {"pdf", "docx", "txt", "png", "jpg", "jpeg"}


@patch("streamlit.sidebar")
@patch("streamlit.status")
@patch("streamlit.button")
@patch("streamlit.slider")
@patch("streamlit.file_uploader")
@patch("streamlit.columns")
@patch("streamlit.error")
def test_render_sidebar_upload_partial_failure(
    mock_error, mock_columns, mock_uploader, mock_slider, mock_button, mock_status, mock_sidebar
):
    from src.ui.components.sidebar import render_sidebar
    mock_client = MagicMock()
    mock_client.check_health.return_value = {"status": "ok"}
    mock_client.upload_document.side_effect = [
        {"filename": "ok.pdf", "pages_extracted": 2, "chunks_indexed": 3},
        RuntimeError("Corrupt document"),
    ]
    mock_slider.return_value = 3
    mock_button.return_value = True

    f1 = MagicMock()
    f1.name = "ok.pdf"
    f1.getvalue.return_value = b"ok"
    f2 = MagicMock()
    f2.name = "corrupt.pdf"
    f2.getvalue.return_value = b"corrupt"

    mock_uploader.return_value = [f1, f2]
    mock_status_ctx = MagicMock()
    mock_status.return_value.__enter__.return_value = mock_status_ctx
    col1, col2, col3 = MagicMock(), MagicMock(), MagicMock()
    mock_columns.return_value = [col1, col2, col3]

    res = render_sidebar(mock_client)
    assert res["uploaded"] is True
    assert mock_client.upload_document.call_count == 2
    mock_error.assert_called_once()
    mock_status_ctx.update.assert_called_once_with(
        label="Hoàn tất nạp tài liệu!",
        state="complete",
        expanded=False,
    )
    col1.metric.assert_called_with("Số tệp đã nạp", "1/2")
    col2.metric.assert_called_with("Tổng số trang", 2)
    col3.metric.assert_called_with("Tổng số chunks", 3)


@patch("streamlit.sidebar")
@patch("streamlit.status")
@patch("streamlit.button")
@patch("streamlit.slider")
@patch("streamlit.file_uploader")
@patch("streamlit.columns")
@patch("streamlit.error")
def test_render_sidebar_upload_total_failure(
    mock_error, mock_columns, mock_uploader, mock_slider, mock_button, mock_status, mock_sidebar
):
    from src.ui.components.sidebar import render_sidebar
    mock_client = MagicMock()
    mock_client.check_health.return_value = {"status": "ok"}
    mock_client.upload_document.side_effect = RuntimeError("Network error")
    mock_slider.return_value = 3
    mock_button.return_value = True

    f1 = MagicMock()
    f1.name = "fail.pdf"
    f1.getvalue.return_value = b"fail"

    mock_uploader.return_value = [f1]
    mock_status_ctx = MagicMock()
    mock_status.return_value.__enter__.return_value = mock_status_ctx
    mock_columns.return_value = [MagicMock(), MagicMock(), MagicMock()]

    res = render_sidebar(mock_client)
    assert res["uploaded"] is False
    mock_status_ctx.update.assert_called_once_with(
        label="Nạp tài liệu thất bại!",
        state="error",
        expanded=True,
    )





