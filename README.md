# Document Q&A Assistant — Chatbot Hỏi Đáp Tài Liệu Kỹ Thuật (Agentic RAG)

Hệ thống Chatbot hỏi đáp tài liệu kỹ thuật chuyên nghiệp ứng dụng kiến trúc **Agentic RAG (Adaptive & Corrective RAG)**, xử lý tài liệu đa định dạng (PDF cả văn bản số và tài liệu scan qua OCR, DOCX, TXT, PNG, JPG, JPEG), hỗ trợ tải lên hàng loạt (batch upload), lưu trữ file gốc bền vững (`data/uploads/`) với cơ chế khử trùng lặp (deduplication), phục vụ tài liệu an toàn trong trình duyệt (safe in-browser file serving), chunking bảo toàn metadata số trang, tìm kiếm tương đồng vector với Qdrant, vòng lặp Agentic RAG với mở rộng truy vấn (query expansion), tự phản chiếu (self-reflection / corrective re-querying), trích dẫn tương tác một chạm mở đúng số trang (`#page={page}`) và cơ chế từ chối (Abstention) chống hallucination triệt để, benchmark định lượng Recall@K, và tách module Retrieval thành microservice qua gRPC.

---

## 1. Kiến trúc hệ thống (Architecture)

Hệ thống tuân thủ kiến trúc Clean / Hexagonal Modular Monorepo kết hợp quy trình **Agentic RAG Loop**:

### Sơ đồ tổng thể hệ thống (System Overview)

```
                      +-----------------------------+
                      |        Client / User        |
                      | (React SPA / Streamlit/API) |
                      +--------------+--------------+
                                     | HTTP REST
                                     v
                      +-----------------------------+
                      |       FastAPI Gateway       |
                      | - POST /api/v1/upload       |
                      | - GET  /api/v1/files        |
                      | - GET  /api/v1/files/{name} |
                      | - POST /api/v1/query        |
                      +-------+--------------+------+
                              |              |
      +-----------------------+              +-----------------------+
      | (Upload / Ingestion)                                         | (Query / Agentic RAG)
      v                                                              v
+-----------------------------+                        +-----------------------------+
| Persistent Raw File Storage |                        |      Agentic RAG Engine     |
|   - Directory data/uploads/ |                        |   (Query Expansion, CRAG,   |
|   - Filename Deduplication  |                        |    Citation Grounding)      |
+-------------+---------------+                        +--------------+--------------+
              | (If new file)                                         |
              v                                                       v
+-----------------------------+                        +-----------------------------+
|    Ingestion Pipeline       |                        |   BaseRetriever Interface   |
|  - Unified DocumentExtractor|                        +--------------+--------------+
|  - PyMuPDF / RapidOCR (PDF) |                                       |
|  - python-docx / txt / img  |                        +--------------+--------------+
|  - Semantic Chunker         |                        |                             |
+-------------+---------------+                        v (Mode: local)               v (Mode: grpc)
              |                                 +--------------+              +---------------+
              | Upsert vectors                  | LocalRetriever|             | GrpcRetriever |
              v                                 +-------+------+              +-------+-------+
+-----------------------------+                         |                             | gRPC Channel
|   Qdrant Vector Database    |<------------------------+                             v
|  (Embedded / Port 6333)     |                                       +-------------------------------+
+-----------------------------+                                       | gRPC Retrieval Server (:50051)|
                                                                      +-------------------------------+
```

### Vòng lặp Agentic RAG (Corrective RAG & Self-Reflection Loop)

```
                            [ Câu hỏi người dùng ]
                                      |
                                      v
                         +--------------------------+
                         |     Query Expansion      |
                         | (Sinh N biến thể query)  |
                         +------------+-------------+
                                      |
                                      v
                         +--------------------------+
                         |  Multi-Query Retrieval   |
                         |  & Evidence Deduplication|
                         +------------+-------------+
                                      |
                                      v
                         +--------------------------+
                         |     Self-Reflection      |
                         |   (Đánh giá Relevance)   |
                         +------------+-------------+
                                      |
            +-------------------------+-------------------------+
            | Score < Relevance Threshold (Chưa đủ tin cậy)      | Score >= Threshold (Đủ liên quan)
            v                                                   v
+--------------------------+                         +--------------------------+
|      Query Rewrite       |                         |    Answer Generation     |
| (Viết lại truy vấn mới)  |                         |  (Dựa trên Ground Truth) |
+------------+-------------+                         +------------+-------------+
             | (Tối đa max_query_iterations)                      |
             +--------------------> Quay lại Retrieval            v
                                                     +--------------------------+
                                                     |    Citation Grounding    |
                                                     |  (Hậu kiểm & khử ảo giác)|
                                                     +------------+-------------+
                                                                  |
                                                                  v
                                                     [ Phản hồi & Trích dẫn Clickable ]
                                                     ([Tài liệu, Trang X] -> #page={page})
```

