# Streamlit UI Design Specification — ChatGPT-style Document Q&A Assistant

**Date:** 2026-10-30  
**Status:** Draft / Ready for Review  
**Author:** Antigravity & User  
**Target Architecture:** Decoupled Streamlit Frontend Client interacting with existing FastAPI REST Backend.

---

## 1. Overview & Objectives

Xây dựng giao diện web tương tác trực quan bằng **Streamlit** theo **phong cách ChatGPT** cho hệ thống Document Q&A Assistant. Giao diện cho phép kỹ sư và người dùng:
1. Hỏi đáp kỹ thuật trực tiếp với tài liệu thông qua mô hình RAG (FastAPI + Qdrant Cloud + Google Gemini).
2. Hiển thị trích dẫn nguồn chuẩn xác (tên file, số trang), cờ từ chối (Abstention) khi câu hỏi ngoài phạm vi, và khung tra cứu chi tiết các đoạn context trích xuất (retrieved chunks) kèm điểm tương đồng (similarity score).
3. Kéo-thả tải lên tài liệu PDF mới (hỗ trợ cả PDF số và PDF scan qua OCR), tự động kích hoạt pipeline chia đoạn và đánh chỉ mục lên Qdrant Cloud.
4. Quản lý phiên hội thoại với nút "+ New chat", gợi ý câu hỏi mẫu khi bắt đầu, và kiểm tra trạng thái Backend theo thời gian thực.

---

## 2. Architecture & Component Boundaries

Hệ thống tuân thủ mô hình **Client-Server phân tách (Decoupled)**:
- **Backend (Existing):** FastAPI server chạy tại `http://localhost:8000`, cung cấp các endpoint REST:
  - `GET /api/v1/health`: Kiểm tra trạng thái hệ thống.
  - `POST /api/v1/upload`: Upload file multipart PDF, bóc tách text/OCR, chunking và index vào Qdrant.
  - `POST /api/v1/query`: Nhận `QARequest(question, top_k)` và trả về `QAResponse(answer, citations, abstained, retrieved_chunks)`.
- **Frontend (New):** Streamlit application độc lập, giao tiếp với Backend qua HTTP client (`httpx`). Không can thiệp trực tiếp vào file lock hay connection pool nội bộ của Backend.

