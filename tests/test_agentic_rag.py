"""Tests for AgenticRAG: Query expansion, multi-query retrieval, self-correction, and citation grounding."""

import json
from unittest.mock import MagicMock
from src.models import DocumentChunk, RetrievalResult
from src.rag.prompt import ABSTAIN_PHRASE
from src.retrieval.base import BaseRetriever
from src.rag.agent import AgenticRAG


def _create_chunk(doc_name: str, page_number: int, chunk_id: str, text: str, score: float, chunk_index: int = 0) -> RetrievalResult:
    return RetrievalResult(
        chunk=DocumentChunk(
            chunk_id=chunk_id,
            doc_name=doc_name,
            page_number=page_number,
            text=text,
            metadata={"chunk_index": chunk_index}
        ),
        score=score
    )


def test_agent_query_expansion_generates_variations():
    """Test expand_query('áp suất máy bơm') returns a list of 1-3 distinct formulations."""
    mock_retriever = MagicMock(spec=BaseRetriever)
    agent = AgenticRAG(retriever=mock_retriever, llm_client=None)

    # 1. Deterministic / mock mode without LLM
    variations = agent.expand_query("áp suất máy bơm")
    assert isinstance(variations, list)
    assert 1 <= len(variations) <= 4
    assert len(set(variations)) == len(variations)  # All distinct
    assert any("áp suất máy bơm" in v for v in variations)

    # 2. LLM mode with mocked client
    mock_llm = MagicMock()
    mock_llm.models.generate_content.return_value.text = "áp suất tối đa máy bơm\ntiêu chuẩn áp lực bơm\náp lực làm việc của bơm"
    agent_with_llm = AgenticRAG(retriever=mock_retriever, llm_client=mock_llm, provider="gemini")
    llm_variations = agent_with_llm.expand_query("áp suất máy bơm")
    assert isinstance(llm_variations, list)
    assert 1 <= len(llm_variations) <= 4
    assert len(set(llm_variations)) == len(llm_variations)
    assert "áp suất tối đa máy bơm" in llm_variations


def test_agent_multi_query_retrieval_deduplication():
    """Mock retriever with overlapping chunks for 2 queries, verify chunks are merged and deduplicated."""
    mock_retriever = MagicMock(spec=BaseRetriever)

    chunk_a_low = _create_chunk("pump.pdf", 1, "c1", "Van an toàn mở ở 10 bar", score=0.70, chunk_index=0)
    chunk_b = _create_chunk("pump.pdf", 2, "c2", "Công suất động cơ 15kW", score=0.60, chunk_index=1)
    chunk_a_high = _create_chunk("pump.pdf", 1, "c1", "Van an toàn mở ở 10 bar", score=0.95, chunk_index=0)
    chunk_c = _create_chunk("manual.pdf", 5, "c3", "Bảo dưỡng định kỳ 6 tháng", score=0.80, chunk_index=0)

    def mock_search(query: str, top_k: int = 5):
        if "thông số" in query:
            return [chunk_a_high, chunk_c]
        return [chunk_a_low, chunk_b]

    mock_retriever.search.side_effect = mock_search

    agent = AgenticRAG(retriever=mock_retriever, llm_client=None)
    results = agent.multi_query_retrieve(["áp suất máy bơm", "áp suất máy bơm thông số"], top_k=5)

    # Must be deduplicated: only 3 unique chunks (c1, c2, c3)
    assert len(results) == 3

    # Best score for chunk_a should be 0.95
    c1_results = [r for r in results if r.chunk.chunk_id == "c1"]
    assert len(c1_results) == 1
    assert c1_results[0].score == 0.95

    # Results must be sorted descending by score
    scores = [r.score for r in results]
    assert scores == sorted(scores, reverse=True)
    assert scores == [0.95, 0.80, 0.60]