---

## 2. Các chức năng chính (Core Features)

1. **Agentic RAG Architecture (Adaptive & Corrective RAG Loop)**:
   - **Query Expansion**: Mở rộng câu hỏi đầu vào thành nhiều góc nhìn ngữ nghĩa khác nhau (`expand_query`) giúp tìm kiếm toàn diện hơn.
   - **Multi-Query Retrieval & Deduplication**: Truy xuất song song cho các biến thể truy vấn và tự động khử trùng lặp (deduplicate) các evidence chunks dựa trên `doc_name`, `page_number` và `text`.
   - **Self-Reflection / Corrective RAG (CRAG)**: Đánh giá độ tin cậy của tài liệu truy xuất thông qua ngưỡng liên quan (`relevance_threshold`). Nếu điểm số thấp, hệ thống tự động kích hoạt vòng lặp viết lại truy vấn (Query Rewriting) và tái truy xuất tối đa `max_query_iterations` lần.
   - **Citation Grounding**: Cơ chế hậu kiểm nghiêm ngặt, đối chiếu từng trích dẫn trong câu trả lời với tập chunk tài liệu thực tế thu thập được, loại bỏ hoàn toàn các trích dẫn bịa đặt (hallucinated citations).
   - **Abstention dứt khoát**: Từ chối trả lời nếu sau các lần tái truy xuất vẫn không tìm thấy bằng chứng thỏa mãn độ tin cậy (`"Tôi không tìm thấy thông tin này trong tài liệu được cung cấp."`).

2. **Persistent Raw File Storage & Filename Deduplication**:
   - Lưu trữ an toàn các tệp tài liệu nguyên bản vào thư mục `data/uploads/`.
   - **Filename Deduplication**: Kiểm tra tệp đã tồn tại trước khi xử lý. Nếu tệp đã có trong hệ thống, backend phản hồi trạng thái `already_exists` và bỏ qua (skip) toàn bộ chu trình phân trang, chunking và embedding vào Qdrant, giúp tiết kiệm tối đa tài nguyên tính toán và ngăn ngừa nhiễu vector.

3. **Interactive In-Browser Citations & Safe File Serving**:
   - Endpoint an toàn `GET /api/v1/files/{filename}` phục vụ tệp trực tiếp trong trình duyệt (`inline` viewing) với cơ chế bảo mật ngăn chặn tấn công Path Traversal (`is_relative_to`).
   - Hỗ trợ fragment nhảy trang chính xác (`#page={page}`): Người dùng bấm vào badge trích dẫn hoặc bằng chứng truy xuất sẽ mở tài liệu trong tab mới và tự động cuộn đến đúng trang chứa thông tin (hỗ trợ native trên PDF viewer của Chrome, Edge, Safari, Firefox).

4. **Multi-format Document Processing & OCR Fallback**:
   - Hỗ trợ đa dạng định dạng tài liệu kỹ thuật: **PDF** (`.pdf`), **Word** (`.docx`), **Text** (`.txt`), và **Ảnh** (`.png`, `.jpg`, `.jpeg`).
   - **PDF (PyMuPDF + RapidOCR)**: Tự động trích xuất trang văn bản số (digital text). Nếu mật độ văn bản thấp (< 50 ký tự, như tài liệu scan, bản vẽ, sơ đồ), tự động render ảnh 300 DPI và kích hoạt **RapidOCR** để nhận diện ký tự quang học.
   - **Word (DOCX)**: Trích xuất đoạn văn bản cấu trúc qua `python-docx` kết hợp phân trang logic (~2.000 ký tự/trang, `logical_page_size = 2000`).
   - **Text (TXT)**: Đọc văn bản thuần hỗ trợ fallback bảng mã (UTF-8, Latin-1) kèm phân trang logic (~2.000 ký tự/trang, `logical_page_size = 2000`).
   - **Ảnh kỹ thuật (PNG, JPG, JPEG)**: Nhận diện nội dung chữ trực tiếp từ ảnh qua RapidOCR engine (gán trang mặc định là 1).

