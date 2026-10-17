# Specification: Document Q&A Assistant (Chatbot hỏi đáp tài liệu kỹ thuật)

- **Date**: 2026-10-17
- **Status**: Approved
- **Scope**: Architectural MVP (Modular Monorepo -> gRPC Separation)

---

## 1. Mục tiêu & Bối cảnh dự án

Xây dựng hệ thống Document Q&A Assistant chuyên dụng cho tài liệu kỹ thuật dạng PDF (hỗ trợ cả digital PDF và PDF scan/hình ảnh). Hệ thống giải quyết các bài toán cốt lõi:
1. **Document Processing & OCR**: Trích xuất văn bản kèm chỉ mục số trang chính xác từ PDF gốc và fallback qua OCR đối với trang dạng scan/ảnh.
2. **Vector Database & Retrieval**: Phân đoạn (chunking), tạo embedding và lưu trữ vector trên Qdrant, hỗ trợ tìm kiếm ngữ nghĩa top-k.
3. **RAG Pipeline & Guardrails**: Sinh câu trả lời kèm trích dẫn nguồn chuẩn xác (tên file và số trang), đồng thời kích hoạt cơ chế từ chối (Abstention) khi tài liệu không chứa đủ dữ kiện, ngăn chặn hoàn toàn hallucination.
4. **Evaluation**: Bộ đo lường định lượng Recall@K (K ∈ {3, 5, 10}), Abstention Accuracy và Citation Precision trên tập dữ liệu kiểm thử chuẩn (Ground Truth).
5. **Microservice Separation qua gRPC**: Tách tầng Retrieval thành một RPC service độc lập giao tiếp qua Protocol Buffers, cho phép chuyển đổi mượt mà giữa chạy cục bộ (Monolith) và phân tán (gRPC).

---

## 2. Phạm vi & Giới hạn (Scope & Non-Goals)

### Trong phạm vi MVP:
- Hỗ trợ tải lên và lập chỉ mục PDF kỹ thuật (cả dạng văn bản số và tài liệu scan).
- Lưu trữ vector trong Qdrant (hỗ trợ lưu trữ cục bộ dạng file `data/qdrant_storage` hoặc container Docker).
- Mô hình Embedding nhẹ (chạy cục bộ bằng `sentence-transformers`, ví dụ: `all-MiniLM-L6-v2` hoặc `paraphrase-multilingual-MiniLM-L12-v2`).
- LLM inference thông qua API (Gemini / OpenAI API) hoặc tùy chọn Local LLM khi cần.
- API RESTful qua FastAPI cho phép upload file và gửi câu hỏi.
- Bộ benchmark tự động đo Recall@K và sinh báo cáo Markdown.
- Service gRPC độc lập cho Retrieval kèm adapter client cho FastAPI.

### Ngoài phạm vi (Deferred - chưa cần thiết ở giai đoạn 1–2 tuần):
- Không dùng kiến trúc Multi-Agent phức tạp hoặc LangGraph (sẽ bổ sung sau khi RAG cơ bản hoàn thiện và có baseline Recall@K).
- Không triển khai Kafka, Kubernetes hay hệ thống multi-tenant.
- Không tự huấn luyện (fine-tune) mô hình embedding hoặc LLM.

---

## 3. Kiến trúc tổng thể hệ thống

Hệ thống được thiết kế theo kiến trúc Hexagonal / Clean Architecture tối giản, tách biệt giữa Domain Logic, Data Storage, và Giao diện giao tiếp (FastAPI / gRPC).

```
                      +-----------------------------+
                      |       Client / User         |
                      +--------------+--------------+
                                     | HTTP REST
                                     v
                      +-----------------------------+
                      |       FastAPI Gateway       |
                      |   (POST /upload, /query)    |
                      +--------------+--------------+
                                     |
              +----------------------+----------------------+
              |                                             |
              v (Ingestion)                                 v (Retrieval: Local or gRPC)
+-----------------------------+               +-----------------------------+
|    Ingestion Pipeline       |               |     BaseRetriever Interface  |
|  - PyMuPDF Extractor        |               +--------------+--------------+
|  - OCR Fallback Engine      |                              |
|  - Semantic Chunker         |               +--------------+--------------+
+--------------+--------------+               |                             |
               |                              v (Mode: local)               v (Mode: grpc)
               | Upsert vectors        +--------------+              +---------------+
               |                       | LocalRetriever|             | GrpcRetriever |
               |                       +-------+------+              +-------+-------+
               v                               |                             | gRPC Channel
+-----------------------------+                |                             v
|   Qdrant Vector Database    |<---------------+             +-------------------------------+
|  (Payload: text, file, page)|                              | gRPC Retrieval Server (:50051)|
+-----------------------------+                              +-------------------------------+
```

