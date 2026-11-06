"""Unit tests for synthetic QA generation and LLM-judge helpers (no network)."""

import time

import pytest

from src.eval.synthetic import (
    RateLimiter,
    generate_question_for_page,
    graded_ndcg,
    judge_passages,
    parse_json_object,
    shuffled_pool,
)

PAGE = {"doc_name": "tài liệu máy bơm.pdf", "page_number": 7, "text": "Áp suất làm việc tối đa là 10 bar."}


def test_parse_json_object_handles_code_fences_and_garbage():
    assert parse_json_object('```json\n{"a": 1}\n```') == {"a": 1}
    assert parse_json_object("không có json") is None
    assert parse_json_object("{broken") is None
    assert parse_json_object("") is None


def test_generate_question_labels_with_source_page():
    llm = lambda _: '{"skip": false, "question": "Áp suất làm việc tối đa là bao nhiêu?", "answer": "10 bar"}'
    item = generate_question_for_page(PAGE, llm)
    assert item["expected_doc"] == "tài liệu máy bơm.pdf"
    assert item["expected_pages"] == [7]
    assert item["ground_truth_answer"] == "10 bar"
    assert item["should_abstain"] is False


@pytest.mark.parametrize("raw", ['{"skip": true}', '{"question": "ngắn"}', "lỗi"])
def test_generate_question_rejects_skipped_or_invalid(raw):
    assert generate_question_for_page(PAGE, lambda _: raw) is None


def test_judge_passages_clamps_and_marks_missing():
    llm = lambda _: '{"grades": {"P1": 2, "P2": 5, "P3": "x"}}'
    assert judge_passages("q", ["a", "b", "c", "d"], llm) == [2, 2, None, None]
    assert judge_passages("q", [], llm) == []


def test_graded_ndcg_uses_pooled_ideal():
    pool = [2, 2, 1, 0, 0, 0]
    assert graded_ndcg([2, 2, 1, 0, 0], pool, k=5) == pytest.approx(1.0)
    assert graded_ndcg([0, 0, 0, 0, 0], pool, k=5) == 0.0
    assert 0.0 < graded_ndcg([0, 0, 1, 2, 2], pool, k=5) < 1.0
    assert graded_ndcg([0, 0], [0, 0], k=5) == 0.0


def test_shuffled_pool_dedupes_and_is_deterministic():
    texts = {"old": ["a", "b", " c "], "new": ["c", "d", "a"]}
    pool = shuffled_pool(texts, seed=3)
    assert sorted(pool) == ["a", "b", "c", "d"]
    assert pool == shuffled_pool(texts, seed=3)


def test_rate_limiter_spaces_calls():
    limiter = RateLimiter(rpm=600)  # 0.1s interval
    start = time.monotonic()
    for _ in range(3):
        limiter.wait()
    assert time.monotonic() - start >= 0.19
    RateLimiter(rpm=0).wait()  # disabled limiter never blocks