5. **Multi-file Batch Upload & Trực quan hóa tiến độ**:
   - Tải lên đồng thời nhiều tệp tài liệu trong một lượt thao tác. Giao diện Streamlit điều phối upload tuần tự từng file kèm cơ chế xử lý lỗi độc lập.
   - Theo dõi trạng thái trực tiếp theo thời gian thực qua container `st.status` và các thẻ thống kê `st.metric` (tổng số tệp, thành công, đã tồn tại / trùng lặp, thất bại, và tổng số chunk đã nạp vào vector database).

6. **Chunking bảo toàn số trang & metadata**:
   - Phân chia văn bản thành các đoạn (chunks) có overlap.
   - Giữ nguyên `doc_name` và `page_number` (1-indexed) ở từng chunk bất kể tài liệu là PDF, DOCX, TXT hay Ảnh.

7. **Vector Database (Qdrant Cloud & Local)**:
   - Sử dụng model `sentence-transformers/all-MiniLM-L6-v2` tạo vector 384 chiều chuẩn hóa.
   - Hỗ trợ kết nối Qdrant Cloud Cluster (`QDRANT_URL`, `QDRANT_API_KEY`) hoặc lưu trữ cục bộ.

8. **Evaluation Suite (Recall@K Benchmark)**:
   - Bộ dữ liệu Ground Truth kiểm thử 15 câu hỏi kỹ thuật và out-of-scope.
   - Đo lường tự động: `Recall@1`, `Recall@3`, `Recall@5`, `Recall@10` và `Abstention Accuracy`.

9. **gRPC Retrieval Service**:
   - Định nghĩa API hợp đồng bằng Protocol Buffers (`proto/retrieval.proto`).
   - Cung cấp `start_grpc_server` và `GrpcRetriever` adapter. Chuyển đổi giữa chạy local và gRPC chỉ bằng 1 biến môi trường `RETRIEVAL_MODE=grpc`.

10. **Giao diện Web Hiện Đại (React SPA Obsidian UI & Streamlit Companion)**:
    - **React Single-Page Application (Primary UI)**:
      - Thiết kế Dark Mode tối giản (Obsidian theme), font chữ kỹ thuật sắc nét, giảm mỏi mắt khi đọc tài liệu dài.
      - **Split-view Document Viewer**: Xem tài liệu PDF/văn bản trực tiếp bên cạnh khung chat; nhấp vào badge trích dẫn sẽ tự động mở panel tài liệu và cuộn đến đúng trang (`#page={page}`).
      - **Interactive Citations & Reasoning Steps**: Badge trích dẫn tương tác một chạm, hộp các bước suy luận Agentic RAG và chi tiết bằng chứng đối sánh (Evidence Chunks với Cosine score) có thể thu gọn/mở rộng.
      - **Render Công thức Toán học LaTeX & Markdown**: Hỗ trợ toàn diện công thức toán học qua KaTeX (`$x$`, `$$x$$`) và định dạng GitHub Flavored Markdown (bảng thông số kỹ thuật, code block, checklist).
      - **Quản lý tài liệu & Batch Upload**: Kéo thả, tải lên đồng thời nhiều tệp với tiến độ thời gian thực, xóa tài liệu khỏi index/đĩa cứng, điều chỉnh độ sâu `top_k`.
      - **Thiết kế Responsive**: Tự động co giãn mượt mà trên thiết bị di động, tablet và desktop.
    - **Giao diện Streamlit (Companion / Fallback UI)**:
      - Giao diện chat phong cách ChatGPT hiện đại (`st.chat_message`, `st.chat_input`), phù hợp chạy thử nghiệm hoặc demo nhanh.

---

## 3. Cài đặt & Khởi động nhanh (Quickstart)

### Yêu cầu môi trường
- Python 3.10 trở lên (khuyến nghị Python 3.12).
- Node.js 18 trở lên và npm (dành cho React Frontend).
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
UPLOAD_DIR="data/uploads"          # Thư mục lưu trữ tài liệu gốc
```

### 3. Chạy Benchmark Evaluation
```bash
# Chạy benchmark đo Recall@K trên tập Ground Truth
python scripts/run_eval.py
```

### 4. Khởi chạy FastAPI Backend
```bash
.venv/bin/uvicorn src.api.main:app --host 0.0.0.0 --port 8000 --reload
```
- API Docs Swagger: [http://localhost:8000/docs](http://localhost:8000/docs)
- Health Check: `GET http://localhost:8000/api/v1/health`