---

## 4. Chi tiết các module

### 4.1. Data Models (`src/models.py`)

- `DocumentChunk`:
  - `chunk_id: str`: Định danh duy nhất (ví dụ: `hash(doc_name + page + index)`).
  - `doc_name: str`: Tên file PDF nguồn.
  - `page_number: int`: Số trang tài liệu (1-indexed).
  - `text: str`: Nội dung đoạn trích.
  - `metadata: dict`: Thông tin mở rộng (ngày index, vị trí trang).
- `RetrievalResult`:
  - `chunk: DocumentChunk`
  - `score: float`: Cosine similarity score.
- `QARequest`:
  - `question: str`: Câu hỏi của người dùng.
  - `top_k: int = 5`: Số đoạn context cần lấy.
- `QAResponse`:
  - `answer: str`: Câu trả lời từ LLM hoặc thông báo từ chối.
  - `citations: list[Citation]`: Danh sách gồm `{ doc_name: str, page_number: int }`.
  - `abstained: bool`: True nếu câu hỏi ngoài phạm vi tài liệu.
  - `retrieved_chunks: list[RetrievalResult]`: Danh sách chunks phục vụ kiểm tra và audit.

### 4.2. Ingestion & OCR Pipeline (`src/ingestion/`)

1. **`pdf_extractor.py`**:
   - Sử dụng PyMuPDF (`fitz`) duyệt qua từng trang tài liệu.
   - Trích xuất văn bản dạng text số (`page.get_text()`).
   - Kiểm tra mật độ ký tự: Nếu độ dài text trang < 50 ký tự (trang trống, hình vẽ hoặc tài liệu scan), chuyển hướng trang đó qua `ocr_engine.py`.
2. **`ocr_engine.py`**:
   - Chuyển đổi trang PDF thành hình ảnh có độ phân giải cao (`pixmap`, 300 DPI).
   - Áp dụng OCR (Tesseract / RapidOCR) để đọc text từ ảnh và trả về nội dung kèm số trang tương ứng.
3. **`chunker.py`**:
   - Chia văn bản thành các đoạn (chunk size 500 ký tự, overlap 50 ký tự).
   - Bảo toàn metadata nguyên vẹn ở từng chunk: `doc_name`, `page_number`, `chunk_id`.

### 4.3. Vector Store & Embeddings (`src/vector_store/`)

1. **`embedding.py`**:
   - Wrapper thống nhất chuyển đổi `str` -> `list[float]`.
   - Sử dụng mô hình `sentence-transformers` đa ngôn ngữ nhẹ (`paraphrase-multilingual-MiniLM-L12-v2` hoặc `all-MiniLM-L6-v2`, kích thước vector 384).
2. **`qdrant_store.py`**:
   - Quản lý collection `technical_documents` trên Qdrant với khoảng cách Cosine.
   - Hỗ trợ lưu trữ file cục bộ (`path="data/qdrant_storage"`) không phụ thuộc Docker daemon, hoặc kết nối tới Qdrant container khi có cấu hình URL.
   - Cung cấp hàm `upsert_chunks(chunks)` và `search(query_vector, top_k)`.

### 4.4. Retrieval Layer (`src/retrieval/`)

- **`base.py` (`BaseRetriever`)**:
  ```python
  class BaseRetriever(ABC):
      @abstractmethod
      def search(self, query: str, top_k: int = 5) -> list[RetrievalResult]:
          pass
  ```
- **`local.py` (`LocalRetriever`)**:
  Gọi trực tiếp `embedding_model.encode(query)` và `qdrant_store.search()`.
- **`grpc_client.py` (`GrpcRetriever`)**:
  Chuyển đổi query thành `SearchRequest(query=query, top_k=top_k)`, gửi qua gRPC stub tới `RetrievalService`, và unpack `SearchResponse` thành danh sách `RetrievalResult`.

### 4.5. RAG Engine & Guardrails (`src/rag/`)

1. **Prompt Template (`prompt.py`)**:
   - Đưa context vào với định dạng rõ ràng:
     ```
     [Tài liệu: {doc_name} | Trang: {page_number}]
     {chunk_text}
     ```
   - Chỉ thị hệ thống (System Prompt):
     - Chỉ trả lời dựa vào các đoạn trích dẫn được cung cấp.
     - Với mỗi ý trả lời, bắt buộc ghi rõ nguồn: `[Tài liệu: <doc_name>, Trang <page_number>]`.
     - Nếu không tìm thấy thông tin phù hợp, trả lời chính xác:
       `"Tôi không tìm thấy thông tin này trong tài liệu được cung cấp."`