def test_agent_self_reflection_triggers_query_rewrite_on_low_score():
    """Mock retriever returning score < 0.45 on first query, verify rewrite_query is invoked and second search runs."""
    mock_retriever = MagicMock(spec=BaseRetriever)

    low_score_chunk = _create_chunk("pump.pdf", 1, "c1", "Thông tin chung", score=0.30)
    high_score_chunk = _create_chunk("pump.pdf", 3, "c2", "Áp suất làm việc danh định 16 bar", score=0.88)

    queries_searched = []

    def mock_search(query: str, top_k: int = 5):
        queries_searched.append(query)
        if "nguyên lý" in query or "tổng quan" in query:
            return [high_score_chunk]
        return [low_score_chunk]

    mock_retriever.search.side_effect = mock_search

    agent = AgenticRAG(
        retriever=mock_retriever,
        llm_client=None,
        min_relevance_score=0.45,
        max_retries=1
    )

    response = agent.answer("áp suất danh định máy bơm", top_k=3)

    # Verify query rewrite was triggered and searched
    assert any("nguyên lý" in q or "tổng quan" in q for q in queries_searched)
    assert response.abstained is False
    assert len(response.citations) >= 1
    assert response.citations[0].doc_name == "pump.pdf"
    assert response.citations[0].page_number == 3
    assert response.rewritten_queries is not None
    assert len(response.rewritten_queries) > 1
    assert response.reasoning_steps is not None
    assert any("rewrite" in step.lower() or "thấp" in step.lower() or "below" in step.lower() for step in response.reasoning_steps)


def test_agent_citation_grounding_preserves_valid_and_rejects_hallucinations():
    """Verify that synthesized answer citations are strictly verified against retrieved chunks."""
    mock_retriever = MagicMock(spec=BaseRetriever)
    retrieved_chunk = _create_chunk("pump.pdf", 5, "c1", "Nhiệt độ tối đa 80 độ C.", score=0.90)
    mock_retriever.search.return_value = [retrieved_chunk]

    agent = AgenticRAG(retriever=mock_retriever, llm_client=None, min_relevance_score=0.45)

    # 1. Valid citation matching pump.pdf p.5 and hallucinated citation pointing to ghost_manual.pdf p.99
    raw_mixed = (
        "Nhiệt độ tối đa là 80 độ C [Tài liệu: pump.pdf, Trang 5]. "
        "Ngoài ra van phụ trợ chịu 120 độ C [Tài liệu: ghost_manual.pdf, Trang 99]."
    )
    validated = agent.validate_citations(raw_mixed, [retrieved_chunk])
    assert validated.abstained is False
    assert len(validated.citations) == 1
    assert validated.citations[0].doc_name == "pump.pdf"
    assert validated.citations[0].page_number == 5

    # 2. Fully hallucinated citation triggers abstention
    raw_hallucinated = "Thông số bịa đặt [Tài liệu: ghost_manual.pdf, Trang 99]."
    validated_hallucinated = agent.validate_citations(raw_hallucinated, [retrieved_chunk])
    assert validated_hallucinated.abstained is True
    assert ABSTAIN_PHRASE in validated_hallucinated.answer
    assert len(validated_hallucinated.citations) == 0


def test_agent_abstains_when_no_relevant_data_found():
    """Test question with zero relevant chunks yields abstained=True."""
    mock_retriever = MagicMock(spec=BaseRetriever)
    # Return only irrelevant low-scoring chunk for all attempts
    irrelevant_chunk = _create_chunk("other.pdf", 10, "c9", "Nội dung không liên quan", score=0.20)
    mock_retriever.search.return_value = [irrelevant_chunk]

    agent = AgenticRAG(
        retriever=mock_retriever,
        llm_client=None,
        min_relevance_score=0.45,
        max_retries=1
    )

    response = agent.answer("câu hỏi về công nghệ vũ trụ NASA", top_k=3)
    assert response.abstained is True
    assert ABSTAIN_PHRASE in response.answer
    assert len(response.citations) == 0
    assert response.reasoning_steps is not None


def test_agent_chitchat_router_handles_greetings_without_db_query():
    """Verify that greetings and bot introductory queries respond immediately without querying retriever."""
    mock_retriever = MagicMock(spec=BaseRetriever)
    agent = AgenticRAG(retriever=mock_retriever, llm_client=None)

    greetings = [
        "hello",
        "Hello!",
        "hi",
        "xin chào",
        "Chào bạn",
        "bạn là ai",
        "bạn có thể làm gì",
        "bạn giúp gì được cho tôi",
        "how can you help me",
        "what can you do",
        "who are you",
        "cảm ơn",
        "tạm biệt",
    ]
    for q in greetings:
        resp = agent.answer(q)
        assert resp.abstained is False, f"Failed for '{q}'"
        assert len(resp.citations) == 0
        assert len(resp.retrieved_chunks) == 0
        assert len(resp.answer.strip()) > 10
        assert any("Chit-chat" in step for step in resp.reasoning_steps)

    # Verify retriever search was never called for chit-chat
    mock_retriever.search.assert_not_called()


