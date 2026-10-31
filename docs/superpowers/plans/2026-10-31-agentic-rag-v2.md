# Agentic RAG v2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build and integrate Agentic RAG v2 with Hybrid Search (BM25 + Qdrant Dense via RRF), Local Cross-Encoder Reranker (`bge-reranker-base`), Context Sufficiency Grading, Feedback-guided Query Rewrite, Citation Self-Correction retry loops, and clean LangGraph StateGraph visualization.

**Architecture:** An 8-node compiled LangGraph StateGraph connecting an intent-extracting router, multilingual query expansion, BM25 + Dense vector hybrid search fused via RRF, local cross-encoder reranking, LLM context sufficiency grading with feedback rewrite, grounded generation, and citation self-correction loops.

**Tech Stack:** Python 3.12, FastAPI, LangGraph, Qdrant Client, `rank-bm25`, `sentence-transformers` (CrossEncoder), Google GenAI (`gemini-3.5-flash-lite`), Streamlit, Pytest.

**Spec:** [`docs/superpowers/specs/2026-10-31-agentic-rag-v2-architecture.md`](file:///Users/lehieu/Projects/personal/Agentic_RAG/docs/superpowers/specs/2026-10-31-agentic-rag-v2-architecture.md)

---

## Global Constraints

- Python floor: `>=3.10`.
- All Git operations MUST be prefixed with `DEVELOPER_DIR=/Library/Developer/CommandLineTools GIT_CONFIG_GLOBAL=/dev/null`.
- Existing `AgenticRAG.answer(question: str, top_k: int = 5) -> QAResponse` signature and `QAResponse` model MUST remain 100% backward-compatible.
- Unit tests MUST run quickly and deterministically without requiring live external internet or Gemini API access (mocking LLM and CrossEncoder where appropriate).
- Default LLM model name MUST be `gemini-3.5-flash-lite`.
- Graph diagram export MUST save to `docs/langgraph_workflow.png`.

---

## Review Focus

1. **Mixed-intent queries:** Queries like *"Chào bạn, TCVN 9222 quy định về điều gì?"* must not be trapped in canned chitchat; the greeting prefix must be stripped and the technical query passed into retrieval.
2. **Standard codes and exact identifiers:** Strings like `TCVN 9222:2012`, `ISO 9906:1999`, `Điều 24`, and `TKE-380` must be preserved intact by the BM25 tokenizer and score high in sparse search.
3. **Empty or low-relevance retrieval:** If neither BM25 nor dense search yields relevant chunks, the sufficiency grader must trigger query rewrite with clear feedback, and if still insufficient, gracefully abstain without unhandled exceptions.
4. **Citation self-correction limit:** The citation correction loop must retry at most 1 time (`gen_retries < 1`). If the regenerated answer still contains invalid citations, it must transition to abstain to prevent infinite generation loops.
5. **No regression on existing test suite:** All 76 existing unit and integration tests must continue passing.

---

## Tasks

### Task 1: Sparse BM25 Retriever

**Files:**
- Modify: `pyproject.toml`
- Create: `src/retrieval/bm25.py`
- Test: `tests/test_bm25.py`

**Interfaces:**
- Consumes: `DocumentChunk` from `src.models`
- Produces:
  ```python
  class BM25Retriever(BaseRetriever):
      def __init__(self, chunks: Optional[List[DocumentChunk]] = None) -> None: ...
      def index_chunks(self, chunks: List[DocumentChunk]) -> int: ...
      def search(self, query: str, top_k: int = 10) -> List[RetrievalResult]: ...
  ```

- [ ] **Step 1: Add `rank-bm25>=0.2.2` to `pyproject.toml` and install in `.venv`**
  Run: `.venv/bin/pip install rank-bm25>=0.2.2`

- [ ] **Step 2: Write failing tests in `tests/test_bm25.py`**
  Cover:
  - Exact token match on standard code `TCVN 9222:2012` and model name `TKE-380`.
  - Empty index and empty query safety.
  - Sorting results by BM25 score.

- [ ] **Step 3: Run test to verify it fails**
  Run: `.venv/bin/pytest tests/test_bm25.py -v`
  Expected: FAIL with `ModuleNotFoundError: No module named 'src.retrieval.bm25'`

- [ ] **Step 4: Implement `src/retrieval/bm25.py`**
  Use regex tokenizer `r"[\w]+|[^\s\w]+"` to retain alphanumeric sequences and hyphenated/colon symbols. Wrap `BM25Okapi` and normalize scores to `[0.0, 1.0]`.

- [ ] **Step 5: Run test to verify it passes**
  Run: `.venv/bin/pytest tests/test_bm25.py -v`
  Expected: PASS

- [ ] **Step 6: Commit**
  ```bash
  DEVELOPER_DIR=/Library/Developer/CommandLineTools GIT_CONFIG_GLOBAL=/dev/null git add pyproject.toml src/retrieval/bm25.py tests/test_bm25.py
  DEVELOPER_DIR=/Library/Developer/CommandLineTools GIT_CONFIG_GLOBAL=/dev/null git commit -m "feat(retrieval): implement BM25Retriever with technical symbol tokenization"
  ```

---

### Task 2: Hybrid Retriever with Reciprocal Rank Fusion (RRF)

**Files:**
- Create: `src/retrieval/hybrid.py`
- Modify: `src/retrieval/__init__.py`
- Test: `tests/test_hybrid.py`

**Interfaces:**
- Consumes: `BaseRetriever` from `src.retrieval.base`, `DocumentChunk`, `RetrievalResult` from `src.models`
- Produces:
  ```python
  class HybridRetriever(BaseRetriever):
      def __init__(self, dense_retriever: BaseRetriever, sparse_retriever: BM25Retriever, rrf_k: int = 60) -> None: ...
      def index_chunks(self, chunks: List[DocumentChunk]) -> int: ...
      def search(self, query: str, top_k: int = 20) -> List[RetrievalResult]: ...
  ```

- [ ] **Step 1: Write failing tests in `tests/test_hybrid.py`**
  Cover:
  - Combining mock dense results and mock sparse results using RRF score formula `1.0 / (rrf_k + rank)`.
  - Chunk deduplication by `chunk_id`.
  - Indexing delegation to both dense and sparse components.

- [ ] **Step 2: Run test to verify it fails**
  Run: `.venv/bin/pytest tests/test_hybrid.py -v`
  Expected: FAIL with `ModuleNotFoundError: No module named 'src.retrieval.hybrid'`

- [ ] **Step 3: Implement `src/retrieval/hybrid.py`**
  Implement `HybridRetriever` adhering to `BaseRetriever`. Export it in `src/retrieval/__init__.py`.

- [ ] **Step 4: Run test to verify it passes**
  Run: `.venv/bin/pytest tests/test_hybrid.py -v`
  Expected: PASS

- [ ] **Step 5: Commit**
  ```bash
  DEVELOPER_DIR=/Library/Developer/CommandLineTools GIT_CONFIG_GLOBAL=/dev/null git add src/retrieval/hybrid.py src/retrieval/__init__.py tests/test_hybrid.py
  DEVELOPER_DIR=/Library/Developer/CommandLineTools GIT_CONFIG_GLOBAL=/dev/null git commit -m "feat(retrieval): implement HybridRetriever with Reciprocal Rank Fusion"
  ```

---

### Task 3: Local Cross-Encoder Reranker

**Files:**
- Create: `src/retrieval/reranker.py`
- Modify: `src/config.py`
- Test: `tests/test_reranker.py`

**Interfaces:**
- Consumes: `RetrievalResult` from `src.models`
- Produces:
  ```python
  class CrossEncoderReranker:
      def __init__(self, model_name: str = "BAAI/bge-reranker-base", device: Optional[str] = None) -> None: ...
      def rerank(self, query: str, candidates: List[RetrievalResult], top_k: int = 5) -> List[RetrievalResult]: ...
  ```

- [ ] **Step 1: Add configuration keys to `src/config.py`**
  Add:
  - `reranker_model: str = "BAAI/bge-reranker-base"`
  - `hybrid_rrf_k: int = 60`
  - `hybrid_candidate_top_k: int = 20`
  - `rerank_top_k: int = 5`

- [ ] **Step 2: Write failing tests in `tests/test_reranker.py`**
  Cover:
  - Lazy initialization of CrossEncoder.
  - Scoring candidate pairs and updating `RetrievalResult.score`.
  - Truncation to `top_k`.
  - Empty candidate list safety.

- [ ] **Step 3: Run test to verify it fails**
  Run: `.venv/bin/pytest tests/test_reranker.py -v`
  Expected: FAIL with `ModuleNotFoundError: No module named 'src.retrieval.reranker'`

- [ ] **Step 4: Implement `src/retrieval/reranker.py`**
  Use `sentence_transformers.CrossEncoder`. Implement lazy loading so import/unit tests without heavy model download remain instantaneous.

- [ ] **Step 5: Run test to verify it passes**
  Run: `.venv/bin/pytest tests/test_reranker.py -v`
  Expected: PASS

- [ ] **Step 6: Commit**
  ```bash
  DEVELOPER_DIR=/Library/Developer/CommandLineTools GIT_CONFIG_GLOBAL=/dev/null git add src/retrieval/reranker.py src/config.py tests/test_reranker.py
  DEVELOPER_DIR=/Library/Developer/CommandLineTools GIT_CONFIG_GLOBAL=/dev/null git commit -m "feat(retrieval): implement CrossEncoderReranker with lazy loading"
  ```

---

### Task 4: LangGraph Closed-Loop AgenticRAG Engine

**Files:**
- Modify: `src/rag/agent.py`
- Modify: `src/api/main.py`
- Modify: `tests/test_agentic_rag.py`
- Output: `docs/langgraph_workflow.png`

**Interfaces:**
- Consumes: `HybridRetriever`, `CrossEncoderReranker`, `RAGGenerator`
- Produces:
  ```python
  class AgenticRAG:
      def __init__(
          self,
          retriever: Optional[BaseRetriever] = None,
          reranker: Optional[CrossEncoderReranker] = None,
          llm_client: Optional[Any] = None,
          provider: str = "gemini",
          model_name: Optional[str] = None,
          min_relevance_score: float = 0.35,
          max_retries: int = 1,
          max_gen_retries: int = 1
      ) -> None: ...
      def answer(self, question: str, top_k: int = 5) -> QAResponse: ...
      def draw_png(self, output_path: Optional[str] = "docs/langgraph_workflow.png") -> bytes: ...
  ```

- [ ] **Step 1: Write failing unit tests in `tests/test_agentic_rag.py`**
  Add tests for:
  - Mixed intent: `"Chào bạn, máy bơm TKE-380 có cấu tạo gì?"` strips greeting and searches for pump structure.
  - Relevance Grader triggers `rewrite_query` with feedback when context is insufficient.
  - Citation self-correction loop regenerates with feedback on invalid citations.
  - Safe abstention after max retries exhausted.

- [ ] **Step 2: Run test to verify it fails**
  Run: `.venv/bin/pytest tests/test_agentic_rag.py -v`
  Expected: FAIL on new assertions.

- [ ] **Step 3: Refactor `src/rag/agent.py`**
  Implement the 8+1 numbered nodes:
  - `1_router`: Intent extractor & greeting stripper.
  - `2_expand_query`: Multilingual/OCR query generator.
  - `3_hybrid_retrieve`: Multi-query retrieval.
  - `4_rerank`: Cross-Encoder reranking.
  - `5_grade_relevance`: Context sufficiency grader.
  - `6_rewrite_query`: Feedback-guided query rewrite.
  - `7_generate`: Grounded synthesis.
  - `8_validate_citations`: Citation grounding with 1-time retry loop.
  - `9_abstain`: Grounded refusal.
  Update `draw_png()` to render the simplified, numbered diagram.

- [ ] **Step 4: Update `src/api/main.py`**
  Wire `BM25Retriever`, `HybridRetriever`, and `CrossEncoderReranker` into `app.state` upon startup. Rebuild BM25 index from stored uploads.

- [ ] **Step 5: Run test to verify it passes**
  Run: `.venv/bin/pytest tests/test_agentic_rag.py -v`
  Expected: PASS

- [ ] **Step 6: Export updated LangGraph diagram**
  Run: `.venv/bin/python -c "from src.rag.agent import AgenticRAG; agent = AgenticRAG(retriever=None); agent.draw_png('docs/langgraph_workflow.png')"`

- [ ] **Step 7: Commit**
  ```bash
  DEVELOPER_DIR=/Library/Developer/CommandLineTools GIT_CONFIG_GLOBAL=/dev/null git add src/rag/agent.py src/api/main.py tests/test_agentic_rag.py docs/langgraph_workflow.png
  DEVELOPER_DIR=/Library/Developer/CommandLineTools GIT_CONFIG_GLOBAL=/dev/null git commit -m "feat(rag): implement LangGraph v2 with grader, citation correction, and hybrid rerank"
  ```

---

### Task 5: End-to-End Regression Verification & Deployment

**Files:**
- Test: All tests in `tests/`
- Documentation & Artifacts: `docs/langgraph_workflow.png`

- [ ] **Step 1: Run complete test suite**
  Run: `.venv/bin/pytest -v`
  Expected: All tests pass (80+ tests).

- [ ] **Step 2: Launch backend and UI daemons**
  - Start FastAPI: `.venv/bin/uvicorn src.api.main:app --host 0.0.0.0 --port 8000` (IsDaemon: true)
  - Start Streamlit: `.venv/bin/streamlit run src/ui/app.py --server.port 8501 --server.headless true` (IsDaemon: true)

- [ ] **Step 3: Execute verification queries**
  - Verify `curl -s http://localhost:8000/api/v1/health` returns status ok.
  - Verify mixed query: `curl -s -X POST http://localhost:8000/api/v1/query -H "Content-Type: application/json" -d '{"question": "Chào bạn, phương pháp đo diện tích vận tốc được nêu ở đâu?"}'` returns grounded response citing page 2 of pump manual.

- [ ] **Step 4: Final commit and push**
  ```bash
  DEVELOPER_DIR=/Library/Developer/CommandLineTools GIT_CONFIG_GLOBAL=/dev/null git push origin main
  ```
