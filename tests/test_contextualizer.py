import pytest
from unittest.mock import MagicMock
from src.rag.agent import AgenticRAG
from src.models import RetrievalResult, DocumentChunk
from src.rag.prompt import build_rag_prompt


@pytest.fixture
def mock_agent():
    mock_retriever = MagicMock()
    mock_chunk = DocumentChunk(
        chunk_id="c1",
        doc_name="manual.pdf",
        page_number=1,
        text="Cột áp toàn phần H = 35m"
    )
    mock_retriever.retrieve.return_value = [RetrievalResult(chunk=mock_chunk, score=0.9)]
    mock_retriever.hybrid_search.return_value = [RetrievalResult(chunk=mock_chunk, score=0.9)]

    mock_llm = MagicMock()

    # Mock contextualizer to reformulate follow-up
    def mock_generate(prompt, **kwargs):
        if "standalone" in prompt.lower() or "viết lại" in prompt.lower():
            return "Cột áp toàn phần H bằng bao nhiêu?"
        return "Cột áp toàn phần H = 35m [Tài liệu: manual.pdf, Trang 1]."

    mock_llm.generate.side_effect = mock_generate

    agent = AgenticRAG(retriever=mock_retriever, llm_client=mock_llm, provider="mock")
    return agent


def test_contextualize_with_history_rewrites_query(mock_agent):
    history = [
        {"role": "user", "content": "Bơm ly tâm đang thử nghiệm có thông số gì?"},
        {"role": "assistant", "content": "Bơm thử theo TCVN 9222 [Tài liệu: manual.pdf, Trang 1]."}
    ]
    response = mock_agent.answer("Nó có H bằng bao nhiêu?", top_k=5, history=history)
    assert response.standalone_question == "Cột áp toàn phần H bằng bao nhiêu?"
    assert "35m" in response.answer
    assert any("0. contextualize" in step for step in response.reasoning_steps or [])


def test_contextualize_without_history_passes_through(mock_agent):
    response = mock_agent.answer("Tính Reynolds khi D = 0.2m", top_k=5, history=[])
    assert response.standalone_question is None


def test_contextualize_none_history_bypasses_llm():
    mock_retriever = MagicMock()
    mock_chunk = DocumentChunk(
        chunk_id="c1",
        doc_name="manual.pdf",
        page_number=1,
        text="Công thức tính Reynolds Re = V*D/nu"
    )
    mock_retriever.retrieve.return_value = [RetrievalResult(chunk=mock_chunk, score=0.9)]
    mock_llm = MagicMock()
    mock_llm.generate.return_value = "Công thức tính Reynolds Re = V*D/nu [Tài liệu: manual.pdf, Trang 1]."

    agent = AgenticRAG(retriever=mock_retriever, llm_client=mock_llm, provider="mock")
    response = agent.answer("Tính Reynolds khi D = 0.2m", top_k=5, history=None)

    assert response.standalone_question is None
    # Ensure contextualizer LLM prompt was never called when history=None
    for call_args in mock_llm.generate.call_args_list:
        prompt_arg = call_args[0][0]
        assert "lịch sử hội thoại" not in prompt_arg.lower()
        assert "câu hỏi độc lập" not in prompt_arg.lower()


def test_contextualize_llm_failure_falls_back_to_raw_question():
    mock_retriever = MagicMock()
    mock_chunk = DocumentChunk(
        chunk_id="c1",
        doc_name="manual.pdf",
        page_number=1,
        text="Khối lượng máy bơm là 150kg"
    )
    mock_retriever.retrieve.return_value = [RetrievalResult(chunk=mock_chunk, score=0.9)]

    mock_llm = MagicMock()

    def mock_generate_failing(prompt, **kwargs):
        if "lịch sử hội thoại" in prompt.lower() or "câu hỏi độc lập" in prompt.lower():
            raise RuntimeError("LLM API Timeout")
        return "Khối lượng máy bơm là 150kg [Tài liệu: manual.pdf, Trang 1]."

    mock_llm.generate.side_effect = mock_generate_failing

    agent = AgenticRAG(retriever=mock_retriever, llm_client=mock_llm, provider="mock")
    history = [{"role": "user", "content": "Thông số máy bơm"}]
    response = agent.answer("Nó nặng bao nhiêu kg?", top_k=5, history=history)

    assert response.standalone_question is None


def test_build_rag_prompt_with_history():
    mock_chunk = DocumentChunk(
        chunk_id="c1",
        doc_name="pump.pdf",
        page_number=3,
        text="Công suất bơm P = 15kW"
    )
    chunks = [RetrievalResult(chunk=mock_chunk, score=0.9)]
    history = [
        {"role": "user", "content": "Bơm loại gì?"},
        {"role": "assistant", "content": "Bơm ly tâm trục ngang [Tài liệu: pump.pdf, Trang 1]."}
    ]
    prompt = build_rag_prompt("Công suất bao nhiêu?", chunks, history=history)

    assert "LỊCH SỬ TRAO ĐỔI GẦN ĐÂY:" in prompt
    assert "Người dùng: Bơm loại gì?" in prompt
    assert "Trợ lý: Bơm ly tâm trục ngang" in prompt
    assert "DỮ LIỆU TÀI LIỆU CUNG CẤP:" in prompt
    assert "CÂU HỎI:" in prompt
    assert "Công suất bao nhiêu?" in prompt


def test_build_rag_prompt_without_history():
    mock_chunk = DocumentChunk(
        chunk_id="c1",
        doc_name="pump.pdf",
        page_number=3,
        text="Công suất bơm P = 15kW"
    )
    chunks = [RetrievalResult(chunk=mock_chunk, score=0.9)]
    prompt = build_rag_prompt("Công suất bao nhiêu?", chunks, history=None)

    assert "LỊCH SỬ TRAO ĐỔI GẦN ĐÂY:" not in prompt
    assert "DỮ LIỆU TÀI LIỆU CUNG CẤP:" in prompt