def test_agent_hybrid_router_llm_intent_classification():
    """Verify that when regex does not match, LLM intent classifier fallback detects chitchat vs technical query."""
    mock_retriever = MagicMock(spec=BaseRetriever)
    mock_llm = MagicMock()

    # 1. Non-regex chitchat query recognized by LLM
    mock_llm.models.generate_content.return_value.text = json.dumps({
        "intent": "CHITCHAT",
        "reply": "I am an intelligent document assistant designed to help engineering teams."
    })
    agent = AgenticRAG(retriever=mock_retriever, llm_client=mock_llm, provider="gemini")

    novel_query = "Could you elaborate on the functionalities you provide to engineers?"
    resp = agent.answer(novel_query)

    assert resp.abstained is False
    assert "intelligent document assistant" in resp.answer
    assert len(resp.citations) == 0
    assert any("LLM" in step and "Router" in step for step in resp.reasoning_steps)
    mock_retriever.search.assert_not_called()

    # 2. Technical query correctly classified by LLM
    mock_llm.models.generate_content.return_value.text = json.dumps({
        "intent": "TECHNICAL_QUERY",
        "reply": None
    })
    router_state = agent._node_router({"question": "Cho biết công suất động cơ máy bơm"})
    assert router_state["is_chitchat"] is False
    assert router_state["clean_question"] == "Cho biết công suất động cơ máy bơm"


def test_agent_expand_query_includes_unaccented_vietnamese():
    """Verify that query expansion adds unaccented Vietnamese variation for OCR tolerance."""
    mock_retriever = MagicMock(spec=BaseRetriever)
    agent = AgenticRAG(retriever=mock_retriever, llm_client=None)

    variations = agent.expand_query("phương pháp đo diện tích vận tốc")
    assert any("phuong phap do dien tich van toc" in v.lower() for v in variations)


def test_agent_mixed_intent_greeting_stripping():
    """Verify that greetings in mixed queries are stripped and search proceeds with clean_question."""
    mock_retriever = MagicMock(spec=BaseRetriever)
    pump_chunk = _create_chunk("pump.pdf", 1, "c1", "Máy bơm TKE-380 có cấu tạo gồm trục và cánh bơm.", score=0.90)
    searched_queries = []

    def mock_search(query: str, top_k: int = 5):
        searched_queries.append(query)
        return [pump_chunk]

    mock_retriever.search.side_effect = mock_search
    agent = AgenticRAG(retriever=mock_retriever, llm_client=None)

    resp = agent.answer("Chào bạn, máy bơm TKE-380 có cấu tạo gì?", top_k=3)
    assert resp.abstained is False
    assert len(resp.citations) >= 1
    assert resp.citations[0].doc_name == "pump.pdf"
    # Verify retriever was called with queries derived from the cleaned question, NOT with "Chào bạn"
    assert len(searched_queries) > 0
    assert any("máy bơm tke-380" in q.lower() for q in searched_queries)
    assert not any(q.strip().lower().startswith("chào bạn,") for q in searched_queries)
    assert any("chuẩn hóa" in s.lower() or "tke-380" in s.lower() for s in resp.reasoning_steps)


