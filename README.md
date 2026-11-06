# Document Q&A Assistant — Chatbot Hỏi Đáp Tài Liệu Kỹ Thuật (Agentic RAG)

Hệ thống Chatbot hỏi đáp tài liệu kỹ thuật chuyên nghiệp ứng dụng kiến trúc **Agentic RAG (Adaptive & Corrective RAG)**, xử lý tài liệu đa định dạng (PDF cả văn bản số và tài liệu scan qua OCR, DOCX, TXT, PNG, JPG, JPEG), hỗ trợ tải lên hàng loạt (batch upload), lưu trữ file gốc bền vững (`data/uploads/`) với cơ chế khử trùng lặp (deduplication), phục vụ tài liệu an toàn trong trình duyệt (safe in-browser file serving), chunking bảo toàn metadata số trang, tìm kiếm tương đồng vector với Qdrant, vòng lặp Agentic RAG với mở rộng truy vấn (query expansion), tự phản chiếu (self-reflection / corrective re-querying), trích dẫn tương tác một chạm mở đúng số trang (`#page={page}`) và cơ chế từ chối (Abstention) chống hallucination triệt để, benchmark định lượng Recall@K, và tách module Retrieval thành microservice qua gRPC.

---

## 1. Kiến trúc hệ thống (Architecture)

Hệ thống tuân thủ kiến trúc Clean / Hexagonal Modular Monorepo kết hợp quy trình **Agentic RAG Loop**:

### Sơ đồ tổng thể hệ thống (System Overview)

```
                      +-----------------------------+
                      |        Client / User        |
                      |    (React SPA / REST API)   |
                      +--------------+--------------+
                                     | HTTP REST
                                     v
                      +-----------------------------+
                      |       FastAPI Gateway       |
                      | - POST   /api/v1/upload     |
                      | - GET    /api/v1/files      |
                      | - GET    /api/v1/files/{n}  |
                      | - POST   /api/v1/query      |
                      | - GET    /api/v1/sessions   |
                      | - GET    /api/v1/sessions/id|
                      | - DELETE /api/v1/sessions/id|
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

2. **Multi-turn Conversational Memory & Dynamic Session Management**:
   - **History-aware Contextualizer**: Node `rephrase_question` phân tích ngữ cảnh lịch sử hội thoại gần nhất và viết lại các câu hỏi kế tiếp mơ hồ (ví dụ: *"Áp suất của nó là bao nhiêu?"* -> *"Áp suất làm việc tối đa của máy bơm công nghiệp ly tâm là bao nhiêu?"*) để truy xuất chính xác tài liệu liên quan mà vẫn bảo toàn câu hỏi nguyên bản của người dùng trên giao diện.
   - **Persistent SQLite Session Store**: Lưu trữ phiên và tin nhắn bền vững tại `data/chat_history.db` (hỗ trợ foreign key cascade deletion khi xóa phiên), tích hợp cơ chế sliding window context giới hạn số lượt hội thoại gần nhất nạp vào prompt nhằm tối ưu hóa chi phí token.
   - **Automatic Session Title Generation**: Tự động tạo tiêu đề ngắn gọn từ câu hỏi đầu tiên của người dùng khi khởi tạo phiên mới.
   - **Giao diện React SPA**: Quản lý danh sách cuộc trò chuyện gần đây ở Sidebar (chọn, chuyển đổi, xóa phiên) với trạng thái lưu trữ bền vững.

3. **Persistent Raw File Storage & Filename Deduplication**:
   - Lưu trữ an toàn các tệp tài liệu nguyên bản vào thư mục `data/uploads/`.
   - **Filename Deduplication**: Kiểm tra tệp đã tồn tại trước khi xử lý. Nếu tệp đã có trong hệ thống, backend phản hồi trạng thái `already_exists` và bỏ qua (skip) toàn bộ chu trình phân trang, chunking và embedding vào Qdrant, giúp tiết kiệm tối đa tài nguyên tính toán và ngăn ngừa nhiễu vector.

4. **Interactive In-Browser Citations & Safe File Serving**:
   - Endpoint an toàn `GET /api/v1/files/{filename}` phục vụ tệp trực tiếp trong trình duyệt (`inline` viewing) với cơ chế bảo mật ngăn chặn tấn công Path Traversal (`is_relative_to`).
   - Hỗ trợ fragment nhảy trang chính xác (`#page={page}`): Người dùng bấm vào badge trích dẫn hoặc bằng chứng truy xuất sẽ mở tài liệu trong tab mới và tự động cuộn đến đúng trang chứa thông tin (hỗ trợ native trên PDF viewer của Chrome, Edge, Safari, Firefox).

