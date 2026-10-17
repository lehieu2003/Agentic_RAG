# Document Q&A Assistant Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Xây dựng hệ thống Document Q&A Assistant chuyên nghiệp cho tài liệu kỹ thuật PDF, bao gồm pipeline OCR, chunking bảo toàn metadata số trang, tìm kiếm vector trên Qdrant, RAG có trích dẫn nguồn và cơ chế từ chối (Abstention), đo lường Recall@K trên tập Ground Truth, và tách module Retrieval thành microservice gRPC.

**Architecture:** Hexagonal / Clean Modular Monorepo với Abstract `BaseRetriever` làm trung tâm. Dữ liệu PDF được ingest qua PyMuPDF với OCR fallback cho trang scan, chunk và lưu vào Qdrant (hỗ trợ local embedded mode). Chatbot RAG chạy trên FastAPI dùng LLM API với guardrail trích dẫn & abstention. Module Retrieval có thể hoán đổi giữa `LocalRetriever` và `GrpcRetriever` (kết nối tới gRPC Server) chỉ qua cấu hình môi trường.

**Tech Stack:** Python 3.12, PyMuPDF (fitz), RapidOCR / pytesseract, Sentence-Transformers, Qdrant Client, FastAPI, Uvicorn, Pydantic v2, google-genai / openai, gRPC, protobuf, pytest.