def test_relevance_and_sufficiency_grader_triggers_rewrite_when_insufficient():
    """Verify grader node identifies insufficient context and triggers feedback-guided rewrite."""
    mock_retriever = MagicMock(spec=BaseRetriever)
    mock_llm = MagicMock()

    chunk_vague = _create_chunk("manual.pdf", 2, "c1", "Máy bơm dùng trong công nghiệp.", score=0.60)
    chunk_full = _create_chunk("manual.pdf", 5, "c2", "Cấu tạo máy bơm TKE-380 gồm động cơ 15kW, trục thép và 2 cánh bơm.", score=0.92)

    def mock_search(query: str, top_k: int = 5):
        if "cấu tạo" in query.lower() and "trục" in query.lower():
            return [chunk_full]
        return [chunk_vague]

    mock_retriever.search.side_effect = mock_search

    call_counts = {"grade": 0}

    def mock_generate_content(model: str, contents: str):
        mock_resp = MagicMock()
        if "phân loại ý định" in contents.lower() or "intent" in contents.lower():
            mock_resp.text = '{"intent": "TECHNICAL_QUERY", "reply": null}'
        elif "đánh giá ngữ cảnh" in contents.lower() or "sufficiency" in contents.lower():
            call_counts["grade"] += 1
            if call_counts["grade"] == 1:
                mock_resp.text = '{"is_sufficient": false, "missing_aspects": "thiếu cấu tạo trục và cánh"}'
            else:
                mock_resp.text = '{"is_sufficient": true, "missing_aspects": ""}'
        elif "viết lại" in contents.lower() or "rewrite" in contents.lower():
            mock_resp.text = "máy bơm TKE-380 cấu tạo trục"
        elif "biến thể tìm kiếm" in contents.lower():
            mock_resp.text = "máy bơm TKE-380\npump TKE-380"
        else:
            mock_resp.text = "Cấu tạo gồm động cơ, trục và 2 cánh [Tài liệu: manual.pdf, Trang 5]."
        return mock_resp

    mock_llm.models.generate_content.side_effect = mock_generate_content

    agent = AgenticRAG(retriever=mock_retriever, llm_client=mock_llm, provider="gemini", max_retries=1)
    resp = agent.answer("máy bơm TKE-380 cấu tạo thế nào?", top_k=3)

    assert resp.abstained is False
    assert len(resp.citations) == 1
    assert resp.citations[0].doc_name == "manual.pdf"
    assert resp.citations[0].page_number == 5
    assert call_counts["grade"] == 2
    assert any("thiếu cấu tạo" in s.lower() or "chưa đủ" in s.lower() for s in resp.reasoning_steps)


def test_feedback_guided_rewrite_incorporates_grader_reason():
    """Verify that rewrite_query receives and incorporates grader feedback into prompt."""
    mock_retriever = MagicMock(spec=BaseRetriever)
    mock_llm = MagicMock()

    prompts_captured = []

    def mock_generate_content(model: str, contents: str):
        prompts_captured.append(contents)
        mock_resp = MagicMock()
        if "đánh giá ngữ cảnh" in contents.lower() or "sufficiency" in contents.lower():
            mock_resp.text = '{"is_sufficient": false, "missing_aspects": "thiếu thông số áp lực danh định"}'
        elif "viết lại" in contents.lower() or "truy vấn" in contents.lower():
            mock_resp.text = "áp suất danh định máy bơm TKE"
        else:
            mock_resp.text = "áp suất máy bơm\náp lực làm việc"
        return mock_resp

    mock_llm.models.generate_content.side_effect = mock_generate_content
    agent = AgenticRAG(retriever=mock_retriever, llm_client=mock_llm, provider="gemini", max_retries=0)

    agent.rewrite_query(
        question="máy bơm TKE",
        attempted_queries=["máy bơm TKE"],
        missing_aspect="thiếu thông số áp lực danh định"
    )

    rewrite_prompts = [p for p in prompts_captured if "viết lại" in p.lower() or "truy vấn" in p.lower()]
    assert len(rewrite_prompts) >= 1
    assert "thiếu thông số áp lực danh định" in rewrite_prompts[0]


def test_citation_self_correction_loop_regenerates_with_feedback():
    """Verify citation failure triggers 1-time regeneration loop with error feedback directive."""
    mock_retriever = MagicMock(spec=BaseRetriever)
    mock_llm = MagicMock()

    retrieved_chunk = _create_chunk("pump.pdf", 3, "c1", "Áp suất tối đa 16 bar.", score=0.90)
    mock_retriever.search.return_value = [retrieved_chunk]

    generate_prompts = []
    gen_call = {"count": 0}

    def mock_generate_content(model: str, contents: str):
        mock_resp = MagicMock()
        if "phân loại ý định" in contents.lower() or "intent" in contents.lower():
            mock_resp.text = '{"intent": "TECHNICAL_QUERY", "reply": null}'
        elif "đánh giá ngữ cảnh" in contents.lower() or "sufficiency" in contents.lower():
            mock_resp.text = '{"is_sufficient": true, "missing_aspects": ""}'
        elif "biến thể tìm kiếm" in contents.lower():
            mock_resp.text = "áp suất máy bơm\npump pressure"
        else:
            generate_prompts.append(contents)
            gen_call["count"] += 1
            if gen_call["count"] == 1:
                mock_resp.text = "Áp suất máy bơm là 16 bar [Tài liệu: fake_manual.pdf, Trang 99]."
            else:
                mock_resp.text = "Áp suất máy bơm là 16 bar [Tài liệu: pump.pdf, Trang 3]."
        return mock_resp

    mock_llm.models.generate_content.side_effect = mock_generate_content

    agent = AgenticRAG(retriever=mock_retriever, llm_client=mock_llm, provider="gemini", max_gen_retries=1)
    resp = agent.answer("áp suất máy bơm?", top_k=3)

    assert resp.abstained is False
    assert len(resp.citations) == 1
    assert resp.citations[0].doc_name == "pump.pdf"
    assert resp.citations[0].page_number == 3
    assert gen_call["count"] == 2
    assert len(generate_prompts) == 2
    assert "fake_manual.pdf" in generate_prompts[1] or "Lưu ý" in generate_prompts[1]