5. **Multi-format Document Processing & OCR Fallback**:
   - Hỗ trợ đa dạng định dạng tài liệu kỹ thuật: **PDF** (`.pdf`), **Word** (`.docx`), **Text** (`.txt`), và **Ảnh** (`.png`, `.jpg`, `.jpeg`).
   - **PDF (PyMuPDF + RapidOCR)**: Tự động trích xuất trang văn bản số (digital text). Nếu mật độ văn bản thấp (< 50 ký tự, như tài liệu scan, bản vẽ, sơ đồ), tự động render ảnh 300 DPI và kích hoạt **RapidOCR** để nhận diện ký tự quang học.
   - **Word (DOCX)**: Trích xuất đoạn văn bản cấu trúc qua `python-docx` kết hợp phân trang logic (~2.000 ký tự/trang, `logical_page_size = 2000`).
   - **Text (TXT)**: Đọc văn bản thuần hỗ trợ fallback bảng mã (UTF-8, Latin-1) kèm phân trang logic (~2.000 ký tự/trang, `logical_page_size = 2000`).
   - **Ảnh kỹ thuật (PNG, JPG, JPEG)**: Nhận diện nội dung chữ trực tiếp từ ảnh qua RapidOCR engine (gán trang mặc định là 1).

6. **Multi-file Batch Upload & Trực quan hóa tiến độ**:
   - Tải lên đồng thời nhiều tệp tài liệu trong một lượt thao tác qua giao diện React SPA với cơ chế xử lý lỗi độc lập cho từng file.
   - Theo dõi trạng thái trực tiếp theo thời gian thực (tổng số tệp, thành công, đã tồn tại / trùng lặp, thất bại, và tổng số chunk đã nạp vào vector database).

7. **Chunking bảo toàn số trang & metadata**:
   - Phân chia văn bản theo **token** của chính tokenizer embedding (mặc định 400 token, overlap 50), luôn nằm gọn trong `EMBEDDING_MAX_SEQ_LENGTH` (chừa 64 token cho prefix query). Khi không có tokenizer, fallback về chế độ ký tự (1.200 ký tự, overlap 200).
   - Giữ nguyên `doc_name` và `page_number` (1-indexed) ở từng chunk bất kể tài liệu là PDF, DOCX, TXT hay Ảnh.

8. **Vector Database (Qdrant Cloud & Local)**:
   - Embedding đa ngữ Việt–Anh `intfloat/multilingual-e5-large-instruct` (1024 chiều, chuẩn hoá) với prefix instruct cho query; reranker `BAAI/bge-reranker-v2-m3`.
   - Khởi động sẽ báo lỗi ngay nếu số chiều collection không khớp model. Sau khi đổi `EMBEDDING_MODEL`, chạy `python scripts/reindex.py --recreate --yes` (hoặc đổi `QDRANT_COLLECTION` sang collection mới rồi chạy `python scripts/reindex.py`). Dùng `--dry-run` để xem trước số chunk.
   - Hỗ trợ kết nối Qdrant Cloud Cluster (`QDRANT_URL`, `QDRANT_API_KEY`) hoặc lưu trữ cục bộ.