### 5. Khởi chạy React SPA Frontend (Khuyến nghị / Primary UI)
Mở một terminal mới và chạy:
```bash
cd frontend
npm install
npm run dev
```
- Truy cập giao diện tại: [http://localhost:5173](http://localhost:5173)
- **Đóng gói Production Build:**
  ```bash
  cd frontend
  npm run build
  ```
  Tệp build tĩnh sẵn sàng phục vụ sẽ được xuất bản tại thư mục `frontend/dist/`.
- **Chạy bộ kiểm thử Frontend (Vitest):**
  ```bash
  cd frontend
  npm run test -- --run
  ```

### 6. Khởi chạy Giao diện Streamlit (Companion / Fallback UI)
Giao diện Streamlit truyền thống vẫn được duy trì song song phục vụ mục đích kiểm thử và demo nhanh:
```bash
.venv/bin/streamlit run src/ui/app.py
```
- Truy cập giao diện tại: [http://localhost:8501](http://localhost:8501)

### 7. Sử dụng API RESTful

#### 7.1. Upload tài liệu (Lưu file & Khử trùng lặp)
Endpoint `/api/v1/upload` tiếp nhận 1 tệp mỗi lượt yêu cầu (`multipart/form-data`). File được lưu vào `data/uploads/`. Nếu tên file đã tồn tại, API trả về `status: "already_exists"` và bỏ qua việc tạo vector mới.

```bash
# Upload file PDF
curl -X POST "http://localhost:8000/api/v1/upload" \
  -H "accept: application/json" \
  -F "file=@path/to/document.pdf"

# Upload file Word (.docx)
curl -X POST "http://localhost:8000/api/v1/upload" \
  -H "accept: application/json" \
  -F "file=@path/to/document.docx"

# Upload file Text (.txt)
curl -X POST "http://localhost:8000/api/v1/upload" \
  -H "accept: application/json" \
  -F "file=@path/to/notes.txt"

# Upload ảnh kỹ thuật hoặc bản scan (.png, .jpg, .jpeg)
curl -X POST "http://localhost:8000/api/v1/upload" \
  -H "accept: application/json" \
  -F "file=@path/to/diagram.png"
```

Phản hồi mẫu:
```json
{
  "filename": "may_bom_cong_nghiep.pdf",
  "status": "uploaded",
  "chunks_indexed": 12,
  "message": "Successfully indexed 12 chunks from may_bom_cong_nghiep.pdf"
}
```
*(Nếu tệp đã tồn tại: `"status": "already_exists"`, `"chunks_indexed": 0`)*

#### 7.2. Danh sách tài liệu đã lưu trữ
Lấy danh sách tất cả các tài liệu hiện đang được lưu trữ trong hệ thống:
```bash
curl -X GET "http://localhost:8000/api/v1/files"
```
Phản hồi mẫu:
```json
{
  "files": [
    {
      "filename": "may_bom_cong_nghiep.pdf",
      "size_bytes": 1048576,
      "uploaded_at": "2026-10-31T10:00:00Z"
    }
  ]
}
```

#### 7.3. Xem tài liệu an toàn trong trình duyệt (Inline Viewing & Jump to Page)
Mở trực tiếp tài liệu trong trình duyệt, kèm hỗ trợ nhảy đến số trang mong muốn thông qua URL hash:
```
http://localhost:8000/api/v1/files/may_bom_cong_nghiep.pdf#page=3
```
Endpoint bảo vệ an toàn tuyệt đối chống tấn công Path Traversal: các yêu cầu chứa đường dẫn bất thường (ví dụ: `../etc/passwd`) sẽ bị từ chối với mã lỗi `400 Bad Request`.

#### 7.4. Đặt câu hỏi Q&A (Kích hoạt Agentic RAG)
Gửi câu hỏi tới hệ thống để thực thi quy trình Agentic RAG (Query Expansion -> Corrective Retrieval -> Reflection -> Grounding):
```bash
curl -X POST "http://localhost:8000/api/v1/query" \
  -H "Content-Type: application/json" \
  -d '{
    "question": "Những nguyên nhân nào khiến áp suất đầu ra của máy bơm giảm?",
    "top_k": 5
  }'
```
Phản hồi mẫu:
```json
{
  "answer": "Theo tài liệu kỹ thuật, áp suất đầu ra của máy bơm giảm do các nguyên nhân sau: cánh bơm bị mòn, rò rỉ tại vòng đệm và đường ống hút bị tắc nghẽn [Tài liệu: may_bom_cong_nghiep.pdf, Trang 3].",
  "citations": [
    {
      "document": "may_bom_cong_nghiep.pdf",
      "page": 3
    }
  ],
  "evidence": [
    {
      "doc_name": "may_bom_cong_nghiep.pdf",
      "page_number": 3,
      "text": "Sự cố suy giảm áp suất: Nguyên nhân chính bao gồm mài mòn cánh bơm...",
      "score": 0.89
    }
  ]
}
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