```
+-------------------------------------------------------------+
|                      Browser / User                         |
+------------------------------+------------------------------+
                               |
                               v
+-------------------------------------------------------------+
|               Streamlit UI Layer (`src/ui/`)                |
|  - `app.py`: Streamlit entrypoint & page layout             |
|  - `components/chat.py`: Chat message & source renderers    |
|  - `components/sidebar.py`: Upload widget & config controls  |
|  - `api_client.py`: HTTP Client calling FastAPI endpoints   |
+------------------------------+------------------------------+
                               | (HTTP / REST API)
                               v
+-------------------------------------------------------------+
|                   FastAPI Backend Server                    |
|                `http://localhost:8000/api/v1/`              |
|        (/health, /upload, /query -> Qdrant + Gemini)        |
+-------------------------------------------------------------+
```

---

## 3. Detailed UI Design & User Flow

### 3.1. Main Chat Area (ChatGPT-Style)
- **Empty State (Chưa có tin nhắn):**
  - Tiêu đề trung tâm: `🤖 Document Q&A Assistant`.
  - Phụ đề: *Hỏi đáp tài liệu kỹ thuật có trích dẫn nguồn & kiểm soát suy đoán*.
  - **Prompt Suggestions:** 3 nút câu hỏi mẫu sẵn sàng click:
    1. *"Những nguyên nhân nào khiến áp suất đầu ra của máy bơm bị giảm?"*
    2. *"Nhiệt độ tối đa cho phép của thân bơm trong vận hành liên tục là bao nhiêu?"*
    3. *"Rơ le nhiệt FR1 trên sơ đồ mạch điện cài đặt dòng bao nhiêu ampe?"*
    - Khi người dùng click vào bất kỳ nút nào, câu hỏi sẽ được điền vào ô chat và gửi đi ngay lập tức.
- **Message List (`st.chat_message`):**
  - **User message:** Avatar người dùng, văn bản câu hỏi.
  - **Assistant message:** Avatar trợ lý, nội dung trả lời từ LLM Markdown.
    - **Citations Pills/Badges:** Mỗi trích dẫn hiển thị dưới dạng badge rõ ràng: `📄 [Tài liệu: <doc_name>, Trang <page_number>]`.
    - **Abstention Banner:** Nếu `abstained == True`, hiển thị warning box: *"⚠️ Thông tin này không có trong tài liệu được cung cấp. Hệ thống đã từ chối suy đoán để đảm bảo tính an toàn kỹ thuật."*
    - **Evidence Expander (`st.expander`):** `🔍 Xem chi tiết {len(chunks)} đoạn trích dẫn & Độ khớp`:
      - Hiển thị từng chunk: số trang, điểm Cosine Similarity (`score`), trích đoạn văn bản gốc trong tài liệu.
- **Fixed Chat Input (`st.chat_input`):**
  - Cố định ở cuối trang với placeholder: *"Hỏi bất kỳ điều gì về tài liệu kỹ thuật..."*.

### 3.2. Sidebar (Collapsible Control Panel)
- **Header:** Nút **`+ New Chat`** (Tạo đoạn chat mới) $\rightarrow$ xóa sạch `st.session_state.messages` và đưa giao diện về Empty State.
- **Tài liệu & Upload:**
  - File uploader nhận file `.pdf`.
  - Nút **"Nạp tài liệu" (Upload & Index)**:
    - Hiển thị spinner và progress status khi đang gửi file tới `POST /api/v1/upload`.
    - Hiển thị thông báo thành công: `✅ Đã nạp thành công {filename}: {pages} trang, {chunks} chunks đã lưu vào Qdrant`.
- **Cấu hình & Trạng thái:**
  - Slider **Độ sâu tìm kiếm (`top_k`)**: Giá trị từ 1 đến 10 (mặc định: 3).
  - **Backend Status Indicator:**
    - Gọi ngầm `GET /api/v1/health`.
    - Hiển thị: `🟢 Backend Online` (kèm thông tin mode retrieval) hoặc `🔴 Backend Offline` (kèm cảnh báo và hướng dẫn khởi động FastAPI).

---

## 4. Technical File Structure

```
src/
├── ui/
│   ├── __init__.py
│   ├── api_client.py         # HTTP client wrapper gọi FastAPI
│   ├── app.py                # File chạy chính của Streamlit
│   └── components/
│       ├── __init__.py
│       ├── chat.py           # Render danh sách tin nhắn, badges, expander
│       └── sidebar.py        # Render sidebar, uploader, connection badge
pyproject.toml                # Thêm dependency: streamlit>=1.32.0
tests/
├── test_ui_api_client.py     # Unit test cho API Client (mock HTTP responses)
└── test_ui_components.py     # Unit test cho logic format citations & messages
```

---

## 5. API Client Specification (`src/ui/api_client.py`)

Lớp `ApiClient` sử dụng `httpx` (đã có trong `pyproject.toml`):
```python
class ApiClient:
    def __init__(self, base_url: str = "http://localhost:8000/api/v1", timeout: float = 30.0):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def check_health(self) -> dict | None:
        """Trả về payload health dict hoặc None nếu không kết nối được."""
        ...

    def upload_document(self, file_bytes: bytes, filename: str) -> dict:
        """Gửi multipart/form-data upload file PDF lên FastAPI backend."""
        ...

    def query(self, question: str, top_k: int = 3) -> QAResponse:
        """Gửi câu hỏi tới /query và parse kết quả thành QAResponse model."""
        ...
```

---

## 6. Error Handling & Edge Cases

1. **Backend Server Offline:**
   - Sidebar hiển thị cảnh báo rõ: *"Không thể kết nối tới FastAPI backend tại http://localhost:8000. Hãy chạy: .venv/bin/uvicorn src.api.main:app --port 8000"*.
   - Khung chat vô hiệu hóa hoặc thông báo lỗi thân thiện khi bấm gửi thay vì làm crash app Streamlit.
2. **Upload file không hợp lệ hoặc lỗi OCR:**
   - Kiểm tra định dạng đuôi `.pdf` ngay trên UI.
   - Bắt mã lỗi HTTP 400, 501, 503 từ backend và hiển thị dạng `st.error(detail)`.
3. **Mạng chậm / Query LLM mất thời gian:**
   - Dùng `st.spinner("Đang tìm kiếm tài liệu và sinh câu trả lời...")` để phản hồi trực quan cho người dùng.
4. **Phản hồi ngoài phạm vi (Abstention):**
   - Không hiển thị trích dẫn ảo nếu `abstained == True`.

---

## 7. Testing Strategy

1. **Unit Testing (`tests/test_ui_api_client.py`):**
   - Mock HTTP requests bằng `unittest.mock` hoặc `httpx.Response` để test:
     - `check_health` thành công / mất kết nối trả về `None`.
     - `upload_document` thành công / nhận mã lỗi 400.
     - `query` parse đúng `QAResponse` bao gồm `citations`, `abstained`, `retrieved_chunks`.
2. **Logic Testing (`tests/test_ui_components.py`):**
   - Test hàm format citation badge và xử lý logic hiển thị câu từ chối.
3. **Integration Verification:**
   - Khởi động backend và chạy Streamlit UI (`streamlit run src/ui/app.py`).
   - Kiểm tra tương tác thực tế với câu hỏi in-scope, câu hỏi scan OCR, và câu hỏi ngoài phạm vi.