9. **Evaluation Suite (trên tài liệu thật, không cần ground truth viết tay)**:
   - **Synthetic QA**: LLM sinh một câu hỏi cho mỗi trang trong `data/uploads/`; trang nguồn chính là nhãn → đo `Recall@K`, `MRR@5` cho từng tầng dense / hybrid / rerank.
   - **LLM-as-judge**: top-5 của các cấu hình được gộp, xáo trộn và chấm mù 0/1/2 → `precision@5`, `nDCG@5`, `hit@5`, tỷ lệ thắng/thua.
   - Mỗi cấu hình được index lại riêng trong Qdrant tạm, không đụng collection production.

10. **gRPC Retrieval Service**:
   - Định nghĩa API hợp đồng bằng Protocol Buffers (`proto/retrieval.proto`).
   - Cung cấp `start_grpc_server` và `GrpcRetriever` adapter. Chuyển đổi giữa chạy local và gRPC chỉ bằng 1 biến môi trường `RETRIEVAL_MODE=grpc`.

11. **Giao diện Web Hiện Đại (React SPA Obsidian UI)**:
    - Thiết kế Dark Mode tối giản (Obsidian theme), font chữ kỹ thuật sắc nét, giảm mỏi mắt khi đọc tài liệu dài.
    - **Split-view Document Viewer**: Xem tài liệu PDF/văn bản trực tiếp bên cạnh khung chat; nhấp vào badge trích dẫn sẽ tự động mở panel tài liệu và cuộn đến đúng trang (`#page={page}`).
    - **Interactive Citations & Reasoning Steps**: Badge trích dẫn tương tác một chạm, hộp các bước suy luận Agentic RAG và chi tiết bằng chứng đối sánh (Evidence Chunks với Cosine score) có thể thu gọn/mở rộng.
    - **Render Công thức Toán học LaTeX & Markdown**: Hỗ trợ toàn diện công thức toán học qua KaTeX (`$x$`, `$$x$$`) và định dạng GitHub Flavored Markdown (bảng thông số kỹ thuật, code block, checklist).
    - **Quản lý tài liệu & Batch Upload**: Kéo thả, tải lên đồng thời nhiều tệp với tiến độ thời gian thực, xóa tài liệu khỏi index/đĩa cứng. Số đoạn ngữ cảnh đưa vào LLM do hệ thống tự chọn (`RERANK_TOP_K`), người dùng không cần chỉnh.
    - **Thiết kế Responsive**: Tự động co giãn mượt mà trên thiết bị di động, tablet và desktop.

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

### 3. Đánh giá retrieval trên tài liệu thật
```bash
# A. Sinh bộ câu hỏi từ data/uploads -> data/eval/synthetic_qa.json (cần GEMINI_API_KEY)
python scripts/build_synthetic_qa.py            # --resume để sinh bù trang bị lỗi rate limit

# A + B. So sánh các cấu hình model -> data/eval/reports/compare-<timestamp>.md/.json
python scripts/compare_models.py                # mặc định: old (MiniLM) vs new (e5)
python scripts/compare_models.py --no-judge     # chỉ chấm theo nhãn, không gọi LLM
python scripts/compare_models.py --configs '[{"name":"x","embedding":"...","reranker":"..."}]'
```
Bộ câu hỏi, báo cáo và cache trang (`data/eval/`) chứa trích đoạn tài liệu nên không được commit. Gemini free tier giới hạn 15 request/phút; script tự giới hạn ở `--rpm 14`.

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

### 6. Sử dụng API RESTful

#### 6.1. Upload tài liệu (Lưu file & Khử trùng lặp)
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

#### 6.2. Danh sách tài liệu đã lưu trữ
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

