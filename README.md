# Document Q&A Assistant — Chatbot Hỏi Đáp Tài Liệu Kỹ Thuật

Hệ thống Chatbot hỏi đáp tài liệu kỹ thuật chuyên nghiệp, xử lý tài liệu PDF (cả văn bản số và tài liệu scan qua OCR), chunking bảo toàn metadata số trang, tìm kiếm tương đồng vector với Qdrant, RAG pipeline với trích dẫn chính xác và cơ chế từ chối (Abstention) chống hallucination, benchmark định lượng Recall@K, và tách module Retrieval thành microservice qua gRPC.

---

## 1. Kiến trúc hệ thống (Architecture)

Hệ thống tuân thủ kiến trúc Clean / Hexagonal Modular Monorepo:

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
|  - RapidOCR Fallback Engine |                              |
|  - Semantic Chunker         |               +--------------+--------------+
+--------------+--------------+               |                             |
               |                              v (Mode: local)               v (Mode: grpc)
               |                       +--------------+              +---------------+
               | Upsert vectors        | LocalRetriever|             | GrpcRetriever |
               v                       +-------+------+              +-------+-------+
+-----------------------------+                |                             | gRPC Channel
|   Qdrant Vector Database    |<---------------+                             v
|  (Embedded / Port 6333)     |                              +-------------------------------+
+-----------------------------+                              | gRPC Retrieval Server (:50051)|
                                                             +-------------------------------+
```

---

## 2. Các chức năng chính (Core Features)

1. **Document Processing & OCR Fallback**:
   - Tự động nhận diện trang văn bản số (digital text) qua PyMuPDF.
   - Khi trang PDF có mật độ ký tự thấp (< 50 ký tự, như sơ đồ, bản vẽ, tài liệu scan), hệ thống tự động render sang ảnh 300 DPI và kích hoạt **RapidOCR** để trích xuất text.
2. **Chunking bảo toàn số trang**:
   - Phân chia văn bản thành các đoạn (chunks) có overlap.
   - Giữ nguyên `doc_name` và `page_number` (1-indexed) ở từng chunk.
3. **Vector Database (Qdrant Embedded)**:
   - Sử dụng model `sentence-transformers/all-MiniLM-L6-v2` tạo vector 384 chiều chuẩn hóa.
   - Lưu trữ trực tiếp trên file cục bộ `data/qdrant_storage/` không bắt buộc chạy Docker.
4. **RAG Guardrails (Citations & Abstention)**:
   - Trả lời luôn kèm nguồn gốc: `[Tài liệu: <doc_name>, Trang <page_number>]`.
   - Cơ chế từ chối dứt khoát khi tài liệu không chứa đủ dữ kiện: `"Tôi không tìm thấy thông tin này trong tài liệu được cung cấp."` (ngăn chặn hallucination).
5. **Evaluation Suite (Recall@K Benchmark)**:
   - Bộ dữ liệu Ground Truth kiểm thử 15 câu hỏi kỹ thuật và out-of-scope.
   - Đo lường tự động: `Recall@1`, `Recall@3`, `Recall@5`, `Recall@10` và `Abstention Accuracy`.
6. **gRPC Retrieval Service**:
   - Định nghĩa API hợp đồng bằng Protocol Buffers (`proto/retrieval.proto`).
   - Cung cấp `start_grpc_server` và `GrpcRetriever` adapter. Chuyển đổi giữa chạy local và gRPC chỉ bằng 1 biến môi trường `RETRIEVAL_MODE=grpc`.

---

## 3. Cài đặt & Khởi động nhanh (Quickstart)

### Yêu cầu môi trường
- Python 3.10 trở lên (khuyến nghị Python 3.12).
- MacOS / Linux / Windows.

### 1. Khởi tạo môi trường ảo và cài đặt thư viện
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

### 2. Cấu hình biến môi trường
Tạo file `.env` tại thư mục gốc (nếu dùng Gemini hoặc OpenAI API):
```env
APP_NAME="Document Q&A Assistant"
LLM_PROVIDER="gemini"             # hoặc "openai", "mock"
GEMINI_API_KEY="your-gemini-api-key"
OPENAI_API_KEY="your-openai-api-key"
RETRIEVAL_MODE="local"            # "local" hoặc "grpc"
GRPC_PORT=50051
```

### 3. Tạo dữ liệu mẫu & chạy Benchmark Evaluation
```bash
# Tạo 2 tài liệu kỹ thuật mẫu (PDF digital + PDF scan)
python scripts/generate_sample_docs.py

# Chạy benchmark đo Recall@K trên tập Ground Truth
python scripts/run_eval.py
```

### 4. Khởi chạy FastAPI Backend
```bash
uvicorn src.api.main:app --host 0.0.0.0 --port 8000 --reload
```
- API Docs Swagger: [http://localhost:8000/docs](http://localhost:8000/docs)
- Health Check: `GET http://localhost:8000/api/v1/health`

### 5. Sử dụng API
**Upload tài liệu PDF:**
```bash
curl -X POST "http://localhost:8000/api/v1/upload" \
  -H "accept: application/json" \
  -F "file=@sample_docs/pump_maintenance_guide.pdf"
```

**Đặt câu hỏi Q&A:**
```bash
curl -X POST "http://localhost:8000/api/v1/query" \
  -H "Content-Type: application/json" \
  -d '{
    "question": "Những nguyên nhân nào khiến áp suất đầu ra của máy bơm giảm?",
    "top_k": 5
  }'
```

---

## 4. Chạy với gRPC Service (Microservice Mode)

Khi bạn muốn tách tầng Retrieval thành một process / service độc lập:

1. **Khởi động gRPC Retrieval Server:**
   ```python
   # Chạy server trên cổng 50051
   from src.retrieval.local import LocalRetriever
   from src.vector_store.embedding import EmbeddingModel
   from src.vector_store.qdrant_store import QdrantVectorStore
   from src.rpc.server import start_grpc_server

   embedder = EmbeddingModel()
   store = QdrantVectorStore()
   retriever = LocalRetriever(embedder, store)
   server = start_grpc_server(retriever, port=50051)
   server.wait_for_termination()
   ```

2. **Cấu hình FastAPI gọi qua gRPC:**
   Trong `.env`:
   ```env
   RETRIEVAL_MODE="grpc"
   GRPC_HOST="localhost"
   GRPC_PORT=50051
   ```
   FastAPI sẽ tự động kích hoạt `GrpcRetriever` để gửi RPC search query qua port 50051.

---

## 5. Kết quả đánh giá (Benchmark Results)

Kết quả đo lường thực tế trên bộ dữ liệu kiểm thử `data/eval/ground_truth.json`:

| Chỉ số | Kết quả đạt được | Mục tiêu đề ra | Đánh giá |
|---|---|---|---|
| **Recall@1** | **91.7%** | ≥ 70% | Vượt mục tiêu |
| **Recall@3** | **91.7%** | ≥ 70% | Vượt mục tiêu |
| **Recall@5** | **100.0%** | ≥ 70% | Hoàn hảo (12/12 câu in-scope) |
| **Recall@10** | **100.0%** | ≥ 70% | Hoàn hảo |
| **Abstention Accuracy** | **100.0%** (Live LLM) | ≥ 90% | Chống hallucination triệt để |