def test_abstention_when_retries_exhausted_or_invalid_citations_persist():
    """Verify safe abstention when retrieval retries exhausted or invalid citations persist."""
    mock_retriever = MagicMock(spec=BaseRetriever)
    mock_llm = MagicMock()

    retrieved_chunk = _create_chunk("pump.pdf", 3, "c1", "Áp suất tối đa 16 bar.", score=0.90)
    mock_retriever.search.return_value = [retrieved_chunk]

    def mock_generate_content(model: str, contents: str):
        mock_resp = MagicMock()
        if "phân loại ý định" in contents.lower() or "intent" in contents.lower():
            mock_resp.text = '{"intent": "TECHNICAL_QUERY", "reply": null}'
        elif "đánh giá ngữ cảnh" in contents.lower() or "sufficiency" in contents.lower():
            mock_resp.text = '{"is_sufficient": true, "missing_aspects": ""}'
        elif "biến thể tìm kiếm" in contents.lower():
            mock_resp.text = "áp suất máy bơm"
        else:
            mock_resp.text = "Áp suất máy bơm là 16 bar [Tài liệu: ghost_manual.pdf, Trang 99]."
        return mock_resp

    mock_llm.models.generate_content.side_effect = mock_generate_content

    agent = AgenticRAG(retriever=mock_retriever, llm_client=mock_llm, provider="gemini", max_gen_retries=1)
    resp = agent.answer("áp suất máy bơm?", top_k=3)

    assert resp.abstained is True
    assert ABSTAIN_PHRASE in resp.answer
    assert len(resp.citations) == 0



def test_refusal_on_sufficient_context_retries_with_refusal_directive():
    """A bare refusal after the grader judged context sufficient is retried with a
    directive to use the evidence (not a misleading 'missing citation' message)."""
    mock_retriever = MagicMock(spec=BaseRetriever)
    mock_llm = MagicMock()
    chunk = _create_chunk(
        "pump.pdf", 8, "c8",
        "He so Reynolds, tinh theo cong thurc (s) V trong do: U la van toc; D la duong kinh; v la do nhot", 0.9,
    )
    mock_retriever.search.return_value = [chunk]

    generate_prompts = []

    def mock_generate_content(model: str, contents: str):
        mock_resp = MagicMock()
        if contents.startswith("Bạn là trợ lý hỏi đáp tài liệu kỹ thuật"):
            generate_prompts.append(contents)
            mock_resp.text = (
                ABSTAIN_PHRASE if len(generate_prompts) == 1
                else "Re = U·D/ν [Tài liệu: pump.pdf, Trang 8]; còn thiếu vận tốc U và độ nhớt ν."
            )
        elif "phân loại ý định" in contents.lower() or "intent" in contents.lower():
            mock_resp.text = '{"intent": "TECHNICAL_QUERY", "reply": null}'
        elif "đánh giá ngữ cảnh" in contents.lower() or "sufficiency" in contents.lower():
            mock_resp.text = '{"is_sufficient": true, "missing_aspects": ""}'
        elif "biến thể tìm kiếm" in contents.lower():
            mock_resp.text = "chuẩn số Reynolds"
        return mock_resp

    mock_llm.models.generate_content.side_effect = mock_generate_content
    agent = AgenticRAG(retriever=mock_retriever, llm_client=mock_llm, provider="gemini", max_gen_retries=1)
    resp = agent.answer("Tính chuẩn số Reynolds cho ống D=150mm", top_k=3)

    assert resp.abstained is False
    assert [(c.doc_name, c.page_number) for c in resp.citations] == [("pump.pdf", 8)]
    assert len(generate_prompts) == 2
    assert "Bạn đã từ chối trả lời" in generate_prompts[1]
    assert "Thiếu trích dẫn nguồn" not in generate_prompts[1]
    assert any("Mô hình từ chối dù ngữ cảnh đủ căn cứ" in s for s in resp.reasoning_steps)