#### 6.3. Xem tài liệu an toàn trong trình duyệt (Inline Viewing & Jump to Page)
Mở trực tiếp tài liệu trong trình duyệt, kèm hỗ trợ nhảy đến số trang mong muốn thông qua URL hash:
```
http://localhost:8000/api/v1/files/may_bom_cong_nghiep.pdf#page=3
```
Endpoint bảo vệ an toàn tuyệt đối chống tấn công Path Traversal: các yêu cầu chứa đường dẫn bất thường (ví dụ: `../etc/passwd`) sẽ bị từ chối với mã lỗi `400 Bad Request`.

#### 6.4. Đặt câu hỏi Q&A (Kích hoạt Agentic RAG & Ngữ cảnh Đa lượt)
Gửi câu hỏi tới hệ thống để thực thi quy trình Agentic RAG (Contextualizer -> Query Expansion -> Corrective Retrieval -> Reflection -> Grounding):
- Truyền `session_id` để duy trì mạch hội thoại đa lượt (multi-turn context). Nếu `session_id` là `null` hoặc không truyền, hệ thống sẽ tự động tạo một phiên trò chuyện mới và trả về `session_id` trong phản hồi.
- Khi có ngữ cảnh trước đó, hệ thống tự động viết lại câu hỏi kế tiếp mơ hồ thành câu hỏi độc lập (`standalone_question`) để truy vấn tài liệu chính xác nhất.

```bash
# Lượt hỏi 1: Khởi tạo phiên mới (hoặc truyền session_id cụ thể)
curl -X POST "http://localhost:8000/api/v1/query" \
  -H "Content-Type: application/json" \
  -d '{
    "question": "Những nguyên nhân nào khiến áp suất đầu ra của máy bơm giảm?"
  }'
```
Phản hồi mẫu:
```json
{
  "answer": "Theo tài liệu kỹ thuật, áp suất đầu ra của máy bơm giảm do các nguyên nhân sau: cánh bơm bị mòn, rò rỉ tại vòng đệm và đường ống hút bị tắc nghẽn [Tài liệu: may_bom_cong_nghiep.pdf, Trang 3].",
  "citations": [
    {
      "doc_name": "may_bom_cong_nghiep.pdf",
      "page_number": 3
    }
  ],
  "abstained": false,
  "retrieved_chunks": [
    {
      "chunk": {
        "chunk_id": "chunk_123",
        "doc_name": "may_bom_cong_nghiep.pdf",
        "page_number": 3,
        "text": "Sự cố suy giảm áp suất: Nguyên nhân chính bao gồm mài mòn cánh bơm..."
      },
      "score": 0.89
    }
  ],
  "reasoning_steps": [
    "Khởi tạo phiên hội thoại mới: a1b2c3d4-...",
    "Mở rộng truy vấn thành 3 góc nhìn kỹ thuật",
    "Truy xuất và hợp nhất các đoạn bằng chứng liên quan",
    "Tự phản chiếu: Đạt ngưỡng liên quan 0.89 >= 0.70",
    "Hậu kiểm trích dẫn và tổng hợp câu trả lời"
  ],
  "standalone_question": "Những nguyên nhân nào khiến áp suất đầu ra của máy bơm giảm?",
  "session_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
}
```

```bash
# Lượt hỏi 2 (Follow-up): Tái sử dụng session_id vừa nhận được
curl -X POST "http://localhost:8000/api/v1/query" \
  -H "Content-Type: application/json" \
  -d '{
    "question": "Cách khắc phục nguyên nhân thứ nhất như thế nào?",
    "session_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
  }'
```

*(Hệ thống sẽ tự động ngữ cảnh hóa câu hỏi thành: "Cách khắc phục tình trạng cánh bơm bị mòn của máy bơm như thế nào?" và truy xuất trả lời chính xác dựa trên tài liệu).*

#### 6.5. Quản lý phiên hội thoại (Conversational Session API)

##### 6.5.1. Lấy danh sách tất cả các phiên hội thoại
Lấy danh sách các phiên trò chuyện, sắp xếp theo thời gian cập nhật mới nhất (`updated_at` giảm dần).
Hỗ trợ tham số truy vấn tùy chọn `limit` (mặc định 50, từ 1 đến 200).