2. **Generator (`generator.py`)**:
   - Gửi prompt tới LLM (Gemini API hoặc OpenAI API).
   - Phân tích cú pháp câu trả lời để trích xuất danh sách `citations` cấu trúc và phát hiện trạng thái `abstained`.

### 4.6. Evaluation Suite (`src/eval/`)

1. **Tập dữ liệu Ground Truth (`data/eval/ground_truth.json`)**:
   - Định dạng:
     ```json
     [
       {
         "id": "q1",
         "question": "Những nguyên nhân nào khiến áp suất đầu ra của máy bơm giảm?",
         "expected_doc": "pump_maintenance_manual.pdf",
         "expected_pages": [12, 13],
         "ground_truth_answer": "...",
         "should_abstain": false
       },
       {
         "id": "q_oos_1",
         "question": "Thủ đô của nước Pháp là gì?",
         "expected_doc": null,
         "expected_pages": [],
         "ground_truth_answer": "Abstain",
         "should_abstain": true
       }
     ]
     ```
2. **Metrics & Runner (`metrics.py`, `runner.py`)**:
   - **Recall@K**: Kiểm tra xem trong top-K chunks trả về có tồn tại chunk thuộc `expected_pages` của `expected_doc` hay không.
   - **Abstention Accuracy**: Tỷ lệ trả lời "không tìm thấy thông tin" chính xác trên các câu hỏi out-of-scope.
   - **Citation Precision**: Tỷ lệ các số trang được trích dẫn trong câu trả lời trùng khớp với số trang thực tế của dữ liệu.
   - Xuất bảng kết quả Markdown chi tiết.

### 4.7. Protocol Buffers & gRPC Service (`proto/`, `src/rpc/`)

- **`proto/retrieval.proto`**:
  ```protobuf
  syntax = "proto3";
  package retrieval;

  service RetrievalService {
    rpc Search (SearchRequest) returns (SearchResponse);
  }

  message SearchRequest {
    string query = 1;
    int32 top_k = 2;
  }

  message Chunk {
    string chunk_id = 1;
    string doc_name = 2;
    int32 page_number = 3;
    string text = 4;
    float score = 5;
  }

  message SearchResponse {
    repeated Chunk chunks = 1;
  }
  ```
- **`src/rpc/server.py`**:
  - Chạy gRPC server trên cổng 50051 (mặc định).
  - Xử lý request từ `retrieval.proto` bằng cách ủy quyền cho `LocalRetriever`.

---

## 5. Chiến lược kiểm thử & Đảm bảo chất lượng (Testing Plan)

1. **Unit Tests (`tests/`)**:
   - `test_pdf_extractor.py`: Kiểm tra đọc đúng số trang và văn bản từ PDF kỹ thuật số.
   - `test_ocr_engine.py`: Kiểm tra trích xuất text từ ảnh/trang scan.
   - `test_chunker.py`: Đảm bảo chunk size, overlap và bảo toàn metadata (doc_name, page_number).
   - `test_retriever.py`: Kiểm tra tìm kiếm vector cục bộ và kết quả trả về đúng định dạng.
   - `test_abstention.py`: Kiểm tra prompt và generator trả lời từ chối đối với context không liên quan.
2. **Integration Tests**:
   - `test_api.py`: Kiểm tra các API endpoints `/upload` và `/query` của FastAPI.
   - `test_grpc.py`: Khởi động gRPC server test và kiểm tra `GrpcRetriever` giao tiếp thành công.
3. **Benchmark Test**:
   - Chạy `python -m src.eval.runner` và kiểm tra `Recall@5 >= 0.8`.

---

## 6. Lộ trình triển khai (Implementation Roadmap)

- **Giai đoạn 1**: Khởi tạo môi trường Python 3.12, cấu trúc thư mục, Ingestion Pipeline (PyMuPDF + OCR fallback) & Unit tests.
- **Giai đoạn 2**: Vector Store (Qdrant embedded), Chunking & Embedding với SentenceTransformers, Local Search.
- **Giai đoạn 3**: RAG Pipeline (FastAPI, LLM API, Prompt trích dẫn & Abstention).
- **Giai đoạn 4**: Bộ dữ liệu Ground Truth mẫu và Runner đánh giá Recall@K.
- **Giai đoạn 5**: Khai báo Protobuf, build code gRPC, triển khai gRPC Retrieval Server & GrpcRetriever adapter.