**Spec:** [docs/superpowers/specs/2026-10-17-document-qa-assistant-design.md](file:///Users/lehieu/Projects/personal/Agentic_RAG/docs/superpowers/specs/2026-10-17-document-qa-assistant-design.md)

---

## Global Constraints

- Python version floor: `>= 3.10` (Target runtime: `/opt/homebrew/bin/python3.12`).
- Vector dimensions: 384 (tương ứng với model `sentence-transformers/all-MiniLM-L6-v2` hoặc `paraphrase-multilingual-MiniLM-L12-v2`).
- Qdrant collection name: `technical_documents`, distance metric: Cosine.
- Metadata contract: Mọi chunk bắt buộc phải có `doc_name: str` và `page_number: int` (1-indexed).
- Abstention contract: Khi context không chứa thông tin trả lời, output text phải chứa chính xác cụm: `"Tôi không tìm thấy thông tin này trong tài liệu được cung cấp."` và flag `abstained == True`.
- Citation contract: Mọi trích dẫn phải theo định dạng `[Tài liệu: <doc_name>, Trang <page_number>]`.
- Retrieval contract: Mọi retriever (`LocalRetriever`, `GrpcRetriever`) kế thừa `BaseRetriever` và thực thi signature `search(query: str, top_k: int = 5) -> list[RetrievalResult]`.

---

## Review Focus

1. **Trang PDF scan/ảnh hoàn toàn không có text layer:** Hệ thống phải kích hoạt OCR fallback trích xuất đúng nội dung thay vì trả về chuỗi rỗng hoặc bỏ qua trang.
2. **File PDF nhiều trang với mật độ text không đều (trang có text, trang có sơ đồ scan):** Quá trình trích xuất phải xử lý độc lập từng trang, không để lỗi ở một trang làm đứt gãy toàn bộ tài liệu.
3. **Câu hỏi ngoài phạm vi tài liệu (out-of-scope query):** LLM tuyệt đối không được bịa đặt (hallucinate), phải trả lời câu từ chối chuẩn và flag `abstained: true`.
4. **Đánh giá Recall@K:** Nếu ground truth kỳ vọng trang 12 mà top-K chỉ lấy được trang 15, kết quả benchmark phải ghi nhận là Miss (`0`), không được làm tròn sai.
5. **Đứt kết nối gRPC server:** Khi `RETRIEVAL_MODE=grpc` nhưng gRPC server chưa khởi động hoặc gặp sự cố, client phải bắt lỗi rõ ràng, trả về mã lỗi HTTP 503 thay vì crash ứng dụng FastAPI.

---

### Task 1: Project Setup, Dependencies & Data Models

**Files:**
- Create: `pyproject.toml`
- Create: `src/__init__.py`
- Create: `src/config.py`
- Create: `src/models.py`
- Test: `tests/test_models.py`

**Interfaces:**
- Produces:
  - `src.config.Settings`: `app_name: str`, `qdrant_path: str`, `embedding_model: str`, `llm_provider: str`, `gemini_api_key: str`, `openai_api_key: str`, `grpc_port: int`, `retrieval_mode: str`.
  - `src.models.DocumentChunk`: `chunk_id: str`, `doc_name: str`, `page_number: int`, `text: str`, `metadata: dict`.
  - `src.models.RetrievalResult`: `chunk: DocumentChunk`, `score: float`.
  - `src.models.Citation`: `doc_name: str`, `page_number: int`.
  - `src.models.QAResponse`: `answer: str`, `citations: list[Citation]`, `abstained: bool`, `retrieved_chunks: list[RetrievalResult]`.

- [x] **Step 1: Write the failing test for models and configuration**

```python
# tests/test_models.py
from src.models import DocumentChunk, RetrievalResult, Citation, QAResponse
from src.config import Settings

def test_document_chunk_validation():
    chunk = DocumentChunk(
        chunk_id="chk_1",
        doc_name="pump_manual.pdf",
        page_number=1,
        text="Máy bơm hoạt động ở công suất 5kW.",
        metadata={"author": "TKE"}
    )
    assert chunk.page_number == 1
    assert chunk.doc_name == "pump_manual.pdf"

def test_qa_response_schema():
    resp = QAResponse(
        answer="Áp suất giảm do hỏng van.",
        citations=[Citation(doc_name="pump.pdf", page_number=3)],
        abstained=False,
        retrieved_chunks=[]
    )
    assert resp.abstained is False
    assert len(resp.citations) == 1

def test_default_settings():
    settings = Settings()
    assert settings.retrieval_mode in ["local", "grpc"]
```

- [x] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_models.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'src'`

- [x] **Step 3: Setup virtual environment, dependencies & implement `config.py` and `models.py`**

Create `pyproject.toml` with dependencies (`pydantic`, `pydantic-settings`, `pymupdf`, `sentence-transformers`, `qdrant-client`, `fastapi`, `uvicorn`, `grpcio`, `grpcio-tools`, `pytest`, `rapidocr-onnxruntime`).
Install dependencies in virtual environment.
Implement `src/config.py` and `src/models.py`.

- [x] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_models.py -v`
Expected: PASS

- [x] **Step 5: Commit**

```bash
GIT_CONFIG_GLOBAL=/dev/null git add pyproject.toml src/ tests/
GIT_CONFIG_GLOBAL=/dev/null git commit -m "feat: setup project config, dependencies and core models"
```

---

### Task 2: PDF Document Processing & PyMuPDF Extractor

**Files:**
- Create: `src/ingestion/__init__.py`
- Create: `src/ingestion/pdf_extractor.py`
- Test: `tests/test_pdf_extractor.py`

**Interfaces:**
- Consumes: `src.models.DocumentChunk`
- Produces: `src.ingestion.pdf_extractor.extract_pages_from_pdf(pdf_path: str) -> list[dict[str, Any]]`
  - Output list item structure: `{"doc_name": str, "page_number": int, "text": str, "is_scanned": bool, "image_bytes": bytes | None}`

- [x] **Step 1: Write the failing test for PDF text extraction**

```python
# tests/test_pdf_extractor.py
import fitz
import pytest
from pathlib import Path
from src.ingestion.pdf_extractor import extract_pages_from_pdf

@pytest.fixture
def sample_digital_pdf(tmp_path: Path):
    doc = fitz.open()
    page1 = doc.new_page()
    page1.insert_text((50, 72), "Tài liệu kỹ thuật máy bơm công nghiệp. Trang 1 giới thiệu.")
    page2 = doc.new_page()
    page2.insert_text((50, 72), "Hướng dẫn bảo trì định kỳ van xả và cánh bơm. Trang 2.")
    file_path = tmp_path / "sample_pump.pdf"
    doc.save(file_path)
    doc.close()
    return str(file_path)

def test_extract_pages_from_digital_pdf(sample_digital_pdf):
    pages = extract_pages_from_pdf(sample_digital_pdf)
    assert len(pages) == 2
    assert pages[0]["page_number"] == 1
    assert "máy bơm công nghiệp" in pages[0]["text"]
    assert pages[0]["is_scanned"] is False
    assert pages[1]["page_number"] == 2
    assert "bảo trì định kỳ" in pages[1]["text"]
```

- [x] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_pdf_extractor.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'src.ingestion.pdf_extractor'`

- [x] **Step 3: Implement `extract_pages_from_pdf` in `src/ingestion/pdf_extractor.py`**

Read PDF with `fitz.open(pdf_path)`.
For each page:
- Extract text with `page.get_text()`.
- If `len(text.strip()) < 50`: mark `is_scanned=True` and render pixmap to PNG bytes (`page.get_pixmap(dpi=300).tobytes("png")`).
- Else: mark `is_scanned=False`, `image_bytes=None`.

- [x] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_pdf_extractor.py -v`
Expected: PASS

- [x] **Step 5: Commit**

```bash
GIT_CONFIG_GLOBAL=/dev/null git add src/ingestion/ tests/test_pdf_extractor.py
GIT_CONFIG_GLOBAL=/dev/null git commit -m "feat: implement PDF text extraction with PyMuPDF"
```

---

### Task 3: OCR Engine Fallback for Scanned Pages

**Files:**
- Create: `src/ingestion/ocr_engine.py`
- Modify: `src/ingestion/pdf_extractor.py`
- Test: `tests/test_ocr_engine.py`

**Interfaces:**
- Produces: `src.ingestion.ocr_engine.OcrEngine.extract_text_from_image(image_bytes: bytes) -> str`
- Modify: `src.ingestion.pdf_extractor.extract_pages_from_pdf(pdf_path: str, ocr_engine: OcrEngine | None = None) -> list[dict[str, Any]]`

- [x] **Step 1: Write the failing test for OCR engine**

```python
# tests/test_ocr_engine.py
import pytest
from PIL import Image, ImageDraw
import io
from src.ingestion.ocr_engine import OcrEngine

@pytest.fixture
def sample_scanned_image_bytes():
    img = Image.new("RGB", (400, 100), color=(255, 255, 255))
    draw = ImageDraw.Draw(img)
    draw.text((20, 35), "CANH BAO AP SUAT CAO", fill=(0, 0, 0))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()

def test_ocr_extract_text(sample_scanned_image_bytes):
    engine = OcrEngine()
    text = engine.extract_text_from_image(sample_scanned_image_bytes)
    assert "AP SUAT" in text.upper() or "CANH BAO" in text.upper()
```

- [x] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_ocr_engine.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'src.ingestion.ocr_engine'`

- [x] **Step 3: Implement `OcrEngine` using RapidOCR / pytesseract**

Implement `OcrEngine` with support for RapidOCR (pure onnxruntime, cross-platform) with fallback or configurable engine.
Integrate OCR engine inside `extract_pages_from_pdf` so when `is_scanned=True`, it automatically calls OCR to populate `text`.

- [x] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_ocr_engine.py -v`
Expected: PASS

- [x] **Step 5: Commit**

```bash
GIT_CONFIG_GLOBAL=/dev/null git add src/ingestion/ocr_engine.py src/ingestion/pdf_extractor.py tests/test_ocr_engine.py
GIT_CONFIG_GLOBAL=/dev/null git commit -m "feat: add OCR engine fallback for scanned documents"
```

---

### Task 4: Text Chunker with Preserved Page Metadata

**Files:**
- Create: `src/ingestion/chunker.py`
- Test: `tests/test_chunker.py`

**Interfaces:**
- Consumes: Page dicts from `pdf_extractor`
- Produces: `src.ingestion.chunker.chunk_document(pages: list[dict[str, Any]], chunk_size: int = 500, chunk_overlap: int = 50) -> list[DocumentChunk]`

- [x] **Step 1: Write the failing test for chunking**

```python
# tests/test_chunker.py
from src.ingestion.chunker import chunk_document
from src.models import DocumentChunk

def test_chunk_preserves_page_metadata():
    pages = [
        {
            "doc_name": "manual.pdf",
            "page_number": 1,
            "text": "Đoạn văn ngắn của trang 1."
        },
        {
            "doc_name": "manual.pdf",
            "page_number": 2,
            "text": "Nội dung rất dài của trang 2. " * 30  # > 500 chars
        }
    ]
    chunks = chunk_document(pages, chunk_size=300, chunk_overlap=30)
    assert len(chunks) >= 3
    # Mọi chunk phải có doc_name và page_number chính xác
    assert chunks[0].page_number == 1
    assert chunks[0].doc_name == "manual.pdf"
    assert chunks[1].page_number == 2
    assert chunks[1].doc_name == "manual.pdf"
    assert all(isinstance(c, DocumentChunk) for c in chunks)
```

- [x] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_chunker.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'src.ingestion.chunker'`

- [x] **Step 3: Implement `chunk_document` in `src/ingestion/chunker.py`**

Implement recursive text splitter with overlap respecting sentence/paragraph boundaries where possible.
Generate unique `chunk_id` for each chunk using `hashlib.sha256(f"{doc_name}_{page}_{idx}_{text[:20]}".encode()).hexdigest()[:16]`.

- [x] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_chunker.py -v`
Expected: PASS

- [x] **Step 5: Commit**

```bash
GIT_CONFIG_GLOBAL=/dev/null git add src/ingestion/chunker.py tests/test_chunker.py
GIT_CONFIG_GLOBAL=/dev/null git commit -m "feat: implement chunker preserving document and page metadata"
```

---

### Task 5: Embedding Model & Qdrant Vector Store

**Files:**
- Create: `src/vector_store/__init__.py`
- Create: `src/vector_store/embedding.py`
- Create: `src/vector_store/qdrant_store.py`
- Test: `tests/test_vector_store.py`

**Interfaces:**
- Consumes: `src.models.DocumentChunk`
- Produces:
  - `src.vector_store.embedding.EmbeddingModel.embed_texts(texts: list[str]) -> list[list[float]]`
  - `src.vector_store.embedding.EmbeddingModel.embed_query(query: str) -> list[float]`
  - `src.vector_store.qdrant_store.QdrantVectorStore.upsert_chunks(chunks: list[DocumentChunk]) -> int`
  - `src.vector_store.qdrant_store.QdrantVectorStore.search(query_vector: list[float], top_k: int = 5) -> list[RetrievalResult]`

- [x] **Step 1: Write the failing test for embedding and vector store**

```python
# tests/test_vector_store.py
import pytest
from pathlib import Path
from src.models import DocumentChunk
from src.vector_store.embedding import EmbeddingModel
from src.vector_store.qdrant_store import QdrantVectorStore

@pytest.fixture
def temp_qdrant_store(tmp_path: Path):
    embedder = EmbeddingModel(model_name="all-MiniLM-L6-v2")
    store = QdrantVectorStore(storage_path=str(tmp_path / "qdrant"), collection_name="test_collection")
    return embedder, store

def test_embed_and_search(temp_qdrant_store):
    embedder, store = temp_qdrant_store
    chunks = [
        DocumentChunk(
            chunk_id="c1",
            doc_name="manual.pdf",
            page_number=5,
            text="Van an toàn sẽ xả áp khi áp suất vượt quá 10 bar."
        ),
        DocumentChunk(
            chunk_id="c2",
            doc_name="manual.pdf",
            page_number=8,
            text="Bôi trơn ổ bi bằng dầu nhờn định kỳ 3 tháng một lần."
        )
    ]
    # Upsert with embeddings
    vectors = embedder.embed_texts([c.text for c in chunks])
    store.upsert_chunks_with_vectors(chunks, vectors)

    # Search
    query_vec = embedder.embed_query("Khi nào van an toàn mở?")
    results = store.search(query_vec, top_k=1)

    assert len(results) == 1
    assert results[0].chunk.page_number == 5
    assert "Van an toàn" in results[0].chunk.text
    assert results[0].score > 0.0
```

- [x] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_vector_store.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'src.vector_store.embedding'`

- [x] **Step 3: Implement `EmbeddingModel` and `QdrantVectorStore`**

`EmbeddingModel`: wraps `SentenceTransformer(model_name)` with batching and normalized embeddings.
`QdrantVectorStore`: uses `QdrantClient(path=storage_path)` (local disk mode). Creates collection with Cosine distance and 384 dimensions if not exists. Stores chunk attributes as payload.

- [x] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_vector_store.py -v`
Expected: PASS

- [x] **Step 5: Commit**

```bash
GIT_CONFIG_GLOBAL=/dev/null git add src/vector_store/ tests/test_vector_store.py
GIT_CONFIG_GLOBAL=/dev/null git commit -m "feat: add SentenceTransformer embedding and Qdrant store"
```

---

### Task 6: Unified Retriever Interface & LocalRetriever

**Files:**
- Create: `src/retrieval/__init__.py`
- Create: `src/retrieval/base.py`
- Create: `src/retrieval/local.py`
- Test: `tests/test_retrieval.py`

**Interfaces:**
- Consumes: `EmbeddingModel`, `QdrantVectorStore`
- Produces: `src.retrieval.base.BaseRetriever`, `src.retrieval.local.LocalRetriever`
  - Method: `search(query: str, top_k: int = 5) -> list[RetrievalResult]`

- [x] **Step 1: Write the failing test for LocalRetriever**

```python
# tests/test_retrieval.py
import pytest
from src.models import DocumentChunk
from src.retrieval.base import BaseRetriever
from src.retrieval.local import LocalRetriever
from src.vector_store.embedding import EmbeddingModel
from src.vector_store.qdrant_store import QdrantVectorStore

def test_local_retriever_conforms_to_base(tmp_path):
    embedder = EmbeddingModel("all-MiniLM-L6-v2")
    store = QdrantVectorStore(storage_path=str(tmp_path / "qdrant"), collection_name="test_retrieval")
    retriever = LocalRetriever(embedding_model=embedder, vector_store=store)

    assert isinstance(retriever, BaseRetriever)

    # Ingest 1 chunk
    chunk = DocumentChunk(chunk_id="c1", doc_name="guide.pdf", page_number=2, text="Nhiệt độ tối đa cho phép là 80 độ C.")
    retriever.index_chunks([chunk])

    # Search
    results = retriever.search("nhiệt độ tối đa bao nhiêu", top_k=1)
    assert len(results) == 1
    assert results[0].chunk.page_number == 2
```

- [x] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_retrieval.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'src.retrieval.base'`

- [x] **Step 3: Implement `BaseRetriever` and `LocalRetriever`**

Define abstract class `BaseRetriever(ABC)`.
Implement `LocalRetriever`: embeds query, queries `vector_store.search()`, returns `list[RetrievalResult]`.

- [x] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_retrieval.py -v`
Expected: PASS

- [x] **Step 5: Commit**

```bash
GIT_CONFIG_GLOBAL=/dev/null git add src/retrieval/ tests/test_retrieval.py
GIT_CONFIG_GLOBAL=/dev/null git commit -m "feat: implement BaseRetriever interface and LocalRetriever"
```

---

### Task 7: RAG Prompt, Citations & Abstention Engine

**Files:**
- Create: `src/rag/__init__.py`
- Create: `src/rag/prompt.py`
- Create: `src/rag/generator.py`
- Test: `tests/test_rag.py`

**Interfaces:**
- Consumes: `list[RetrievalResult]`
- Produces: `src.rag.generator.RAGGenerator.generate_answer(question: str, context_chunks: list[RetrievalResult]) -> QAResponse`

- [x] **Step 1: Write the failing test for prompt formatting and abstention parsing**

```python
# tests/test_rag.py
from src.models import DocumentChunk, RetrievalResult
from src.rag.prompt import build_rag_prompt, ABSTAIN_PHRASE
from src.rag.generator import RAGGenerator

def test_prompt_formatting():
    chunks = [
        RetrievalResult(
            chunk=DocumentChunk(chunk_id="c1", doc_name="pump.pdf", page_number=12, text="Lưu lượng thiết kế 50 m3/h."),
            score=0.88
        )
    ]
    prompt = build_rag_prompt(question="Lưu lượng là bao nhiêu?", chunks=chunks)
    assert "[Tài liệu: pump.pdf | Trang: 12]" in prompt
    assert "Lưu lượng thiết kế 50 m3/h." in prompt
    assert ABSTAIN_PHRASE in prompt

def test_abstention_handling():
    gen = RAGGenerator(llm_client=None)  # Mock or deterministic mode
    response = gen.parse_llm_output(
        raw_output=f"{ABSTAIN_PHRASE}",
        retrieved_chunks=[]
    )
    assert response.abstained is True
    assert ABSTAIN_PHRASE in response.answer
    assert len(response.citations) == 0

def test_citation_parsing():
    gen = RAGGenerator(llm_client=None)
    raw = "Theo tài liệu, lưu lượng bơm là 50 m3/h [Tài liệu: pump.pdf, Trang 12]."
    response = gen.parse_llm_output(raw_output=raw, retrieved_chunks=[])
    assert response.abstained is False
    assert len(response.citations) == 1
    assert response.citations[0].doc_name == "pump.pdf"
    assert response.citations[0].page_number == 12
```

- [x] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_rag.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'src.rag.prompt'`

- [x] **Step 3: Implement prompt template and `RAGGenerator`**

Implement `src/rag/prompt.py` with standard citations instructions and the explicit `ABSTAIN_PHRASE`: `"Tôi không tìm thấy thông tin này trong tài liệu được cung cấp."`.
Implement `src/rag/generator.py`: calls LLM (Gemini or OpenAI API), regex parses `[Tài liệu: (.*?), Trang (\d+)]` to populate `citations`, checks if answer matches abstain phrase to set `abstained=True`.

- [x] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_rag.py -v`
Expected: PASS

- [x] **Step 5: Commit**

```bash
GIT_CONFIG_GLOBAL=/dev/null git add src/rag/ tests/test_rag.py
GIT_CONFIG_GLOBAL=/dev/null git commit -m "feat: implement RAG prompt, citation parsing and abstention logic"
```

---

### Task 8: Evaluation Suite (Ground Truth & Recall@K Benchmark)

**Files:**
- Create: `data/eval/ground_truth.json`
- Create: `src/eval/__init__.py`
- Create: `src/eval/metrics.py`
- Create: `src/eval/runner.py`
- Test: `tests/test_eval.py`

**Interfaces:**
- Produces:
  - `src.eval.metrics.calculate_recall_at_k(retrieved_chunks: list[RetrievalResult], expected_doc: str, expected_pages: list[int], k: int) -> float`
  - `src.eval.metrics.evaluate_abstention(should_abstain: bool, actually_abstained: bool) -> bool`
  - `src.eval.runner.run_benchmark(retriever: BaseRetriever, ground_truth_file: str, k_values: list[int]) -> dict[str, Any]`

- [x] **Step 1: Write the failing test for evaluation metrics**

```python
# tests/test_eval.py
from src.models import DocumentChunk, RetrievalResult
from src.eval.metrics import calculate_recall_at_k, evaluate_abstention

def test_recall_at_k_hit():
    chunks = [
        RetrievalResult(chunk=DocumentChunk(chunk_id="c1", doc_name="pump.pdf", page_number=5, text="A"), score=0.9),
        RetrievalResult(chunk=DocumentChunk(chunk_id="c2", doc_name="pump.pdf", page_number=12, text="B"), score=0.8),
        RetrievalResult(chunk=DocumentChunk(chunk_id="c3", doc_name="pump.pdf", page_number=20, text="C"), score=0.7),
    ]
    # K=1: Trang 12 chưa xuất hiện -> 0.0
    assert calculate_recall_at_k(chunks, expected_doc="pump.pdf", expected_pages=[12], k=1) == 0.0
    # K=2: Trang 12 xuất hiện ở vị trí thứ 2 -> 1.0
    assert calculate_recall_at_k(chunks, expected_doc="pump.pdf", expected_pages=[12], k=2) == 1.0

def test_abstention_metric():
    assert evaluate_abstention(should_abstain=True, actually_abstained=True) is True
    assert evaluate_abstention(should_abstain=False, actually_abstained=True) is False
```

- [x] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_eval.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'src.eval.metrics'`

- [x] **Step 3: Implement `metrics.py`, `runner.py`, and sample `data/eval/ground_truth.json`**

Implement formula for Recall@K, Abstention rate, and runner outputting formatted Markdown benchmark table. Create at least 15 QA pairs in `ground_truth.json`.

- [x] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_eval.py -v`
Expected: PASS

- [x] **Step 5: Commit**

```bash
GIT_CONFIG_GLOBAL=/dev/null git add data/eval/ src/eval/ tests/test_eval.py
GIT_CONFIG_GLOBAL=/dev/null git commit -m "feat: implement evaluation metrics and Recall@K benchmark runner"
```

---

### Task 9: FastAPI Backend REST API

**Files:**
- Create: `src/api/__init__.py`
- Create: `src/api/routes.py`
- Create: `src/api/main.py`
- Test: `tests/test_api.py`

**Interfaces:**
- Produces HTTP Endpoints:
  - `POST /api/v1/upload`: Nhận file `.pdf`, thực hiện extraction + chunking + indexing vào Qdrant, trả về số trang và số chunk đã index.
  - `POST /api/v1/query`: Nhận `QARequest(question, top_k)`, trả về `QAResponse`.
  - `GET /api/v1/health`: Trả về trạng thái hệ thống.

- [x] **Step 1: Write the failing test for FastAPI endpoints**

```python
# tests/test_api.py
import pytest
from fastapi.testclient import TestClient
from src.api.main import app

client = TestClient(app)

def test_health_endpoint():
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"

def test_query_endpoint_structure():
    response = client.post("/api/v1/query", json={"question": "Kiểm tra áp suất máy bơm?", "top_k": 3})
    assert response.status_code == 200
    data = response.json()
    assert "answer" in data
    assert "citations" in data
    assert "abstained" in data
```

- [x] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_api.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'src.api.main'`

- [x] **Step 3: Implement FastAPI routes and app lifespan**

Implement `src/api/routes.py` and `src/api/main.py`. Initialize `BaseRetriever` and `RAGGenerator` at startup. Add upload endpoint accepting multipart PDF.

- [x] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_api.py -v`
Expected: PASS

- [x] **Step 5: Commit**

```bash
GIT_CONFIG_GLOBAL=/dev/null git add src/api/ tests/test_api.py
GIT_CONFIG_GLOBAL=/dev/null git commit -m "feat: implement FastAPI upload and Q&A endpoints"
```

---

### Task 10: gRPC Retrieval Service & GrpcRetriever Client Adapter

**Files:**
- Create: `proto/retrieval.proto`
- Create: `src/rpc/__init__.py`
- Create: `src/rpc/server.py`
- Create: `src/retrieval/grpc_client.py`
- Modify: `src/retrieval/__init__.py`
- Test: `tests/test_grpc.py`

**Interfaces:**
- Consumes: `proto/retrieval.proto`, `LocalRetriever`
- Produces:
  - `src.rpc.server.RetrievalGrpcServer`: runs gRPC server on specified port.
  - `src.retrieval.grpc_client.GrpcRetriever`: implements `BaseRetriever`, connects to gRPC server and translates protobuf responses.

- [x] **Step 1: Write the failing test for gRPC client/server**

```python
# tests/test_grpc.py
import pytest
import time
from src.models import DocumentChunk
from src.retrieval.base import BaseRetriever
from src.retrieval.local import LocalRetriever
from src.vector_store.embedding import EmbeddingModel
from src.vector_store.qdrant_store import QdrantVectorStore
from src.rpc.server import start_grpc_server
from src.retrieval.grpc_client import GrpcRetriever

@pytest.fixture(scope="module")
def running_grpc_server(tmp_path_factory):
    temp_dir = tmp_path_factory.mktemp("grpc_test")
    embedder = EmbeddingModel("all-MiniLM-L6-v2")
    store = QdrantVectorStore(storage_path=str(temp_dir / "qdrant"), collection_name="grpc_test")
    local_retriever = LocalRetriever(embedder, store)

    chunk = DocumentChunk(chunk_id="g1", doc_name="motor.pdf", page_number=7, text="Động cơ điện 3 pha công suất 15kW.")
    local_retriever.index_chunks([chunk])

    port = 50055
    server = start_grpc_server(local_retriever, port=port)
    time.sleep(0.5)
    yield port
    server.stop(0)

def test_grpc_retriever_queries_server(running_grpc_server):
    retriever = GrpcRetriever(host="localhost", port=running_grpc_server)
    assert isinstance(retriever, BaseRetriever)

    results = retriever.search("công suất động cơ 3 pha", top_k=1)
    assert len(results) == 1
    assert results[0].chunk.page_number == 7
    assert results[0].chunk.doc_name == "motor.pdf"
```

- [x] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_grpc.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'src.rpc.server'`

- [x] **Step 3: Define `proto/retrieval.proto`, compile stubs, implement server & client adapter**

Compile protobuf stubs with `python -m grpc_tools.protoc -I. --python_out=. --grpc_python_out=. proto/retrieval.proto`.
Implement `RetrievalServicer` in `src/rpc/server.py`.
Implement `GrpcRetriever` in `src/retrieval/grpc_client.py` adhering strictly to `BaseRetriever`.

- [x] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_grpc.py -v`
Expected: PASS

- [x] **Step 5: Commit**

```bash
GIT_CONFIG_GLOBAL=/dev/null git add proto/ src/rpc/ src/retrieval/grpc_client.py tests/test_grpc.py
GIT_CONFIG_GLOBAL=/dev/null git commit -m "feat: implement gRPC retrieval service and client adapter"
```

---

### Task 11: Sample Technical Documents, End-to-End Verification & Documentation

**Files:**
- Create: `sample_docs/pump_maintenance_guide.pdf` (sample multi-page digital PDF with technical specs)
- Create: `sample_docs/scanned_circuit_diagram.pdf` (sample scanned/image page PDF for OCR verification)
- Create: `README.md`
- Test: `tests/test_e2e.py`

**Interfaces:**
- Verification: Full end-to-end flow: Ingest sample documents -> Run benchmark -> Run query via FastAPI with citations & abstention -> Validate gRPC switch.

- [x] **Step 1: Write the failing end-to-end integration test**

```python
# tests/test_e2e.py
import pytest
from pathlib import Path
from src.ingestion.pdf_extractor import extract_pages_from_pdf
from src.ingestion.chunker import chunk_document
from src.retrieval.local import LocalRetriever
from src.vector_store.embedding import EmbeddingModel
from src.vector_store.qdrant_store import QdrantVectorStore
from src.eval.runner import run_benchmark

def test_full_pipeline_on_sample_docs(tmp_path):
    pdf_path = "sample_docs/pump_maintenance_guide.pdf"
    assert Path(pdf_path).exists(), "Sample doc must exist"

    pages = extract_pages_from_pdf(pdf_path)
    assert len(pages) >= 2

    chunks = chunk_document(pages)
    assert len(chunks) > 0

    embedder = EmbeddingModel("all-MiniLM-L6-v2")
    store = QdrantVectorStore(storage_path=str(tmp_path / "e2e_qdrant"), collection_name="e2e")
    retriever = LocalRetriever(embedder, store)
    retriever.index_chunks(chunks)

    # Benchmark run
    report = run_benchmark(retriever, ground_truth_file="data/eval/ground_truth.json", k_values=[1, 3, 5])
    assert report["recall@5"] >= 0.7
```

- [x] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_e2e.py -v`
Expected: FAIL with `AssertionError: Sample doc must exist`

- [x] **Step 3: Generate sample PDF documents, run benchmark, write README.md**

Generate synthetic technical PDF sample files using PyMuPDF (digital pump manual + scanned diagram).
Execute benchmark to confirm Recall@5 threshold.
Write comprehensive `README.md` with:
- Architecture overview diagram.
- Quickstart guide (setup, run API, run gRPC server).
- Ingestion & OCR instructions.
- How to run evaluation and interpret Recall@K.

- [x] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_e2e.py -v`
Expected: PASS

- [x] **Step 5: Commit**

```bash
GIT_CONFIG_GLOBAL=/dev/null git add sample_docs/ README.md tests/test_e2e.py
GIT_CONFIG_GLOBAL=/dev/null git commit -m "docs: add sample technical documents, e2e tests and README"
```