```bash
curl -X GET "http://localhost:8000/api/v1/sessions?limit=20"
```

Phản hồi mẫu:
```json
{
  "sessions": [
    {
      "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
      "title": "Những nguyên nhân khiến áp suất máy bơm giảm",
      "created_at": "2026-11-01T13:00:00+00:00",
      "updated_at": "2026-11-01T13:05:00+00:00"
    }
  ]
}
```

##### 6.5.2. Lấy chi tiết phiên hội thoại & lịch sử tin nhắn
Truy xuất thông tin chi tiết một phiên cùng toàn bộ lịch sử tin nhắn đã gửi giữa người dùng và trợ lý:

```bash
curl -X GET "http://localhost:8000/api/v1/sessions/a1b2c3d4-e5f6-7890-abcd-ef1234567890"
```

Phản hồi mẫu:
```json
{
  "session": {
    "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
    "title": "Những nguyên nhân khiến áp suất máy bơm giảm",
    "created_at": "2026-11-01T13:00:00+00:00",
    "updated_at": "2026-11-01T13:05:00+00:00"
  },
  "messages": [
    {
      "role": "user",
      "content": "Những nguyên nhân nào khiến áp suất đầu ra của máy bơm giảm?",
      "created_at": "2026-11-01T13:00:00+00:00"
    },
    {
      "role": "assistant",
      "content": "Theo tài liệu kỹ thuật, áp suất đầu ra giảm do...",
      "citations": [
        {
          "doc_name": "may_bom_cong_nghiep.pdf",
          "page_number": 3
        }
      ],
      "reasoning_steps": [
        "Mở rộng truy vấn thành 3 góc nhìn kỹ thuật",
        "Truy xuất và kiểm tra ngưỡng liên quan"
      ],
      "created_at": "2026-11-01T13:00:02+00:00"
    }
  ]
}
```

##### 6.5.3. Xóa phiên hội thoại
Xóa hoàn toàn phiên hội thoại và tự động xóa toàn bộ tin nhắn liên quan trong cơ sở dữ liệu (`ON DELETE CASCADE`):

```bash
curl -X DELETE "http://localhost:8000/api/v1/sessions/a1b2c3d4-e5f6-7890-abcd-ef1234567890"
```

Phản hồi mẫu:
```json
{
  "message": "Đã xóa thành công phiên hội thoại a1b2c3d4-e5f6-7890-abcd-ef1234567890."
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
   store = QdrantVectorStore(vector_size=embedder.dimension)
   retriever = LocalRetriever(embedder, store)
   server = start_grpc_server(retriever, port=50051)
   server.wait_for_termination()
   ```
   Hoặc chạy trực tiếp: `python -m src.rpc.server` (đọc cấu hình từ `.env`).

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

Đo ngày 2026-11-06 trên tài liệu thật (105 trang, 2 tài liệu), 102 câu hỏi synthetic, pipeline hybrid (dense + BM25, RRF) → rerank top-5:

| Chỉ số (sau rerank) | MiniLM-L6-v2 + bge-reranker-base | **multilingual-e5-large-instruct + bge-reranker-v2-m3** |
|---|---:|---:|
| Recall@1 | 34.3% | **60.8%** |
| Recall@3 | 59.8% | **76.5%** |
| Recall@5 | 69.6% | **82.4%** |
| MRR@5 | 0.471 | **0.688** |
| LLM judge hit@5 (≥1 đoạn trả lời trực tiếp) | 60.8% | **86.3%** |
| LLM judge nDCG@5 | 0.391 | **0.575** |
| Thắng / hoà (nDCG@5, 102 câu) | 28 | **65** / 9 hoà |
| Latency rerank / câu (20 ứng viên, EMBEDDING_DEVICE auto) | ~0.3 s | ~2.1 s |

